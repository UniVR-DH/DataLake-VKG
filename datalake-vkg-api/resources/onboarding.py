import json
import logging
import os
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Request, File, HTTPException, Query, UploadFile, Depends
from fastapi.exceptions import HTTPException
import subprocess
import docker
import httpx
import time

from datalake_vkg_api.tools.setup.dremio import add_dataset_to_dremio
from datalake_vkg_api.tools.setup.garage import upload_csv_to_garage 
from datalake_vkg_api.tools.mapping.mapping_generation import generate_mappings, merge_mapping_files, merge_ontology_files
from datalake_vkg_api.resources.constants import ONTOP_SPARQL_URL, SparqlRequest

router = APIRouter()

logger = logging.getLogger(__name__)

@router.post("/dataset", status_code=201, summary="Onboard a new dataset into the system")
async def onboard_dataset(source_name: str, mimeType:str, path: Optional[str] = None):
    """
    Onboard a new dataset into Dremio.

    - **source_name**: The name of the source to create.
    - **path**: The path to the dataset to be onboarded.
    - **mimeType**: The MIME type of the dataset. Accepted values are: "text/csv", "application/parquet", "text/sql".

    """
    if path is not None:
        path = path.strip()
    source_name = source_name.strip()

    ## Garage ingestion (only for CSV files)
    try:
        target_bucket = os.getenv("GARAGE_CSV_BUCKET", "csv")
        ontop_input = Path(os.getenv("ONTOP_INPUT_DIR", "/app/datalake_vkg_api/tools/ontop/input"))
        raw = Path(path)
        for prefix in ("systems/ontop/input/", "systems/ontop/input"):
            if str(raw).startswith(prefix):
                raw = Path(str(raw)[len(prefix):].lstrip("/"))
                break
        abs_file = raw if raw.is_absolute() else ontop_input / raw
        file_data = abs_file.read_bytes()
        upload_csv_response = await upload_csv_to_garage(file_data, abs_file.name, target_bucket)
        if not upload_csv_response:  # or however success is signaled
            raise HTTPException(status_code=500, detail="CSV upload to Garage failed")
    except Exception as e:
        logger.error("Failed to upload CSV to Garage: %s", e)
        raise HTTPException(status_code=500, detail="Failed to upload CSV to Garage")

    ## Dremio ingestion
    dremio_response = await add_dataset_to_dremio(source_name, "text/csv", path)
    if dremio_response.status_code == 409:
        logger.warning(
            "Dataset already registered in Dremio for source_name=%s, skipping.",
            source_name,
        )
    elif dremio_response.status_code != 201:
        logger.error(
            "Dremio dataset creation failed for source_name=%s with status_code=%s",
            source_name,
            dremio_response.status_code,
        )
        raise HTTPException(status_code=500, detail="Failed to add dataset to Dremio")

    ## Croissant generation
    croissant = await generate_croissant(path, f"Croissant ontology for {source_name}")
    try: 
        croissant_text = (Path(os.getenv("ONTOP_INPUT_DIR", "/app/datalake_vkg_api/tools/ontop/input")) / "croissant" / (Path(path).stem + ".ttl")).read_text()
        croissant_dict = json.loads(croissant_text)
    except Exception as e:
        logger.error("Failed to read Croissant profile: %s", e)
        raise HTTPException(status_code=500, detail="Failed to read Croissant profile")
    
    ## Mapping and ontology generation
    try:
        csv_filename = Path(path).name if mimeType == "text/csv" else None
        generate_mappings(croissant_dict, source_name, mimeType, "public", csv_filename=csv_filename, dremio_source_name=source_name)
    except Exception as e:
        logger.error("Failed to generate mappings and ontology: %s", e)
        raise HTTPException(status_code=500, detail="Failed to generate mappings and ontology")
    
    return {"message": f"Dataset at {path} has been successfully onboarded."}



_MAX_CSV_BYTES = 512 * 1024 * 1024  # 512 MB


@router.post(
    "/garage/upload",
    status_code=201,
    summary="Upload a CSV file to Garage S3",
)
async def upload_csv(
    file: UploadFile = File(..., description="CSV file to ingest into Garage")
):
    """
    Ingest a local CSV dataset into the Garage S3-compatible object store.

    - **file**: CSV file sent as `multipart/form-data`.
    - **bucket**: Destination bucket name. Falls back to the `GARAGE_CSV_BUCKET`
      environment variable, then to `csvdata`.

    The endpoint reads Garage credentials written by the `garage-init` service
    (from the shared `/credentials/` volume) and uploads the file using the
    S3 API.  On success it returns the `s3://` URI of the ingested object.
    """
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted")

    target_bucket = os.getenv("GARAGE_CSV_BUCKET", "csvdata")

    data = await file.read()
    if len(data) > _MAX_CSV_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (max {_MAX_CSV_BYTES // (1024 * 1024)} MB)",
        )
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    uri = await upload_csv_to_garage(data, file.filename, target_bucket)

    return {
        "message": f"Successfully ingested '{file.filename}' into Garage",
        "uri": uri,
        "bucket": target_bucket,
        "size_bytes": len(data),
    }

@router.post(
    "/croissant",
    status_code=201,
    summary="Upload a CSV file to Garage S3",
)
async def generate_croissant(
    path: str, 
    description: str,
):
    """
    Generate the Croissant profile from the provided CSV file. 
    - **file**: CSV file sent as `multipart/form-data`.
    """
    ontop_input = Path(os.getenv("ONTOP_INPUT_DIR", "/app/datalake_vkg_api/tools/ontop/input"))

    # Accept either a bare filename, a path relative to systems/ontop/input/, or an absolute path.
    raw = Path(path)
    if raw.is_absolute():
        abs_file = raw
    else:
        # Strip the host-side prefix (systems/ontop/input) if the user passed it
        for prefix in ("systems/ontop/input/", "systems/ontop/input"):
            if str(raw).startswith(prefix):
                raw = Path(str(raw)[len(prefix):].lstrip("/"))
                break
        abs_file = ontop_input / raw

    input_dir = str(abs_file.parent)
    stem = abs_file.stem
    output_path = str(ontop_input / "croissant" / (stem + ".ttl"))

    try: 
        subprocess.run([
            "croissant-baker",
            "--input", input_dir,
            "--creator", "DataLake-VKG,dl-vkg@example.com",
            "--description", description,
            "--license", "CC-BY-4.0",
            "--output", output_path,
        ], check=True)
    except subprocess.CalledProcessError as e:
        logger.error("Croissant generation failed: %s", e)
        raise HTTPException(status_code=500, detail="Croissant generation failed")


@router.get(
    "/ontop/restart",
    status_code=200,
    summary="Restart the Ontop server with new mappings and ontologies",
)
async def restart_ontop():
    """
    Restart the Ontop server to apply new mappings and ontologies.
    """
    
    merge_mapping_files()
    merge_ontology_files()
    try:
        client = docker.from_env()
        container = client.containers.get("ontop-endpoint")
        container.restart()
    except Exception as e:
        logger.error("Failed to restart Ontop container: %s", e)
        raise HTTPException(status_code=500, detail="Failed to restart Ontop server")


@router.post("/query/sparql")
async def execute_sparql_query(
    body: SparqlRequest
):
    """Endpoint to execute SPARQL queries against the Ontop endpoint."""

    query = body.query
    logger.info("Received SPARQL query: %s", query)

    headers = {
        "Content-Type": "application/sparql-query",
        "Accept": "application/sparql-results+json",
    }

    timeout = httpx.Timeout(connect=60.0, read=600.0, write=600.0, pool=600.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        start_time = time.perf_counter()
        resp = await client.post(ONTOP_SPARQL_URL, content=query, headers=headers)
        elapsed = time.perf_counter() - start_time

    logger.info("SPARQL query executed in %.3fs (status=%s)", elapsed, resp.status_code)

    if resp.status_code != 200:
        raise HTTPException(
            status_code=500, detail=f"Ontop SPARQL query failed: {resp.text}"
        )

    return resp.json()
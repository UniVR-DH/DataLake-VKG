import logging
import os
from pathlib import Path
from fastapi import APIRouter, Request, File, HTTPException, Query, UploadFile
from fastapi.exceptions import HTTPException
import subprocess

from datalake_vkg_api.tools.setup.dremio import add_dataset_to_dremio
from datalake_vkg_api.tools.setup.garage import upload_csv_to_garage 


router = APIRouter()

logger = logging.getLogger(__name__)

@router.post("/dataset", status_code=201, summary="Onboard a new dataset into the system")
async def onboard_dataset(source_name: str, path: str, mimeType:str):
    """
    Onboard a new dataset into Dremio.

    - **source_name**: The name of the source to create.
    - **path**: The path to the dataset to be onboarded.
    - **mimeType**: The MIME type of the dataset. Accepted values are: "text/csv", "application/parquet", "text/sql".

    """
    path = path.strip()
    mimeType = mimeType.strip()
    if mimeType not in ["text/csv", "application/parquet", "text/sql"]:
        raise HTTPException(status_code=400, detail="Invalid MIME type. Accepted values are: 'text/csv', 'application/parquet', 'text/sql'.")
    if mimeType == "text/csv" and not path.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="For MIME type 'text/csv', the path must end with '.csv'.")
    if mimeType == "application/parquet" and not path.lower().endswith(".parquet"):
        raise HTTPException(status_code=400, detail="For MIME type 'application/parquet', the path must end with '.parquet'.")
    if mimeType == "text/csv":
        try:
            target_bucket = os.getenv("GARAGE_CSV_BUCKET", "csvdata")
            upload_csv_response = await upload_csv_to_garage(b"", path.split("/")[-1], target_bucket)
        except Exception as e:
            logger.error("Failed to upload CSV to Garage: %s", e)
            raise HTTPException(status_code=500, detail="Failed to upload CSV to Garage")
    dremio_response = await add_dataset_to_dremio(source_name, path, mimeType)
    if dremio_response.status_code != 201:
        logger.error(
            "Dremio dataset creation failed for source_name=%s with status_code=%s",
            source_name,
            dremio_response.status_code,
        )
        raise HTTPException(status_code=500, detail="Failed to add dataset to Dremio")
    return {"message": f"Dataset at {path} has been successfully onboarded."}

_MAX_CSV_BYTES = 512 * 1024 * 1024  # 512 MB


@router.post(
    "/garage/upload",
    status_code=201,
    summary="Upload a CSV file to Garage S3",
)
async def upload_csv(
    file: UploadFile = File(..., description="CSV file to ingest into Garage"),
    bucket: str = Query(
        None,
        description="Target Garage bucket (defaults to GARAGE_CSV_BUCKET env var or 'csvdata')",
    ),
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

    target_bucket = bucket or os.getenv("GARAGE_CSV_BUCKET", "csvdata")

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

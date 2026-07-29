import asyncio
import logging
import os
import httpx
import requests

from fastapi.exceptions import HTTPException
from urllib.parse import quote
from pathlib import PurePosixPath

from datalake_vkg_api.resources.constants import MockResponse, GARAGE_CSV_BUCKET, S3_SOURCE_NAME
from datalake_vkg_api.tools.setup.garage import _read_garage_credentials

logger = logging.getLogger(__name__)

DREMIO_BASE_URL = os.getenv("DREMIO_BASE_URL", "http://dremio:9047")
POSTGRES_DB = os.getenv("POSTGRES_DB", "ds_era5_land")
CSV_FORMAT = {
    "type": "Text",
    "fieldDelimiter": ",",
    "extractHeader": True,
    "autoGenerateColumnNames": False,
    "trimHeader": True
}



async def add_dataset_to_dremio(source_name: str, mimeType: str, path: str):
    """
    Add a dataset to Dremio.
    - **source_name**: The name of the source to create.
    - **path**: The path to the dataset to be added.
    - **mimeType**: The MIME type of the dataset. Accepted values are: "text/csv", "text/sql".

    """
    dremio_token = await get_dremio_token()
    if mimeType == "text/csv":
        filename = PurePosixPath(path).name
        created = await create_csv_source(dremio_token, source_name, filename)
    elif mimeType == "text/sql":
        created = await create_postgres_source(dremio_token, POSTGRES_DB, source_name)
    else:
        logger.error("Unsupported mimeType=%s for source_name=%s", mimeType, source_name)
        return MockResponse(status_code=400)

    if created:
        return MockResponse(status_code=201)

    return MockResponse(status_code=500)


async def get_dremio_token() -> str:
    if not os.getenv("DREMIO_ADMIN_USER") or not os.getenv("DREMIO_ADMIN_PASSWORD"):
        raise HTTPException(
            status_code=500,
            detail="Missing Dremio admin credentials in environment",
        )

    url = f"{os.getenv('DREMIO_BASE_URL')}/apiv2/login"
    logger.info("Requesting Dremio token from %s with user %s", url, os.getenv("DREMIO_ADMIN_USER"))
    logger.info("dremio url: %s", os.getenv("DREMIO_BASE_URL"))
    payload = {"userName": os.getenv("DREMIO_ADMIN_USER"), "password": os.getenv("DREMIO_ADMIN_PASSWORD")}

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15)) as client:
            response = await client.post(url, json=payload)
    except httpx.RequestError as exc:
        logger.exception("Failed to contact Dremio login endpoint")
        raise HTTPException(
            status_code=502, detail="Cannot reach Dremio login endpoint"
        ) from exc

    if response.status_code != 200:
        logger.error(
            "Dremio login failed with status=%s body=%s",
            response.status_code,
            response.text[:500],
        )
        raise HTTPException(status_code=502, detail="Dremio authentication failed")

    token = response.json().get("token")
    if not token:
        raise HTTPException(
            status_code=502, detail="Missing token in Dremio login response"
        )

    return token

def auth_headers(token):
    return {"Authorization": f"_dremio{token}", "Content-Type": "application/json"}

async def create_csv_source(token: str, source_name: str, file_path:str) -> bool:
    logger.info("Creating CSV source in Dremio")

    key_id, secret = _read_garage_credentials()

    s3_payload = {
        "entityType": "source",
        "name": S3_SOURCE_NAME,
        "type": "S3",
        "config": {
            "credentialType": "ACCESS_KEY",
            "accessKey": key_id,
            "accessSecret": secret,
            "secure": False,
            "compatibilityMode": True,
            "whitelistedBuckets": [os.getenv("GARAGE_CSV_BUCKET")],
            "propertyList": [
                # Core Garage connectivity — this source's propertyList is now the
                # single source of truth for S3A config (core-site.xml removed).
                {"name": "fs.s3a.endpoint", "value": os.getenv("GARAGE_ENDPOINT_DREMIO")},
                {"name": "fs.s3a.path.style.access", "value": "true"},
                {"name": "fs.s3a.connection.ssl.enabled", "value": "false"},
                {"name": "fs.s3a.impl", "value": "org.apache.hadoop.fs.s3a.S3AFileSystem"},
                {"name": "fs.s3a.aws.credentials.provider", "value": "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider"},

                # Region configuration for Garage
                {"name": "fs.s3a.endpoint.region", "value": "us-east-1"},

                # AWS Signature V4 signing for Garage compatibility.
                # DO NOT set fs.s3a.signing-algorithm=S3SignerType — that forces
                # AWS Signature V2, which breaks Garage's V4 signing.
                {"name": "fs.s3a.aws.s3.dualstack.enabled", "value": "false"},

                # Connection settings
                {"name": "fs.s3a.connection.maximum", "value": "50"},
                {"name": "fs.s3a.max.total.tasks", "value": "10"},
                {"name": "fs.s3a.threads.max", "value": "10"},

                # List and discovery settings for Garage
                {"name": "fs.s3a.list.version", "value": "2"},
                {"name": "fs.s3a.directory.marker.retention", "value": "keep"},
                {"name": "fs.s3a.bucket.probe", "value": "0"},
                {"name": "fs.s3a.change.detection.mode", "value": "none"},

                # Multipart and object settings
                {"name": "fs.s3a.multipart.size", "value": "104857600"},
                {"name": "fs.s3a.multipart.threshold", "value": "104857600"},
            ]
        },
    }
    r = requests.post(f"{os.getenv('DREMIO_BASE_URL')}/api/v3/catalog", headers=auth_headers(token), json=s3_payload, timeout=30)
    if r.status_code in (200, 201):
        logger.info("  ✓ Created S3 source")
    elif r.status_code == 409:
        logger.warning("  ⚠ S3 source '%s' already exists in Dremio, skipping creation.", source_name)
    else:
        logger.error("  ✗ Failed: %s - %s", r.status_code, r.text[:200])
    try:
        return promote_file(token, S3_SOURCE_NAME, os.getenv("GARAGE_CSV_BUCKET"), file_path, CSV_FORMAT)
    except Exception as e:
        logger.error("Failed to promote file to Dremio: %s", e)
        raise HTTPException(status_code=500, detail="Failed to promote file to Dremio")

def promote_file(token, source_name, bucket, filename, file_format):
    by_path = source_file_path(S3_SOURCE_NAME, GARAGE_CSV_BUCKET, filename)
    catalog_lookup = f"{DREMIO_BASE_URL}/api/v3/catalog/by-path/{by_path}"
    try:
        lookup = requests.get(catalog_lookup, headers=auth_headers(token), timeout=30)
        if lookup.status_code != 200:
            logger.error(f"  ✗ Failed to find '{filename}' in source: HTTP {lookup.status_code}")
            return False

        entity = lookup.json()
    except Exception as e:
        logger.error(f"  ✗ Failed to parse lookup response for '{filename}': {e}")
        return False
    file_id = entity.get("id")
    entity_type = entity.get("entityType")

    if entity_type == "dataset":
        # Already promoted previously — force a metadata refresh instead of re-promoting
        refresh_url = f"{DREMIO_BASE_URL}/api/v3/catalog/{quote(file_id, safe='')}/refresh"
        r = requests.post(refresh_url, headers=auth_headers(token), timeout=30)
        if r.status_code in (200, 204):
            logger.info(f"  ✓ Refreshed metadata for '{filename}'")
            return True
        logger.error(f"  ✗ Failed to refresh '{filename}': HTTP {r.status_code} {r.text[:200]}")
        return False
    try:
        promote_url = f"{DREMIO_BASE_URL}/api/v3/catalog/{quote(file_id, safe='')}"
        payload = {
            "entityType": "dataset",
            "id": file_id,
            "type": "PHYSICAL_DATASET",
            "path": [S3_SOURCE_NAME, GARAGE_CSV_BUCKET, filename],
            "format": file_format,
        }
        r = requests.post(promote_url, headers=auth_headers(token), json=payload, timeout=30)
        if r.status_code in (200, 201):
            logger.info(f"  ✓ Promoted '{filename}'")
            return True
        elif r.status_code == 409:
            logger.info(f"  ✓ '{filename}' already promoted")
            return True
        else:
            logger.error(f"  ✗ Failed to promote '{filename}': HTTP {r.status_code}")
            return False
    except Exception as e:
        logger.error(f"  ✗ Failed to promote '{filename}': {e}")
        return False
    
async def create_postgres_source(token: str, db_name: str, source_name: str) -> bool:
    """Create a PostgreSQL source in Dremio with the given database name and source name.
    The connection details are retrieved from environment variables.
    """
    pg_payload = {
        "entityType": "source",
        "name": source_name,
        "type": "POSTGRES",
        "config": {
            "hostname": os.getenv("POSTGRES_HOST"),
            "port": int(os.getenv("POSTGRES_PORT")),
            "databaseName": db_name,
            "username": os.getenv("POSTGRES_USER"),
            "password": os.getenv("POSTGRES_PASSWORD", ""),
            "useSsl": False,
        },
    }

    url = f"{os.getenv('DREMIO_BASE_URL')}/api/v3/catalog"
    headers = {
        "Authorization": f"_dremio{token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30)) as client:
            response = await client.post(url, headers=headers, json=pg_payload)
    except httpx.RequestError:
        logger.exception(
            "Dremio catalog request failed for source_name=%s", source_name
        )
        return False
    if response.status_code == 409:
        logger.warning(
            "PostgreSQL source already exists in Dremio for source_name=%s", source_name
        )
        return True
    if response.status_code in (200, 201):
        return True

    logger.error(
        "Dremio source creation failed for source_name=%s, status=%s, body=%s",
        source_name,
        response.status_code,
        response.text[:500],
    )
    return False

def source_file_path(source_name, bucket, filename):
    return "/".join([source_name, bucket, filename])
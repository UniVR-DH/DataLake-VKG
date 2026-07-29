import logging
import os
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException

logger = logging.getLogger(__name__)

_CREDENTIALS_DIR = Path(os.getenv("GARAGE_CREDENTIALS_DIR", "/credentials"))


def _read_garage_credentials() -> tuple[str, str]:
    """
    Return (key_id, secret_key) for Garage.

    Priority:
    1. /credentials/ volume written by garage-init.sh
    2. GARAGE_KEY_ID / GARAGE_SECRET environment variables
    """
    key_file = _CREDENTIALS_DIR / "key_id"
    secret_file = _CREDENTIALS_DIR / "secret_key"

    if key_file.exists() and secret_file.exists():
        key_id = key_file.read_text().strip()
        secret = secret_file.read_text().strip()
        if key_id and secret:
            return key_id, secret

    key_id = os.getenv("GARAGE_KEY_ID", "")
    secret = os.getenv("GARAGE_SECRET", "")
    if key_id and secret:
        return key_id, secret

    raise RuntimeError(
        "Garage credentials not found. "
        "Expected /credentials/key_id and /credentials/secret_key "
        "(written by garage-init) or GARAGE_KEY_ID/GARAGE_SECRET env vars."
    )


def _make_s3_client():
    key_id, secret = _read_garage_credentials()
    endpoint = os.getenv("GARAGE_ENDPOINT_URL", "http://garage:3900")
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=key_id,
        aws_secret_access_key=secret,
        region_name="us-east-1",
        config=Config(s3={"addressing_style": "path"}, signature_version="s3v4"),
    )


async def upload_csv_to_garage(data: bytes, filename: str, bucket: str) -> str:
    """
    Upload *data* as *filename* into *bucket* on the Garage S3 store.

    Returns the s3:// URI of the uploaded object.
    Raises HTTPException on credential or upload errors.
    """
    try:
        client = _make_s3_client()
    except RuntimeError as exc:
        logger.error("Cannot build Garage S3 client: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))

    try:
        logger.info("Uploading %s (%d bytes) to s3://%s/", filename, len(data), bucket)
        client.put_object(
            Bucket=bucket,
            Key=filename,
            Body=data,
            ContentType="text/csv",
        )
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        logger.error("Garage S3 ClientError [%s] uploading %s: %s", code, filename, exc)
        raise HTTPException(status_code=502, detail=f"Garage upload failed: {code}")
    except BotoCoreError as exc:
        logger.exception("Garage S3 BotoCoreError uploading %s", filename)
        raise HTTPException(status_code=502, detail="Garage upload failed (connection error)")

    uri = f"s3://{bucket}/{filename}"
    logger.info("Upload successful: %s", uri)
    return uri
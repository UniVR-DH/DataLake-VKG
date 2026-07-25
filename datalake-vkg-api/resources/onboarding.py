import logging
from fastapi import APIRouter, Request
from fastapi.exceptions import HTTPException

from datalake_vkg_api.tools.setup.dremio import add_dataset_to_dremio


router = APIRouter()

logger = logging.getLogger(__name__)

@router.post("/dataset/", status_code=201, summary="Onboard a new dataset into the system")
async def onboard_dataset(source_name: str, path: str, mimeType:str):
    """
    Onboard a new dataset into Dremio.

    - **source_name**: The name of the source to create.
    - **path**: The path to the dataset to be onboarded.
    - **mimeType**: The MIME type of the dataset. Accepted values are: "text/csv", "application/parquet", "text/sql".

    """
    path = path.strip()
    mimeType = mimeType.strip()
    dremio_response = await add_dataset_to_dremio(source_name, path, mimeType)
    if dremio_response.status_code != 201:
        logger.error(
            "Dremio dataset creation failed for source_name=%s with status_code=%s",
            source_name,
            dremio_response.status_code,
        )
        raise HTTPException(status_code=500, detail="Failed to add dataset to Dremio")
    return {"message": f"Dataset at {path} has been successfully onboarded."}




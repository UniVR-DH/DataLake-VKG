import logging 
import os

from datalake_vkg_api.resources import onboarding
from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
import uvicorn

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(
    title="Virtual Data Catalog API",
    description="API for the Virtual Data Catalog, allowing users to manage and query their data assets.",
    version="1.0.0",
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/swagger",
    redoc_url="/api/v1/redoc",
    root_path=os.getenv("ROOT_PATH", ""),
)

app.include_router(onboarding.router, prefix="/api/v1")


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"status_code": exc.status_code, "detail": exc.detail},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"status_code": 500, "detail": str(exc)},
    )


@app.get("/api/v1")
def read_root():
    app_version = os.getenv("APP_VERSION", "dev")
    return {
        "message": f"API V1 is running (version: {app_version})",
        "endpoints": {
            "dataset": {
                "description": "Onboard a new dataset into the system",
                "methods": ["POST"],
                "url": "/api/v1/dataset",
            },
            "garage/upload": {
                "description": "Upload a CSV file into the Garage S3 object store",
                "methods": ["POST"],
                "url": "/api/v1/garage/upload",
            },
            "croissant":{
                "description": "Generate a Croissant ontology from a CSV file",
                "methods": ["POST"],
                "url": "/api/v1/croissant",
            }, 
            "ontop/restart": {
                "description": "Restart the Ontop server to apply new mappings and ontologies",
                "methods": ["GET"],
                "url": "/api/v1/ontop/restart",
            },
        },
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("SERVER_PORT", 5000)))
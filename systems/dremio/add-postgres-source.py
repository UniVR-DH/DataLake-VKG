import os
import sys
import time
import requests

DREMIO_HOST = os.environ.get("DREMIO_HOST", "dremio")
DREMIO_PORT = os.environ.get("DREMIO_PORT", "9047")
DREMIO_URL = f"http://{DREMIO_HOST}:{DREMIO_PORT}"

DREMIO_USER = os.environ["DREMIO_ADMIN_USER"]
DREMIO_PASSWORD = os.environ["DREMIO_ADMIN_PASSWORD"]
SOURCE_NAME = os.environ.get("DREMIO_PG_SOURCE_NAME", "era5_postgres")

PG_HOST = os.environ.get("PG_HOST", "postgres")
PG_PORT = int(os.environ.get("PG_PORT", "5432"))
PG_DATABASE = os.environ.get("PG_DATABASE", "era5land")
PG_USER = os.environ.get("PG_USER", "postgres")
PG_PASSWORD = os.environ.get("PG_PASSWORD", "postgres")


def login():
    for attempt in range(30):
        try:
            resp = requests.post(
                f"{DREMIO_URL}/apiv2/login",
                json={"userName": DREMIO_USER, "password": DREMIO_PASSWORD},
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json()["token"]
            print(f"Login attempt {attempt+1} failed: {resp.status_code} {resp.text}")
        except requests.exceptions.RequestException as e:
            print(f"Login attempt {attempt+1} error: {e}")
        time.sleep(5)
    raise RuntimeError("Could not log in to Dremio after multiple attempts")


def source_exists(token):
    headers = {"Authorization": f"_dremio{token}"}
    resp = requests.get(f"{DREMIO_URL}/api/v3/catalog", headers=headers, timeout=10)
    resp.raise_for_status()
    for entry in resp.json().get("data", []):
        if entry.get("path", [None])[0] == SOURCE_NAME:
            return True
    return False


def create_postgres_source(token):
    headers = {
        "Authorization": f"_dremio{token}",
        "Content-Type": "application/json",
    }

    payload = {
        "entityType": "source",
        "name": SOURCE_NAME,
        "type": "POSTGRES",
        "config": {
            "hostname": PG_HOST,
            "port": PG_PORT,
            "databaseName": PG_DATABASE,
            "username": PG_USER,
            "password": PG_PASSWORD,
            "authenticationType": "MASTER",
            "fetchSize": 200,
        },
        "metadataPolicy": {
            "authTTLMs": 86400000,
            "namesRefreshMs": 3600000,
            "datasetRefreshAfterMs": 3600000,
            "datasetExpireAfterMs": 10800000,
            "datasetUpdateMode": "PREFETCH_QUERIED",
        },
    }

    resp = requests.post(
        f"{DREMIO_URL}/api/v3/catalog", headers=headers, json=payload, timeout=30
    )

    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Failed to create source: {resp.status_code} {resp.text}"
        )

    print(f"Source '{SOURCE_NAME}' created successfully.")


def main():
    token = login()

    if source_exists(token):
        print(f"Source '{SOURCE_NAME}' already exists, skipping.")
        return

    create_postgres_source(token)


if __name__ == "__main__":
    sys.exit(main())
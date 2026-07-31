# DataLake-VKG

Virtual Knowledge Graph for Data Lakes using Ontop associated with the Data Federator Dremio. 
This folder is a running example outside the DataGEMS platform. The full deployed version is the following: https://github.com/datagems-eosc/virtual-data-catalog

License: [LICENSE](LICENSE)

## Services
The compose stack includes the following services:

| Service | Purpose | Compose build command |
| --- | --- | --- |
| API | FastAPI onboarding and SPARQL API | docker compose build api |
| loader | ERA5 dataset loader | docker compose build loader |
| ontop | Ontop SPARQL endpoint | No build required; image-based service |
| garage | Garage S3-compatible object store | No build required; image-based service |
| garage_config | Generates Garage configuration | No build required; helper service |
| garage_init | Creates the Garage bucket and credentials | No build required; helper service |
| dremio | Dremio data federation engine | No build required; image-based service |
| dremio_init | Applies initial Dremio configuration | No build required; helper service |
| dremio_postgres_source_init | Adds the PostgreSQL source to Dremio | No build required; helper service |
| postgres | PostgreSQL source for ERA5 data | No build required; image-based service |

To build the local images and start the API service:

```bash
docker compose build api loader
docker compose up -d api
```

Useful endpoints:

* Dremio: http://localhost:9047
* Ontop endpoint: http://localhost:8080

## API Usage 
The use of the API is described in https://github.com/UniVR-DH/DataLake-VKG/blob/main/API_USAGE.md
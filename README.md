# DataLake-VKG

DataLake-VKG provides a reproductible environment for constructing a Virtual Knowledge Graph (VKG) over heterogeneous data sources. 
The system integrates the Ontop system with the Dremio data federator.
This repository contains a standalone demonstrator independent of the DataGEMS platform. The fully deployed version is available at: https://github.com/datagems-eosc/virtual-data-catalog

License: [LICENSE](LICENSE)


## Architecture and Services


API → Ontop → Dremio → {PostgreSQL, Garage}



| Service | Purpose | Description | Endpoint |
| --- | --- | --- | --- |
| API | FastAPI onboarding and SPARQL API | Dataset onboarding, Mapping, ontology and lenses file generation and SPARQL access| |
| [ontop](https://ontop-vkg.org/) | Ontop SPARQL endpoint | VKG system | http://localhost:8080 |
| [dremio](https://www.dremio.com/) | Dremio data federation engine | Data federator to access postgres dataset and csv files | http://localhost:9047 |
| [garage](https://garagehq.deuxfleurs.fr/) | Garage S3-compatible object store |  S3-compatible object storage | |
| [postgres](https://www.postgresql.org/) | PostgreSQL source for ERA5 data | ERA 5 land relational data source | |

## Prerequisites

The execution of the DataLake‑VKG environment requires the following software components:

- **Docker** (version 20.10 or later)
- **Docker Compose** (version 2.0 or later)
- **Git** for cloning the repository
- **Python 3.10+** (optional; required only for local API development or dataset preprocessing)

All services are containerized; therefore, no additional system‑level dependencies are required.  
Adequate memory (≥ 8 GB) is recommended to ensure stable execution of Dremio and Ontop.

## Quick Start

The following steps provide a minimal procedure for deploying the core components of the DataLake‑VKG stack.

1. **Clone the repository**
```bash
git clone https://github.com/UniVR-DH/DataLake-VKG.git
cd DataLake-VKG
```

2. **Build the required images**
```bash
docker-compose build 
```

3. **Start the services**
```bash
docker-compose up -d 
```

4. **Access the system interfaces**
- Dremio Web Interface: http://localhost:9047 
- Ontop SPARQL Endpoint: http://localhost:8080

## API Usage 
The use of the API is described in https://github.com/UniVR-DH/DataLake-VKG/blob/main/API_USAGE.md

## Data Sources
- ERA5-Land dataset: [https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land?tab=download](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land?tab=download)
License: The ERA5-Land dataset is provided under the terms specified by the
Copernicus Climate Change Service (C3S) and the Copernicus Climate Data Store.

- Climpact.gr dataset: [https://data.climpact.gr/dataset/497dc26d-45e0-4ad5-b8f3-5f8890f65129](https://data.climpact.gr/dataset/497dc26d-45e0-4ad5-b8f3-5f8890f65129)
License: Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)
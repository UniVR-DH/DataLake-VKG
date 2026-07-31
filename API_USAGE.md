# API Usage Examples
The API is available at: `http://localhost:5002/api/v1`

The proposed setup contains Era5land dataset into postgres, but the dataset needs to integrating into Ontop to be queried. 
A CSV file containing weather stations information is provided, and should be onboarded into the setup. 
The user can also onboard CSV files. 

## Table of Contents
- [1) Registering a CSV into garage](#1-registering-a-csv-file-into-garage)
- [2) Onboarding of a CSV file](#2-onboarding-of-a-csv-file)
- [3) Generating integration files from Croissant metadata](#3-generating-integration-files-from-croissant-metadata)
- [4) Generating Croissant Metadata](#4-generating-croissant-metadata)
- [5) Restarting Ontop](#5-restarting-ontop)
- [6) Querying using SPARQL](#6-querying-using-sparql)

## 1) Registering a CSV file into garage
To register a CSV into the S3-like storage Garage:
```bash
curl -X POST "http://localhost:5002/api/v1/garage/upload" \
  -F "file=@systems/ontop/input/data/stations_list.csv"
```

## 2) Onboarding of a CSV file
To onboard a CSV file into Ontop, the following step are done:
1) Ingestion into Garage
2) Ingestion into Dremio
3) Croissant Generation
4) Mapping, ontology and lenses files generation

Parameters:
- **source_name**: name of the dataset
- **path**: local path of the CSV file
This process is done by executing the following curl: 
```bash
curl -X POST "http://localhost:5002/api/v1/dataset?source_name=stations&path=systems/ontop/input/data/stations_list.csv"
```

## 3) Generating integration files from Croissant metadata
To generate the integration files, i.e., mappings, ontology and lenses files for the era5land postgres dataset
```bash
curl -X POST "http://localhost:5002/api/v1/mappings?path=systems/ontop/input/croissant/era5_land.json"
```

Notes: 
- The Croissant file must contain valid datatypes for all fields.

## 4) Generating Croissant Metadata
Croissant metadata can be generated directly from a CSV file. This endpoint is using the Croissant Baker tool: https://github.com/MIT-LCP/croissant-baker
Only CSV files are supported. 

Parameters:
- **path** local CSV file path
- **description**: small description of the dataset

```bash
curl -X POST "http://localhost:5002/api/v1/croissant?path=systems/ontop/input/data/stations_list.csv&description=List%20of%20weather%20stations%20with%20coordinates%20and%20metadata"
```

## 5) Restarting Ontop
When new mappings, ontology and lenses files are generating, Ontop needs to be restarted so the datasets can be queried. 
To restart Ontop, the following query should be executed:  
```bash
curl -X POST "http://localhost:5002/api/v1/ontop/restart"
```
## 6) Querying using SPARQL 
A SPARQL query can be sent to Ontop using the following curl: 
```bash
curl -X 'POST' \
  'http://localhost:5002/api/v1/query/sparql' \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{"query": "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10"}'
```
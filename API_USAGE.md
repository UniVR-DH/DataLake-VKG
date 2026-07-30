## CSV ingestion into garage
```bash
curl -X POST "http://localhost:5002/api/v1/garage/upload"   -F "file=@systems/ontop/input/data/stations_list.csv"
```


## CSV Dataset Onboarding
1) Ingestion into Garage
2) Ingestion into Dremio
3) Croissant Generation
4) Mapping and ontology files generation
```bash
curl -X POST "http://localhost:5002/api/v1/dataset?source_name=stations&path=systems/ontop/input/data/stations_list.csv"
```

```bash
curl -X POST "http://localhost:5002/api/v1/dataset?source_name=era5land&mimeType=text/sql"
```
## Croissant Generator
```bash
curl -X POST "http://localhost:5002/api/v1/croissant?path=systems/ontop/input/data/stations_list.csv&description=List%20of%20weather%20stations%20with%20coordinates%20and%20metadata"
```

## Restarting Ontop 
```bash
curl -X GET "http://localhost:5002/api/v1/ontop/restart"
```
## SPARQL Query 
```bash
curl -X 'POST' \
  'http://localhost:5002/api/v1/query/sparql' \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{"query": "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10"}'
```
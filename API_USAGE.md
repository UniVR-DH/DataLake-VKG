## CSV ingestion into garage
```bash
curl -X POST "http://localhost:5002/api/v1/garage/upload"   -F "file=@systems/ontop/input/data/stations_list.csv"
```

## Dataset Onboarding
1) If CSV: ingestion into Garage
2) Ingestion into Dremio
3) Croissant Generation
4) Mapping and ontology files generation
5) Ontop restart
```bash
curl -X POST "http://localhost:5002/api/v1/dataset?source_name=stations&path=systems/ontop/input/data/stations_list.csv&mimeType=text/csv"
```
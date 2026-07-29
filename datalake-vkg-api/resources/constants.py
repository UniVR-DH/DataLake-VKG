import os
from pydantic import BaseModel

class MockResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code

class SparqlRequest(BaseModel):
    query: str

S3_SOURCE_NAME = "garage"
GARAGE_CSV_BUCKET = os.getenv("GARAGE_CSV_BUCKET", "csvdata")
ONTOP_SPARQL_URL = os.getenv("ONTOP_SPARQL_URL", "http://ontop:8080/sparql")
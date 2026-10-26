import json
from pathlib import Path
import jsonschema

def test_core_schemas_validity():
    schema_path = Path(__file__).resolve().parents[2] / "schemas" / "core-schemas.json"
    assert schema_path.exists(), "core-schemas.json must exist"
    
    with open(schema_path) as f:
        schema = json.load(f)
        
    assert "$defs" in schema or "properties" in schema or "$schema" in schema
    print(f"Loaded schema with title: {schema.get('title', 'Untitled')}")

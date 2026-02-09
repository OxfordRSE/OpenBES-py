import sys
from jsonschema import Draft202012Validator
import json

schema = json.load(open(sys.argv[1], "r"))

Draft202012Validator.check_schema(schema)
print("Schema is valid.")

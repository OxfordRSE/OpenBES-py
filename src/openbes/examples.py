import json
from importlib.resources import files
from pathlib import Path

from .schemas import OpenBESSpecificationV2
from .schemas.conversion import json_to_toml
from .types import OpenBESSpecification

json_path = Path(str(files("openbes.example_data") / "holywell_house.json"))
with open(json_path) as json_data:
    json_content = json.load(json_data)
toml_content = json_to_toml(json_content)

HOLYWELL_HOUSE_SPEC = OpenBESSpecification.from_toml(toml_content)

HOLYWELL_HOUSE_SPEC_V2 = OpenBESSpecificationV2(**json_content)

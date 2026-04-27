"""
To add a new example, create a JSON file in the `openbes.example_data` package and
add an entry to the `examples` dictionary with the name, description, and JSON file name.
The `load_example` function will then be able to load the example by name.
"""

import json
from copy import deepcopy
from importlib.resources import files
from pathlib import Path
from typing import List, Dict

from .schemas import OpenBESSpecificationV2, toml_to_json
from .schemas.conversion import json_to_toml
from .types import OpenBESSpecification

json_path = Path(str(files("openbes.example_data") / "holywell_house.json"))
with open(json_path) as json_data:
    json_content = json.load(json_data)
toml_content = json_to_toml(json_content)

_HOLYWELL_HOUSE_SPEC = OpenBESSpecification.from_toml(toml_content)
_HOLYWELL_HOUSE_SPEC_V2 = OpenBESSpecificationV2(**json_content)


def get_holywell_house_spec() -> OpenBESSpecification:
    """Return a deep copy of the Holywell House v1 specification."""
    return deepcopy(_HOLYWELL_HOUSE_SPEC)


def get_holywell_house_spec_v2() -> OpenBESSpecificationV2:
    """Return a deep copy of the Holywell House v2 specification."""
    return deepcopy(_HOLYWELL_HOUSE_SPEC_V2)


# Backwards-compatible module constants.
HOLYWELL_HOUSE_SPEC = get_holywell_house_spec()
HOLYWELL_HOUSE_SPEC_V2 = get_holywell_house_spec_v2()

examples = {
    "Holywell House": {
        "description": "A university building on an Oxford business estate.",
        "file": "holywell_house.json",
    },
    "Semi-detached House": {
        "description": "A typical UK semi-detached house, with a simple construction and energy system.",
        "file": "semi_detached_house.json",
    },
    "Semi-detached Passive House": {
        "description": "A highly insulated, airtight semi-detached house built to the Passive House standard.",
        "file": "semi_detached_passivehouse.json",
    },
    "University Building": {
        "description": "A large university building with a complex layout and multiple energy systems.",
        "file": "university_building.json",
    },
}


def list_examples() -> List[Dict]:
    return [{"name": name, "description": info["description"]} for name, info in examples.items()]


def load_example(name: str) -> OpenBESSpecification:
    if name not in examples:
        raise ValueError(f"Example '{name}' not found. Available examples: {', '.join(examples.keys())}")
    f = examples[name]["file"]
    if not f:
        raise NotImplementedError(f"Example '{name}' does not have a specification file defined yet.")
    example_path = Path(str(files("openbes.example_data") / f))
    j = None
    if str(example_path).endswith(".toml"):
        j = toml_to_json(example_path)
    else:
        with open(example_path) as f:
            j = json.load(f)
    if j is None:
        raise ValueError(f"Error reading specification from {example_path}")
    return OpenBESSpecificationV2(**j)

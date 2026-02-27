import json
from copy import deepcopy
from importlib.resources import files
from pathlib import Path

from .schemas import OpenBESSpecificationV2
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

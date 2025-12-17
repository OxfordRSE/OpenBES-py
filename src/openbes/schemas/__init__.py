import json
from importlib.resources import files

from .generated.models import (
    Ballast,
    Building,
    COOLINGSYSTEMTYPES,
    CoolingSystem,
    Duration,
    ENERGYSOURCES,
    HEATINGSYSTEMTYPES,
    HeatingSystem,
    HotWaterSystem,
    LightingControl,
    LightingSystem,
    LightingSystemTech,
    METEOROLOGICALFILE,
    OpenBESParameters as OpenBESParametersV2,
    OpenBESSpecificationV2,
    OccupationSchedule,
    Range,
    TERRAINCLASS,
    VentilationSystem,
    Zone,
)
from .conversion import toml_to_json, json_to_toml

with open(str(files("openbes.schemas") / "OpenBES.schema.json"), "r") as json_file:
    SPECIFICATION = json.load(json_file)
    SPECIFICATION_VERSION = SPECIFICATION["$version"]

__all__ = [
    "Ballast",
    "Building",
    "COOLINGSYSTEMTYPES",
    "CoolingSystem",
    "Duration",
    "ENERGYSOURCES",
    "HEATINGSYSTEMTYPES",
    "HeatingSystem",
    "HotWaterSystem",
    "LightingControl",
    "LightingSystem",
    "LightingSystemTech",
    "METEOROLOGICALFILE",
    "OpenBESParametersV2",
    "OpenBESSpecificationV2",
    "OccupationSchedule",
    "Range",
    "TERRAINCLASS",
    "VentilationSystem",
    "Zone",
    "toml_to_json",
    "json_to_toml",
    "SPECIFICATION",
    "SPECIFICATION_VERSION",
]
import sys
from pathlib import Path
from typing import Union, Dict, Any

from openbes.simulations.building_energy import BuildingEnergySimulation
from openbes.types import OpenBESSpecification


def bes(
    spec: Union[OpenBESSpecification, str, Path, Dict[str, Any]],
) -> BuildingEnergySimulation:
    if isinstance(spec, OpenBESSpecification):
        specification = spec
    elif isinstance(spec, dict):
        specification = OpenBESSpecification(**spec)
    else:
        specification = OpenBESSpecification.from_toml(spec)
    return BuildingEnergySimulation(spec=specification)


if __name__ == "__main__":
    bes(sys.argv[1])

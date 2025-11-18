import csv
import os
import re
import tomllib
import unittest

from src.openbes.simulations.building_energy import BuildingEnergySimulation
from src.openbes.types import (
    OpenBESSpecification,
    ENERGY_SOURCES,
    HEATING_SYSTEM_TYPES,
    COOLING_SYSTEM_TYPES,
    HEAT_CAPACTIY_CLASSES,
    LIGHTING_CONTROL,
    LIGHTING_BALLASTS,
    LIGHTING_TECHNOLOGIES,
    OpenBESParameters,
    TERRAINS,
)


class MyTestCase(unittest.TestCase):
    def setUp(self):
        case_files = []
        case_file_dir = os.path.join(os.path.dirname(__file__), 'cases')
        for file in os.listdir(case_file_dir):
            if file.endswith('.toml'):
                case_files.append(os.path.join(case_file_dir, file))
        self.case_files = case_files
        with open(os.path.join(os.path.dirname(__file__), 'openbes-outputs.csv'), 'r') as f:
            reader = csv.DictReader(f)
            self.csv_data = [row for row in reader]

    def get_meteorological_file(self, filename: str) -> str:
        if 'Denver' in filename:
            return 'USA_Denver_725650TYCST.epw'
        if 'Oxford' in filename:
            return 'UK_Oxford_GBR_ENG_RAF.Benson.036580_TMYx.2007-2021.epw'
        if 'Sevilla' in filename:
            return 'SPAIN_Sevilla.083910_SWEC.epw'
        if 'Madrid' in filename:
            return 'SPAIN_Madrid.082210_SWEC.epw'
        raise ValueError(f"Unknown meteorological file: {filename}")

    def toml_to_spec(self, toml_content: dict) -> OpenBESSpecification:
        filtered = {k: v for k, v in toml_content.items() if v is not None and v != ""}
        typed = filtered
        for k, v in typed.items():
            if k == 'i.meteorological_file':
                typed[k] = self.get_meteorological_file(v)
            if k.endswith('_energy_source'):
                typed[k] = ENERGY_SOURCES.get_by_value(v)
            elif k.endswith('_type'):
                if bool(re.search('[id]\.heating_system\d_type', k)):
                    typed[k] = HEATING_SYSTEM_TYPES.get_by_value(v)
                elif bool(re.search('[id]\.cooling_system\d_type', k)):
                    typed[k] = COOLING_SYSTEM_TYPES.get_by_value(v)
            elif k == 'i.heat_capacity':
                typed[k] = HEAT_CAPACTIY_CLASSES.get_by_value(v)
            elif k == 'i.lighting_control':
                typed[k] = LIGHTING_CONTROL.get_by_value(v)
            elif k.startswith('i.lighting_system_ballast'):
                typed[k] = LIGHTING_BALLASTS.get_by_value(v)
            elif k.startswith('i.lighting_system_tech'):
                typed[k] = LIGHTING_TECHNOLOGIES.get_by_value(v)
            elif k == 'i.terrain_class':
                typed[k] = TERRAINS.get_by_value(v)
            elif isinstance(v, str) and v.lower() in ['false', 'no']:
                typed[k] = False
            elif isinstance(v, str) and v.lower() in ['true', 'yes']:
                typed[k] = True
        parameters = {k[2:]: v for k, v in filtered.items() if k.startswith("d")}
        specification = {k[2:]: v for k, v in filtered.items() if k.startswith("i")}
        return OpenBESSpecification(parameters=OpenBESParameters(**parameters), **specification)

    def test_cases(self):
        for file in self.case_files:
            with self.subTest(case=os.path.basename(file)):
                with open(file, 'rb') as f:
                    toml_content = tomllib.load(f)
                spec = self.toml_to_spec(toml_content)
                simulation = BuildingEnergySimulation(spec=spec)
                simulation.energy_use

if __name__ == '__main__':
    unittest.main()

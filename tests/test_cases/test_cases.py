import csv
import os
import re
import tomllib
import unittest
from typing import Dict, Any, List

from pandas import Series

from src.openbes.simulations.base import HOURS_DF
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
    ENERGY_USE_CATEGORIES,
    MONTHS,
)


m_index = HOURS_DF.index.names.index('month')
d_index = HOURS_DF.index.names.index('day')
h_index = HOURS_DF.index.names.index('hour')

def day_of_the_month(d: int, m: int) -> int:
    first_day_of_the_month = HOURS_DF.index.get_loc((m, 1, 1))
    return (d - HOURS_DF.index.get_level_values('day')[first_day_of_the_month]) + 1

def translate_index(summary_column: Series, summary_value: float, title: str) -> dict:
    """Extract the value, month, day-of-the-month, hour from a DataFrame row and return as dict.
    """
    index = summary_column[summary_column == summary_value].index[0]
    return {
        title: summary_column,
        f'{title}_month': MONTHS.get_by_index(index[m_index] - 1).value[:3],
        f'{title}_day': day_of_the_month(index[d_index], index[m_index]),
        f'{title}_hour': index[h_index],
    }


class ASHRAE140_2023(unittest.TestCase):
    decimal_places = 2

    def setUp(self):
        self.case_outputs: List[Dict[str, Any]] = []
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
                summary = {
                    'case': os.path.basename(file).rstrip('.toml'),
                    **translate_index(
                        simulation.energy_use_by_category[ENERGY_USE_CATEGORIES.Heating].max(axis="columns"),
                        simulation.energy_use_by_category[ENERGY_USE_CATEGORIES.Heating].max(axis="columns").max(),
                        'peak_heating_load'
                    ),
                    **translate_index(
                        simulation.energy_use_by_category[ENERGY_USE_CATEGORIES.Cooling].max(axis="columns"),
                        simulation.energy_use_by_category[ENERGY_USE_CATEGORIES.Cooling].max(axis="columns").max(),
                        'peak_cooling_load'
                    ),
                    'temperature_setpoint_avg_hr': simulation.climate.air_set_temp.mean(),
                    **translate_index(
                        simulation.climate.air_set_temp,
                        simulation.climate.air_set_temp.min(),
                        'temperature_setpoint_min'
                    ),
                    **translate_index(
                        simulation.climate.air_set_temp,
                        simulation.climate.air_set_temp.max(),
                        'temperature_setpoint_max'
                    ),
                }
                self.case_outputs.append(summary)
                # Find matching row in CSV data
                matching_rows = [
                    row for row in self.csv_data if row['case'] == summary['case']
                ]
                self.assertTrue(
                    len(matching_rows) == 1,
                    msg=f"Expected one matching row in CSV for case {summary['case']}, found {len(matching_rows)}"
                )
                csv_row = matching_rows[0]
                for key, value in summary.items():
                    if key == 'case':
                        continue
                    with self.subTest(metric=key):
                        expected_value = float(csv_row[key])
                        if isinstance(expected_value, float):
                            self.assertAlmostEqual(
                                expected_value,
                                value,
                                places=self.decimal_places,
                            )
                        else:
                            self.assertEqual(expected_value, value)

if __name__ == '__main__':
    unittest.main()

import csv
import os
import re
import tomllib
import unittest
from typing import Dict

from numpy import nan
from pandas import Series, DataFrame

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
    MONTHS,
)


m_index = HOURS_DF.index.names.index('month')
d_index = HOURS_DF.index.names.index('day')
h_index = HOURS_DF.index.names.index('hour')

def day_of_the_month(d: int, m: int) -> int:
    first_day_of_the_month = HOURS_DF.index.get_locs([m, slice(None), 1])[0]
    return (d - HOURS_DF.index.get_level_values('day')[first_day_of_the_month]) + 1

def translate_index(summary_column: Series, summary_value: float, title: str) -> dict:
    """Extract the value, month, day-of-the-month, hour from a DataFrame row and return as dict.
    """
    index = summary_column[summary_column == summary_value].index[0]
    hour_suffix = '_hr' if '_setpoint_' in title else '_hour'
    return {
        title: summary_column.loc[index],
        f'{title}_month': MONTHS.get_by_index(index[m_index] - 1).value[:3],
        f'{title}_day': day_of_the_month(index[d_index], index[m_index]),
        f'{title}_{hour_suffix}': index[h_index],
    }


class ASHRAE140_2023(unittest.TestCase):
    ENABLE_DETAIL = False

    decimal_places = 2
    case_outputs: DataFrame = None
    case_files: Dict[str, str] = {}
    simulations: Dict[str, BuildingEnergySimulation] = {}
    float_cols: list = [
        'cal', 'peak_heating_load', 'peak_heating_load_day', 'peak_heating_load_hour',
        'peak_cooling_load', 'peak_cooling_load_day', 'peak_cooling_load_hour',
        'temperature_setpoint_avg_hr', 'temperature_setpoint_min', 'temperature_setpoint_min_day',
        'temperature_setpoint_min_hr', 'temperature_setpoint_max', 'temperature_setpoint_max_day'
    ]
    str_cols: list = [
        'peak_heating_load_month', 'peak_cooling_load_month',
        'temperature_setpoint_min_month', 'temperature_setpoint_max_month'
    ]

    def setUp(self):
        case_file_dir = os.path.join(os.path.dirname(__file__), 'cases')
        for file in os.listdir(case_file_dir):
            if file.endswith('.toml'):
                self.case_files[os.path.basename(file).rstrip('.toml')] = os.path.join(case_file_dir, file)
        with open(os.path.join(os.path.dirname(__file__), 'openbes-outputs.csv'), 'r') as f:
            reader = csv.DictReader(f)
            csv_data = [row for row in reader]
            csv_data = DataFrame(csv_data)
            csv_data.loc[csv_data['ref_min'] == "", 'ref_min'] = nan
            csv_data.loc[csv_data['ref_max'] == "", 'ref_max'] = nan
            csv_data['should_pass'] = csv_data['should_pass'] == 'TRUE'
            csv_data['abs_test'] = csv_data['abs_test'] == 'TRUE'
            csv_data['in_range'] = csv_data['in_range'] == 'TRUE'
            csv_data['expected'] = csv_data['expected'] == 'TRUE'
            csv_data = csv_data.astype({
                'ref_min': float, 'ref_max': float, 'should_pass': bool, 'abs_test': bool,
                'cal': float, 'in_range': bool, 'expected': bool, 'peak_heating_load': float,
                'peak_heating_load_month': str, 'peak_heating_load_day': float, 'peak_heating_load_hour': float,
                'peak_cooling_load': float, 'peak_cooling_load_month': str, 'peak_cooling_load_day': float,
                'peak_cooling_load_hour': float, 'temperature_setpoint_avg_hr': float,
                'temperature_setpoint_min': float, 'temperature_setpoint_min_month': str,
                'temperature_setpoint_min_day': float, 'temperature_setpoint_min_hr': float,
                'temperature_setpoint_max': float, 'temperature_setpoint_max_month': str,
                'temperature_setpoint_max_day': float, 'temperature_setpoint_max_hr': float,
            })
            self.csv_data = csv_data

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
            elif k.startswith('condition_z'):
                typed[k] = v.lower() == "Conditioned"

        parameters = {k[2:]: v for k, v in filtered.items() if k.startswith("d")}
        specification = {k[2:]: v for k, v in filtered.items() if k.startswith("i")}
        return OpenBESSpecification(parameters=OpenBESParameters(**parameters), **specification)

    def _load_sim(self, name: str) -> BuildingEnergySimulation:
        if name not in self.simulations:
            file = self.case_files[name]
            with open(file, 'rb') as f:
                toml_content = tomllib.load(f)
            spec = self.toml_to_spec(toml_content)
            simulation = BuildingEnergySimulation(spec=spec)
            self.simulations[name] = simulation
        return self.simulations[name]

    def get_summary(self, sim: BuildingEnergySimulation) -> dict:
        return {
            **translate_index(
                sim.climate.heating_demand,
                sim.climate.heating_demand.max(),
                'peak_heating_load'
            ),
            **translate_index(
                -sim.climate.cooling_demand,
                -sim.climate.cooling_demand.max(),
                'peak_cooling_load'
            ),
            'temperature_setpoint_avg_hr': sim.climate.air_set_temp.mean(),
            **translate_index(
                sim.climate.air_set_temp,
                sim.climate.air_set_temp.min(),
                'temperature_setpoint_min'
            ),
            **translate_index(
                sim.climate.air_set_temp,
                sim.climate.air_set_temp.max(),
                'temperature_setpoint_max'
            ),
        }

    def test_cases(self):
        self.case_outputs = DataFrame([], index=self.csv_data.index, columns=self.csv_data.columns)
        for idx, case in self.csv_data.iterrows():
            name = case['case'][:-1]
            category = case['case'][-1]
            with self.subTest(case=name, category=category):
                simulation = self._load_sim(name)
                summary = self.get_summary(simulation)
                if category == "H":
                    summary['cal'] = simulation.climate.heating_demand.sum()
                else:
                    summary['cal'] = simulation.climate.cooling_demand.sum()
                summary["cal"] *= (
                    simulation.geometry.conditioned_floor_area / 1_000_000.0
                )  # W/m2 -> MWh

                baseline = case['baseline'][:-1] if case['baseline'] else None
                if baseline:
                    baseline_sim = self._load_sim(baseline)
                    if category == "H":
                        base_cal = baseline_sim.climate.heating_demand.sum()
                    else:
                        base_cal = baseline_sim.climate.cooling_demand.sum()
                    base_cal = base_cal * baseline_sim.geometry.conditioned_floor_area / 1_000_000.0  # W/m2 -> MWh
                    summary['cal'] -= base_cal

                summary['in_range'] = case['ref_min'] <= summary['cal'] <= case['ref_max']
                self.case_outputs.loc[idx] = {**case, **summary}
                expected = self.csv_data.loc[idx, self.float_cols].astype(float).round(self.decimal_places)
                computed = self.case_outputs.loc[idx, self.float_cols].astype(float).round(self.decimal_places)
                for c in self.str_cols:
                    expected[c] = self.csv_data.loc[idx, c]
                    computed[c] = self.case_outputs.loc[idx, c]

                self.assertTrue(
                    expected['cal'] == computed['cal'] or expected['cal'] == 0.0,
                    f"Cal values not equal for case {name}{category}:\n"
                    f"{expected['cal']} [expected]\n"
                    f"{computed['cal']} [computed]"
                )
                if case['expected']:
                    self.assertTrue(
                        summary['in_range'],
                        f"Cal value {summary['cal']} not in range [{case['ref_min']}, {case['ref_max']}] "
                        f"for case {name}{category}"
                    )
                if self.ENABLE_DETAIL:
                    self.assertTrue(expected.equals(computed), expected.compare(computed))
                else:
                    if not expected.equals(computed):
                        print("Detailed dataframes are not equal.")
                        print(expected.compare(computed))
        print(self.csv_data.compare(self.case_outputs))

if __name__ == '__main__':
    unittest.main()

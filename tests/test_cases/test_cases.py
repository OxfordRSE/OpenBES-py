import csv
import os
import unittest
from typing import Dict

from numpy import nan
from pandas import Series, DataFrame

from src.openbes.simulations.base import HOURS_DF
from src.openbes.simulations.building_energy import (
    BuildingEnergySimulation,
    day_of_the_month,
)
from src.openbes.types import (
    OpenBESSpecification,
    MONTHS,
)
from tests.unit.utils import describe_differences, OpenBESTestCase

m_index = HOURS_DF.index.names.index("month")
d_index = HOURS_DF.index.names.index("day")
h_index = HOURS_DF.index.names.index("hour")


def translate_index(
    summary_column: Series, summary_value: float, title: str, area: float
) -> dict:
    """Extract the value, month, day-of-the-month, hour from a DataFrame row and return as dict."""
    index = summary_column[summary_column == summary_value].index[0]
    hour_suffix = "_hr" if "_setpoint_" in title else "_hour"
    return {
        title: abs(summary_column.loc[index] * area / 1000.0),
        f"{title}_month": MONTHS.get_by_index(index[m_index] - 1).value[:3],
        f"{title}_day": day_of_the_month(index[d_index], index[m_index]),
        f"{title}_{hour_suffix}": index[h_index],
    }


def get_summary(sim: BuildingEnergySimulation) -> dict:
    return {
        **translate_index(
            sim.thermal.heating_demand,
            sim.thermal.heating_demand.max(),
            "peak_heating_load",
            sim.geometry.conditioned_floor_area,
        ),
        **translate_index(
            -sim.thermal.cooling_demand,
            -sim.thermal.cooling_demand.max(),
            "peak_cooling_load",
            sim.geometry.conditioned_floor_area,
        ),
        "temperature_setpoint_avg_hr": sim.thermal.air_set_temp.mean(),
        **translate_index(
            sim.thermal.air_set_temp,
            sim.thermal.air_set_temp.min(),
            "temperature_setpoint_min",
            sim.geometry.conditioned_floor_area,
        ),
        **translate_index(
            sim.thermal.air_set_temp,
            sim.thermal.air_set_temp.max(),
            "temperature_setpoint_max",
            sim.geometry.conditioned_floor_area,
        ),
    }


class ASHRAE140_2023(unittest.TestCase):
    """
    The ASHRAE 140 tests target the heating/cooling need values. They do not model heating/cooling systems.

    [BES Tool cells N103, Q103]
    """

    ENABLE_DETAIL = False

    decimal_places = 2
    case_outputs: DataFrame = None
    case_files: Dict[str, str] = {}
    simulations: Dict[str, BuildingEnergySimulation] = {}
    float_cols: list = [
        "cal",
        "peak_heating_load",
        "peak_heating_load_day",
        "peak_heating_load_hour",
        "peak_cooling_load",
        "peak_cooling_load_day",
        "peak_cooling_load_hour",
        "temperature_setpoint_avg_hr",
        "temperature_setpoint_min",
        "temperature_setpoint_min_day",
        "temperature_setpoint_min_hr",
        "temperature_setpoint_max",
        "temperature_setpoint_max_day",
    ]
    str_cols: list = [
        "peak_heating_load_month",
        "peak_cooling_load_month",
        "temperature_setpoint_min_month",
        "temperature_setpoint_max_month",
    ]

    def setUp(self):
        case_file_dir = os.path.join(os.path.dirname(__file__), "cases")
        for file in os.listdir(case_file_dir):
            if file.endswith(".toml"):
                self.case_files[os.path.basename(file).rstrip(".toml")] = os.path.join(
                    case_file_dir, file
                )
        with open(
            os.path.join(os.path.dirname(__file__), "openbes-outputs.csv"), "r"
        ) as f:
            reader = csv.DictReader(f)
            csv_data = [row for row in reader]
            csv_data = DataFrame(csv_data)
            csv_data.loc[csv_data["ref_min"] == "", "ref_min"] = nan
            csv_data.loc[csv_data["ref_max"] == "", "ref_max"] = nan
            csv_data["should_pass"] = csv_data["should_pass"] == "TRUE"
            csv_data["abs_test"] = csv_data["abs_test"] == "TRUE"
            csv_data["in_range"] = csv_data["in_range"] == "TRUE"
            csv_data["expected"] = csv_data["expected"] == "TRUE"
            csv_data = csv_data.astype(
                {
                    "ref_min": float,
                    "ref_max": float,
                    "should_pass": bool,
                    "abs_test": bool,
                    "cal": float,
                    "in_range": bool,
                    "expected": bool,
                    "peak_heating_load": float,
                    "peak_heating_load_month": str,
                    "peak_heating_load_day": float,
                    "peak_heating_load_hour": float,
                    "peak_cooling_load": float,
                    "peak_cooling_load_month": str,
                    "peak_cooling_load_day": float,
                    "peak_cooling_load_hour": float,
                    "temperature_setpoint_avg_hr": float,
                    "temperature_setpoint_min": float,
                    "temperature_setpoint_min_month": str,
                    "temperature_setpoint_min_day": float,
                    "temperature_setpoint_min_hr": float,
                    "temperature_setpoint_max": float,
                    "temperature_setpoint_max_month": str,
                    "temperature_setpoint_max_day": float,
                    "temperature_setpoint_max_hr": float,
                }
            )
            self.csv_data = csv_data

    def _load_sim(self, name: str) -> BuildingEnergySimulation:
        if name not in self.simulations:
            spec = OpenBESSpecification.from_toml(self.case_files[name])
            simulation = BuildingEnergySimulation(spec=spec)
            self.simulations[name] = simulation
        return self.simulations[name]

    @unittest.skip("Debug only")
    def test_debug_case(self, case: str = None, debug_values: Series = None):
        if case is None:
            case = input("Enter case name: ")
        name = case[:-1]
        category = case[-1]
        simulation = self._load_sim(name)
        calculated_values = (
            simulation.thermal.heating_demand
            if category == "H"
            else simulation.thermal.cooling_demand
        )
        if debug_values is None:
            debug_file = "../../.dbg/case.csv"
            debug_values = calculated_values.copy()
            debug_values[:] = OpenBESTestCase.read_single_col_csv_to_series(
                debug_file
            ).tolist()
        if any(debug_values < 0) and not any(calculated_values < 0):
            debug_values = debug_values.abs()
        print(describe_differences(debug_values, calculated_values, tolerance=1e-6))

    def test_cases(self):
        # cases = ['900C']
        # _debug = read_csv(os.path.join(os.path.dirname(__file__), 'debug.csv')).squeeze()

        self.case_outputs = DataFrame(
            [], index=self.csv_data.index, columns=self.csv_data.columns
        )
        for idx, case in self.csv_data.iterrows():
            try:
                if case["case"] not in cases:  # noqa: F821
                    continue
            except NameError:
                pass
            name = case["case"][:-1]
            category = case["case"][-1]
            with self.subTest(case=name, category=category):
                simulation = self._load_sim(name)
                summary = get_summary(simulation)
                if category == "H":
                    summary["cal"] = simulation.thermal.heating_demand.sum()
                else:
                    summary["cal"] = simulation.thermal.cooling_demand.sum()
                summary["cal"] *= (
                    simulation.geometry.conditioned_floor_area / 1_000_000.0
                )  # W/m2 -> MWh

                baseline = case["baseline"][:-1] if case["baseline"] else None
                if baseline:
                    baseline_sim = self._load_sim(baseline)
                    if category == "H":
                        base_cal = baseline_sim.thermal.heating_demand.sum()
                    else:
                        base_cal = baseline_sim.thermal.cooling_demand.sum()
                    base_cal = (
                        base_cal
                        * baseline_sim.geometry.conditioned_floor_area
                        / 1_000_000.0
                    )  # W/m2 -> MWh
                    summary["cal"] -= base_cal

                summary["in_range"] = (
                    case["ref_min"] <= summary["cal"] <= case["ref_max"]
                )
                self.case_outputs.loc[idx] = {**case, **summary}
                expected = (
                    self.csv_data.loc[idx, self.float_cols]
                    .astype(float)
                    .round(self.decimal_places)
                )
                computed = (
                    self.case_outputs.loc[idx, self.float_cols]
                    .astype(float)
                    .round(self.decimal_places)
                )
                for c in self.str_cols:
                    expected[c] = self.csv_data.loc[idx, c]
                    computed[c] = self.case_outputs.loc[idx, c]

                self.assertTrue(
                    expected["cal"] == computed["cal"] or expected["cal"] == 0.0,
                    f"Cal values not equal for case {name}{category}:\n"
                    f"{expected['cal']} [expected]\n"
                    f"{computed['cal']} [computed]",
                )
                if case["expected"]:
                    self.assertTrue(
                        summary["in_range"],
                        f"Cal value {summary['cal']} not in range [{case['ref_min']}, {case['ref_max']}] "
                        f"for case {name}{category}",
                    )
                if self.ENABLE_DETAIL:
                    self.assertTrue(
                        expected.equals(computed), expected.compare(computed)
                    )
                else:
                    if not expected.equals(computed):
                        print("Detailed dataframes are not equal.")
                        print(expected.compare(computed))

        computed = (
            self.case_outputs[["case", "cal", "in_range"]]
            .round(self.decimal_places)
            .set_index(["case"])
        )
        expected = (
            self.csv_data[["case", "cal", "in_range"]]
            .round(self.decimal_places)
            .set_index(["case"])
        )
        comp = expected.compare(computed)
        comp["cal_diff"] = comp[("cal", "self")] - comp[("cal", "other")]
        print(comp)


if __name__ == "__main__":
    unittest.main()

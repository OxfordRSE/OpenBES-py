import unittest
from typing import Union, Optional

import pandas as pd
import os

from openbes.examples import get_holywell_house_spec


def duplicate_secondary_hvac_systems(spec):
    """Populate system 2 inputs by mirroring system 1 for HVAC tests."""
    duplicated_fields = {
        "heating_system2_type": spec.heating_system1_type,
        "heating_system2_number": spec.heating_system1_number,
        "heating_system2_nominal_capacity": spec.heating_system1_nominal_capacity,
        "heating_system2_energy_source": spec.heating_system1_energy_source,
        "heating_system2_efficiency_cop": spec.heating_system1_efficiency_cop,
        "heating_system2_on_time": spec.heating_system1_on_time,
        "heating_system2_off_time": spec.heating_system1_off_time,
        "heating_system2_simultaneity_factor_office": spec.heating_system1_simultaneity_factor_office,
        "heating_system2_simultaneity_factor_teaching": spec.heating_system1_simultaneity_factor_teaching,
        "heating_system2_simultaneity_factor_canteen": spec.heating_system1_simultaneity_factor_canteen,
        "heating_system2_simultaneity_factor_common": spec.heating_system1_simultaneity_factor_common,
        "heating_system2_simultaneity_factor_other": spec.heating_system1_simultaneity_factor_other,
        "cooling_system2_type": spec.cooling_system1_type,
        "cooling_system2_number": spec.cooling_system1_number,
        "cooling_system2_nominal_capacity": spec.cooling_system1_nominal_capacity,
        "cooling_system2_sensible_nominal_capacity": spec.cooling_system1_sensible_nominal_capacity,
        "cooling_system2_energy_source": spec.cooling_system1_energy_source,
        "cooling_system2_energy_efficifiency_ratio": spec.cooling_system1_energy_efficifiency_ratio,
        "cooling_system2_on_time": spec.cooling_system1_on_time,
        "cooling_system2_off_time": spec.cooling_system1_off_time,
        "cooling_system2_simultaneity_factor_office": spec.cooling_system1_simultaneity_factor_office,
        "cooling_system2_simultaneity_factor_teaching": spec.cooling_system1_simultaneity_factor_teaching,
        "cooling_system2_simultaneity_factor_canteen": spec.cooling_system1_simultaneity_factor_canteen,
        "cooling_system2_simultaneity_factor_common": spec.cooling_system1_simultaneity_factor_common,
        "cooling_system2_simultaneity_factor_other": spec.cooling_system1_simultaneity_factor_other,
        "ventilation_system2_airflow": spec.ventilation_system1_airflow,
        "ventilation_system2_energy_source": spec.ventilation_system1_energy_source,
        "ventilation_system2_heat_recovery_efficiency": spec.ventilation_system1_heat_recovery_efficiency,
        "ventilation_system2_on_time": spec.ventilation_system1_on_time,
        "ventilation_system2_off_time": spec.ventilation_system1_off_time,
        "ventilation_system2_rated_input_power": spec.ventilation_system1_rated_input_power,
        "ventilation_system2_type": spec.ventilation_system1_type,
        "ventilation_system2_ventilated_area": spec.ventilation_system1_ventilated_area,
    }
    for field, value in duplicated_fields.items():
        setattr(spec.parameters, field, value)

    spec.parameters.heating_system2_min_demand = (
        spec.parameters.heating_system1_min_demand
    )
    spec.parameters.cooling_system2_min_demand = (
        spec.parameters.cooling_system1_min_demand
    )
    return spec


def distinct_secondary_hvac_systems(spec):
    """Populate system 2 inputs with values that differ from system 1."""
    spec = duplicate_secondary_hvac_systems(spec)

    spec.parameters.heating_system2_number = 1
    spec.parameters.heating_system2_nominal_capacity = 24.0
    spec.parameters.heating_system2_efficiency_cop = 0.95
    spec.parameters.heating_system2_min_demand = 20.0
    spec.parameters.heating_system2_on_time = 9
    spec.parameters.heating_system2_off_time = 16
    spec.parameters.heating_system2_simultaneity_factor_office = 0.5
    spec.parameters.heating_system2_simultaneity_factor_teaching = 0.25
    spec.parameters.heating_system2_simultaneity_factor_canteen = 0.5
    spec.parameters.heating_system2_simultaneity_factor_common = 0.1
    spec.parameters.heating_system2_simultaneity_factor_other = 0.0

    spec.parameters.cooling_system2_number = 1
    spec.parameters.cooling_system2_nominal_capacity = 48.0
    spec.parameters.cooling_system2_sensible_nominal_capacity = 37.5
    spec.parameters.cooling_system2_energy_efficifiency_ratio = 3.5
    spec.parameters.cooling_system2_min_demand = 10.0
    spec.parameters.cooling_system2_on_time = 9
    spec.parameters.cooling_system2_off_time = 16
    spec.parameters.cooling_system2_simultaneity_factor_office = 0.5
    spec.parameters.cooling_system2_simultaneity_factor_teaching = 0.25
    spec.parameters.cooling_system2_simultaneity_factor_canteen = 0.5
    spec.parameters.cooling_system2_simultaneity_factor_common = 0.1
    spec.parameters.cooling_system2_simultaneity_factor_other = 0.0

    spec.parameters.ventilation_system2_airflow = 150.0
    spec.parameters.ventilation_system2_heat_recovery_efficiency = 0.5
    spec.parameters.ventilation_system2_on_time = 11
    spec.parameters.ventilation_system2_off_time = 13
    spec.parameters.ventilation_system2_rated_input_power = 0.15
    spec.parameters.ventilation_system2_ventilated_area = 50.0

    return spec


def describe_differences(
    expected: pd.Series, calculated: pd.Series, tolerance: float = 0.0
) -> str:
    differences = expected.compare(calculated, result_names=("expected", "calculated"))
    if differences.empty:
        return "No differences found."
    if expected.dtype == "O":
        return (
            f"{len(differences)} rows differ ({len(differences) / len(expected) * 100:.2f}% of all rows):\n"
            f"{differences}"
        )

    differences["ex_minus_calc"] = differences["expected"] - differences["calculated"]
    percent = len(differences) / len(expected) * 100
    max_diff = max(abs(differences["expected"] - differences["calculated"]))
    max_loc = calculated.index[abs(calculated - expected) == max_diff].tolist()
    max_loc = [{"index": x, "rownum": calculated.index.get_loc(x)} for x in max_loc]
    mean_diff = sum(abs(differences["expected"] - differences["calculated"])) / len(
        differences
    )
    if tolerance == 0.0:
        return (
            f"{len(differences)} rows differ ({percent:.2f}% of all rows):\n"
            f"Max difference: {max_diff} {max_loc}\n"
            f"Mean difference: {mean_diff}\n"
            f"{differences}"
        )

    def big_diffs(t):
        mask = abs(differences["expected"] - differences["calculated"]) > t
        return differences[mask]

    return (
        f"{len(differences)} rows differ ({percent:.2f}% of all rows):\n"
        f"Max difference: {max_diff} {max_loc}\n"
        f"Mean difference: {mean_diff}\n"
        f"{len(big_diffs(tolerance))} rows outside of tolerable difference +/- {tolerance}:\n"
        f"% of differences outside tolerance: {len(big_diffs(tolerance)) / len(expected) * 100:.2f}%\n"
        f"% of differences outside 2 x tolerance ({tolerance * 2}): {len(big_diffs(2 * tolerance)) / len(expected) * 100:.2f}%\n"
        f"% of differences outside 10 x tolerance ({tolerance * 10}): {len(big_diffs(10 * tolerance)) / len(expected) * 100:.2f}%\n"
        f"{big_diffs(tolerance)}"
    )


class OpenBESTestCase(unittest.TestCase):
    # If a float is provided, it is treated as a tolerance value, otherwise as decimal places.
    # Values are rounded to the specified decimal places before comparison,
    # or compared within the specified tolerance.
    decimal_places_or_tolerance: Union[int, float] = 6
    decimal_places = 6  # Legacy test methods below use decimal_places

    def setUp(self):
        self.spec = get_holywell_house_spec()

    @classmethod
    def read_csv(cls, relative_path: str) -> pd.DataFrame:
        base_path = os.path.dirname(__file__)
        full_path = os.path.join(base_path, relative_path)
        return pd.read_csv(full_path)

    @classmethod
    def read_single_col_csv_to_series(cls, relative_path: str) -> pd.Series:
        return cls.read_csv(relative_path).squeeze()

    @classmethod
    def get_expectation_for_series(
        cls, series: pd.Series, expected_values: list
    ) -> pd.Series:
        """
        Set the values of a pandas Series to the provided list of values.
        This will preserve the original index of the Series.

        Example:
            calcualted = Series([0, 0, 0, 0], index=[10, 11, 12, 13])
            expected = set_series_values(calculated, [1, 2, 3, 4])
            # expected is now Series([1, 2, 3, 4], index=[10, 11, 12, 13])
        """
        series = series.copy()
        series = series.iloc[: len(expected_values)]
        return series

    def get_decimal_places_and_tolerance(
        self, decimal_places_or_tolerance: Union[int, float] = None
    ) -> tuple[Optional[int], Optional[float]]:
        if decimal_places_or_tolerance is None:
            decimal_places_or_tolerance = self.decimal_places_or_tolerance
        decimal_places = None
        tolerance = None
        if isinstance(decimal_places_or_tolerance, int):
            decimal_places = decimal_places_or_tolerance
        elif isinstance(decimal_places_or_tolerance, float):
            tolerance = decimal_places_or_tolerance
        return decimal_places, tolerance

    def check_series_versus_values(
        self,
        series: pd.Series,
        expected_values: Union[list, pd.Series],
        decimal_places_or_tolerance: Union[int, float] = None,
    ) -> None:
        if series.dtype == "O":
            decimal_places, tolerance = None, None
        else:
            decimal_places, tolerance = self.get_decimal_places_and_tolerance(
                decimal_places_or_tolerance
            )

        calculated = self.get_expectation_for_series(series, expected_values)
        if decimal_places is not None:
            calculated = calculated.round(decimal_places)
        if not isinstance(expected_values, pd.Series):
            expected_values = pd.Series(expected_values)
        expected = (
            expected_values.round(decimal_places)
            if decimal_places is not None
            else expected_values
        )
        expected.index = calculated.index
        if tolerance is None:
            self.assertTrue(
                expected.equals(calculated),
                describe_differences(expected, calculated, 0.0),
            )
        else:
            differences = expected.compare(calculated)
            mask = abs(differences["self"] - differences["other"]) > tolerance
            self.assertTrue(
                differences[mask].empty,
                describe_differences(expected, calculated, tolerance),
            )

    def check_series_versus_csv(
        self,
        series: pd.Series,
        csv_file_relative_path: str,
        decimal_places_or_tolerance: Union[int, float] = None,
    ) -> None:
        expected = self.read_single_col_csv_to_series(csv_file_relative_path)
        self.check_series_versus_values(series, expected, decimal_places_or_tolerance)

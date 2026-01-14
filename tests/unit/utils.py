import unittest
from typing import Union, Optional

import pandas as pd
import os

from src.openbes.examples import HOLYWELL_HOUSE_SPEC


def describe_differences(
        expected: pd.Series,
        calculated: pd.Series,
        tolerance: float = 0.0
) -> str:
    differences = expected.compare(calculated, result_names=('expected', 'calculated'))
    if differences.empty:
        return "No differences found."
    differences['ex_minus_calc'] = differences['expected'] - differences['calculated']
    percent = len(differences) / len(expected) * 100
    max_diff = max(abs(differences['expected'] - differences['calculated']))
    max_loc = calculated.index[abs(calculated - expected) == max_diff].tolist()
    max_loc = [{'index': x, 'rownum': calculated.index.get_loc(x)} for x in max_loc]
    mean_diff = sum(abs(differences['expected'] - differences['calculated'])) / len(differences)
    if tolerance == 0.0:
        return (
            f"{len(differences)} rows differ ({percent:.2f}% of all rows):\n"
            f"Max difference: {max_diff} {max_loc}\n"
            f"Mean difference: {mean_diff}\n"
            f"{differences}"
        )
    def big_diffs(t):
        mask = abs(differences['expected'] - differences['calculated']) > t
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
        self.spec = HOLYWELL_HOUSE_SPEC

    @classmethod
    def read_csv(cls, relative_path: str) -> pd.DataFrame:
        base_path = os.path.dirname(__file__)
        full_path = os.path.join(base_path, relative_path)
        return pd.read_csv(full_path)

    @classmethod
    def read_single_col_csv_to_series(cls, relative_path: str) -> pd.Series:
        return cls.read_csv(relative_path).squeeze()

    @classmethod
    def get_expectation_for_series(cls, series: pd.Series, expected_values: list) -> pd.Series:
        """
        Set the values of a pandas Series to the provided list of values.
        This will preserve the original index of the Series.

        Example:
            calcualted = Series([0, 0, 0, 0], index=[10, 11, 12, 13])
            expected = set_series_values(calculated, [1, 2, 3, 4])
            # expected is now Series([1, 2, 3, 4], index=[10, 11, 12, 13])
        """
        series = series.copy()
        series = series.iloc[:len(expected_values)]
        return series

    def get_decimal_places_and_tolerance(
            self,
            decimal_places_or_tolerance: Union[int, float] = None
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
            decimal_places_or_tolerance: Union[int, float] = None
    ) -> None:
        decimal_places, tolerance = self.get_decimal_places_and_tolerance(decimal_places_or_tolerance)

        calculated = self.get_expectation_for_series(series, expected_values)
        if decimal_places is not None:
            calculated = calculated.round(decimal_places)
        if not isinstance(expected_values, pd.Series):
            expected_values = pd.Series(expected_values)
        expected = expected_values.round(decimal_places) if decimal_places is not None else expected_values
        expected.index = calculated.index
        if tolerance is None:
            self.assertTrue(expected.equals(calculated), describe_differences(expected, calculated, 0.0))
        else:
            differences = expected.compare(calculated)
            mask = abs(differences['self'] - differences['other']) > tolerance
            self.assertTrue(
                differences[mask].empty,
                describe_differences(expected, calculated, tolerance)
            )

    def check_series_versus_csv(
            self,
            series: pd.Series,
            csv_file_relative_path: str,
            decimal_places_or_tolerance: Union[int, float] = None
    ) -> None:
        expected = self.read_single_col_csv_to_series(csv_file_relative_path)
        self.check_series_versus_values(series, expected, decimal_places_or_tolerance)


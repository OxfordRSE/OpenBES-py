import unittest
from copy import deepcopy

from openbes.types.enums import DAYS
from openbes.simulations.occupancy import (
    day_of_the_week,
    is_public_holiday,
    OccupationSimulation,
)
from openbes.simulations.base import HOURS_DF
from tests.unit.utils import OpenBESTestCase
from openbes.examples import HOLYWELL_HOUSE_SPEC


class Occupancy(OpenBESTestCase):
    def setUp(self):
        self.spec = HOLYWELL_HOUSE_SPEC
        self.sim = OccupationSimulation(self.spec)

    def test_day_of_the_week(self):
        days = [DAYS.Mon, DAYS.Tue, DAYS.Wed, DAYS.Thu, DAYS.Fri, DAYS.Sat, DAYS.Sun]
        for i in range(1, 15):
            with self.subTest(i=i):
                self.assertEqual(days[(i - 1) % 7], day_of_the_week(i))

    def test_is_public_holiday(self):
        days = range(1, 366)
        holidays = [*range(1, 6), *range(358, 366)]
        for i in days:
            with self.subTest(i=i):
                if i in holidays:
                    self.assertTrue(is_public_holiday(i))
                else:
                    self.assertFalse(is_public_holiday(i))

    def test_is_occupied_day(self):
        days = range(1, 366)
        holiday_count = 11
        weekend_count = 104  # 52 weekends * 2 days
        occupied_count = 365 - holiday_count - weekend_count
        self.assertEqual(
            sum([int(self.sim.is_occupied_day(d)) for d in days]), occupied_count
        )

    def test_HOURS_DF(self):
        # Check we have 24 * 365 rows
        self.assertEqual(len(HOURS_DF), 24 * 365)
        df = HOURS_DF.copy().reset_index()
        self.assertEqual(df["month"].nunique(), 12)
        self.assertEqual(df["hour"].nunique(), 24)

    def test_occupation_by_zone(self):
        with self.subTest(method="Occupation/Capacity"):
            self.assertEqual(self.sim.occupation_ratio, 0.50)
        with self.subTest(method="Occupation/Area"):
            spec = deepcopy(self.spec)
            spec.max_building_occupation = None
            sim = OccupationSimulation(spec)
            zonal_capacities = [
                (190.56 + 494.85) / 5,
                129.28 / 1.5,
                97.88 / 5,
                (132.76 + 55.65 + 52.93) / 5,
                0.0,
            ]
            expected = round(
                spec.typical_occupation / sum(zonal_capacities), self.decimal_places
            )
            computed = round(sim.occupation_ratio, self.decimal_places)
            self.assertEqual(expected, computed)

    def test_occupation_by_hour(self):
        expected = self.read_single_col_csv_to_series(
            "fixtures/hh_occupancy_ratio.csv"
        ).to_frame("occupancy_ratio")
        expected.index = HOURS_DF.index
        expected["is_occupied"] = expected["occupancy_ratio"].apply(lambda x: x > 0)
        with self.subTest(column="is_occupied"):
            tmp = expected.copy()
            tmp["is_occupied"] = self.sim.is_occupied
            tmp["occupancy_ratio"] = self.sim.occupancy_ratio
            self.assertTrue(expected.equals(tmp), expected.compare(tmp))
        with self.subTest(column="is_occupied_day"):
            expected = expected.groupby(level="day")["is_occupied"].transform("max")
            self.check_series_versus_values(self.sim.occupied_days, expected)

    def test_occupation_m2_per_person(self):
        expected = round(4.86522963366, self.decimal_places)
        calculated = round(self.sim.occupation_m2_per_person, self.decimal_places)
        self.assertEqual(expected, calculated)

    def test_metabolic_rate_per_m2(self):
        expected = round(5.0, self.decimal_places)
        calculated = round(self.sim.metabolic_rate_per_m2, self.decimal_places)
        self.assertEqual(expected, calculated)


if __name__ == "__main__":
    unittest.main()

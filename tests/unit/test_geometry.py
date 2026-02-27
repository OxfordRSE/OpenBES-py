import unittest
from copy import copy

from pandas import DataFrame, Series

from openbes.simulations.geometry import (
    Rectangle,
    BuildingGeometry,
)
from openbes.types import FLOORS, COMPASS_POINTS, ORIENTATIONS
from tests.unit.utils import OpenBESTestCase
from openbes.examples import HOLYWELL_HOUSE_SPEC


class Geometry(OpenBESTestCase):
    def setUp(self):
        self.geometry = BuildingGeometry(spec=HOLYWELL_HOUSE_SPEC)

    def test_equivalent_rectangle(self):
        expected = Rectangle(length=43.410, width=14.130)
        calculated = self.geometry.equivalent_rectangle
        self.assertTrue(expected == calculated, expected.compare(calculated))

    def test_gross_floor_areas(self):
        with self.subTest("series"):
            calculated = self.geometry.gross_floor_areas
            self.check_series_versus_values(
                calculated,
                [
                    190.56,
                    129.28,
                    97.88,
                    132.76,
                    0.0,
                    494.85,
                    0.0,
                    0.0,
                    55.65,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    52.93,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                ],
            )
        with self.subTest("by_floor"):
            expected = {
                FLOORS.Ground: 550.48,
                FLOORS.First: 550.50,
                FLOORS.Second: 52.93,
                FLOORS.Third: 0.0,
                FLOORS.Fourth: 0.0,
            }
            for floor, expected_area in expected.items():
                calculated = self.geometry.get_gross_floor_area_for_floor(floor)
                self.assertEqual(expected_area, calculated)
        with self.subTest("total"):
            expected = 1153.91
            calculated = round(self.geometry.gross_floor_area, self.decimal_places)
            self.assertEqual(expected, calculated)

    def test_conditioned_floor_area(self):
        floors = [
            {"floor": FLOORS.Ground, "expected": 522.956000},
            {"floor": FLOORS.First, "expected": 522.975000},
            {"floor": FLOORS.Second, "expected": 50.283500},
            {"floor": FLOORS.Third, "expected": 0.000000},
            {"floor": FLOORS.Fourth, "expected": 0.000000},
        ]
        for item in floors:
            with self.subTest(floors=item["floor"]):
                expected = item["expected"]
                calculated = round(
                    self.geometry.get_conditioned_floor_area_for_floor(item["floor"]),
                    self.decimal_places,
                )
                self.assertEqual(expected, calculated)
        with self.subTest(floors="all"):
            expected = 1096.214500
            calculated = round(
                self.geometry.conditioned_floor_area, self.decimal_places
            )
            self.assertEqual(expected, calculated)

    def test_conditioned_external_vertical_envelope_area(self):
        """
        This test uses rounding to decimal_places because Python and Excel round slightly differently.
        """
        decimal_palces = (
            self.decimal_places - 2
        )  # precise enough, and avoids rounding differences between Excel and Python
        expected = Series(
            [
                130.268601,
                42.402565,
                130.268601,
                42.402565,
                130.270967,
                42.403335,
                130.270967,
                42.403335,
                40.394285,
                13.148382,
                40.394285,
                13.148382,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
            ]
        )
        expected = expected.round(decimal_palces)
        calculated = self.geometry.external_vertical_envelope_conditioned_areas
        expected.index = calculated.index
        calculated = calculated.round(decimal_palces)
        self.assertTrue(expected.equals(calculated), expected.compare(calculated))

    def test_windows(self):
        with self.subTest("count"):
            calculated = self.geometry.window_count
            self.check_series_versus_values(
                calculated,
                [
                    9,
                    3,
                    9,
                    0,
                    9,
                    3,
                    9,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                ],
            )
        with self.subTest("area"):
            calculated = self.geometry.window_area_orientation
            self.check_series_versus_values(
                calculated,
                [
                    34.56,
                    11.52,
                    34.56,
                    0.0,
                    34.56,
                    11.52,
                    34.56,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                ],
            )
        with self.subTest("ratio"):
            calculated = self.geometry.window_ratio
            self.check_series_versus_values(
                calculated,
                [
                    0.258581,
                    0.264803,
                    0.258581,
                    0.0,
                    0.258576,
                    0.264798,
                    0.258576,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                ],
            )

    def test_facing_directions(self):
        expected = DataFrame(
            {
                COMPASS_POINTS.North: [45],
                COMPASS_POINTS.NorthEast: [37],
                COMPASS_POINTS.East: [51],
                COMPASS_POINTS.SouthEast: [51],
                COMPASS_POINTS.South: [36],
                COMPASS_POINTS.SouthWest: [51],
                COMPASS_POINTS.West: [51],
                COMPASS_POINTS.NorthWest: [38],
            }
        )
        self.assertEqual(expected.sum(axis="columns").values[0], 360)
        calculated = DataFrame(
            {
                COMPASS_POINTS.North: [0],
                COMPASS_POINTS.NorthEast: [0],
                COMPASS_POINTS.East: [0],
                COMPASS_POINTS.SouthEast: [0],
                COMPASS_POINTS.South: [0],
                COMPASS_POINTS.SouthWest: [0],
                COMPASS_POINTS.West: [0],
                COMPASS_POINTS.NorthWest: [0],
            }
        )
        for orientation in range(360):
            compass_point = self.geometry.get_facing_direction(orientation)
            calculated.loc[0, compass_point] += 1
        self.assertTrue(expected.equals(calculated), expected.compare(calculated))

    def test_compass_point_for_orientation(self):
        with self.subTest("aligned"):
            spec = copy(HOLYWELL_HOUSE_SPEC)
            spec.orientation_angle = 0.0
            geometry = BuildingGeometry(spec=spec)
            expected = {
                ORIENTATIONS.Up: COMPASS_POINTS.North,
                ORIENTATIONS.Right: COMPASS_POINTS.East,
                ORIENTATIONS.Down: COMPASS_POINTS.South,
                ORIENTATIONS.Left: COMPASS_POINTS.West,
            }
            for orientation, compass_point in expected.items():
                calculated = geometry.get_compass_point_for_orientation(orientation)
                self.assertEqual(compass_point, calculated)

        with self.subTest("askew"):
            spec = copy(HOLYWELL_HOUSE_SPEC)
            spec.orientation_angle = 22.0
            geometry = BuildingGeometry(spec=spec)
            expected = {
                ORIENTATIONS.Up: COMPASS_POINTS.North,
                ORIENTATIONS.Right: COMPASS_POINTS.SouthEast,
                ORIENTATIONS.Down: COMPASS_POINTS.SouthWest,
                ORIENTATIONS.Left: COMPASS_POINTS.West,
            }
            for orientation, compass_point in expected.items():
                calculated = geometry.get_compass_point_for_orientation(orientation)
                self.assertEqual(compass_point, calculated)

    def test_window_areas(self):
        expected = Series(
            [
                33.684921,
                0.0,
                0.0,
                0.0,
                33.684921,
                0.0,
                11.228307,
                0.0,
                33.684921,
                0.0,
                0.0,
                0.0,
                33.684921,
                0.0,
                11.228307,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
            ]
        )
        expected = expected.round(self.decimal_places)
        calculated = self.geometry.window_areas.round(self.decimal_places)
        expected.index = calculated.index
        with self.subTest("by_compass_point"):
            self.assertTrue(expected.equals(calculated), expected.compare(calculated))
        with self.subTest("total"):
            expected_total = expected.sum()
            calculated_total = self.geometry.window_area
            self.assertAlmostEqual(
                expected_total, calculated_total, self.decimal_places - 1
            )
        with self.subTest("opaque_areas"):
            summed_areas = self.geometry.opaque_areas + self.geometry.window_areas
            expected = self.geometry.conditioned_facade_areas
            self.assertTrue(
                expected.equals(summed_areas), expected.compare(summed_areas)
            )

    def test_window_shading(self):
        expected = Series([36.842883, 36.842883, 0.0, 0.0, 0.0])
        expected = expected.round(self.decimal_places)
        calculated = self.geometry.window_shading.round(self.decimal_places)
        expected.index = calculated.index
        self.assertTrue(expected.equals(calculated), expected.compare(calculated))

    def test_heat_transfer_rate_windows(self):
        self.assertEqual(
            round(self.geometry.heat_transfer_rate_windows, self.decimal_places),
            round(0.358498, self.decimal_places),
        )

    def test_heat_transfer_rate_opaque(self):
        # This test uses rounding to self.decimal_places - 2 because of Excel/Python rounding differences
        self.assertEqual(
            round(self.geometry.heat_transfer_rate_opaque, self.decimal_places - 2),
            round(1.739035, self.decimal_places - 2),
        )

    def test_roof_factor(self):
        self.assertEqual(
            round(self.geometry.roof_factor, self.decimal_places),
            round(1.059481, self.decimal_places),
        )


if __name__ == "__main__":
    unittest.main()

import unittest
from copy import copy

from pandas import DataFrame

from src.openbes.simulations.geometry import (
    Rectangle,
    BuildingGeometry,
    ZONAL_RECTANGLES,
    ORIENTATION_FACADE,
    COMPASS_POINT_FACADE,
)
from src.openbes.types import FLOORS, COMPASS_POINTS, ORIENTATIONS
from tests.test_holywell_house import DECIMAL_PLACES
from tests.utils import HOLYWELL_HOUSE_SPEC


class Geometry(unittest.TestCase):
    def setUp(self):
        self.geometry = BuildingGeometry(spec=HOLYWELL_HOUSE_SPEC)

    def test_equivalent_rectangle(self):
        expected = Rectangle(length=43.410, width=14.130)
        calculated = self.geometry.equivalent_rectangle
        self.assertTrue(expected == calculated, expected.compare(calculated))

    def test_gross_floor_areas(self):
        with self.subTest('dataframe'):
            expected = ZONAL_RECTANGLES.copy()
            expected['gross_floor_area'] = [
                190.56, 129.28, 97.88, 132.76, 0.0,
                494.85, 0.0, 0.0, 55.65, 0.0,
                0.0, 0.0, 0.0, 52.93, 0.0,
                0.0, 0.0, 0.0, 0.0, 0.0,
                0.0, 0.0, 0.0, 0.0, 0.0,
            ]
            calculated = self.geometry.gross_floor_areas
            self.assertTrue(expected.equals(calculated), expected.compare(calculated))
        with self.subTest('by_floor'):
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
        with self.subTest('total'):
            expected = 1153.91
            calculated = round(self.geometry.gross_floor_area, DECIMAL_PLACES)
            self.assertEqual(expected, calculated)

    def test_conditioned_floor_area(self):
        floors = [
            {'floor': FLOORS.Ground, 'expected': 522.956000},
            {'floor': FLOORS.First, 'expected': 522.975000},
            {'floor': FLOORS.Second, 'expected': 50.283500},
            {'floor': FLOORS.Third, 'expected': 0.000000},
            {'floor': FLOORS.Fourth, 'expected': 0.000000},
        ]
        for item in floors:
            with self.subTest(floors=item['floor']):
                expected = item['expected']
                calculated = round(self.geometry.get_conditioned_floor_area_for_floor(item['floor']), DECIMAL_PLACES)
                self.assertEqual(expected, calculated)
        with self.subTest(floors='all'):
            expected = 1096.214500
            calculated = round(self.geometry.conditioned_floor_area, DECIMAL_PLACES)
            self.assertEqual(expected, calculated)

    def test_conditioned_external_vertical_envelope_area(self):
        """
        This test uses rounding to decimal_places because Python and Excel round slightly differently.
        """
        decimal_palces = DECIMAL_PLACES - 2  # precise enough, and avoids rounding differences between Excel and Python
        expected = ORIENTATION_FACADE.copy()
        expected['external_vertical_envelope_conditioned_area'] = [
            130.268601, 42.402565, 130.268601, 42.402565,
            130.270967, 42.403335, 130.270967, 42.403335,
            40.394285, 13.148382, 40.394285, 13.148382,
            0.0, 0.0, 0.0, 0.0,
            0.0, 0.0, 0.0, 0.0,
        ]
        expected = expected.round(decimal_palces)
        calculated = self.geometry.external_vertical_envelope_conditioned_areas
        calculated = calculated.round(decimal_palces)
        self.assertTrue(expected.equals(calculated), expected.compare(calculated))

    def test_windows(self):
        with self.subTest('count'):
            expected = ORIENTATION_FACADE.copy()
            expected['window_count'] = [
                9, 3, 9, 0,
                9, 3, 9, 0,
                0, 0, 0, 0,
                0, 0, 0, 0,
                0, 0, 0, 0,
            ]
            calculated = self.geometry.window_count
            self.assertTrue(expected.equals(calculated), expected.compare(calculated))
        with self.subTest('area'):
            expected = ORIENTATION_FACADE.copy()
            expected['window_area_orientation'] = [
                34.56, 11.52, 34.56, 0.0,
                34.56, 11.52, 34.56, 0.0,
                0.0, 0.0, 0.0, 0.0,
                0.0, 0.0, 0.0, 0.0,
                0.0, 0.0, 0.0, 0.0,
            ]
            calculated = self.geometry.window_area_orientation.round(DECIMAL_PLACES)
            self.assertTrue(expected.equals(calculated), expected.compare(calculated))
        with self.subTest('ratio'):
            expected = ORIENTATION_FACADE.copy()
            expected['window_ratio'] = [
                0.258581, 0.264803, 0.258581, 0.0,
                0.258576, 0.264798, 0.258576, 0.0,
                0.0, 0.0, 0.0, 0.0,
                0.0, 0.0, 0.0, 0.0,
                0.0, 0.0, 0.0, 0.0,
            ]
            expected = expected.round(DECIMAL_PLACES)
            calculated = self.geometry.window_ratio
            calculated = calculated.round(DECIMAL_PLACES)
            self.assertTrue(expected.equals(calculated), expected.compare(calculated))

    def test_facing_directions(self):
        expected = DataFrame({
            COMPASS_POINTS.North: [45],
            COMPASS_POINTS.NorthEast: [37],
            COMPASS_POINTS.East: [51],
            COMPASS_POINTS.SouthEast: [51],
            COMPASS_POINTS.South: [36],
            COMPASS_POINTS.SouthWest: [51],
            COMPASS_POINTS.West: [51],
            COMPASS_POINTS.NorthWest: [38],
        })
        self.assertEqual(expected.sum(axis="columns").values[0], 360)
        calculated = DataFrame({
            COMPASS_POINTS.North: [0],
            COMPASS_POINTS.NorthEast: [0],
            COMPASS_POINTS.East: [0],
            COMPASS_POINTS.SouthEast: [0],
            COMPASS_POINTS.South: [0],
            COMPASS_POINTS.SouthWest: [0],
            COMPASS_POINTS.West: [0],
            COMPASS_POINTS.NorthWest: [0],
        })
        for orientation in range(360):
            compass_point = self.geometry.get_facing_direction(orientation)
            calculated.loc[0, compass_point] += 1
        self.assertTrue(expected.equals(calculated), expected.compare(calculated))

    def test_compass_point_for_orientation(self):
        with self.subTest('aligned'):
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

        with self.subTest('askew'):
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

    def test_window_area(self):
        expected = COMPASS_POINT_FACADE.copy()
        expected['window_area'] = [
            33.684921, 0.0,	0.0, 0.0, 33.684921, 0.0, 11.228307, 0.0,
            33.684921, 0.0,	0.0, 0.0, 33.684921, 0.0, 11.228307, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
        ]
        expected = expected.round(DECIMAL_PLACES)
        calculated = self.geometry.window_area.round(DECIMAL_PLACES)
        self.assertTrue(expected.equals(calculated), expected.compare(calculated))

    def test_window_shading(self):
        expected = DataFrame()
        expected['window_area'] = [36.842883, 36.842883, 0.0, 0.0, 0.0]
        expected = expected.round(DECIMAL_PLACES)
        calculated = self.geometry.window_shading.round(DECIMAL_PLACES)
        expected.index = calculated.index
        self.assertTrue(expected.equals(calculated), expected.compare(calculated))

if __name__ == '__main__':
    unittest.main()

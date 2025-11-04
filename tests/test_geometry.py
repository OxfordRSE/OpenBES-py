import unittest

from src.openbes.simulations.geometry import (
    get_conditioned_floor_area,
    Rectangle,
    get_equivalent_rectangle,
    get_conditioned_external_vertical_envelope_area,
)
from src.openbes.types import FLOORS, ORIENTATIONS
from tests.test_holywell_house import DECIMAL_PLACES
from tests.utils import HOLYWELL_HOUSE_SPEC


class Geometry(unittest.TestCase):
    def setUp(self):
        self.spec = HOLYWELL_HOUSE_SPEC

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
                calculated = round(get_conditioned_floor_area(self.spec, floors=[item['floor']]), DECIMAL_PLACES)
                self.assertEqual(expected, calculated)
        with self.subTest(floors='all'):
            expected = 1096.214500
            calculated = round(get_conditioned_floor_area(self.spec), DECIMAL_PLACES)
            self.assertEqual(expected, calculated)

    def test_equivalent_rectangle(self):
        expected = Rectangle(length=43.410, width=14.130)
        calculated = get_equivalent_rectangle(self.spec)
        self.assertTrue(expected == calculated, expected.compare(calculated))

    def test_conditioned_external_vertical_envelope_area(self):
        """
        This test uses rounding to decimal_places because Python and Excel round slightly differently.
        """
        decimal_places = 2
        cases = [
            {'floor': FLOORS.Ground, 'orientation': ORIENTATIONS.Up, 'expected': 130.268601},
            {'floor': FLOORS.Ground, 'orientation': ORIENTATIONS.Right, 'expected': 42.402565},
            {'floor': FLOORS.Ground, 'orientation': ORIENTATIONS.Down, 'expected': 130.268601},
            {'floor': FLOORS.Ground, 'orientation': ORIENTATIONS.Left, 'expected': 42.402565},
            {'floor': FLOORS.First, 'orientation': ORIENTATIONS.Up, 'expected': 130.268601},
            {'floor': FLOORS.First, 'orientation': ORIENTATIONS.Right, 'expected': 42.402565},
            {'floor': FLOORS.First, 'orientation': ORIENTATIONS.Down, 'expected': 130.268601},
            {'floor': FLOORS.First, 'orientation': ORIENTATIONS.Left, 'expected': 42.402565},
            {'floor': FLOORS.Second, 'orientation': ORIENTATIONS.Up, 'expected': 40.394285},
            {'floor': FLOORS.Second, 'orientation': ORIENTATIONS.Right, 'expected': 13.148382},
            {'floor': FLOORS.Second, 'orientation': ORIENTATIONS.Down, 'expected': 40.394285},
            {'floor': FLOORS.Second, 'orientation': ORIENTATIONS.Left, 'expected': 13.148382},
            {'floor': FLOORS.Third, 'orientation': ORIENTATIONS.Up, 'expected': 0.0},
            {'floor': FLOORS.Third, 'orientation': ORIENTATIONS.Right, 'expected': 0.0},
            {'floor': FLOORS.Third, 'orientation': ORIENTATIONS.Down, 'expected': 0.0},
            {'floor': FLOORS.Third, 'orientation': ORIENTATIONS.Left, 'expected': 0.0},
        ]
        for item in cases:
            with self.subTest(floors=item['floor'].value, orientation=item['orientation'].value):
                expected = round(item['expected'], decimal_places)
                calculated = round(
                    get_conditioned_external_vertical_envelope_area(
                        spec=self.spec,
                        orientations=[item['orientation']],
                        floors=[item['floor']]
                    ),
                    decimal_places
                )
                self.assertEqual(expected, calculated)
        for orientation in ORIENTATIONS:
            with self.subTest(floors='all', orientation=orientation.value):
                if orientation in [ORIENTATIONS.Up, ORIENTATIONS.Down]:
                    expected = round(300.931487, decimal_places)
                else:
                    expected = round(97.953512, decimal_places)
                calculated = round(
                    get_conditioned_external_vertical_envelope_area(
                        spec=self.spec,
                        orientations=[orientation],
                    ),
                    decimal_places
                )
                self.assertEqual(expected, calculated)
        for floor in FLOORS:
            with self.subTest(floors=floor.value, orientation='all'):
                if floor == FLOORS.Ground:
                    expected = round(345.342232, decimal_places)
                elif floor == FLOORS.First:
                    expected = round(345.348604, decimal_places)
                elif floor == FLOORS.Second:
                    expected = round(107.085333, decimal_places)
                else:
                    expected = 0.0
                calculated = round(
                    get_conditioned_external_vertical_envelope_area(
                        spec=self.spec,
                        floors=[floor],
                    ),
                    decimal_places
                )
                self.assertEqual(expected, calculated)
        with self.subTest(floors='all', orientation='all'):
            expected = round(797.77627, decimal_places)
            calculated = round(
                get_conditioned_external_vertical_envelope_area(
                    spec=self.spec,
                ),
                decimal_places
            )
            self.assertEqual(expected, calculated)

if __name__ == '__main__':
    unittest.main()

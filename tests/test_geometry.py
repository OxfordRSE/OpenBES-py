import unittest

from src.openbes.simulations.geometry import get_conditioned_floor_area
from tests.test_holywell_house import DECIMAL_PLACES
from tests.utils import HOLYWELL_HOUSE_SPEC


class Geometry(unittest.TestCase):
    def setUp(self):
        self.spec = HOLYWELL_HOUSE_SPEC

    def test_conditioned_floor_area(self):
        expected = 1096.214500
        calculated = round(get_conditioned_floor_area(self.spec), DECIMAL_PLACES)
        self.assertEqual(expected, calculated)

if __name__ == '__main__':
    unittest.main()

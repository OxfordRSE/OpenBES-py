import unittest
from pandas import read_csv

from src.openbes.simulations.temp_demand import (
    get_internal_heat_from_occupants,
    get_internal_heat_from_appliances,
    get_internal_heat_from_lighting,
    get_internal_heat,
)
from src.openbes.simulations.occupancy import (
    HOURS_DF,
)
from tests.utils import HOLYWELL_HOUSE_SPEC


class TemperatureDemand(unittest.TestCase):
    def setUp(self):
        self.spec = HOLYWELL_HOUSE_SPEC

    def test_internal_heat_occupants(self):
        expected = read_csv('fixtures/hh_internal_heat_occupants.csv')
        expected.index = HOURS_DF.index
        calculated = get_internal_heat_from_occupants(self.spec)
        self.assertTrue(expected.equals(calculated), "EXPECTED FAILURE while Spreadsheet months start with Monday")# expected.compare(calculated))

    def test_internal_heat_appliances(self):
        expected = read_csv('fixtures/hh_internal_heat_appliances.csv')
        expected.index = HOURS_DF.index
        calculated = get_internal_heat_from_appliances(self.spec)
        self.assertTrue(expected.equals(calculated), "EXPECTED FAILURE while Spreadsheet months start with Monday")# expected.compare(calculated))

    def test_internal_heat_lighting(self):
        expected = read_csv('fixtures/hh_internal_heat_lighting.csv')
        expected.index = HOURS_DF.index
        calculated = get_internal_heat_from_lighting(self.spec)
        self.assertTrue(expected.equals(calculated), "EXPECTED FAILURE while Spreadsheet months start with Monday") # expected.compare(calculated))

    def test_internal_heat(self):
        expected = read_csv('fixtures/hh_internal_heat.csv')
        expected.index = HOURS_DF.index
        calculated = get_internal_heat(self.spec)
        self.assertTrue(expected.equals(calculated), "EXPECTED FAILURE while Spreadsheet months start with Monday") # expected.compare(calculated))

if __name__ == '__main__':
    unittest.main()

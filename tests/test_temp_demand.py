import unittest
from pandas import read_csv, Series

from src.openbes.simulations.temp_demand import (
    get_internal_heat_from_occupants,
    get_internal_heat_from_appliances,
    get_internal_heat_from_lighting,
    get_internal_heat,
    get_air_free_temp_0m,
)
from src.openbes.simulations.base import HOURS_DF
from tests.test_holywell_house import DECIMAL_PLACES
from tests.utils import HOLYWELL_HOUSE_SPEC


class TemperatureDemand(unittest.TestCase):
    def setUp(self):
        self.spec = HOLYWELL_HOUSE_SPEC

    def test_internal_heat_occupants(self):
        expected = read_csv('fixtures/hh_internal_heat_occupants.csv')
        expected.index = HOURS_DF.index
        calculated = get_internal_heat_from_occupants(self.spec)
        self.assertTrue(expected.equals(calculated), expected.compare(calculated))

    def test_internal_heat_appliances(self):
        expected = read_csv('fixtures/hh_internal_heat_appliances.csv')
        expected.index = HOURS_DF.index
        calculated = get_internal_heat_from_appliances(self.spec)
        self.assertTrue(expected.equals(calculated), expected.compare(calculated))

    def test_internal_heat_lighting(self):
        expected = read_csv('fixtures/hh_internal_heat_lighting.csv')
        expected.index = HOURS_DF.index
        calculated = get_internal_heat_from_lighting(self.spec)
        self.assertTrue(expected.equals(calculated),  expected.compare(calculated))

    def test_internal_heat(self):
        expected = read_csv('fixtures/hh_internal_heat.csv')
        expected.index = HOURS_DF.index
        calculated = get_internal_heat(self.spec)
        self.assertTrue(expected.equals(calculated), expected.compare(calculated))

    def test_air_free_temp_0m(self):
        df = get_air_free_temp_0m(self.spec)
        self.assertIn('air_free_temp_0m', df.columns)
        self.assertEqual(len(df), len(HOURS_DF))
        expected = Series([
            17.163339, 16.910388, 16.666814, 16.430517, 16.229176,
            16.019031, 15.815558, 15.622937, 15.406070, 15.235680
        ])
        computed = df.iloc[range(10)]['air_free_temp_0m'].round(DECIMAL_PLACES)
        expected.index = computed.index
        expected = expected.astype(computed.dtype).round(DECIMAL_PLACES)
        self.assertTrue(expected.equals(computed), expected.compare(computed))

if __name__ == '__main__':
    unittest.main()

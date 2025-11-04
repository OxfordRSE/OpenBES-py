import unittest
from pandas import Series

from src.openbes.simulations.climate import (
    get_hourly_set_point_temperature,
    get_epw_data,
    get_heating_and_cooling_degrees_days,
    get_relative_humidity,
    get_wet_bulb_temperature,
    get_internal_surface_temp,
)
from src.openbes.simulations.occupancy import HOURS_DF
from src.openbes.types import OpenBESParameters
from tests.test_holywell_house import DECIMAL_PLACES
from tests.utils import HOLYWELL_HOUSE_SPEC


class Climate(unittest.TestCase):
    def setUp(self):
        self.spec = HOLYWELL_HOUSE_SPEC
        self.params = OpenBESParameters(temperature_tolerance=0.0)

    def test_hourly_set_point(self):
        expected = HOURS_DF.copy()
        expected['min_temp_set_point'] = expected['is_daytime'].apply(lambda x: 22.0 if x else 18.0)
        expected['max_temp_set_point'] = expected['is_daytime'].apply(lambda x: 21.0 if x else 29.0)
        calculated = get_hourly_set_point_temperature(self.spec, self.params)
        self.assertTrue(expected.equals(calculated), expected.compare(calculated))

    def test_hourly_dry_bulb_temperature(self):
        df = get_epw_data(self.spec)
        self.assertEqual(len(df), len(HOURS_DF))

    def test_heating_degree_days(self):
        expected = HOURS_DF.copy()
        expected = expected.drop(columns=['is_daytime'])
        expected = expected.groupby(['month', 'day']).mean().reset_index(['month'])
        expected['heating_degree_day'] = [8.9, 12.85, 9.1, 11, 9.75, 12.8, 9.2, 10.35, 8.15, 8.9, 10.35, 12.35, 18.05, 18.6, 15.95, 16, 18.55, 10.75, 9.3, 10.7, 8.8, 10.2, 13.6, 14.65, 9.05, 13.45, 13.55, 16.15, 17.05, 18.6, 17.55, 15.35, 9.9, 10.5, 12.65, 12.8, 16.75, 16.4, 19.1, 19.6, 18.9, 21.5, 19.05, 19.3, 15.3, 9.95, 9.15, 9.95, 11.6, 11.1, 5.75, 7.5, 12, 9.45, 4.85, 11.9, 14.25, 14.25, 12.75, 12.6, 8.2, 8.5, 14.9, 15.2, 17.4, 8.9, 10.45, 11.4, 11.35, 12.1, 8.4, 9.9, 10.85, 9.45, 6.9, 10.45, 13.05, 15.65, 15.3, 13.7, 11.75, 16.4, 17.1, 15.15, 13.75, 10.7, 13.45, 10, 10.95, 9.9, 10.8, 13.9, 15.2, 13.55, 9.35, 9.7, 10.55, 9.2, 10.2, 11.4, 13.95, 14.25, 13.7, 14.65, 10.4, 8.8, 7.0, 4.05, 3.9, 4.65, 5.4, 3.85, 3.85, 5.95, 7.4, 8.55, 8.55, 8.5, 8.8, 8.45, 3.9, 6.95, 9.65, 8.75, 3.9, 0.45, 0.3, 4.35, 4.35, 4.6, 6.1, 7.1, 8.7, 9.95, 8.7, 4.0, 4.5, 5.9, 8.3, 5.65, 6.55, 5.25, 5.85, 6.55, 7.35, 5.7, 5.6, 5.8, 2.5, 5.65, 7.45, 0.8, 3.2, 5.15, 8.0, 6.0, 7.1, 6.7, 6.45, 5.5, 4.5, 4.75, 7.25, 0.05, 2.45, 2.75, 3.65, 2.7, 5.8, 4.4, 4.9, 4.95, 4.45, 0.0, 2.75, 0.0, 0.85, 1.45, 0.0, 0.0, 0.0, 2.6, 0.0, 0.0, 0.0, 1.4, 2.0, 1.15, 0.9, 0.2, 2.8, 3.35, 1.0, 1.9, 0.3, 2.7, 1.05, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 2.4, 1.55, 2.35, 1.45, 2.45, 0.0, 1.15, 2.45, 1.8, 2.45, 2.65, 4.25, 0.0, 0.55, 0.4, 1.25, 0.0, 0.65, 0.0, 0.35, 0.0, 0.0, 0.0, 0.0, 0.2, 1.85, 2.2, 3.1, 2.7, 0.5, 3.25, 2.35, 1.6, 3.45, 4.5, 1.3, 3.2, 4.4, 4.3, 5.05, 2.6, 1.6, 0.0, 3.1, 6.85, 4.7, 3.5, 5.45, 3.0, 3.1, 3.15, 6.5, 5.25, 1.35, 3.95, 5.4, 2.55, 3.75, 5.4, 7.05, 6.5, 6.5, 5.4, 4.8, 4.45, 4.8, 6.65, 8.5, 7.75, 3.0, 2.2, 7.25, 9.35, 8.25, 7.9, 6.85, 9.6, 10.35, 12.5, 8.2, 7.35, 7.4, 6.75, 6.95, 8.2, 6.45, 6.75, 7.4, 9.2, 12.4, 7.35, 3.7, 5.4, 5.6, 4.45, 5.65, 13.15, 14.4, 8.65, 7.4, 6.95, 4.9, 7.8, 8.9, 8.0, 7.35, 7.85, 6.6, 7.9, 8.9, 6.25, 7.9, 9.35, 11.6, 11.75, 13.9, 13.65, 16.9, 11.9, 10.55, 13.55, 14.85, 12.2, 7.15, 6.85, 13.45, 19.15, 17.2, 19, 12.15, 16.05, 18.4, 19.25, 13.65, 15.5, 12.25, 17.45, 20.4, 21.2, 20.2, 12.65, 9.85, 11.55, 12.1, 12.8, 12.95, 9.45, 11.85, 8.15, 7.3, 8.35, 11.4, 11.75, 11.85, 9.95, 9.5, 10.55]
        expected['cooling_degree_day'] = [0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.05, 0.0, 0.45, 0.0, 0.0, 1.15, 4.7, 2.55, 0.0, 0.15, 0.05, 0.6, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.55, 3.6, 4.35, 5.7, 3.85, 3.55, 1.6, 0.1, 0.15, 1.65, 1.4, 0.0, 0.0, 0.0, 0.0, 0.0, 0.3, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.05, 0.0, 0.0, 0.0, 1.0, 0.0, 0.9, 0.0, 0.15, 3.1, 3.25, 2.65, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 2.65, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0]
        calculated = get_heating_and_cooling_degrees_days(self.spec).round(2)
        self.assertTrue(expected.equals(calculated), expected.compare(calculated))

    def test_relative_humidity(self):
        df = get_relative_humidity(self.spec)
        self.assertIn('relative_humidity', df.columns)
        self.assertEqual(len(df), len(HOURS_DF))
        expected = Series([88.0, 93.0, 93.0, 90.0, 87.0, 88.0, 87.0, 83.0, 83.0, 86.0])
        computed = df.iloc[range(10)]['relative_humidity']
        expected.index = computed.index
        expected = expected.astype(computed.dtype)
        self.assertTrue(expected.equals(computed), expected.compare(computed))

    def test_wet_bulb_temperature(self):
        df = get_wet_bulb_temperature(self.spec)
        self.assertIn('wet_bulb_temp', df.columns)
        self.assertEqual(len(df), len(HOURS_DF))
        expected = Series([
            10.9738923, 11.1071821, 11.0079916, 10.5942447, 10.6729677,
            10.4837591, 10.2818267, 9.8684777, 9.1909558, 9.5929055
        ])
        computed = df.iloc[range(10)]['wet_bulb_temp'].round(DECIMAL_PLACES)
        expected.index = computed.index
        expected = expected.astype(computed.dtype).round(DECIMAL_PLACES)
        self.assertTrue(expected.equals(computed), expected.compare(computed))

    def test_internal_surface_temperature(self):
        df = get_internal_surface_temp(self.spec)
        self.assertIn('internal_surface_temp', df.columns)
        self.assertEqual(len(df), len(HOURS_DF))
        expected = Series([
            17.189529, 16.938033, 16.693035, 16.455385, 16.248080,
            16.038826, 15.834325, 15.639793, 15.427721, 15.254648
        ])
        computed = df.iloc[range(10)]['internal_surface_temp'].round(DECIMAL_PLACES)
        expected.index = computed.index
        expected = expected.astype(computed.dtype).round(DECIMAL_PLACES)
        self.assertTrue(expected.equals(computed), expected.compare(computed))


if __name__ == '__main__':
    unittest.main()

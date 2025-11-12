import os

from pvlib.iotools import read_epw
import unittest

from src.openbes.simulations.solar_irradiation import SolarIrradiationSimulation
from src.openbes.types import COMPASS_POINTS
from tests.utils import (
    HOLYWELL_HOUSE_SPEC, 
    OpenBESTestCase, 
)


class SolarIrradiation(OpenBESTestCase):
    def setUp(self):
        climate_dir_path = os.path.join(os.path.dirname(__file__), '../src/openbes/simulations/climate_data')
        data, metadata = read_epw(os.path.join(climate_dir_path, HOLYWELL_HOUSE_SPEC.meteorological_file))
        self.sim = SolarIrradiationSimulation(epw_data=data, epw_metadata=metadata)

    def test_lon(self):
        self.assertEqual(round(self.sim.lon, 1), -1.1)

    def test_ghi(self):
        expected_ghi_start = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 15.0, 39.0, 64.0, 83.0, 75.0, 39.0, 10.0, 2.0]
        self.check_series_versus_values(self.sim.ghi[:16], expected_ghi_start)

    def test_solar_altitude_degrees(self):
        """
        The solar altitude implementation uses PVLib, which may differ slightly from
        the Excel calculations used in the original BES software.

        To compensate, we just check if the degrees are within tolerance.
        """
        tolerance = 1.0
        first_day = [
            -59.640770, -54.115912, -46.319728, -37.430886, -28.155482, -18.944647, -10.148630, -2.098972, 4.850895,
            10.317646, 13.919479, 15.351120, 14.476575, 11.379997, 6.333511, -0.291371, -8.107076, -16.752306,
            -25.892695, -35.188169, -44.222961, -52.372301, -58.588631, -61.356930
        ]
        calculated = self.sim.solarposition['apparent_elevation'][:24]
        for i in range(24):
            with self.subTest(hour=i + 1):
                self.assertTrue((first_day[i] - tolerance) < calculated.iat[i] < (first_day[i] + tolerance))

    def test_solar_irradiation(self):
        def col_to_point(col: str) -> COMPASS_POINTS:
            if col == 's':
                return COMPASS_POINTS.South
            if col == 'se':
                return COMPASS_POINTS.SouthEast
            if col == 'e':
                return COMPASS_POINTS.East
            if col == 'ne':
                return COMPASS_POINTS.NorthEast
            if col == 'n':
                return COMPASS_POINTS.North
            if col == 'nw':
                return COMPASS_POINTS.NorthWest
            if col == 'w':
                return COMPASS_POINTS.West
            if col == 'sw':
                return COMPASS_POINTS.SouthWest
            raise ValueError(f'Unknown column {col}')

        tolerance = 10.0  # Quite a large tolerance due to differences in solar position calculation
        csv = self.read_csv('fixtures/hh_solar_radiation.csv')
        for col in csv.columns:
            with self.subTest(col):
                expected = csv[col]
                if col == 'hor':
                    calculated = self.sim.ghi
                else:
                    calculated = self.sim.get_solar_irradiation(col_to_point(col))
                self.check_series_versus_values(calculated, expected, tolerance=tolerance)

if __name__ == '__main__':
    unittest.main()

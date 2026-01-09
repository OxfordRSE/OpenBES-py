import os

from pandas import Series
from pvlib.iotools import read_epw
import unittest

from src.openbes.simulations.solar_irradiation import SolarIrradiationSimulation
from src.openbes.types import COMPASS_POINTS
from tests.unit.utils import (
    OpenBESTestCase,
)
from src.openbes.examples import HOLYWELL_HOUSE_SPEC


class SolarIrradiation(OpenBESTestCase):
    def setUp(self):
        climate_dir_path = os.path.join(os.path.dirname(__file__), '../../src/openbes/simulations/climate_data')
        data, metadata = read_epw(os.path.join(climate_dir_path, HOLYWELL_HOUSE_SPEC.meteorological_file))
        self.sim = SolarIrradiationSimulation(epw_data=data, epw_metadata=metadata)

    def test_lon(self):
        self.assertEqual(round(self.sim.lon, 1), -1.1)

    def test_ghi(self):
        expected_ghi_start = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 15.0, 39.0, 64.0, 83.0, 75.0, 39.0, 10.0, 2.0]
        self.check_series_versus_values(self.sim.ghi[:16], expected_ghi_start)

    def test_hour_angle(self):
        expected_hour_angles = [
            -3.041623, -2.779906, -2.518188, -2.256471, -1.994753, -1.733035, -1.471318, -1.209600, -0.947883,
            -0.686165, -0.424447, -0.162729, 0.098988, 0.360706, 0.622424, 0.884142, 1.145860, 1.407578, 1.669296,
            1.931014, 2.192732, 2.454450, 2.716168, 2.977886
        ]
        calculated = Series(self.sim._hour_angle)
        self.check_series_versus_values(calculated, expected_hour_angles)

    def test_declination(self):
        expected = [
            -0.403065,-0.403012,-0.402960,-0.402907,-0.402854,-0.402801,-0.402747,-0.402694,-0.402640,
            -0.402585,-0.402531,-0.402476,-0.402422,-0.402366,-0.402311,-0.402256,-0.402200,-0.402144,-0.402087,
            -0.402031,-0.401974,-0.401917,-0.401860,-0.401803
        ]
        calculated = Series(self.sim._solar_declination)
        self.check_series_versus_values(calculated, expected)

    def test_solar_altitude_degrees(self):
        first_day = [
            -61.133654, -57.311922, -50.454100, -41.991545, -32.839732, -23.550200, -14.508486, -6.047391, 1.494438,
            7.748209, 12.325474, 14.871928, 15.156871, 13.152798, 9.046038, 3.169558, -4.089719, -12.355446,
            -21.282270, -30.539365, -39.761088, -48.450145, -55.800968, -60.500068
        ]
        calculated = self.sim.solar_altitude
        self.check_series_versus_values(calculated, first_day)

    def test_solar_azimuth_degrees(self):
        first_day = [
            10.962373, 37.064313, 57.509802, 73.332085, 86.366204, 97.956422, 108.986757, 120.064594, 131.626933,
            143.964098, 157.179780, 171.127695, 185.405813, 199.481190, 212.902742, 225.457582, 237.193399,
            248.360499, 259.360916, 270.754367, 283.342686, 298.338720, 317.486061, 342.265330
        ]
        calculated = self.sim.solar_azimuth
        self.check_series_versus_values(calculated, first_day)

    def test_solar_irradiation(self):
        def col_to_point(column: str) -> COMPASS_POINTS:
            if column == 's':
                return COMPASS_POINTS.South
            if column == 'se':
                return COMPASS_POINTS.SouthEast
            if column == 'e':
                return COMPASS_POINTS.East
            if column == 'ne':
                return COMPASS_POINTS.NorthEast
            if column == 'n':
                return COMPASS_POINTS.North
            if column == 'nw':
                return COMPASS_POINTS.NorthWest
            if column == 'w':
                return COMPASS_POINTS.West
            if column == 'sw':
                return COMPASS_POINTS.SouthWest
            raise ValueError(f'Unknown column {column}')

        csv = self.read_csv('fixtures/hh_solar_radiation.csv')
        for col in csv.columns:
            with self.subTest(col):
                expected = csv[col]
                if col == 'hor':
                    calculated = self.sim.ghi
                else:
                    calculated = self.sim.get_solar_irradiation(col_to_point(col))
                self.check_series_versus_values(calculated, expected)

if __name__ == '__main__':
    unittest.main()

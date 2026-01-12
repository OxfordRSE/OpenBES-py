import os

from pandas import Series, IndexSlice
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

    def test_aoi(self):
        expected = {
            COMPASS_POINTS.South: [-0.473959, -0.430950, -0.342005, -0.213180, -0.053251, 0.126891],
            COMPASS_POINTS.SouthEast: [-0.270223, -0.074562, 0.137913, 0.352729, 0.555256, 0.731698],
            COMPASS_POINTS.East: [0.091805, 0.325503, 0.537043, 0.712015, 0.838502, 0.907886],
            COMPASS_POINTS.NorthEast: [0.400055, 0.534893, 0.621580, 0.654212, 0.630564, 0.552247],
            COMPASS_POINTS.North: [0.473959, 0.430950, 0.342005, 0.213180, 0.053251, -0.126891],
            COMPASS_POINTS.NorthWest: [0.270223, 0.074562, -0.137913, -0.352729, -0.555256, -0.731698],
            COMPASS_POINTS.West: [-0.091805, -0.325503, -0.537043, -0.712015, -0.838502, -0.907886],
            COMPASS_POINTS.SouthWest: [-0.400055, -0.534893, -0.621580, -0.654212, -0.630564, -0.552247]
        }
        for point, expected_values in expected.items():
            with self.subTest(point):
                calculated_aoi = self.sim.get_aoi(point)
                self.check_series_versus_values(calculated_aoi[:6], expected_values)

    def test_relative_air_mass(self):
        first_day = [
            0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 22.479324, 7.057500,
            4.592010, 3.844061, 3.775454, 4.318635, 6.128844, 14.585011, 0.000000, 0.000000, 0.000000, 0.000000,
            0.000000, 0.000000, 0.000000, 0.000000
        ]
        calculated = self.sim.relative_air_mass
        self.check_series_versus_values(calculated, first_day)

    def test_brightness_delta(self):
        first_day = [
            0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.238785, 0.194917,
            0.204869, 0.220500, 0.197849, 0.119274, 0.043402, 0.020657, 0.000000, 0.000000, 0.000000, 0.000000,
            0.000000, 0.000000, 0.000000, 0.000000
        ]
        calculated = self.sim.brightness_delta
        self.check_series_versus_values(calculated, first_day)

    def test_clearness(self):
        first_day = [
            99.000000, 99.000000, 99.000000, 99.000000, 99.000000, 99.000000, 99.000000, 99.000000,
            1.000000, 1.000000, 1.017668, 1.025821, 1.016280, 1.007302, 1.000000, 1.000000,
            99.000000, 99.000000, 99.000000, 99.000000, 99.000000, 99.000000, 99.000000, 99.000000
        ]
        calculated = self.sim.clearness
        self.check_series_versus_values(calculated, first_day)

    def test_perez(self):
        coefficients = {
            'perez_f11': [1.060159, -0.008312],
            'perez_f12': [-1.599914, 0.587729],
            'perez_f13': [-0.358922, -0.062064],
            'perez_f21': [0.264212, -0.059601],
            'perez_f22': [-1.127234, 0.072125],
            'perez_f23': [0.131069, -0.022022],
            'perez_F1': [0.4584824770, 0.0361587908],
            'perez_F2': [0.483930, -0.076396],
        }
        test_idx = IndexSlice[(1, 1, slice(8, 9))]
        for coef, expected_values in coefficients.items():
            with self.subTest(coef):
                values = getattr(self.sim, coef)
                calculated = values.loc[test_idx].values
                self.check_series_versus_values(Series(calculated), expected_values)

        with self.subTest('perez_b'):
            first_day = [
                0.087156, 0.087156, 0.087156, 0.087156, 0.087156, 0.087156, 0.087156, 0.087156, 0.087156, 0.134820,
                0.213465, 0.256659, 0.261463, 0.227549, 0.157228, 0.087156, 0.087156, 0.087156, 0.087156, 0.087156,
                0.087156, 0.087156, 0.087156, 0.087156
            ]
            calculated = self.sim.perez_b
            self.check_series_versus_values(calculated, first_day)

    def test_beam_component(self):
        expected = {
            COMPASS_POINTS.South: [0.000000, 3.601925],
            COMPASS_POINTS.SouthEast: [0.000000, 3.618641],
            COMPASS_POINTS.East: [0.000000, 1.515606],
            COMPASS_POINTS.NorthEast: [0.0, 0.0],
            COMPASS_POINTS.North: [0.0, 0.0],
            COMPASS_POINTS.NorthWest: [0.0, 0.0],
            COMPASS_POINTS.West: [0.0, 0.0],
            COMPASS_POINTS.SouthWest: [0.000000, 1.475250]
        }
        test_idx = IndexSlice[(1, 1, slice(10, 11))]
        for point, expected_values in expected.items():
            with self.subTest(point):
                calculated_beam = self.sim.get_beam_component(point)
                self.check_series_versus_values(calculated_beam.loc[test_idx], expected_values)

    def test_diffuse_component(self):
        expected = {
            COMPASS_POINTS.South: [0.000000, 10.215353],
            COMPASS_POINTS.SouthEast: [0.000000, 12.293111],
            COMPASS_POINTS.East: [0.000000, 10.732993],
            COMPASS_POINTS.NorthEast: [0.000000, 6.448897],
            COMPASS_POINTS.North: [0.000000, 6.082871],
            COMPASS_POINTS.NorthWest: [0.000000, 6.082871],
            COMPASS_POINTS.West: [0.000000, 6.082871],
            COMPASS_POINTS.SouthWest: [0.000000, 6.082871]
        }
        test_idx = IndexSlice[(1, 1, slice(8, 9))]
        for point, expected_values in expected.items():
            with self.subTest(point):
                calculated = self.sim.get_diffuse_component(point)
                self.check_series_versus_values(calculated.loc[test_idx], expected_values)

    def test_ground_reflected_component(self):
        first_day = [
            0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 1.500000, 3.900000,
            6.400000, 8.300000, 7.500000, 3.900000, 1.000000, 0.200000, 0.000000, 0.000000, 0.000000, 0.000000,
            0.000000, 0.000000, 0.000000, 0.000000
        ]
        calculated = self.sim.ground_reflected_component
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

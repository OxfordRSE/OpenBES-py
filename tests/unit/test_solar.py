import os

from pandas import Series, IndexSlice
from pvlib.iotools import read_epw
import unittest

from openbes.simulations.solar_irradiation import SolarIrradiationSimulation
from openbes.types import COMPASS_POINTS
from tests.unit.utils import (
    OpenBESTestCase,
)
from openbes.examples import HOLYWELL_HOUSE_SPEC


class SolarIrradiation(OpenBESTestCase):
    def setUp(self):
        epw_dir_path = os.path.join(
            os.path.dirname(__file__), "../../src/openbes/simulations/epw_data"
        )
        data, metadata = read_epw(
            os.path.join(epw_dir_path, HOLYWELL_HOUSE_SPEC.meteorological_file_path.replace("openbes://", ""))
        )
        self.sim = SolarIrradiationSimulation(epw_data=data, epw_metadata=metadata, elevation=metadata["altitude"])
        self.decimal_places_or_tolerance = 1e-10

    def test_lon(self):
        self.assertEqual(round(self.sim.lon, 1), -1.1)

    def test_ghi(self):
        expected_ghi_start = [
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            15.0,
            39.0,
            64.0,
            83.0,
            75.0,
            39.0,
            10.0,
            2.0,
        ]
        self.check_series_versus_values(self.sim.ghi[:16], expected_ghi_start)

    def test_hour_angle(self):
        expected_hour_angles = [
            -3.0416230601654700,
            -2.7799055895755100,
            -2.5181880912654000,
            -2.2564705651021200,
            -1.9947530109526900,
            -1.7330354286842100,
            -1.4713178181638500,
            -1.2096001792588100,
            -0.9478825118363640,
            -0.6861648157638580,
            -0.4244470909086820,
            -0.1627293371382940,
            0.0989884456797888,
            0.3607062576779880,
            0.6224240989886620,
            0.8841419697441100,
            1.1458598700765700,
            1.4075778001182100,
            1.6692957600011400,
            1.9310137498574200,
            2.1927317698190200,
            2.4544498200178700,
            2.7161679005858300,
            2.9778860116546900,
        ]
        calculated = Series(self.sim._hour_angle)
        self.check_series_versus_values(calculated, expected_hour_angles)

    def test_declination(self):
        expected = [
            -0.4030647383382700,
            -0.4030124162108720,
            -0.4029598615059060,
            -0.4029070742647930,
            -0.4028540545291450,
            -0.4028008023407700,
            -0.4027473177416670,
            -0.4026936007740290,
            -0.4026396514802400,
            -0.4025854699028790,
            -0.4025310560847150,
            -0.4024764100687130,
            -0.4024215318980260,
            -0.4023664216160030,
            -0.4023110792661830,
            -0.4022555048922990,
            -0.4021996985382740,
            -0.4021436602482260,
            -0.4020873900664600,
            -0.4020308880374780,
            -0.4019741542059700,
            -0.4019171886168200,
            -0.4018599913151030,
            -0.4018025623460840,
        ]
        calculated = Series(self.sim._solar_declination)
        self.check_series_versus_values(calculated, expected)

    def test_solar_altitude_degrees(self):
        first_day = [
            -61.1336544057936000,
            -57.3119218166699000,
            -50.4540996660481000,
            -41.9915446527844000,
            -32.8397319170844000,
            -23.5501997872757000,
            -14.5084863570592000,
            -6.0473905856434400,
            1.4944376045526900,
            7.7482089855086700,
            12.3254737984156000,
            14.8719280998734000,
            15.1568710518878000,
            13.1527976526540000,
            9.0460383844863800,
            3.1695579910998100,
            -4.0897192137424800,
            -12.3554455269173000,
            -21.2822697450052000,
            -30.5393645973695000,
            -39.7610880389974000,
            -48.4501447254583000,
            -55.8009682587439000,
            -60.5000679791989000,
        ]
        calculated = self.sim.solar_altitude
        self.check_series_versus_values(calculated, first_day)

    def test_solar_azimuth_degrees(self):
        first_day = [
            10.9623732458212000,
            37.0643130761559000,
            57.5098021022306000,
            73.3320846170427000,
            86.3662040635344000,
            97.9564218669826000,
            108.9867569478370000,
            120.0645944435600000,
            131.6269330718900000,
            143.9640979051280000,
            157.1797801103750000,
            171.1276951207430000,
            185.4058128360640000,
            199.4811896513540000,
            212.9027420746220000,
            225.4575818431360000,
            237.1933985685550000,
            248.3604987339740000,
            259.3609156959560000,
            270.7543665090040000,
            283.3426859666770000,
            298.3387202139570000,
            317.4860611504320000,
            342.2653302120360000,
        ]
        calculated = self.sim.solar_azimuth
        self.check_series_versus_values(calculated, first_day)

    def test_aoi(self):
        expected = {
            COMPASS_POINTS.South: [
                -0.4739586519150830,
                -0.4309501578964200,
                -0.3420047331204710,
                -0.2131801745365750,
                -0.0532506135329706,
                0.1268909384627380,
            ],
            COMPASS_POINTS.SouthEast: [
                -0.2702232574225410,
                -0.0745621929058256,
                0.1379126153841640,
                0.3527294120723070,
                0.5552562718743500,
                0.7316976269842960,
            ],
            COMPASS_POINTS.East: [
                0.0918052563994891,
                0.3255032934487220,
                0.5370426242191000,
                0.7120148929371200,
                0.8385015638103990,
                0.9078857691746630,
            ],
            COMPASS_POINTS.NorthEast: [
                0.4000554961198380,
                0.5348933650981180,
                0.6215803473589240,
                0.6542117061309950,
                0.6305640117373650,
                0.5522467408680420,
            ],
            COMPASS_POINTS.North: [
                0.4739586519150830,
                0.4309501578964200,
                0.3420047331204710,
                0.2131801745365750,
                0.0532506135329707,
                -0.1268909384627390,
            ],
            COMPASS_POINTS.NorthWest: [
                0.2702232574225410,
                0.0745621929058255,
                -0.1379126153841640,
                -0.3527294120723070,
                -0.5552562718743500,
                -0.7316976269842970,
            ],
            COMPASS_POINTS.West: [
                -0.0918052563994893,
                -0.3255032934487220,
                -0.5370426242191000,
                -0.7120148929371200,
                -0.8385015638103990,
                -0.9078857691746630,
            ],
            COMPASS_POINTS.SouthWest: [
                -0.4000554961198380,
                -0.5348933650981180,
                -0.6215803473589240,
                -0.6542117061309950,
                -0.6305640117373650,
                -0.552246740868041,
            ],
        }
        for point, expected_values in expected.items():
            with self.subTest(point):
                calculated_aoi = self.sim.get_aoi(point)
                self.check_series_versus_values(calculated_aoi[:6], expected_values)

    def test_relative_air_mass(self):
        first_day = [
            0.0000000000000000,
            0.0000000000000000,
            0.0000000000000000,
            0.0000000000000000,
            0.0000000000000000,
            0.0000000000000000,
            0.0000000000000000,
            0.0000000000000000,
            22.4793238230682000,
            7.0575004378930500,
            4.5920100259448300,
            3.8440611001525600,
            3.7754537835777200,
            4.3186346113624700,
            6.1288442834929200,
            14.5850114810956000,
            0.0000000000000000,
            0.0000000000000000,
            0.0000000000000000,
            0.0000000000000000,
            0.0000000000000000,
            0.0000000000000000,
            0.0000000000000000,
            0.0000000000000000,
        ]
        calculated = self.sim.relative_air_mass
        self.check_series_versus_values(calculated, first_day)

    def test_brightness_delta(self):
        first_day = [
            0.0000000000000000,
            0.0000000000000000,
            0.0000000000000000,
            0.0000000000000000,
            0.0000000000000000,
            0.0000000000000000,
            0.0000000000000000,
            0.0000000000000000,
            0.2387853740331990,
            0.1949165609771680,
            0.2048691646157820,
            0.2204999627252140,
            0.1978491084236050,
            0.1192735889953480,
            0.0434022062865098,
            0.0206571303728036,
            0.0000000000000000,
            0.0000000000000000,
            0.0000000000000000,
            0.0000000000000000,
            0.0000000000000000,
            0.0000000000000000,
            0.0000000000000000,
            0.0000000000000000,
        ]
        calculated = self.sim.brightness_delta
        self.check_series_versus_values(calculated, first_day)

    def test_clearness(self):
        first_day = [
            99.0000000000000000,
            99.0000000000000000,
            99.0000000000000000,
            99.0000000000000000,
            99.0000000000000000,
            99.0000000000000000,
            99.0000000000000000,
            99.0000000000000000,
            1.0000000000000000,
            1.0000000000000000,
            1.0176676340613100,
            1.0258210445458900,
            1.0162800146087000,
            1.0073016081289600,
            1.0000000000000000,
            1.0000000000000000,
            99.0000000000000000,
            99.0000000000000000,
            99.0000000000000000,
            99.0000000000000000,
            99.0000000000000000,
            99.0000000000000000,
            99.0000000000000000,
            99.0000000000000000,
        ]
        calculated = self.sim.clearness
        self.check_series_versus_values(calculated, first_day)

    def test_perez(self):
        coefficients = {
            "perez_f11": [1.0601591, -0.0083117],
            "perez_f12": [-1.5999137, 0.5877285],
            "perez_f13": [-0.3589221, -0.0620636],
            "perez_f21": [0.26421240, -0.05960120],
            "perez_f22": [-1.127234, 0.07212490],
            "perez_f23": [0.13106940, -0.02202160],
            "perez_F1": [0.4584824770185800, 0.0361587907777212],
            "perez_F2": [0.4839296978989060, -0.0763958909302041],
        }
        test_idx = IndexSlice[(1, 1, slice(8, 9))]
        for coef, expected_values in coefficients.items():
            with self.subTest(coef):
                values = getattr(self.sim, coef)
                calculated = values.loc[test_idx].values
                self.check_series_versus_values(Series(calculated), expected_values)

        with self.subTest("perez_b"):
            first_day = [
                0.0871557427476581,
                0.0871557427476581,
                0.0871557427476581,
                0.0871557427476581,
                0.0871557427476581,
                0.0871557427476581,
                0.0871557427476581,
                0.0871557427476581,
                0.0871557427476581,
                0.1348199566318450,
                0.2134647612854770,
                0.2566592891689210,
                0.2614626958401520,
                0.2275487229948380,
                0.1572280431640290,
                0.0871557427476581,
                0.0871557427476581,
                0.0871557427476581,
                0.0871557427476581,
                0.0871557427476581,
                0.0871557427476581,
                0.0871557427476581,
                0.0871557427476581,
                0.0871557427476581,
            ]
            calculated = self.sim.perez_b
            self.check_series_versus_values(calculated, first_day)

    def test_beam_component(self):
        expected = {
            COMPASS_POINTS.South: [0.000000, 3.6019250032448600],
            COMPASS_POINTS.SouthEast: [0.000000, 3.6186407481434800],
            COMPASS_POINTS.East: [0.000000, 1.5156058201355700],
            COMPASS_POINTS.NorthEast: [0.0, 0.0],
            COMPASS_POINTS.North: [0.0, 0.0],
            COMPASS_POINTS.NorthWest: [0.0, 0.0],
            COMPASS_POINTS.West: [0.0, 0.0],
            COMPASS_POINTS.SouthWest: [0.000000, 1.4752504420961600],
        }
        test_idx = IndexSlice[(1, 1, slice(10, 11))]
        for point, expected_values in expected.items():
            with self.subTest(point):
                calculated_beam = self.sim.get_beam_component(point)
                self.check_series_versus_values(
                    calculated_beam.loc[test_idx], expected_values
                )

    def test_diffuse_component(self):
        expected = {
            COMPASS_POINTS.South: [0.000000, 10.2153534525510000],
            COMPASS_POINTS.SouthEast: [0.000000, 12.2931106124637000],
            COMPASS_POINTS.East: [0.000000, 10.7329934603002000],
            COMPASS_POINTS.NorthEast: [0.000000, 6.4488974649069200],
            COMPASS_POINTS.North: [0.000000, 6.0828707052140300],
            COMPASS_POINTS.NorthWest: [0.000000, 6.0828707052140300],
            COMPASS_POINTS.West: [0.000000, 6.0828707052140300],
            COMPASS_POINTS.SouthWest: [0.000000, 6.0828707052140300],
        }
        test_idx = IndexSlice[(1, 1, slice(8, 9))]
        for point, expected_values in expected.items():
            with self.subTest(point):
                calculated = self.sim.get_diffuse_component(point)
                self.check_series_versus_values(
                    calculated.loc[test_idx], expected_values
                )

    def test_ground_reflected_component(self):
        first_day = [
            0.0000000000000000,
            0.0000000000000000,
            0.0000000000000000,
            0.0000000000000000,
            0.0000000000000000,
            0.0000000000000000,
            0.0000000000000000,
            0.0000000000000000,
            1.5000000000000000,
            3.9000000000000000,
            6.4000000000000000,
            8.3000000000000000,
            7.5000000000000000,
            3.9000000000000000,
            1.0000000000000000,
            0.2000000000000000,
            0.0000000000000000,
            0.0000000000000000,
            0.0000000000000000,
            0.0000000000000000,
            0.0000000000000000,
            0.0000000000000000,
            0.0000000000000000,
            0.0000000000000000,
        ]
        calculated = self.sim.ground_reflected_component
        self.check_series_versus_values(calculated, first_day)

    def test_solar_irradiation(self):
        def col_to_point(column: str) -> COMPASS_POINTS:
            if column == "s":
                return COMPASS_POINTS.South
            if column == "se":
                return COMPASS_POINTS.SouthEast
            if column == "e":
                return COMPASS_POINTS.East
            if column == "ne":
                return COMPASS_POINTS.NorthEast
            if column == "n":
                return COMPASS_POINTS.North
            if column == "nw":
                return COMPASS_POINTS.NorthWest
            if column == "w":
                return COMPASS_POINTS.West
            if column == "sw":
                return COMPASS_POINTS.SouthWest
            raise ValueError(f"Unknown column {column}")

        csv = self.read_csv("fixtures/hh_solar_radiation.csv")
        for col in csv.columns:
            with self.subTest(col):
                expected = csv[col]
                if col == "hor":
                    calculated = self.sim.ghi
                else:
                    calculated = self.sim.get_solar_irradiation(col_to_point(col))
                self.check_series_versus_values(calculated, expected)


if __name__ == "__main__":
    unittest.main()

import unittest
from pandas import DataFrame, Series

from openbes.simulations.base import HOURS_DF
from openbes.simulations.lighting import LightingSimulation
from openbes.types import (
    MONTHS,
    OpenBESSpecification,
    LIGHTING_TECHNOLOGIES,
    LIGHTING_BALLASTS,
    OpenBESParameters,
    ENERGY_SOURCES,
)
from tests.unit.utils import (
    OpenBESTestCase,
)


class LightingWattPerLuminaire(OpenBESTestCase):
    def test_valid_inputs(self):
        test_cases = [
            {
                "description": "LED lighting with 2 lamps of 50W each",
                "input": OpenBESSpecification(
                    lighting_system_tech_z1=LIGHTING_TECHNOLOGIES.LED,
                    lighting_system_lamp_number_z1=2,
                    lighting_system_lamp_power_z1=50,
                    building_length=1.0,
                    building_width=1.0,
                    meteorological_file_path="None.epw"
                ),
                "zone": 1,
                "expected": 100.0,
            },
            {
                "description": "HAL lighting with 4 lamps of 75W each",
                "input": OpenBESSpecification(
                    lighting_system_tech_z1=LIGHTING_TECHNOLOGIES.HAL,
                    lighting_system_lamp_number_z1=4,
                    lighting_system_lamp_power_z1=75,
                    building_length=1.0,
                    building_width=1.0,
                    meteorological_file_path="None.epw"
                ),
                "zone": 1,
                "expected": 300.0,
            },
            {
                "description": "IC lighting with 1 lamp of 100W",
                "input": OpenBESSpecification(
                    lighting_system_tech_z1=LIGHTING_TECHNOLOGIES.IC,
                    lighting_system_lamp_number_z1=1,
                    lighting_system_lamp_power_z1=100,
                    building_length=1.0,
                    building_width=1.0,
                    meteorological_file_path="None.epw"
                ),
                "zone": 1,
                "expected": 100.0,
            },
            {
                "description": "FC lighting with 3 lamps of 13W each",
                "input": OpenBESSpecification(
                    lighting_system_tech_z1=LIGHTING_TECHNOLOGIES.FC,
                    lighting_system_lamp_number_z1=3,
                    lighting_system_lamp_power_z1=13,
                    building_length=1.0,
                    building_width=1.0,
                    meteorological_file_path="None.epw"
                ),
                "zone": 1,
                "expected": 39.0,
            },
            {
                "description": "FT_T5 lighting with 2 lamps of 35W each",
                "input": OpenBESSpecification(
                    lighting_system_tech_z1=LIGHTING_TECHNOLOGIES.FT_T5,
                    lighting_system_lamp_number_z1=2,
                    lighting_system_lamp_power_z1=35,
                    building_length=1.0,
                    building_width=1.0,
                    meteorological_file_path="None.epw"
                ),
                "zone": 1,
                "expected": 72.0,
            },
            {
                "description": "FT_T8 lighting with 2 lamps of 40W each",
                "input": OpenBESSpecification(
                    lighting_system_tech_z1=LIGHTING_TECHNOLOGIES.FT_T8,
                    lighting_system_lamp_number_z1=2,
                    lighting_system_lamp_power_z1=40,
                    building_length=1.0,
                    building_width=1.0,
                    meteorological_file_path="None.epw"
                ),
                "zone": 1,
                "expected": 90.0,
            },
            {
                "description": "FT_T8 lighting with BE ballast, 3 lamps of 58W each",
                "input": OpenBESSpecification(
                    lighting_system_tech_z1=LIGHTING_TECHNOLOGIES.FT_T8,
                    lighting_system_lamp_number_z1=3,
                    lighting_system_lamp_power_z1=58,
                    lighting_system_ballast_z1=LIGHTING_BALLASTS.BE,
                    building_length=1.0,
                    building_width=1.0,
                    meteorological_file_path="None.epw"
                ),
                "zone": 1,
                "expected": 186.0,
            },
            {
                "description": "IM lighting with 2 lamps of 150W each",
                "input": OpenBESSpecification(
                    lighting_system_tech_z1=LIGHTING_TECHNOLOGIES.IM,
                    lighting_system_lamp_number_z1=2,
                    lighting_system_lamp_power_z1=150,
                    building_length=1.0,
                    building_width=1.0,
                    meteorological_file_path="None.epw"
                ),
                "zone": 1,
                "expected": 324.0,
            },
            {
                "description": "IND lighting with 2 lamps of 120W each",
                "input": OpenBESSpecification(
                    lighting_system_tech_z1=LIGHTING_TECHNOLOGIES.IND,
                    lighting_system_lamp_number_z1=1,
                    lighting_system_lamp_power_z1=120,
                    building_length=1.0,
                    building_width=1.0,
                    meteorological_file_path="None.epw"
                ),
                "zone": 1,
                "expected": 126.0,
            },
            {
                "description": "VM lighting with 1 lamp of 400W",
                "input": OpenBESSpecification(
                    lighting_system_tech_z1=LIGHTING_TECHNOLOGIES.VM,
                    lighting_system_lamp_number_z1=1,
                    lighting_system_lamp_power_z1=400,
                    building_length=1.0,
                    building_width=1.0,
                    meteorological_file_path="None.epw"
                ),
                "zone": 1,
                "expected": 419.70,
            },
            {
                "description": "VS lighting with 4 lamps of 70W each",
                "input": OpenBESSpecification(
                    lighting_system_tech_z1=LIGHTING_TECHNOLOGIES.VS,
                    lighting_system_lamp_number_z1=1,
                    lighting_system_lamp_power_z1=70,
                    building_length=1.0,
                    building_width=1.0,
                    meteorological_file_path="None.epw"
                ),
                "zone": 1,
                "expected": 83.0,
            },
        ]

        for case in test_cases:
            with self.subTest(case=case["description"]):
                sim = LightingSimulation(spec=case["input"])
                output = sim.get_w_per_luminaire(case["zone"])
                self.assertEqual(case["expected"], output)

    def test_invalid_inputs(self):
        test_cases = [
            {
                "description": "Mismatched lamp number and power",
                "input": OpenBESSpecification(
                    lighting_system_tech_z1=LIGHTING_TECHNOLOGIES.FT_T8,
                    lighting_system_lamp_number_z1=3,
                    lighting_system_lamp_power_z1=999,
                    building_length=1.0,
                    building_width=1.0, meteorological_file_path="None.epw"
                ),
                "zone": 1,
                "expected": 0.0,
            },
            {
                "description": "Mismatched lamp number and tech",
                "input": OpenBESSpecification(
                    lighting_system_tech_z1=LIGHTING_TECHNOLOGIES.IND,
                    lighting_system_lamp_number_z1=3,
                    lighting_system_lamp_power_z1=50,
                    building_length=1.0,
                    building_width=1.0, meteorological_file_path="None.epw"
                ),
                "zone": 1,
                "expected": 0.0,
            },
        ]
        for case in test_cases:
            with self.subTest(case=case["description"]):
                sim = LightingSimulation(spec=case["input"])
                output = sim.get_w_per_luminaire(case["zone"])
                self.assertEqual(case["expected"], output)


class LightingPipeline(OpenBESTestCase):
    def setUp(self):
        super().setUp()
        self.sim = LightingSimulation(spec=self.spec)

    def test_kwh_per_day_per_zone(self):
        output = self.sim.get_kwh_per_day_per_zone().round(self.decimal_places)
        expected = DataFrame(
            {"kWh/day": [15.680, 12.320, 0, 0, 0, 0]},
            index=[f"Lighting system {i}" for i in range(1, 7)],
        ).round(self.decimal_places)
        self.assertTrue(expected.equals(output), expected.compare(output))

    def test_kwh_per_month_per_zone(self):
        output = self.sim.get_kwh_per_month_per_zone().round(self.decimal_places)
        expected = (
            DataFrame(
                [
                    [282.24000000, 221.76000000, 0.0, 0.0, 0.0, 0.0],
                    [313.60000000, 246.40000000, 0.0, 0.0, 0.0, 0.0],
                    [344.96000000, 271.04000000, 0.0, 0.0, 0.0, 0.0],
                    [329.28000000, 258.72000000, 0.0, 0.0, 0.0, 0.0],
                    [360.64000000, 283.36000000, 0.0, 0.0, 0.0, 0.0],
                    [329.28000000, 258.72000000, 0.0, 0.0, 0.0, 0.0],
                    [344.96000000, 271.04000000, 0.0, 0.0, 0.0, 0.0],
                    [360.64000000, 283.36000000, 0.0, 0.0, 0.0, 0.0],
                    [313.60000000, 246.40000000, 0.0, 0.0, 0.0, 0.0],
                    [360.64000000, 283.36000000, 0.0, 0.0, 0.0, 0.0],
                    [344.96000000, 271.04000000, 0.0, 0.0, 0.0, 0.0],
                    [235.20000000, 184.80000000, 0.0, 0.0, 0.0, 0.0],
                ],
                index=list(MONTHS),
                columns=[f"Lighting system {i}" for i in range(1, 7)],
            )
            .transpose()
            .round(self.decimal_places)
        )
        self.assertTrue(expected.equals(output), expected.compare(output))

    def test_annual_kwh(self):
        output = self.sim.get_kwh_per_month().round(self.decimal_places)
        expected = Series(
            [
                504.0,
                560.0,
                616.0,
                588.0,
                644.0,
                588.0,
                616.0,
                644.0,
                560.0,
                644.0,
                616.0,
                420.0,
            ],
            name="kWh/month",
            index=list(MONTHS),
        )
        self.assertTrue(expected.equals(output), expected.compare(output))

    def test_lighting_ratio(self):
        expected = self.read_single_col_csv_to_series("fixtures/hh_lighting_ratio.csv")
        expected.index = HOURS_DF.index
        expected = expected
        calculated = self.sim.lighting_ratio
        self.check_series_versus_values(calculated, expected)

    def test_parasitic_heat(self):
        with self.subTest(lighting="on"):
            expected = round(0.684931507, self.decimal_places)
            computed = round(self.sim.parasitic_heat, self.decimal_places)
            self.assertEqual(expected, computed)
        with self.subTest(lighting="off"):
            simulation = LightingSimulation(
                spec=OpenBESSpecification(
                    parameters=OpenBESParameters(lighting_on_off=False),
                    building_length=1.0,
                    building_width=1.0, meteorological_file_path="None.epw"
                )
            )
            self.assertEqual(0.0, simulation.parasitic_heat)

    def test_lighting_heat(self):
        with self.subTest(lighting="on"):
            expected = round(17.6184817, self.decimal_places)
            computed = round(self.sim.lighting_heat, self.decimal_places)
            self.assertEqual(expected, computed)
        with self.subTest(lighting="off"):
            simulation = LightingSimulation(
                spec=OpenBESSpecification(
                    parameters=OpenBESParameters(lighting_on_off=False),
                    building_length=1.0,
                    building_width=1.0, meteorological_file_path="None.epw"
                )
            )
            self.assertEqual(0.0, simulation.lighting_heat)

    def test_energy_use(self):
        self.check_series_versus_values(
            self.sim.energy_use[ENERGY_SOURCES.Electricity],
            [self.sim.get_kwh_per_month().sum().sum() / 8760] * 8760,
        )


if __name__ == "__main__":
    unittest.main()

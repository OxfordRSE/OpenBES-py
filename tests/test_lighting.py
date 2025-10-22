import unittest
from pandas import DataFrame
from src.openbes.types import MONTHS, OpenBESSpecification, LIGHTING_TECHNOLOGIES, LIGHTING_BALLASTS
from src.openbes.simulations.lighting import get_w_per_luminaire
from tests.test_holywell_house import DECIMAL_PLACES


class LightingWattPerLuminaire(unittest.TestCase):
    def test_valid_inputs(self):
        test_cases = [
            {
                "description": "LED lighting with 2 lamps of 50W each",
                "input": OpenBESSpecification(
                    lighting_system_tech_z1=LIGHTING_TECHNOLOGIES.LED,
                    lighting_system_lamp_number_z1=2,
                    lighting_system_lamp_power_z1=50,
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
                ),
                "zone": 1,
                "expected": 83.0,
            },
        ]

        for case in test_cases:
            with self.subTest(case=case["description"]):
                output = get_w_per_luminaire(case["input"], case["zone"])
                self.assertEqual(case["expected"], output)

    def test_illegal_inputs(self):
        with self.assertRaises(AttributeError):
            get_w_per_luminaire(
                OpenBESSpecification(
                    lighting_system_tech_z1=LIGHTING_TECHNOLOGIES.UNKNOWN,
                    lighting_system_lamp_number_z1=2,
                    lighting_system_lamp_power_z1=50,
                ),
                zone=1
            )

    def test_invalid_inputs(self):
        test_cases = [
            {
                "description": "Mismatched lamp number and power",
                "input": OpenBESSpecification(
                    lighting_system_tech_z1=LIGHTING_TECHNOLOGIES.FT_T8,
                    lighting_system_lamp_number_z1=3,
                    lighting_system_lamp_power_z1=999,
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
                ),
                "zone": 1,
                "expected": 0.0,
            },
        ]
        for case in test_cases:
            with self.subTest(case=case["description"]):
                output = get_w_per_luminaire(case["input"], case["zone"])
                self.assertEqual(case["expected"], output)


class LightingPipeline(unittest.TestCase):
    def setUp(self):
        self.input = OpenBESSpecification(
            lighting_system_name_z1="First Floor",
            lighting_system_tech_z1=LIGHTING_TECHNOLOGIES.FT_T8,
            lighting_system_lamp_number_z1=4,
            lighting_system_lamp_power_z1=18,
            lighting_system_ballast_z1=LIGHTING_BALLASTS.BE,
            lighting_system_luminary_number_z1=35,
            lighting_system_similar_zone_number_z1=1,
            lighting_system_operating_hours_z1=8,
            lighting_system_simultaneity_factor_z1=0.7,
            lighting_system_name_z2="Second Floor",
            lighting_system_tech_z2=LIGHTING_TECHNOLOGIES.LED,
            lighting_system_lamp_number_z2=1,
            lighting_system_lamp_power_z2=40,
            lighting_system_luminary_number_z2=55,
            lighting_system_similar_zone_number_z2=1,
            lighting_system_operating_hours_z2=8,
            lighting_system_simultaneity_factor_z2=0.7,
        )

    def test_kwh_per_day_per_zone(self):
        from src.openbes.simulations.lighting import get_kwh_per_day_per_zone
        output = get_kwh_per_day_per_zone(self.input).round(DECIMAL_PLACES)
        expected = DataFrame(
            {"kWh/day": [15.680, 12.320, 0, 0, 0, 0]},
            index=[f"Zone type {i}" for i in range(1, 7)],
        ).round(DECIMAL_PLACES)
        self.assertTrue(expected.equals(output), expected.compare(output))

    def test_kwh_per_month_per_zone(self):
        from src.openbes.simulations.lighting import get_kwh_per_month_per_zone
        output = get_kwh_per_month_per_zone(self.input).round(DECIMAL_PLACES)
        expected = DataFrame(
            [
                [282.24, 221.76, 0.0, 0.0, 0.0, 0.0],
                [313.60, 246.40, 0.0, 0.0, 0.0, 0.0],
                [360.64, 283.36, 0.0, 0.0, 0.0, 0.0],
                [344.96, 271.04, 0.0, 0.0, 0.0, 0.0],
                [360.64, 283.36, 0.0, 0.0, 0.0, 0.0],
                [344.96, 271.04, 0.0, 0.0, 0.0, 0.0],
                [329.28, 258.72, 0.0, 0.0, 0.0, 0.0],
                [344.96, 271.04, 0.0, 0.0, 0.0, 0.0],
                [344.96, 271.04, 0.0, 0.0, 0.0, 0.0],
                [360.64, 283.36, 0.0, 0.0, 0.0, 0.0],
                [344.96, 271.04, 0.0, 0.0, 0.0, 0.0],
                [266.56, 209.44, 0.0, 0.0, 0.0, 0.0],
            ],
            index=MONTHS.list(),
            columns=[f"Zone type {i}" for i in range(1, 7)],
        ).transpose().round(DECIMAL_PLACES)
        self.assertTrue(expected.equals(output), expected.compare(output))

    def test_annual_kwh(self):
        from src.openbes.simulations.lighting import get_kwh_per_month
        output = get_kwh_per_month(self.input).round(DECIMAL_PLACES)
        expected = DataFrame(
            [[
                504.000000, 560.000000, 644.000000, 616.000000, 644.000000, 616.000000,
                588.000000, 616.000000, 616.000000, 644.000000, 616.000000, 476.000000,
            ]],
            index=["kWh/month"],
            columns=MONTHS.list()
        )
        self.assertTrue(expected.equals(output), expected.compare(output))

if __name__ == '__main__':
    unittest.main()

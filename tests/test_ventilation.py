import unittest
from pandas import DataFrame

from src.openbes.simulations.ventilation import (
    get_ventilation_hours_per_day,
    get_mv_hours_per_month,
    get_ventilation_per_month
)
from src.openbes.types import OpenBESSpecification, MONTHS, ENERGY_SOURCES
from tests.test_holywell_house import DECIMAL_PLACES


class Ventilation(unittest.TestCase):
    def setUp(self):
        self.input = OpenBESSpecification(
            ventilation_system1_energy_source=ENERGY_SOURCES.Electricity,
            ventilation_system1_rated_input_power=0.3,
            ventilation_system1_on_time=10,
            ventilation_system1_off_time=14,
        )

    def test_ventilation_hours_per_day(self):
        for off_time in range(10, 24):
            spec = OpenBESSpecification(
                ventilation_system1_rated_input_power=0.3,
                ventilation_system1_on_time=10,
                ventilation_system1_off_time=off_time,
            )
            with self.subTest(off_time=off_time):
                expected_hours = off_time - 10 + 1  # off-time is inclusive
                self.assertEqual(
                    get_ventilation_hours_per_day(spec),
                    expected_hours
                )

    def test_ventilation_hours_per_day_error(self):
        input_invalid = OpenBESSpecification(
            ventilation_system1_rated_input_power=0.3,
            ventilation_system1_on_time=20,
            ventilation_system1_off_time=10,
        )
        self.assertEqual(get_ventilation_hours_per_day(input_invalid), 0)

    def test_mv_hours_per_month(self):
        expected = DataFrame(
            [[
                90, 100, 115, 110, 115, 110, 115, 115, 110, 115, 110, 85
            ]],
            index=["mv_hours"],
            columns=MONTHS.list()
        )
        calculated = get_mv_hours_per_month(self.input)
        self.assertTrue(expected.equals(calculated), expected.compare(calculated))


    def test_ventilation_per_month(self):
        expected = DataFrame(
            [[
                27.0, 30.0, 34.5, 33.0, 34.5, 33.0, 34.5, 34.5, 33.0, 34.5, 33.0, 25.5
            ]],
            index=["kWh"],
            columns=MONTHS.list()
        ).round(DECIMAL_PLACES)
        calculated = get_ventilation_per_month(self.input).round(DECIMAL_PLACES)
        self.assertTrue(expected.equals(calculated), expected.compare(calculated))

if __name__ == '__main__':
    unittest.main()

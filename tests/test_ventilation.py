import unittest
from pandas import DataFrame

from src.openbes.simulations.ventilation import (
    get_ventilation_hours_per_day,
    get_mv_hours_per_month,
    get_ventilation_per_month,
    VentilationSimulation,
)
from src.openbes.types import OpenBESSpecification, MONTHS, ENERGY_SOURCES
from tests.test_holywell_house import DECIMAL_PLACES
from tests.utils import OpenBESTestCase


class Ventilation(OpenBESTestCase):
    def setUp(self):
        super().setUp()
        self.input = OpenBESSpecification(
            ventilation_system1_energy_source=ENERGY_SOURCES.Electricity,
            ventilation_system1_rated_input_power=0.3,
            ventilation_system1_on_time=10,
            ventilation_system1_off_time=14,
        )
        self.sim = VentilationSimulation(spec=self.spec)

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
            columns=MONTHS.list_values()
        )
        calculated = get_mv_hours_per_month(self.input)
        self.assertTrue(expected.equals(calculated), expected.compare(calculated))


    def test_ventilation_per_month(self):
        expected = DataFrame(
            [[
                27.0, 30.0, 34.5, 33.0, 34.5, 33.0, 34.5, 34.5, 33.0, 34.5, 33.0, 25.5
            ]],
            index=["kWh"],
            columns=MONTHS.list_values()
        ).round(DECIMAL_PLACES)
        calculated = get_ventilation_per_month(self.input).round(DECIMAL_PLACES)
        self.assertTrue(expected.equals(calculated), expected.compare(calculated))

    def test_air_supply_rate(self):
        max_expected = round(0.068417, self.decimal_places)
        self.assertEqual(
            round(self.sim.air_supply_rate.max(), self.decimal_places),
            max_expected
        )
        self.assertEqual(
            round(self.sim.air_supply_rate.sum(), self.decimal_places - 2),
            round(85.521583, self.decimal_places - 2)
        )

if __name__ == '__main__':
    unittest.main()

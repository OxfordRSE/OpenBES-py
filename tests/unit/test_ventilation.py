import unittest

from src.openbes.simulations.ventilation import VentilationSimulation
from tests.unit.utils import OpenBESTestCase


class Ventilation(OpenBESTestCase):
    def setUp(self):
        super().setUp()
        self.sim = VentilationSimulation(spec=self.spec)

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

    def test_energy_use(self):
        self.check_series_versus_csv(
            self.sim.energy_use[self.spec.ventilation_system1_energy_source],
            'fixtures/hh_ventilation_energy_use.csv'
        )

if __name__ == '__main__':
    unittest.main()

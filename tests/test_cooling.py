import unittest

from src.openbes.simulations.cooling import CoolingSimulation
from src.openbes.types import ENERGY_SOURCES
from tests.utils import OpenBESTestCase


class Cooling(OpenBESTestCase):
    def setUp(self):
        super().setUp()
        self.sim = CoolingSimulation(spec=self.spec)
        self.system = self.sim.cooling_simulations[0]

    def test_nominal_consumption(self):
        self.assertEqual(
            round(self.system.nominal_consumption, self.decimal_places),
            round(34.285714, self.decimal_places)
        )

    def test_area(self):
        self.assertEqual(
            round(self.system.area, self.decimal_places),
            round( 866.941500, self.decimal_places)
        )

    def test_Th_int(self):
        self.assertEqual(
            round(self.system.Th_int, self.decimal_places),
            round(15.24111, self.decimal_places)
        )

    def test_Ts_int(self):
        self.assertEqual(
            round(self.system.Ts_int, self.decimal_places),
            round(21.0, self.decimal_places)
        )

    def test_energy_use(self):
        self.check_series_versus_csv(
            self.system.energy_use[ENERGY_SOURCES.Electricity],
            'fixtures/hh_cooling_energy_use.csv',
            tolerance=1.0
        )

if __name__ == '__main__':
    unittest.main()

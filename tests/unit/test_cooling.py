import unittest

from src.openbes.simulations.climate import ClimateSimulation
from src.openbes.simulations.cooling import CoolingSimulation
from src.openbes.simulations.geometry import BuildingGeometry
from src.openbes.simulations.lighting import LightingSimulation
from src.openbes.simulations.occupancy import OccupationSimulation
from src.openbes.types import ENERGY_SOURCES
from tests.unit.utils import OpenBESTestCase
from src.openbes.examples import HOLYWELL_HOUSE_SPEC


class Cooling(OpenBESTestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = HOLYWELL_HOUSE_SPEC
        cls._geometry = BuildingGeometry(cls.spec)
        cls._occupancy = OccupationSimulation(cls.spec, geometry=cls._geometry)
        cls._lighting = LightingSimulation(cls.spec, occupancy=cls._occupancy)
        cls._climate = ClimateSimulation(spec=cls.spec)

    def setUp(self):
        super().setUp()
        self.sim = CoolingSimulation(
            spec=self.spec,
            climate=self._climate,
        )
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
            'fixtures/hh_cooling_energy_use.csv'
        )

if __name__ == '__main__':
    unittest.main()

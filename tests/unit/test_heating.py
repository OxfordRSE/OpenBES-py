import unittest

from src.openbes.simulations.climate import ClimateSimulation
from src.openbes.simulations.heating import HeatingSimulation
from src.openbes.simulations.geometry import BuildingGeometry
from src.openbes.simulations.lighting import LightingSimulation
from src.openbes.simulations.occupancy import OccupationSimulation
from tests.unit.utils import OpenBESTestCase
from src.openbes.examples import HOLYWELL_HOUSE_SPEC


class Heating(OpenBESTestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = HOLYWELL_HOUSE_SPEC
        cls._geometry = BuildingGeometry(cls.spec)
        cls._occupancy = OccupationSimulation(cls.spec, geometry=cls._geometry)
        cls._lighting = LightingSimulation(cls.spec, occupancy=cls._occupancy)
        cls._climate = ClimateSimulation(spec=cls.spec)

    def setUp(self):
        super().setUp()
        self.sim = HeatingSimulation(
            spec=self.spec,
            climate=self._climate,
        )
        self.system = self.sim.heating_simulations[0]

    def test_area(self):
        self.assertEqual(
            round(self.system.area, self.decimal_places),
            round( 912.79610000, self.decimal_places)
        )

    def test_demand(self):
        self.check_series_versus_csv(
            self.system.demand,
            'fixtures/hh_heating_demand.csv'
        )

    def test_energy_use(self):
        self.check_series_versus_csv(
            self.sim.energy_use.sum(axis="columns"),
            'fixtures/hh_heating_energy_use.csv'
        )

if __name__ == '__main__':
    unittest.main()

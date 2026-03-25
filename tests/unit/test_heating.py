import unittest

from openbes.simulations.thermal import ThermalSimulation
from openbes.simulations.heating import HeatingSimulation
from openbes.simulations.geometry import BuildingGeometry
from openbes.simulations.lighting import LightingSimulation
from openbes.simulations.occupancy import OccupationSimulation
from tests.unit.utils import OpenBESTestCase
from openbes.examples import HOLYWELL_HOUSE_SPEC


class Heating(OpenBESTestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = HOLYWELL_HOUSE_SPEC
        cls._geometry = BuildingGeometry(cls.spec)
        cls._occupancy = OccupationSimulation(cls.spec, geometry=cls._geometry)
        cls._lighting = LightingSimulation(cls.spec, occupancy=cls._occupancy)
        cls._thermal = ThermalSimulation(spec=cls.spec)

    def setUp(self):
        super().setUp()
        self.sim = HeatingSimulation(
            spec=self.spec,
            thermal=self._thermal,
        )
        self.system = self.sim.heating_simulations[0]
        self.decimal_places_or_tolerance = 1e-5

    def test_area(self):
        self.assertEqual(
            round(self.system.area, self.decimal_places),
            round(912.79610000, self.decimal_places),
        )

    def test_demand(self):
        self.check_series_versus_csv(
            self.system.demand, "fixtures/hh_heating_demand.csv"
        )

    def test_energy_use(self):
        self.check_series_versus_csv(
            self.sim.energy_use.sum(axis="columns"),
            "fixtures/hh_heating_energy_use.csv",
        )


if __name__ == "__main__":
    unittest.main()

import unittest

from openbes.simulations.thermal import ThermalSimulation
from openbes.simulations.heating import HeatingSimulation
from openbes.simulations.geometry import BuildingGeometry
from openbes.simulations.lighting import LightingSimulation
from openbes.simulations.occupancy import OccupationSimulation
from tests.unit.utils import (
    OpenBESTestCase,
    duplicate_secondary_hvac_systems,
    distinct_secondary_hvac_systems,
)
from openbes.examples import HOLYWELL_HOUSE_SPEC, get_holywell_house_spec


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


class HeatingMultipleSystems(OpenBESTestCase):
    @classmethod
    def setUpClass(cls):
        cls.single_spec = get_holywell_house_spec()
        cls.single_thermal = ThermalSimulation(spec=cls.single_spec)
        cls.single_sim = HeatingSimulation(
            spec=cls.single_spec, thermal=cls.single_thermal
        )

        cls.duplicated_spec = duplicate_secondary_hvac_systems(
            get_holywell_house_spec()
        )
        cls.duplicated_thermal = ThermalSimulation(spec=cls.duplicated_spec)
        cls.duplicated_sim = HeatingSimulation(
            spec=cls.duplicated_spec, thermal=cls.duplicated_thermal
        )

        cls.distinct_spec = distinct_secondary_hvac_systems(get_holywell_house_spec())
        cls.distinct_thermal = ThermalSimulation(spec=cls.distinct_spec)
        cls.distinct_sim = HeatingSimulation(
            spec=cls.distinct_spec, thermal=cls.distinct_thermal
        )

    def test_builds_two_heating_systems(self):
        self.assertEqual(len(self.distinct_sim.heating_simulations), 2)
        self.assertEqual(len(self.distinct_sim.report.heating_systems), 2)

    def test_duplicated_heating_systems_create_matching_report_entries(self):
        first, second = self.duplicated_sim.report.heating_systems
        self.assertEqual(first.conditioned_area, second.conditioned_area)
        self.assertEqual(first.peak_capacity, second.peak_capacity)
        self.assertGreater(
            self.duplicated_sim.energy_use.sum().sum(),
            self.single_sim.energy_use.sum().sum(),
        )

    def test_distinct_heating_systems_produce_distinct_report_entries(self):
        first, second = self.distinct_sim.report.heating_systems
        self.assertNotEqual(first.conditioned_area, second.conditioned_area)
        self.assertNotEqual(first.peak_capacity, second.peak_capacity)


if __name__ == "__main__":
    unittest.main()

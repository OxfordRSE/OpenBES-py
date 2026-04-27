import unittest

from openbes.simulations.thermal import ThermalSimulation
from openbes.simulations.cooling import CoolingSimulation
from openbes.simulations.geometry import BuildingGeometry
from openbes.simulations.lighting import LightingSimulation
from openbes.simulations.occupancy import OccupationSimulation
from openbes.types import ENERGY_SOURCES
from tests.unit.utils import (
    OpenBESTestCase,
    duplicate_secondary_hvac_systems,
    distinct_secondary_hvac_systems,
)
from openbes.examples import HOLYWELL_HOUSE_SPEC, get_holywell_house_spec


class Cooling(OpenBESTestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = HOLYWELL_HOUSE_SPEC
        cls._geometry = BuildingGeometry(cls.spec)
        cls._occupancy = OccupationSimulation(cls.spec, geometry=cls._geometry)
        cls._lighting = LightingSimulation(cls.spec, occupancy=cls._occupancy)
        cls._thermal = ThermalSimulation(spec=cls.spec)

    def setUp(self):
        super().setUp()
        self.sim = CoolingSimulation(
            spec=self.spec,
            thermal=self._thermal,
        )
        self.system = self.sim.cooling_simulations[0]

    def test_nominal_consumption(self):
        self.assertEqual(
            round(self.system.nominal_consumption, self.decimal_places),
            round(34.285714, self.decimal_places),
        )

    def test_area(self):
        self.assertEqual(
            round(self.system.area, self.decimal_places),
            round(866.941500, self.decimal_places),
        )

    def test_Th_int(self):
        self.assertEqual(
            round(self.system.Th_int, self.decimal_places),
            round(15.24111, self.decimal_places),
        )

    def test_Ts_int(self):
        self.assertEqual(
            round(self.system.Ts_int, self.decimal_places),
            round(21.0, self.decimal_places),
        )

    def test_energy_use(self):
        self.check_series_versus_csv(
            self.system.energy_use[ENERGY_SOURCES.Electricity],
            "fixtures/hh_cooling_energy_use.csv",
        )


class CoolingMultipleSystems(OpenBESTestCase):
    @classmethod
    def setUpClass(cls):
        cls.single_spec = get_holywell_house_spec()
        cls.single_thermal = ThermalSimulation(spec=cls.single_spec)
        cls.single_sim = CoolingSimulation(
            spec=cls.single_spec, thermal=cls.single_thermal
        )

        cls.duplicated_spec = duplicate_secondary_hvac_systems(
            get_holywell_house_spec()
        )
        cls.duplicated_thermal = ThermalSimulation(spec=cls.duplicated_spec)
        cls.duplicated_sim = CoolingSimulation(
            spec=cls.duplicated_spec, thermal=cls.duplicated_thermal
        )

        cls.distinct_spec = distinct_secondary_hvac_systems(get_holywell_house_spec())
        cls.distinct_thermal = ThermalSimulation(spec=cls.distinct_spec)
        cls.distinct_sim = CoolingSimulation(
            spec=cls.distinct_spec, thermal=cls.distinct_thermal
        )

    def test_builds_two_cooling_systems(self):
        self.assertEqual(len(self.distinct_sim.cooling_simulations), 2)
        self.assertEqual(len(self.distinct_sim.report.cooling_systems), 2)

    def test_duplicated_cooling_systems_create_matching_report_entries(self):
        first, second = self.duplicated_sim.report.cooling_systems
        self.assertEqual(first.conditioned_area, second.conditioned_area)
        self.assertEqual(first.peak_capacity, second.peak_capacity)
        self.assertGreater(
            self.duplicated_sim.energy_use.sum().sum(),
            self.single_sim.energy_use.sum().sum(),
        )

    def test_distinct_cooling_systems_produce_distinct_report_entries(self):
        first, second = self.distinct_sim.report.cooling_systems
        self.assertNotEqual(first.conditioned_area, second.conditioned_area)
        self.assertNotEqual(first.peak_capacity, second.peak_capacity)


if __name__ == "__main__":
    unittest.main()

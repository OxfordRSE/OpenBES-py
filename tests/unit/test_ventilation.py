import unittest

from openbes.simulations.ventilation import VentilationSimulation
from openbes.examples import get_holywell_house_spec
from tests.unit.utils import (
    OpenBESTestCase,
    duplicate_secondary_hvac_systems,
    distinct_secondary_hvac_systems,
)


class Ventilation(OpenBESTestCase):
    def setUp(self):
        super().setUp()
        self.sim = VentilationSimulation(spec=self.spec)

    def test_air_supply_rate(self):
        max_expected = round(0.068417, self.decimal_places)
        self.assertEqual(
            round(self.sim.air_supply_rate.max(), self.decimal_places), max_expected
        )
        self.assertEqual(
            round(self.sim.air_supply_rate.sum(), self.decimal_places - 2),
            round(85.521583, self.decimal_places - 2),
        )

    def test_energy_use(self):
        self.check_series_versus_csv(
            self.sim.energy_use[self.spec.ventilation_system1_energy_source],
            "fixtures/hh_ventilation_energy_use.csv",
        )


class VentilationMultipleSystems(OpenBESTestCase):
    @classmethod
    def setUpClass(cls):
        cls.single_spec = get_holywell_house_spec()
        cls.single_sim = VentilationSimulation(spec=cls.single_spec)

        cls.duplicated_spec = duplicate_secondary_hvac_systems(
            get_holywell_house_spec()
        )
        cls.duplicated_sim = VentilationSimulation(spec=cls.duplicated_spec)

        cls.distinct_spec = distinct_secondary_hvac_systems(get_holywell_house_spec())
        cls.distinct_sim = VentilationSimulation(spec=cls.distinct_spec)

    def test_builds_two_ventilation_systems(self):
        self.assertEqual(len(self.distinct_sim.ventilation_simulations), 2)
        self.assertEqual(len(self.distinct_sim.report.ventilation_systems), 2)

    def test_duplicated_ventilation_systems_create_matching_report_entries(self):
        first, second = self.duplicated_sim.report.ventilation_systems
        self.assertEqual(first.energy_demand, second.energy_demand)
        self.assertEqual(first.peak_load, second.peak_load)
        self.assertGreater(
            self.duplicated_sim.energy_use.sum().sum(),
            self.single_sim.energy_use.sum().sum(),
        )

    def test_distinct_ventilation_systems_produce_distinct_report_entries(self):
        first, second = self.distinct_sim.report.ventilation_systems
        self.assertNotEqual(first.energy_demand, second.energy_demand)
        self.assertNotEqual(first.peak_load, second.peak_load)


if __name__ == "__main__":
    unittest.main()

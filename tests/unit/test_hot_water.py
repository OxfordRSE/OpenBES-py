import copy
import unittest
from pandas import Series

from openbes.simulations.hot_water import HotWaterSimulation
from openbes.types import MONTHS
from tests.unit.utils import OpenBESTestCase


class HotWaterPipeline(OpenBESTestCase):
    def setUp(self):
        super(HotWaterPipeline, self).setUp()
        self.sim = HotWaterSimulation(spec=self.spec)
        self.decimal_places = 3

    def test_nominal_consumption(self):
        self.assertAlmostEqual(
            self.sim.get_daily_hot_water_nominal(), 15.32667, self.decimal_places
        )

    def test_nominal_consumption_error(self):
        with self.subTest(missing="water_demand"):
            input = copy.deepcopy(self.spec)
            input.water_demand = None
            sim = HotWaterSimulation(input)
            self.assertEqual(sim.get_daily_hot_water_nominal(), 0.0)
        with self.subTest(missing="water_reference_temperature"):
            input = copy.deepcopy(self.spec)
            input.water_reference_temperature = None
            sim = HotWaterSimulation(input)
            self.assertEqual(sim.get_daily_hot_water_nominal(), 0.0)
        with self.subTest(missing="water_supply_temperature"):
            input = copy.deepcopy(self.spec)
            input.water_supply_temperature = None
            sim = HotWaterSimulation(input)
            self.assertEqual(sim.get_daily_hot_water_nominal(), 0.0)

    def test_consumption(self):
        self.assertAlmostEqual(
            self.sim.get_daily_hot_water(), 15.32667, self.decimal_places
        )

    def test_consumption_error(self):
        with self.subTest(missing="water_demand", inherited_error=True):
            input = copy.deepcopy(self.spec)
            input.water_demand = None
            sim = HotWaterSimulation(input)
            self.assertEqual(sim.get_daily_hot_water_nominal(), 0.0)
        with self.subTest(missing="water_reference_temperature", inherited_error=True):
            input = copy.deepcopy(self.spec)
            input.water_reference_temperature = None
            sim = HotWaterSimulation(input)
            self.assertEqual(sim.get_daily_hot_water_nominal(), 0.0)
        with self.subTest(missing="water_supply_temperature", inherited_error=True):
            input = copy.deepcopy(self.spec)
            input.water_supply_temperature = None
            sim = HotWaterSimulation(input)
            self.assertEqual(sim.get_daily_hot_water_nominal(), 0.0)
        with self.subTest(missing="water_system_efficiency_cop", inherited_error=False):
            input = copy.deepcopy(self.spec)
            input.water_system_efficiency_cop = None
            sim = HotWaterSimulation(input)
            self.assertEqual(sim.get_daily_hot_water(), 0.0)

    def test_hot_water_per_month(self):
        expected = Series(
            [
                275.88000000000,
                306.53333333333,
                337.18666666667,
                321.86000000000,
                352.51333333333,
                321.86000000000,
                337.18666666667,
                352.51333333333,
                306.53333333333,
                352.51333333333,
                337.18666666667,
                229.90000000000,
            ],
            index=list(MONTHS),
            name="kWh",
        ).round(self.decimal_places)
        output = self.sim.get_hot_water_per_month().round(self.decimal_places)
        self.assertTrue(expected.equals(output), expected.compare(output))

    def test_energy_use(self):
        expected = 3831.66666667
        calculated = self.sim.energy_use[self.spec.water_system_energy_source].sum()
        self.assertAlmostEqual(expected, calculated, self.decimal_places)


if __name__ == "__main__":
    unittest.main()

import unittest

from pandas import Series

from openbes.simulations.building_energy import BuildingEnergySimulation
from openbes.types import ENERGY_SOURCES, ENERGY_USE_CATEGORIES
from tests.unit.utils import OpenBESTestCase


class HolywellHousePipeline(OpenBESTestCase):
    def test_energy_use_by_category(self):
        expected = {
            ENERGY_USE_CATEGORIES.Heating: 53498.20504883,
            ENERGY_USE_CATEGORIES.Cooling: 1574.98895054,
            ENERGY_USE_CATEGORIES.Ventilation: 375.00000000,
            ENERGY_USE_CATEGORIES.Hot_water: 3831.66666667,
            ENERGY_USE_CATEGORIES.Lighting: 7000.00000000,
            ENERGY_USE_CATEGORIES.Building_standby: 27854.40000000,
            ENERGY_USE_CATEGORIES.Others: 1136.0 * 12,
        }
        calculated = {
            category: energy_use.sum().sum()
            for category, energy_use in BuildingEnergySimulation(
                spec=self.spec
            ).energy_use_by_category.items()
        }
        for category in ENERGY_USE_CATEGORIES:
            with self.subTest(category=category):
                self.assertAlmostEqual(
                    expected[category], calculated[category], places=self.decimal_places
                )

    def test_total_energy_use(self):
        expected = Series(
            [54_268.0556172062, 0.0, 0.0, 53_498.2050488295, 0.0, 0.0],
            index=list(ENERGY_SOURCES),
        )
        calculated = BuildingEnergySimulation(spec=self.spec).energy_use.sum(
            axis="rows"
        )
        self.check_series_versus_values(calculated, expected)


if __name__ == "__main__":
    unittest.main()

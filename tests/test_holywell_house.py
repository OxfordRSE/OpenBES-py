import unittest

from pandas import Series

from src.openbes.simulations.building_energy import BuildingEnergySimulation
from src.openbes.types import ENERGY_SOURCES, ENERGY_USE_CATEGORIES
from tests.utils import OpenBESTestCase

class HolywellHousePipeline(OpenBESTestCase):
    def test_energy_use_by_category(self):
        expected = {
            ENERGY_USE_CATEGORIES.Others: 13632.00,
            ENERGY_USE_CATEGORIES.Building_standby: 27854.40,
            ENERGY_USE_CATEGORIES.Lighting: 7000.00,
            ENERGY_USE_CATEGORIES.Hot_water: 3831.66666667,
            ENERGY_USE_CATEGORIES.Ventilation: 375,
            ENERGY_USE_CATEGORIES.Cooling: 1778.23405494,
            ENERGY_USE_CATEGORIES.Heating: 54_017.2354943853
        }
        calculated = {
            category: energy_use.sum().sum()
            for category, energy_use in BuildingEnergySimulation(spec=self.spec).energy_use_by_category.items()
        }
        for category in ENERGY_USE_CATEGORIES:
            with self.subTest(category=category):
                self.assertAlmostEqual(expected[category], calculated[category], places=self.decimal_places)

    def test_total_energy_use(self):
        expected = Series(
            [
                54_471.300721610, 0.0, 0.0, 54_017.235494385, 0.0, 0.0
            ],
            index=list(ENERGY_SOURCES)
        )
        calculated = BuildingEnergySimulation(spec=self.spec).energy_use.sum(axis="rows")
        self.check_series_versus_values(
            calculated,
            expected
        )

if __name__ == '__main__':
    unittest.main()

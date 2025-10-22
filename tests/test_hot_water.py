import copy
import unittest
from pandas import DataFrame

from src.openbes.simulations.hot_water import (
    get_daily_hot_water_nominal,
    get_daily_hot_water,
    get_hot_water_per_month,
)
from src.openbes.types import ENERGY_SOURCES, OpenBESSpecification, MONTHS
from tests.test_holywell_house import DECIMAL_PLACES


class HotWaterPipeline(unittest.TestCase):
    def setUp(self):
        self.input = OpenBESSpecification(
            water_system_energy_source=ENERGY_SOURCES.Electricity,
            water_system_efficiency_cop=1.0,
            water_demand=300.0,
            water_reference_temperature=60.0,
            water_supply_temperature=16.0,
        )

    def test_nominal_consumption(self):
        self.assertAlmostEqual(
            get_daily_hot_water_nominal(self.input),
            15.32667,
            DECIMAL_PLACES
        )

    def test_nominal_consumption_error(self):
        with self.subTest(missing="water_demand"):
            input = copy.deepcopy(self.input)
            input.water_demand = None
            self.assertEqual(get_daily_hot_water_nominal(input), 0.0)
        with self.subTest(missing="water_reference_temperature"):
            input = copy.deepcopy(self.input)
            input.water_reference_temperature = None
            self.assertEqual(get_daily_hot_water_nominal(input), 0.0)
        with self.subTest(missing="water_supply_temperature"):
            input = copy.deepcopy(self.input)
            input.water_supply_temperature = None
            self.assertEqual(get_daily_hot_water_nominal(input), 0.0)

    def test_consumption(self):
        self.assertAlmostEqual(
            get_daily_hot_water(self.input),
            15.32667,
            DECIMAL_PLACES
        )

    def test_consumption_error(self):
        with self.subTest(missing="water_demand", inherited_error=True):
            input = copy.deepcopy(self.input)
            input.water_demand = None
            self.assertEqual(get_daily_hot_water_nominal(input), 0.0)
        with self.subTest(missing="water_reference_temperature", inherited_error=True):
            input = copy.deepcopy(self.input)
            input.water_reference_temperature = None
            self.assertEqual(get_daily_hot_water_nominal(input), 0.0)
        with self.subTest(missing="water_supply_temperature", inherited_error=True):
            input = copy.deepcopy(self.input)
            input.water_supply_temperature = None
            self.assertEqual(get_daily_hot_water_nominal(input), 0.0)
        with self.subTest(missing="water_system_efficiency_cop", inherited_error=False):
            input = copy.deepcopy(self.input)
            input.water_system_efficiency_cop = None
            self.assertEqual(get_daily_hot_water(input), 0.0)

    def test_hot_water_per_month(self):
        expected = DataFrame(
            [
                [
                    275.880000, 306.533333, 352.513333, 337.186667, 352.513333, 337.186667,
                    352.513333, 352.513333, 337.186667, 352.513333, 337.186667, 260.553333,
                ]
            ],
            columns=MONTHS.list(),
            index=["kWh"]
        ).round(DECIMAL_PLACES)
        output = get_hot_water_per_month(self.input).round(DECIMAL_PLACES)
        self.assertTrue(expected.equals(output), expected.compare(output))


if __name__ == '__main__':
    unittest.main()

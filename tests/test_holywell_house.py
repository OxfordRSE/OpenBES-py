import unittest
from pandas import DataFrame, NA

from src.openbes.types import MONTHS, ENERGY_SOURCES, ENERGY_USE_CATEGORIES
from src.openbes.wip import (
    sum_energy_totals,
    aggregate_energy_totals,
    aggregate_monthly_zonal_energy,
)

DECIMAL_PLACES = 5

class HolywellHousePipeline(unittest.TestCase):
    def test_monthly_zonal_energy(self):
        data = [
            [282.240000, 221.760000, 0.000000, 0.000000, 0.000000, 0.000000],
            [313.600000, 246.400000, 0.000000, 0.000000, 0.000000, 0.000000],
            [360.640000, 283.360000, 0.000000, 0.000000, 0.000000, 0.000000],
            [344.960000, 271.040000, 0.000000, 0.000000, 0.000000, 0.000000],
            [360.640000, 283.360000, 0.000000, 0.000000, 0.000000, 0.000000],
            [344.960000, 271.040000, 0.000000, 0.000000, 0.000000, 0.000000],
            [329.280000, 258.720000, 0.000000, 0.000000, 0.000000, 0.000000],
            [344.960000, 271.040000, 0.000000, 0.000000, 0.000000, 0.000000],
            [344.960000, 271.040000, 0.000000, 0.000000, 0.000000, 0.000000],
            [360.640000, 283.360000, 0.000000, 0.000000, 0.000000, 0.000000],
            [344.960000, 271.040000, 0.000000, 0.000000, 0.000000, 0.000000],
            [266.560000, 209.440000, 0.000000, 0.000000, 0.000000, 0.000000],
        ]
        columns = [f"Zone type {i}" for i in range(1, 7)]
        input = DataFrame(data, index=MONTHS.list(), columns=columns)
        expected = DataFrame(
            [
                504.000000, 560.000000, 644.000000, 616.000000, 644.000000, 616.000000,
                588.000000, 616.000000, 616.000000, 644.000000, 616.000000, 476.000000,
            ],
            index=MONTHS.list(),
            columns=[ENERGY_USE_CATEGORIES.Lighting.value],
        ).round(DECIMAL_PLACES)
        calculated = aggregate_monthly_zonal_energy(input, ENERGY_USE_CATEGORIES.Lighting).round(DECIMAL_PLACES)
        self.assertTrue(expected.equals(calculated), expected.compare(calculated))

    def test_aggregate_electricity(self):
        input = DataFrame(
            {
                "Others": [1136.0] * 12,
                "Building standby": [2321.2] * 12,
                "Lighting": [504.0, 560.0, 644.0, 616.0, 644.0, 616.0, 588.0, 616.0, 616.0, 644.0, 616.0,
                             476.0],
                "Hot water": [275.88, 306.533333, 352.513333, 337.186667, 352.513333, 337.186667, 352.513333,
                              352.513333, 337.186667, 352.513333, 337.186667, 260.553333],
                "Ventilation": [27.0, 30.0, 34.5, 33.0, 34.5, 33.0, 34.5, 34.5, 33.0, 34.5, 33.0, 25.5],
                "Cooling": [0.0, 0.0, 0.0, 77.257219, 0.0, 578.141948, 1148.711630, 522.771472, 63.590424, 0.0,
                            0.0, 0.0],
                "Heating": [0.0] * 12,
            },
            index=MONTHS.list()
        )
        expected = DataFrame(
            {"kWh/yr": [13632.000000, 27854.400000, 7140.000000, 3954.280000, 387.000000, 2390.472693, 0.000000]},
            index=ENERGY_USE_CATEGORIES.list()
        ).round(DECIMAL_PLACES)
        calculated = aggregate_energy_totals(input).round(DECIMAL_PLACES)
        self.assertTrue(expected.equals(calculated), expected.compare(calculated))

    def test_sum_electricity(self):
        self.assertEqual(
            sum_energy_totals(
                DataFrame(
                    {"kWh/yr": [13632.000000, 27854.400000, 7140.000000, 3954.280000, 387.000000, 2390.472693, 0.000000]},
                    index=ENERGY_USE_CATEGORIES.list()
                )
            ),
            55_358.152693
        )

    def test_total_sums(self):
        self.assertEqual(
            sum_energy_totals(
                DataFrame(
                    {"kWh/yr": [54_874.2, NA, NA, 52_235.2, NA, NA]},
                    index=ENERGY_SOURCES.list()
                )
            ),
            107109.4
        )

    def test_pipeline(self):
        from src.openbes.pipeline import pipeline
        from src.openbes.types.dataclasses import OpenBESSpecification, OpenBESParameters

        input = OpenBESSpecification()
        parameters = OpenBESParameters()

        total_simulated = pipeline(input, parameters)

        self.assertAlmostEqual(total_simulated, 55358.15269, places=DECIMAL_PLACES)


if __name__ == '__main__':
    unittest.main()

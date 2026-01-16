import unittest

from pandas import DataFrame

from openbes import BuildingEnergySimulation
from openbes.examples import HOLYWELL_HOUSE_SPEC
from tests.unit.utils import (
    OpenBESTestCase,
)


class TestOpenBESReport(OpenBESTestCase):
    @classmethod
    def setUpClass(cls):
        cls.sim = BuildingEnergySimulation(spec=HOLYWELL_HOUSE_SPEC)
        cls.report = cls.sim.report

    def test_primary_energy_consumption(self):
        pec = self.report.primary_energy_consumption
        self.assertTrue("Holywell House" in pec.index)
        self.check_series_versus_values(
            pec.loc["Holywell House"],
            [112.7, 18.2, 131.0],
            decimal_places_or_tolerance=1
        )

    def test_final_energy_consumption_distribution(self):
        expected = DataFrame({
            "Heating": [53498, 48.8],
            "Cooling": [1575, 1.4],
            "Ventilation": [375, 0.3],
            "Hot water": [3832, 3.5],
            "Lighting": [7000, 6.4],
            "Building background": [27854, 25.4],
            "Others": [13632, 12.4],
        }, index=["kWh", "kWh/m2"]).transpose()
        for c in expected.columns:
            with self.subTest(column=c):
                self.check_series_versus_values(
                    self.report.final_energy_consumption_distribution[c],
                    expected[c],
                    decimal_places_or_tolerance=0 if c == "kWh" else 1,
                )

    def test_space_hvac_demand(self):
        with self.subTest("Heating"):
            expected = [69.9, 202.2, 184.5]
            calculated = self.report.space_heating_demand.loc[self.sim.building_name].astype(float)
            self.check_series_versus_values(calculated, expected, 1)
        with self.subTest("Cooling"):
            expected = [6.4, 48.0, 43.7]
            calculated = self.report.space_cooling_demand.loc[self.sim.building_name].astype(float)
            self.check_series_versus_values(calculated, expected, 1)

if __name__ == '__main__':
    unittest.main()

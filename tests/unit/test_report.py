import unittest

from pandas import DataFrame, Series

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

    def test_passive_survivability(self):
        expected = 0.09
        calculated = self.report.passive_survivability[self.sim.building_name]
        self.assertAlmostEquals(expected, calculated, 2)

    def test_retrofit_report(self):
        expected = Series(
            {
                "Summer discomfort hours (%)": 9.090909,
                "Peak heating load (kW)": 126.058460,
                "Peak cooling load (kW)": 36.589545,
                "Annual heating demand (kWh/m2)": 69.853243,
                "Annual cooling demand (kWh/m2)": 6.429513,
                "Final energy consumption (kWh/m2)": 98.307640,
                "Non-renewable primary energy consumption (kWh/m2)": 112.738357,
                "CO2 equivalent emissions kg CO2 eq/m2": 18.396515,
            },
            name="baseline",
        )
        calculated = self.sim.sim_to_retrofit_report('baseline')
        self.check_series_versus_values(calculated, expected)

    def test_adaptations(self):
        adaptations = self.sim.retrofit_report
        self.assertEqual(len(adaptations), 7)

if __name__ == '__main__':
    unittest.main()

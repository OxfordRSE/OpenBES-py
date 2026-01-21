import io
import unittest

import pandas as pd
from pandas import DataFrame, Series

from openbes import BuildingEnergySimulation
from openbes.examples import HOLYWELL_HOUSE_SPEC
from tests.unit.utils import (
    OpenBESTestCase,
)


class TestOpenBESReport(OpenBESTestCase):
    decimal_places_or_tolerance = 0.1

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
            decimal_places_or_tolerance=1,
        )

    def test_final_energy_consumption_distribution(self):
        expected = DataFrame(
            {
                "Heating": [53498, 48.8],
                "Cooling": [1575, 1.4],
                "Ventilation": [375, 0.3],
                "Hot water": [3832, 3.5],
                "Lighting": [7000, 6.4],
                "Building background": [27854, 25.4],
                "Others": [13632, 12.4],
            },
            index=["kWh", "kWh/m2"],
        ).transpose()
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
            calculated = self.report.space_heating_demand.loc[
                self.sim.building_name
            ].astype(float)
            self.check_series_versus_values(calculated, expected, 1)
        with self.subTest("Cooling"):
            expected = [6.4, 48.0, 43.7]
            calculated = self.report.space_cooling_demand.loc[
                self.sim.building_name
            ].astype(float)
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
        calculated = self.sim.sim_to_retrofit_report("baseline")
        self.check_series_versus_values(calculated, expected)

    def check_csv(self, csv_data, expected_info):
        df = pd.read_csv(io.StringIO(csv_data))
        self.assertEqual(len(df), expected_info["num_rows"], "Number of rows mismatch")
        self.assertTrue(
            Series(df.columns.values).equals(Series(expected_info["headers"])),
            Series(df.columns.values).compare(Series(expected_info["headers"])),
        )
        if expected_info["num_rows"] > 0:
            if any(isinstance(value, str) for value in expected_info["first_row"]):
                # If any of the expected first row values are strings, compare as strings
                expected_first_row = [
                    str(value) for value in expected_info["first_row"]
                ]
                calculated_first_row = df.iloc[0].astype(str)
            else:
                expected_first_row = expected_info["first_row"]
                calculated_first_row = df.iloc[0]
            self.check_series_versus_values(calculated_first_row, expected_first_row)

    def test_outputs(self):
        outputs = self.sim.outputs
        expected_scalars = {
            "altitude": 68.9,
            "gross_building_area": 1153.9,
            "conditioned_floor_area": 1096.2,
            "indoor_air_volume": 3179.0,
            "indoor_air_heat_capacity": 3907.5,
            "discomfort_hours_percent": 73.4,
            "discomfort_hours_percent_summer": 9.1,
            "infiltration_ach": 0.16,
            "natural_ach": 0.00,
            "lighting_demand": 6.39,
            "lighting_peak_load": 5.00,
            "lighting_load_ratio": 4.56,
            "hot_water_demand": 3.50,
            # Excel report is monthly values so other_energy_use_* are multiplied by 12
            "other_energy_use_electricity": 3.1538 * 12,
            "other_energy_use_gas": 0.00 * 12,
            "on_site_electricity_generated": 0.0,
            "on_site_electricity_used": 0.0,
            "on_site_electricity_fraction": 0.0,
            "all_renewable_fraction": 0.14,
            "final_energy_consumption": 98.3,
            "primary_energy_consumption": 131.0,
            "non_renewable_primary_energy_consumption": 112.7,
            "co2_equivalent_emissions": 18.4,
            "mean_indoor_temperature": 13.76,
        }
        for key, expected_value in expected_scalars.items():
            with self.subTest(key):
                calculated_value = getattr(outputs, key)
                self.assertAlmostEquals(calculated_value, expected_value, places=1)

        expected_peaks = {
            "max_outdoor_temperature": {"value": 30.2},
            "max_indoor_temperature": {
                "value": 33.37,
                "month": "July",
                "day": 20,
                "hour": 17,
            },
            "min_outdoor_temperature": {"value": -7.7},
            "min_indoor_temperature": {
                "value": -1.02,
                "month": "December",
                "day": 14,
                "hour": 7,
            },
        }
        for property, expected_info in expected_peaks.items():
            calculated_info = getattr(outputs, property)
            for key in expected_info.keys():
                with self.subTest(a=property, b=key):
                    self.assertAlmostEquals(
                        getattr(calculated_info, key), expected_info[key], places=1
                    )

        expected_thermal_demands = {
            "heating_demand": {
                "demand_total": 76574.14,
                "demand_scaled": 69.85,
                "load_csv": {
                    "headers": ["month", "Demand (kWh)"],
                    "num_rows": 12,
                    "first_row": ["January", 9624.76],
                },
                "load_duraction_csv": {
                    "headers": ["Quantile", "kW"],
                    "num_rows": 17,
                    "first_row": [0, 0.0],
                },
            },
            "cooling_demand": {
                "demand_total": 7048.13,
                "demand_scaled": 6.43,
                "load_csv": {
                    "headers": ["month", "Demand (kWh)"],
                    "num_rows": 12,
                    "first_row": ["January", 0.0],
                },
                "load_duraction_csv": {
                    "headers": ["Quantile", "kW"],
                    "num_rows": 17,
                    "first_row": [0, 0.0],
                },
            },
        }
        for domain in expected_thermal_demands.keys():
            tdr = getattr(outputs, domain)
            expected = expected_thermal_demands[domain]
            with self.subTest(a=domain, b="demand_total"):
                self.assertAlmostEquals(
                    tdr.demand_total, expected["demand_total"], places=2
                )
            with self.subTest(a=domain, b="demand_scaled"):
                self.assertAlmostEquals(
                    tdr.demand_scaled, expected["demand_scaled"], places=2
                )
            with self.subTest(a=domain, b="load_csv"):
                self.check_csv(tdr.load_csv, expected["load_csv"])
            with self.subTest(a=domain, b="load_duraction_csv"):
                self.check_csv(tdr.load_duraction_csv, expected["load_duraction_csv"])

        expected_csvs = {
            "solstice_ghr_csv": {
                "headers": ["hour", "December 21", "June 21"],
                "num_rows": 24,
                "first_row": [1, 0.0, 0.0],
            },
            "external_internal_temperature_csv": {
                "headers": [
                    "month",
                    "day",
                    "hour",
                    "external_temperature_C",
                    "internal_temperature_C",
                ],
                "num_rows": 8760,
                "first_row": [1, 1, 1, 12.3, 17.2],
            },
            "heat_exchange_breakdown_csv": {
                "headers": [
                    "month",
                    "Heat transfer (infiltration)",
                    "Heat transfer (ventilation)",
                    "Solar gains (opaque)",
                    "Solar gains (glazing)",
                    "Heat from occupants",
                    "Heat from appliances",
                    "Heat from lighting",
                ],
                "num_rows": 12,
                "first_row": [
                    "January",
                    -13.06,
                    -0.99,
                    0.56,
                    1.23,
                    0.45,
                    0.09,
                    1.02,
                ],
            },
            "space_thermal_demand_csv": {
                "headers": [
                    "month",
                    "Heating demand (kWh/m2)",
                    "Cooling demand (kWh/m2)",
                ],
                "num_rows": 12,
                "first_row": ["January", 8.78, 0.0],
            },
            "final_energy_consumption_csv": {
                "headers": ["System", "kWh"],
                "num_rows": 7,
                "first_row": ["Heating", 53498.21],
            },
            "climate_quantiles_csv": {
                "headers": ["Quantile", "Temperature (C)"],
                "num_rows": 17,
                "first_row": [0, -7.7],
            },
            "degree_days_csv": {
                "headers": [
                    "month",
                    "day",
                    "Heating Degree Days",
                    "Cooling Degree Days",
                ],
                "num_rows": 365,
                "first_row": [1, 1, 8.9, 0],
            },
            "annual_incident_solar_radiation_csv": {
                "headers": [
                    "Compass point",
                    "Annual incident solar radiation (kWh/m2)",
                ],
                "num_rows": 8,
                "first_row": ["North", 347.62],
            },
            "running_average_outside_temp_csv": {
                "headers": [
                    "month",
                    "day",
                    "hour",
                    "Running mean outdoor temperature (C)",
                ],
                "num_rows": 8760,
                "first_row": [1, 1, 1, 7.74],
            },
            "overheating_limits_csv": {
                "headers": [
                    "Outdoor running mean temp (C)",
                    "Category I min (C)",
                    "Category I max (C)",
                    "Category II min (C)",
                    "Category II max (C)",
                    "Category III min (C)",
                    "Category III max (C)",
                ],
                "num_rows": 3,
                "first_row": [10.0, 19.1, 24.1, 18.1, 25.1, 17.1, 26.1],
            },
            "building_geometry_csv": {
                "headers": [
                    "Floor",
                    "Opaque facade (m2)",
                    "Roof (m2)",
                    "Floor (m2)",
                    "Windows (m2)",
                    "Window-to-Wall Ratio",
                ],
                "num_rows": 5,
                "first_row": ["ground", 266.74, 0.0, 522.96, 78.6, 0.23],
            },
            "building_geometry_orientation_csv": {
                "headers": ["Compass point", "Opaque facade (m2)", "Windows (m2)"],
                "num_rows": 9,
                "first_row": ["North", 233.56, 67.37],
            },
            "solar_heat_gains_csv": {
                "headers": [
                    "Compass point",
                    "Opaque gains (kWh)",
                    "Window gains (kWh)",
                ],
                "num_rows": 9,
                "first_row": ["North", 1199.72, 5419.53],
            },
            "window_transmissivity_coefficient_csv": {
                "headers": ["Compass point", "Window transmissivity coefficient"],
                "num_rows": 8,
                "first_row": ["North", 0.23],
            },
        }
        for key, expected_info in expected_csvs.items():
            with self.subTest(key):
                self.check_csv(getattr(outputs, key), expected_info)

        with self.subTest("ventilation_systems"):
            vs = outputs.ventilation_systems
            self.assertEqual(len(vs), 1)
            s = vs[0]
            self.assertEqual(s.energy_demand, 3.75)
            self.assertEqual(s.peak_load, 0.30)
            self.assertEqual(s.sfp, 3.60)
            self.assertEqual(s.mechanical_ventilation_rate, 3.00)
            self.assertEqual(s.ventilation_rate, 0.83)
            self.assertEqual(s.ach, 0.02)
        with self.subTest("heating_systems"):
            hs = outputs.heating_systems
            self.assertEqual(len(hs), 1)
            s = hs[0]
            self.assertEqual(s.conditioned_area, 912.80)
            self.assertEqual(s.energy_demand, 58.61)
            self.assertEqual(s.energy_demand_on_all_year, 75.10)
            self.assertEqual(s.system_usage, 43.15)
            self.assertEqual(
                s.peak_load,
                {
                    "value": 202.22,
                    "month": "December",
                    "day": 3,
                    "hour": 8,
                },
            )
            self.assertEqual(s.peak_capacity, 96.00)
            self.assertEqual(s.peak_ratio, 0.76)
        with self.subTest("cooling_systems"):
            cs = outputs.cooling_systems
            self.assertEqual(len(cs), 1)
            s = cs[0]
            self.assertEqual(s.conditioned_area, 866.94)
            self.assertEqual(s.energy_demand, 1.82)
            self.assertEqual(s.energy_demand_on_all_year, 6.78)
            self.assertEqual(s.system_usage, 3.05)
            self.assertEqual(
                s.peak_load,
                {
                    "value": 47.95,
                    "month": "July",
                    "day": 20,
                    "hour": 14,
                },
            )
            self.assertEqual(s.peak_capacity, 75.00)
            self.assertEqual(s.peak_ratio, 2.05)

        expected_validations = {
            "electricity_validation": {
                "energy_use_csv": {
                    "headers": ["month", "Simulated (kWh)", "Measured (kWh)"],
                    "num_rows": 12,
                    "first_row": ["January", 4264.1, 4402.0],
                },
                "nmbe": 0.011,
                "cv_rmse": 0.050,
                "r2": 0.85,
            },
            "gas_validation": {
                "energy_use_csv": {
                    "headers": ["month", "Simulated (kWh)", "Measured (kWh)"],
                    "num_rows": 12,
                    "first_row": ["January", 7890.4, 10129.7],
                },
                "nmbe": -0.0024,
                "cv_rmse": 0.323,
                "r2": 0.94,
            },
        }
        for key, expected_info in expected_validations.items():
            with self.subTest(key):
                calculated_info = getattr(outputs, key)
                self.assertEqual(calculated_info.nmbe, expected_info["nmbe"])
                self.assertEqual(calculated_info.cv_rmse, expected_info["cv_rmse"])
                self.assertEqual(calculated_info.r2, expected_info["r2"])
                self.check_csv(
                    calculated_info.energy_use_csv,
                    expected_info.energy_use_csv,
                )


if __name__ == "__main__":
    unittest.main()

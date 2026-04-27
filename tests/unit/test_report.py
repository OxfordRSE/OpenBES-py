import io
import unittest

import pandas as pd
from pandas import DataFrame, Series

from openbes import BuildingEnergySimulation, OpenBESSpecification
from openbes.examples import HOLYWELL_HOUSE_SPEC, get_holywell_house_spec
from openbes.schemas import OpenBESOutput
from openbes.simulations.building_energy import (
    BuildingEnergySimulationError,
    OpenBESReport,
)
from tests.unit.utils import (
    OpenBESTestCase,
    distinct_secondary_hvac_systems,
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
        """Summing each row recovers the old per-system kWh totals."""
        expected_totals = Series(
            {
                "Heating": 53498,
                "Cooling": 1575,
                "Ventilation": 375,
                "Hot water": 3832,
                "Lighting": 7000,
                "Building background": 27854,
                "Others": 13632,
            }
        )
        row_sums = self.report.final_energy_consumption_distribution.sum(axis=1)
        for system, expected_kwh in expected_totals.items():
            with self.subTest(system=system):
                self.assertAlmostEqual(row_sums[system], expected_kwh, delta=1.0)

    def test_final_energy_consumption_distribution_per_source(self):
        """The distribution DataFrame has [System x ENERGY_SOURCES] structure with correct values."""
        from openbes.types.enums import ENERGY_SOURCES

        df = self.report.final_energy_consumption_distribution
        energy_source_columns = list(ENERGY_SOURCES)

        # Columns are ENERGY_SOURCES enum members
        with self.subTest("columns"):
            self.assertEqual(list(df.columns), energy_source_columns)

        # Index name is "System"
        with self.subTest("index_name"):
            self.assertEqual(df.index.name, "System")

        # First row (Heating): all energy from Natural gas, none from others
        heating_row = df.loc["Heating"]
        with self.subTest("Heating_Natural_gas"):
            self.assertAlmostEqual(
                heating_row[ENERGY_SOURCES.Natural_gas], 53498, delta=1.0
            )
        for source in energy_source_columns:
            if source != ENERGY_SOURCES.Natural_gas:
                with self.subTest(f"Heating_{source.value}_is_zero"):
                    self.assertAlmostEqual(heating_row[source], 0.0, places=3)

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
        self.assertAlmostEqual(expected, calculated, 2)

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

    def flatten_outputs(self, outputs):
        flattened = {}
        for section_name in [
            "location_simulation_output",
            "geometry_simulation_output",
            "thermal_simulation_output",
            "ventilation_simulation_output",
            "heating_simulation_output",
            "cooling_simulation_output",
            "lighting_simulation_output",
            "hot_water_simulation_output",
            "building_energy_simulation_output",
        ]:
            section = getattr(outputs, section_name)
            if section is None:
                continue
            for field in section.__class__.model_fields:
                flattened[field] = getattr(section, field)
        return flattened

    def test_end2end_with_minimal_inputs(self):
        # Building-level inputs can validate, but subsystem-required inputs are now enforced.
        spec = OpenBESSpecification.from_toml({})
        # Building simulation should generate a blank report and a log full of issues
        sim = BuildingEnergySimulation(spec)
        self.assertTrue(isinstance(sim.report, OpenBESReport))
        self.assertTrue(isinstance(sim.outputs, OpenBESOutput))

    def test_outputs(self):
        outputs = self.sim.outputs
        flat_outputs = self.flatten_outputs(outputs)
        expected_scalars = {
            "elevation": 68.9,
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
                calculated_value = flat_outputs[key]
                self.assertAlmostEqual(calculated_value, expected_value, places=1)

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
            calculated_info = flat_outputs[property]
            for key in expected_info.keys():
                with self.subTest(a=property, b=key):
                    self.assertAlmostEqual(
                        getattr(calculated_info, key), expected_info[key], places=1
                    )

        expected_thermal_demands = {
            "heating_demand": {
                "demand_total": 76574.14,
                "demand_scaled": 69.85,
                "demand_on_all_year": 75.0972329030,
                "load_csv": {
                    "headers": ["month", "Demand (kWh)"],
                    "num_rows": 12,
                    "first_row": ["January", 9624.76],
                },
                "load_duration_csv": {
                    "headers": ["Quantile", "kW"],
                    "num_rows": 17,
                    "first_row": [0, 0.0],
                },
            },
            "cooling_demand": {
                "demand_total": 7048.13,
                "demand_scaled": 6.43,
                "demand_on_all_year": 6.7832092631,
                "load_csv": {
                    "headers": ["month", "Demand (kWh)"],
                    "num_rows": 12,
                    "first_row": ["January", 0.0],
                },
                "load_duration_csv": {
                    "headers": ["Quantile", "kW"],
                    "num_rows": 17,
                    "first_row": [0, 0.0],
                },
            },
        }
        for domain in expected_thermal_demands.keys():
            tdr = flat_outputs[domain]
            expected = expected_thermal_demands[domain]
            with self.subTest(a=domain, b="demand_total"):
                self.assertAlmostEqual(
                    tdr.demand_total, expected["demand_total"], places=2
                )
            with self.subTest(a=domain, b="demand_scaled"):
                self.assertAlmostEqual(
                    tdr.demand_scaled, expected["demand_scaled"], places=2
                )
            with self.subTest(a=domain, b="demand_on_all_year"):
                self.assertAlmostEqual(
                    tdr.demand_on_all_year, expected["demand_on_all_year"], places=2
                )
            with self.subTest(a=domain, b="load_csv"):
                self.check_csv(tdr.load_csv, expected["load_csv"])
            with self.subTest(a=domain, b="load_duration_csv"):
                self.check_csv(tdr.load_duration_csv, expected["load_duration_csv"])

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
                    "Transmission heat transfer",
                    "Ventilation and infiltration",
                    "Solar gains (opaque envelope)",
                    "Solar gains (openings)",
                    "Internal gains (occupants)",
                    "Internal gains (appliances)",
                    "Internal gains (lighting)",
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
                "headers": [
                    "System",
                    "Electricity",
                    "Diesel",
                    "LPG",
                    "Natural gas",
                    "Biomass",
                    "Pellets",
                ],
                "num_rows": 7,
                "first_row": ["Heating", 0.0, 0.0, 0.0, 53498.21, 0.0, 0.0],
            },
            "temperature_quantiles_csv": {
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
            "building_envelope_csv": {
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
                self.check_csv(flat_outputs[key], expected_info)

        with self.subTest("ventilation_systems"):
            vs = flat_outputs["ventilation_systems"]
            self.assertEqual(len(vs), 1)
            s = vs[0]
            self.assertAlmostEqual(s.energy_demand, 3.75, places=self.decimal_places)
            self.assertAlmostEqual(s.peak_load, 0.30, places=self.decimal_places)
            self.assertAlmostEqual(s.sfp, 3.60, places=self.decimal_places)
            self.assertAlmostEqual(
                s.mechanical_ventilation_rate, 3.00, places=self.decimal_places
            )
            self.assertAlmostEqual(
                s.ventilation_rate, 0.83333333, places=self.decimal_places
            )
            self.assertAlmostEqual(s.ach, 0.02359216099177, places=self.decimal_places)
        with self.subTest("heating_systems"):
            hs = flat_outputs["heating_systems"]
            self.assertEqual(len(hs), 1)
            s = hs[0]
            self.assertAlmostEqual(
                s.conditioned_area, 912.7961, places=self.decimal_places
            )
            self.assertAlmostEqual(
                s.energy_demand, 58.6091516482, places=self.decimal_places
            )
            self.assertAlmostEqual(
                s.system_usage, 43.153822995, places=self.decimal_places
            )
            self.assertAlmostEqual(s.peak_capacity, 96.00, places=self.decimal_places)
            self.assertAlmostEqual(
                s.peak_ratio, 0.7615514254, places=self.decimal_places
            )
            for prop, value in {
                "value": 202.22,
                "month": "December",
                "day": 3,
                "hour": 8,
            }.items():
                with self.subTest(a="heating_systems", b=prop):
                    self.assertEqual(getattr(s.peak_load, prop), value)
        with self.subTest("cooling_systems"):
            cs = flat_outputs["cooling_systems"]
            self.assertEqual(len(cs), 1)
            s = cs[0]
            self.assertAlmostEqual(
                s.conditioned_area, 866.9415, places=self.decimal_places
            )
            self.assertAlmostEqual(
                s.energy_demand, 1.8167188334, places=self.decimal_places
            )
            self.assertAlmostEqual(
                s.system_usage, 3.0494674, places=self.decimal_places
            )
            self.assertAlmostEqual(s.peak_capacity, 75.00, places=self.decimal_places)
            self.assertAlmostEqual(
                s.peak_ratio, 2.049765830, places=self.decimal_places
            )
            for prop, value in {
                "value": 47.95,
                "month": "July",
                "day": 20,
                "hour": 14,
            }.items():
                with self.subTest(a="cooling_systems", b=prop):
                    self.assertEqual(getattr(s.peak_load, prop), value)

        expected_validations = {
            "electricity_validation": {
                "energy_use_csv": {
                    "headers": ["month", "Simulated (kWh)", "Measured (kWh)"],
                    "num_rows": 12,
                    "first_row": ["January", 4264.08, 4402.20],
                },
                "nmbe": 0.011044270,
                "cv_rmse": 0.050374155,
                "r2": 0.846673353,
            },
            "gas_validation": {
                "energy_use_csv": {
                    "headers": ["month", "Simulated (kWh)", "Measured (kWh)"],
                    "num_rows": 12,
                    "first_row": ["January", 7890.42, 10129.70],
                },
                "nmbe": -0.0241811550,
                "cv_rmse": 0.3230852229,
                "r2": 0.9355730172,
            },
        }
        for key, expected_info in expected_validations.items():
            with self.subTest(key):
                calculated_info = flat_outputs[key]
                self.assertAlmostEqual(
                    calculated_info.nmbe, expected_info["nmbe"], places=6
                )
                self.assertAlmostEqual(
                    calculated_info.cv_rmse, expected_info["cv_rmse"], places=6
                )
                self.assertAlmostEqual(
                    calculated_info.r2, expected_info["r2"], places=4
                )
                self.check_csv(
                    calculated_info.energy_use_csv, expected_info["energy_use_csv"]
                )


if __name__ == "__main__":
    unittest.main()


class TestOpenBESReportMultipleSystems(OpenBESTestCase):
    @classmethod
    def setUpClass(cls):
        spec = distinct_secondary_hvac_systems(get_holywell_house_spec())
        cls.sim = BuildingEnergySimulation(spec=spec)

    def test_outputs_serialize_multiple_systems_as_arrays(self):
        outputs = self.sim.outputs.model_dump(mode="json")

        with self.subTest("heating_systems"):
            self.assertIsInstance(
                outputs["heating_simulation_output"]["heating_systems"], list
            )
            self.assertEqual(
                len(outputs["heating_simulation_output"]["heating_systems"]), 2
            )
            self.assertNotEqual(
                outputs["heating_simulation_output"]["heating_systems"][0][
                    "peak_capacity"
                ],
                outputs["heating_simulation_output"]["heating_systems"][1][
                    "peak_capacity"
                ],
            )

        with self.subTest("cooling_systems"):
            self.assertIsInstance(
                outputs["cooling_simulation_output"]["cooling_systems"], list
            )
            self.assertEqual(
                len(outputs["cooling_simulation_output"]["cooling_systems"]), 2
            )
            self.assertNotEqual(
                outputs["cooling_simulation_output"]["cooling_systems"][0][
                    "peak_capacity"
                ],
                outputs["cooling_simulation_output"]["cooling_systems"][1][
                    "peak_capacity"
                ],
            )

        with self.subTest("ventilation_systems"):
            self.assertIsInstance(
                outputs["ventilation_simulation_output"]["ventilation_systems"], list
            )
            self.assertEqual(
                len(outputs["ventilation_simulation_output"]["ventilation_systems"]), 2
            )
            self.assertNotEqual(
                outputs["ventilation_simulation_output"]["ventilation_systems"][0][
                    "energy_demand"
                ],
                outputs["ventilation_simulation_output"]["ventilation_systems"][1][
                    "energy_demand"
                ],
            )

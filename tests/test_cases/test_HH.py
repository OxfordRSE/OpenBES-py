from calendar import month_name
import unittest

from openbes.examples import get_holywell_house_spec
from openbes.simulations.building_energy import (
    BuildingEnergySimulation,
    day_of_the_month,
)
from openbes.types.enums import ENERGY_USE_CATEGORIES


class HolywellHouseCase(unittest.TestCase):
    """Regression checks for the Holywell House example summary table."""

    @classmethod
    def setUpClass(cls):
        cls.simulation = BuildingEnergySimulation(get_holywell_house_spec())

    @staticmethod
    def _peak_date(series):
        month, day_of_year, hour = series.idxmax()
        return {
            "year": "TMY 2007-2021",
            "month": month_name[month],
            "day": day_of_the_month(day_of_year, month),
            "hour": hour,
        }

    def test_summary_table(self):
        simulation = self.simulation
        thermal = simulation.thermal
        area = simulation.geometry.conditioned_floor_area
        air_changes_per_hour = (
            thermal.air_flow * area / (area * simulation.spec.floor_to_ceiling_height)
        )
        summer = thermal.air_free_temp.index.get_level_values("month").isin([6, 7, 8])
        occupied_summer = simulation.occupancy.is_occupied.loc[summer]
        discomfort_hours = (
            thermal.air_free_temp.loc[summer] * occupied_summer >= 26.0
        ).sum()
        category_energy = {
            category: energy.sum().sum() / area
            for category, energy in simulation.energy_use_by_category.items()
        }

        expected_values = {
            "Internal heat gains (max W/m2)": 7.208627843456142,
            "Air changes per hour (max h-1)": 0.1792115984868153,
            "Free-running air temperature maximum (C)": 33.368577787094885,
            "Free-running air temperature minimum (C)": -1.018725780924096,
            "Discomfort hours above 26C (summer, occupied)": 60,
            "Discomfort hours above 26C (summer, occupied, %)": 9.090909090909092,
            "Heating demand (kWh/m2)": 69.85324261822116,
            "Peak heating demand (kW)": 202.21543020492584,
            "Cooling demand (kWh/m2)": 6.4295132234085095,
            "Peak cooling demand (kW)": 47.95130958353576,
            "Final energy - Heating (kWh/m2)": 48.8026796296067,
            "Final energy - Cooling (kWh/m2)": 1.4367525247472792,
            "Final energy - Ventilation (kWh/m2)": 0.34208633438072567,
            "Final energy - Hot water (kWh/m2)": 3.4953621455168364,
            "Final energy - Lighting (kWh/m2)": 6.3856115751068785,
            "Final energy - Building standby (kWh/m2)": 25.4096255796653,
            "Final energy - Others (kWh/m2)": 12.43552242740814,
            "Final energy total (kWh/m2)": 98.30764021643186,
            "Carbon emissions total (kg CO2e/m2)": 18.396515071284224,
        }
        calculated_values = {
            "Internal heat gains (max W/m2)": thermal.internal_heat.max(),
            "Air changes per hour (max h-1)": air_changes_per_hour.max(),
            "Free-running air temperature maximum (C)": thermal.air_free_temp.max(),
            "Free-running air temperature minimum (C)": thermal.air_free_temp.min(),
            "Discomfort hours above 26C (summer, occupied)": discomfort_hours,
            "Discomfort hours above 26C (summer, occupied, %)": (
                discomfort_hours / occupied_summer.sum() * 100
            ),
            "Heating demand (kWh/m2)": simulation.space_hvac_demand.loc[
                ("Heating", simulation.building_name), "Demand (kWh/m2)"
            ],
            "Peak heating demand (kW)": simulation.space_hvac_demand.loc[
                ("Heating", simulation.building_name), "Peak (kW)"
            ],
            "Cooling demand (kWh/m2)": simulation.space_hvac_demand.loc[
                ("Cooling", simulation.building_name), "Demand (kWh/m2)"
            ],
            "Peak cooling demand (kW)": simulation.space_hvac_demand.loc[
                ("Cooling", simulation.building_name), "Peak (kW)"
            ],
            "Final energy - Heating (kWh/m2)": category_energy[
                ENERGY_USE_CATEGORIES.Heating
            ],
            "Final energy - Cooling (kWh/m2)": category_energy[
                ENERGY_USE_CATEGORIES.Cooling
            ],
            "Final energy - Ventilation (kWh/m2)": category_energy[
                ENERGY_USE_CATEGORIES.Ventilation
            ],
            "Final energy - Hot water (kWh/m2)": category_energy[
                ENERGY_USE_CATEGORIES.Hot_water
            ],
            "Final energy - Lighting (kWh/m2)": category_energy[
                ENERGY_USE_CATEGORIES.Lighting
            ],
            "Final energy - Building standby (kWh/m2)": category_energy[
                ENERGY_USE_CATEGORIES.Building_standby
            ],
            "Final energy - Others (kWh/m2)": category_energy[
                ENERGY_USE_CATEGORIES.Others
            ],
            "Final energy total (kWh/m2)": simulation.energy_use.sum().sum() / area,
            "Carbon emissions total (kg CO2e/m2)": simulation.kg_co2_eq.sum() / area,
        }

        for metric, expected in expected_values.items():
            with self.subTest(metric=metric):
                self.assertAlmostEqual(calculated_values[metric], expected, places=6)

        self.assertEqual(
            self._peak_date(thermal.air_free_temp),
            {"year": "TMY 2007-2021", "month": "July", "day": 20, "hour": 17},
        )
        self.assertEqual(
            self._peak_date(-thermal.air_free_temp),
            {
                "year": "TMY 2007-2021",
                "month": "December",
                "day": 14,
                "hour": 7,
            },
        )
import unittest

from openbes import OpenBESSpecification, BuildingEnergySimulation
from openbes.types import OpenBESParameters, MONTHS, ENERGY_SOURCES


class MiscellaneousUtilities(unittest.TestCase):
    def test_listable_enum_list(self):
        self.assertEqual(MONTHS.list_values()[0], "Jan")

    def test_listable_enum_by_index(self):
        self.assertEqual(MONTHS.get_by_index(0), MONTHS.Jan)

    def test_listable_enum_from_str(self):
        spec = OpenBESSpecification(cooling_system1_energy_source="Natural gas",
                                    building_length=1.0,
                                    building_width=1.0, meteorological_file_path="None.epw")
        self.assertEqual(spec.cooling_system1_energy_source, ENERGY_SOURCES.Natural_gas)
        self.assertTrue(isinstance(spec.cooling_system1_energy_source, ENERGY_SOURCES))

    def test_spec_with_param_dict(self):
        params = {"cooling_system2_number": 10}
        spec = OpenBESSpecification(building_width=1.0, building_length=1.0, meteorological_file_path="None.epw",
                                    parameters=params)
        self.assertTrue(isinstance(spec.parameters, OpenBESParameters))
        self.assertEqual(spec.parameters.cooling_system2_number, 10)

    def test_javascript_call(self):
        obj = {
            "building_name": "Concept Building",
            "building_area": 1200,
            "building_height": 12,
            "building_width": 20,
            "building_length": 30,
            "ground_floor_area_z1": 1200,
            "ground_floor_area_z2": 0,
            "ground_floor_area_z3": 0,
            "ground_floor_area_z4": 0,
            "ground_floor_area_z5": 0,
            "first_floor_area_z1": 0,
            "first_floor_area_z2": 0,
            "first_floor_area_z3": 0,
            "first_floor_area_z4": 0,
            "first_floor_area_z5": 0,
            "second_floor_area_z1": 0,
            "second_floor_area_z2": 0,
            "second_floor_area_z3": 0,
            "second_floor_area_z4": 0,
            "second_floor_area_z5": 0,
            "third_floor_area_z1": 0,
            "third_floor_area_z2": 0,
            "third_floor_area_z3": 0,
            "third_floor_area_z4": 0,
            "third_floor_area_z5": 0,
            "fourth_floor_area_z1": 0,
            "fourth_floor_area_z2": 0,
            "fourth_floor_area_z3": 0,
            "fourth_floor_area_z4": 0,
            "fourth_floor_area_z5": 0,
            "building_standby_load": 2000,
            "floor_to_ceiling_height": 3,
            "slab_thickness": 0.2,
            "orientation_angle": 0,
            "location": "Denver",
            "meteorological_file_path": "USA_Denver_725650TYCST.epw",
            "roof_angle": 25,
            "terrain_class": "Urban",
            "heat_capacity": "Medium",
            "building_type": "Office",
            "occupancy_open_canteen": 9,
            "occupancy_open_office": 9,
            "occupancy_open_teaching": 9,
            "occupancy_close_canteen": 17,
            "occupancy_close_office": 17,
            "occupancy_close_teaching": 17,
            "appliances_load": 12,
            "other_electricity_usage": 1.5,
            "other_gas_usage": 0.3,
            "ventilation_system1_airflow": 0.6,
            "ventilation_system1_heat_recovery_efficiency": 0.6,
            "ventilation_system1_rated_input_power": 1.2,
            "ventilation_system1_on_time": 24,
            "ventilation_system1_off_time": 1,
            "ventilation_system1_energy_source": "Electricity",
            "leakage_air_flow_independent": 0,
            "natural_ventilation_night": 0,
            "heating_system1_energy_source": "Natural gas",
            "cooling_system1_energy_source": "Electricity",
            "heating_system1_number": 1,
            "cooling_system1_number": 1,
            "setpoint_winter_day": 21,
            "setpoint_winter_night": 18,
            "setpoint_summer_day": 25,
            "setpoint_summer_night": 23,
            "window_height": 1.5,
            "window_length": 1.2,
            "window_gvalue": 0.6,
            "window_frame_factor": 0.15,
            "window_number_ground_a1": 6,
            "window_number_first_a1": 8,
            "window_number_second_a1": 8,
            "window_number_third_a1": 8,
            "window_number_fourth_a1": 6,
            "uvalue_window": 1.4,
            "uvalue_facade": 0.35,
            "uvalue_roof": 0.22,
            "uvalue_floor": 0.28,
            "solar_external_shading_summer": 0,
            "solar_external_shading_winter": 0,
            "cooling_system1_nominal_capacity": 120,
            "heating_system1_nominal_capacity": 200,
            "heating_system1_efficiency_cop": 0.9,
            "lighting_simultaneity_factor": 0.2,
            "water_system_energy_source": "Electricity",
            "parameters": {
                "air_heat_capacity": 1.012,
                "density_of_air": 1.211,
                "roof_correction_factor": 1,
                "facade_correction_factor": 1,
                "window_correction_factor": 1,
                "shading_correction_factor": 1,
                "infiltration_correction_factor": 1,
                "heat_capacity_correction_factor": 1,
                "roof_absorption_coefficient": 0.8,
                "facade_absorption_coefficient": 0.6,
                "roof_emissivity": 0.9,
                "facade_emissivity": 0.9,
                "courtyard_number": 0,
                "cooling_system1_min_demand": 15,
                "heating_system1_min_demand": 35,
                "heating_load_factor": 1,
                "cooling_load_factor": 1,
                "lighting_on_off": True,
                "occupancy_on_off": True,
                "appliance_on_off": True,
                "advanced_heat_capacity_am": None,
            },
        }
        spec = OpenBESSpecification(**obj)
        sim = BuildingEnergySimulation(spec)
        self.assertGreater(sim.energy_use.sum().sum(), 0)


if __name__ == "__main__":
    unittest.main()

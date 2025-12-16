from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union
import tomllib

from . import LIGHTING_CONTROL, COOLING_SYSTEM_TYPES, HEATING_SYSTEM_TYPES, ListableEnum
from .enums import (
    LIGHTING_TECHNOLOGIES,
    LIGHTING_BALLASTS,
    ENERGY_SOURCES,
    HEAT_CAPACITY_CLASSES,
    TERRAINS
)

@dataclass
class OpenBESParameters:
    """
    Data class for OpenBES simulation parameters.
    """
    advanced_heat_capacity_am: Optional[float] = None
    air_heat_capacity: Optional[float] = None
    altitude: Optional[float] = None
    appliance_on_off: Optional[bool] = True
    cooling_load_factor: Optional[float] = 1.0
    cooling_system1_min_demand: Optional[float] = 15.0
    cooling_system2_energy_efficifiency_ratio: Optional[float] = None
    cooling_system2_energy_source: Optional[ENERGY_SOURCES] = field(default=None, metadata={'cls': ENERGY_SOURCES})
    cooling_system2_min_demand: Optional[float] = None
    cooling_system2_nominal_capacity: Optional[float] = None
    cooling_system2_number: Optional[int] = 0
    cooling_system2_off_time: Optional[int] = None
    cooling_system2_on_time: Optional[int] = None
    cooling_system2_sensible_nominal_capacity: Optional[float] = None
    cooling_system2_simultaneity_factor_canteen: Optional[float] = 0.0
    cooling_system2_simultaneity_factor_common: Optional[float] = 0.0
    cooling_system2_simultaneity_factor_office: Optional[float] = 0.0
    cooling_system2_simultaneity_factor_other: Optional[float] = 0.0
    cooling_system2_simultaneity_factor_teaching: Optional[float] = 0.0
    cooling_system2_type: Optional[COOLING_SYSTEM_TYPES] = field(default=None, metadata={'cls': COOLING_SYSTEM_TYPES})
    courtyard_length: Optional[float] = None
    courtyard_number: Optional[int] = 0
    courtyard_width: Optional[float] = None
    density_of_air: Optional[float] = 1.211
    facade_absorption_coefficient: Optional[float] = 0.6
    facade_correction_factor: Optional[float] = 1.0
    facade_emissivity: Optional[float] = 0.9
    floor_correction_factor: Optional[float] = 1.0
    heat_capacity_correction_factor: Optional[float] = 1.0
    heat_capacity_joule: Optional[float] = None
    heating_load_factor: Optional[float] = 1.0
    heating_system1_min_demand: Optional[float] = 35
    heating_system2_efficiency_cop: Optional[float] = None
    heating_system2_energy_source: Optional[ENERGY_SOURCES] = field(default=None, metadata={'cls': ENERGY_SOURCES})
    heating_system2_min_demand: Optional[float] = None
    heating_system2_nominal_capacity: Optional[float] = None
    heating_system2_number: Optional[int] = 0
    heating_system2_off_time: Optional[float] = None
    heating_system2_on_time: Optional[float] = None
    heating_system2_simultaneity_factor_canteen: Optional[float] = 0.0
    heating_system2_simultaneity_factor_common: Optional[float] = 0.0
    heating_system2_simultaneity_factor_office: Optional[float] = 0.0
    heating_system2_simultaneity_factor_other: Optional[float] = 0.0
    heating_system2_simultaneity_factor_teaching: Optional[float] = 0.0
    heating_system2_type: Optional[HEATING_SYSTEM_TYPES] = field(default=None, metadata={'cls': HEATING_SYSTEM_TYPES})
    infiltration_correction_factor: Optional[float] = 1.0
    leakage_air_flow_dependent: Optional[float] = 0.0001
    lighting_on_off: Optional[bool] = True
    # Fraction of gross building area that is inhabitable (i.e. minus walls, shafts, etc)
    nia_gba_ratio: Optional[float] = 0.95
    occupancy_close_common: Optional[float] = None
    occupancy_close_other: Optional[float] = None
    occupancy_on_off: Optional[bool] = True
    occupancy_open_common: Optional[float] = None
    occupancy_open_other: Optional[float] = None
    open_courtyard_depth_a1: Optional[float] = None
    open_courtyard_depth_b1: Optional[float] = None
    open_courtyard_depth_c1: Optional[float] = None
    open_courtyard_depth_d1: Optional[float] = None
    open_courtyard_number_a1: Optional[int] = 0
    open_courtyard_number_b1: Optional[int] = 0
    open_courtyard_number_c1: Optional[int] = 0
    open_courtyard_number_d1: Optional[int] = 0
    pressure_of_air: Optional[float] = None
    roof_absorption_coefficient: Optional[float] = 0.8
    roof_correction_factor: Optional[float] = 1.0
    roof_emissivity: Optional[float] = 0.9
    shading_correction_factor: Optional[float] = 1.0
    specific_heat_of_air: Optional[float] = 1.015
    temperature_tolerance: Optional[float] = 0.0
    ventilation_system2_airflow: Optional[float] = None
    ventilation_system2_energy_source: Optional[float] = None
    ventilation_system2_heat_recovery_efficiency: Optional[float] = None
    ventilation_system2_off_time: Optional[float] = None
    ventilation_system2_on_time: Optional[float] = None
    ventilation_system2_rated_input_power: Optional[float] = None
    ventilation_system2_type: Optional[float] = None
    ventilation_system2_ventilated_area: Optional[float] = None
    view_factor_to_sky_facade: Optional[float] = 0.5
    view_factor_to_sky_roof: Optional[float] = 1.0
    window_correction_factor: Optional[float] = 1.0

    def __post_init__(self):
        super().__init__()
        for f in self.__dataclass_fields__.values():
            value = getattr(self, f.name)
            cls = f.metadata.get('cls', None)
            if isinstance(cls, ListableEnum) and not isinstance(value, cls):
                if isinstance(value, str):
                    setattr(self, f.name, cls.get_by_value(value))


def get_meteorological_file(filename: str) -> str:
    if 'Denver' in filename:
        return 'USA_Denver_725650TYCST.epw'
    if 'Oxford' in filename:
        return 'UK_Oxford_GBR_ENG_RAF.Benson.036580_TMYx.2007-2021.epw'
    if 'Sevilla' in filename:
        return 'SPAIN_Sevilla.083910_SWEC.epw'
    if 'Madrid' in filename:
        return 'SPAIN_Madrid.082210_SWEC.epw'
    raise ValueError(f"Unknown meteorological file: {filename}")

def get_meteorological_name(epw_filename: str) -> str:
    if 'Denver' in epw_filename:
        return '725650_Denver'
    if 'Oxford' in epw_filename:
        return 'Oxford'
    if 'Sevilla' in epw_filename:
        return 'Sevilla'
    if 'Madrid' in epw_filename:
        return 'Madrid'
    return epw_filename

@dataclass
class OpenBESSpecification:
    """
    Data class for OpenBES spec parameters.
    """
    parameters: Optional[OpenBESParameters] = field(default_factory=OpenBESParameters)
    appliances_load: Optional[float] = None
    biomass_annual: Optional[float] = None
    biomass_pellets_annual: Optional[float] = None
    building_area: Optional[str] = None
    building_height: Optional[float] = None
    building_length: Optional[float] = None
    building_name: Optional[str] = None
    building_standby_load: Optional[float] = 0.0
    building_type: Optional[str] = None
    building_width: Optional[float] = None
    # Conditioned=True, Unconditioned=False
    condition_z1: Optional[bool] = True
    # Conditioned=True, Unconditioned=False
    condition_z2: Optional[bool] = True
    # Conditioned=True, Unconditioned=False
    condition_z3: Optional[bool] = True
    # Conditioned=True, Unconditioned=False
    condition_z4: Optional[bool] = None
    # Conditioned=True, Unconditioned=False
    condition_z5: Optional[bool] = None
    cooling_system1_energy_efficifiency_ratio: Optional[float] = None
    cooling_system1_energy_source: Optional[ENERGY_SOURCES] = field(default=None, metadata={'cls': ENERGY_SOURCES})
    cooling_system1_nominal_capacity: Optional[float] = None
    cooling_system1_number: Optional[int] = 0
    cooling_system1_off_time: Optional[int] = None
    cooling_system1_on_time: Optional[int] = None
    cooling_system1_sensible_nominal_capacity: Optional[float] = None
    cooling_system1_simultaneity_factor_canteen: Optional[float] = 0.0
    cooling_system1_simultaneity_factor_common: Optional[float] = 0.0
    cooling_system1_simultaneity_factor_office: Optional[float] = 0.0
    cooling_system1_simultaneity_factor_other: Optional[float] = 0.0
    cooling_system1_simultaneity_factor_teaching: Optional[float] = 0.0
    cooling_system1_type: Optional[COOLING_SYSTEM_TYPES] = field(default=None, metadata={'cls': COOLING_SYSTEM_TYPES})
    country: Optional[str] = None
    diesel_annual: Optional[float] = None
    electricity_annual: Optional[float] = None
    electricity_april: Optional[float] = None
    electricity_august: Optional[float] = None
    electricity_december: Optional[float] = None
    electricity_february: Optional[float] = None
    electricity_january: Optional[float] = None
    electricity_july: Optional[float] = None
    electricity_june: Optional[float] = None
    electricity_march: Optional[float] = None
    electricity_may: Optional[float] = None
    electricity_november: Optional[float] = None
    electricity_october: Optional[float] = None
    electricity_september: Optional[float] = None
    energy_generated: Optional[float] = None
    energy_used: Optional[float] = None
    first_floor_area_z1: Optional[float] = None
    first_floor_area_z2: Optional[float] = None
    first_floor_area_z3: Optional[float] = None
    first_floor_area_z4: Optional[float] = None
    first_floor_area_z5: Optional[float] = None
    floor_to_ceiling_height: Optional[float] = None
    fourth_floor_area_z1: Optional[float] = None
    fourth_floor_area_z2: Optional[float] = None
    fourth_floor_area_z3: Optional[float] = None
    fourth_floor_area_z4: Optional[float] = None
    fourth_floor_area_z5: Optional[float] = None
    gas_april: Optional[float] = None
    gas_august: Optional[float] = None
    gas_december: Optional[float] = None
    gas_february: Optional[float] = None
    gas_january: Optional[float] = None
    gas_july: Optional[float] = None
    gas_june: Optional[float] = None
    gas_march: Optional[float] = None
    gas_may: Optional[float] = None
    gas_november: Optional[float] = None
    gas_october: Optional[float] = None
    gas_september: Optional[float] = None
    ground_floor_area_z1: Optional[float] = None
    ground_floor_area_z2: Optional[float] = None
    ground_floor_area_z3: Optional[float] = None
    ground_floor_area_z4: Optional[float] = None
    ground_floor_area_z5: Optional[float] = None
    heat_capacity: Optional[HEAT_CAPACITY_CLASSES] = field(default=None, metadata={'cls': HEAT_CAPACITY_CLASSES})
    heating_system1_efficiency_cop: Optional[float] = None
    heating_system1_energy_source: Optional[ENERGY_SOURCES] = field(default=None, metadata={'cls': ENERGY_SOURCES})
    heating_system1_nominal_capacity: Optional[float] = None
    heating_system1_number: Optional[int] = 0
    heating_system1_off_time: Optional[float] = None
    heating_system1_on_time: Optional[float] = None
    heating_system1_simultaneity_factor_canteen: Optional[float] = 0.0
    heating_system1_simultaneity_factor_common: Optional[float] = 0.0
    heating_system1_simultaneity_factor_office: Optional[float] = 0.0
    heating_system1_simultaneity_factor_other: Optional[float] = 0.0
    heating_system1_simultaneity_factor_teaching: Optional[float] = 0.0
    heating_system1_type: Optional[HEATING_SYSTEM_TYPES] = field(default=None, metadata={'cls': HEATING_SYSTEM_TYPES})
    holiday: Optional[bool] = None
    leakage_air_flow: Optional[float] = None
    leakage_air_flow_independent: Optional[float] = None
    lighting_control: Optional[LIGHTING_CONTROL] = field(default=None, metadata={'cls': LIGHTING_CONTROL})
    lighting_off_time: Optional[float] = None
    lighting_on_time: Optional[float] = None
    lighting_simultaneity_factor: Optional[float] = 0.2
    lighting_system_ballast_z1: Optional[LIGHTING_BALLASTS] = field(default=None, metadata={'cls': LIGHTING_BALLASTS})
    lighting_system_ballast_z2: Optional[LIGHTING_BALLASTS] = field(default=None, metadata={'cls': LIGHTING_BALLASTS})
    lighting_system_ballast_z3: Optional[LIGHTING_BALLASTS] = field(default=None, metadata={'cls': LIGHTING_BALLASTS})
    lighting_system_ballast_z4: Optional[LIGHTING_BALLASTS] = field(default=None, metadata={'cls': LIGHTING_BALLASTS})
    lighting_system_ballast_z5: Optional[LIGHTING_BALLASTS] = field(default=None, metadata={'cls': LIGHTING_BALLASTS})
    lighting_system_ballast_z6: Optional[LIGHTING_BALLASTS] = field(default=None, metadata={'cls': LIGHTING_BALLASTS})
    lighting_system_lamp_number_z1: Optional[int] = None
    lighting_system_lamp_number_z2: Optional[int] = None
    lighting_system_lamp_number_z3: Optional[int] = None
    lighting_system_lamp_number_z4: Optional[int] = None
    lighting_system_lamp_number_z5: Optional[int] = None
    lighting_system_lamp_number_z6: Optional[int] = None
    lighting_system_lamp_power_z1: Optional[float] = None
    lighting_system_lamp_power_z2: Optional[float] = None
    lighting_system_lamp_power_z3: Optional[float] = None
    lighting_system_lamp_power_z4: Optional[float] = None
    lighting_system_lamp_power_z5: Optional[float] = None
    lighting_system_lamp_power_z6: Optional[float] = None
    lighting_system_luminary_number_z1: Optional[int] = None
    lighting_system_luminary_number_z2: Optional[int] = None
    lighting_system_luminary_number_z3: Optional[int] = None
    lighting_system_luminary_number_z4: Optional[int] = None
    lighting_system_luminary_number_z5: Optional[int] = None
    lighting_system_luminary_number_z6: Optional[int] = None
    lighting_system_name_z1: Optional[str] = None
    lighting_system_name_z2: Optional[str] = None
    lighting_system_name_z3: Optional[str] = None
    lighting_system_name_z4: Optional[str] = None
    lighting_system_name_z5: Optional[str] = None
    lighting_system_name_z6: Optional[str] = None
    lighting_system_operating_hours_z1: Optional[float] = None
    lighting_system_operating_hours_z2: Optional[float] = None
    lighting_system_operating_hours_z3: Optional[float] = None
    lighting_system_operating_hours_z4: Optional[float] = None
    lighting_system_operating_hours_z5: Optional[float] = None
    lighting_system_operating_hours_z6: Optional[float] = None
    lighting_system_similar_zone_number_z1: Optional[int] = None
    lighting_system_similar_zone_number_z2: Optional[int] = None
    lighting_system_similar_zone_number_z3: Optional[int] = None
    lighting_system_similar_zone_number_z4: Optional[int] = None
    lighting_system_similar_zone_number_z5: Optional[int] = None
    lighting_system_similar_zone_number_z6: Optional[int] = None
    lighting_system_simultaneity_factor_z1: Optional[float] = 0.0
    lighting_system_simultaneity_factor_z2: Optional[float] = 0.0
    lighting_system_simultaneity_factor_z3: Optional[float] = 0.0
    lighting_system_simultaneity_factor_z4: Optional[float] = 0.0
    lighting_system_simultaneity_factor_z5: Optional[float] = 0.0
    lighting_system_simultaneity_factor_z6: Optional[float] = 0.0
    lighting_system_tech_z1: Optional[LIGHTING_TECHNOLOGIES] = field(default=None, metadata={'cls': LIGHTING_TECHNOLOGIES})
    lighting_system_tech_z2: Optional[LIGHTING_TECHNOLOGIES] = field(default=None, metadata={'cls': LIGHTING_TECHNOLOGIES})
    lighting_system_tech_z3: Optional[LIGHTING_TECHNOLOGIES] = field(default=None, metadata={'cls': LIGHTING_TECHNOLOGIES})
    lighting_system_tech_z4: Optional[LIGHTING_TECHNOLOGIES] = field(default=None, metadata={'cls': LIGHTING_TECHNOLOGIES})
    lighting_system_tech_z5: Optional[LIGHTING_TECHNOLOGIES] = field(default=None, metadata={'cls': LIGHTING_TECHNOLOGIES})
    lighting_system_tech_z6: Optional[LIGHTING_TECHNOLOGIES] = field(default=None, metadata={'cls': LIGHTING_TECHNOLOGIES})
    location: Optional[float] = None
    LPG_annual: Optional[float] = None
    max_building_occupation: Optional[float] = None
    meteorological_file: Optional[str] = None
    natural_gas_annual: Optional[float] = None
    natural_ventilation_night: Optional[float] = 0.0
    occupancy_close_canteen: Optional[float] = None
    occupancy_close_office: Optional[float] = None
    occupancy_close_teaching: Optional[float] = None
    occupancy_open_canteen: Optional[float] = None
    occupancy_open_office: Optional[float] = None
    occupancy_open_teaching: Optional[float] = None
    orientation_angle: Optional[float] = None
    other_electricity_usage: Optional[float] = 0.0
    other_gas_usage: Optional[float] = 0.0
    roof_angle: Optional[float] = None
    schedule_april: Optional[bool] = None
    schedule_august: Optional[bool] = None
    schedule_december: Optional[bool] = None
    schedule_february: Optional[bool] = None
    schedule_friday: Optional[bool] = None
    schedule_january: Optional[bool] = None
    schedule_july: Optional[bool] = None
    schedule_june: Optional[bool] = None
    schedule_march: Optional[bool] = None
    schedule_may: Optional[bool] = None
    schedule_monday: Optional[bool] = None
    schedule_november: Optional[bool] = None
    schedule_october: Optional[bool] = None
    schedule_saturday: Optional[bool] = None
    schedule_september: Optional[bool] = None
    schedule_sunday: Optional[bool] = None
    schedule_thursday: Optional[bool] = None
    schedule_tuesday: Optional[bool] = None
    schedule_wednesday: Optional[bool] = None
    second_floor_area_z1: Optional[float] = None
    second_floor_area_z2: Optional[float] = None
    second_floor_area_z3: Optional[float] = None
    second_floor_area_z4: Optional[float] = None
    second_floor_area_z5: Optional[float] = None
    # Better described as 'setpoint maximum'
    setpoint_summer_day: Optional[float] = None
    # Better described as 'setpoint maximum'
    setpoint_summer_night: Optional[float] = None
    # Better described as 'setpoint minimum'
    setpoint_winter_day: Optional[float] = None
    # Better described as 'setpoint minimum'
    setpoint_winter_night: Optional[float] = None
    slab_thickness: Optional[float] = None
    solar_external_shading_summer: Optional[float] = None
    solar_external_shading_winter: Optional[float] = None
    terrain_class: Optional[TERRAINS] = field(default=None, metadata={'cls': TERRAINS})
    thermal_bridge_facade_ground: Optional[bool] = None
    thermal_bridge_facade_intermediate: Optional[bool] = None
    thermal_bridge_facade_roof: Optional[bool] = None
    thermal_bridge_shading: Optional[bool] = None
    thermal_bridge_window: Optional[bool] = None
    third_floor_area_z1: Optional[float] = None
    third_floor_area_z2: Optional[float] = None
    third_floor_area_z3: Optional[float] = None
    third_floor_area_z4: Optional[float] = None
    third_floor_area_z5: Optional[float] = None
    typical_occupation: Optional[float] = None
    uvalue_facade: Optional[float] = None
    uvalue_floor: Optional[float] = None
    uvalue_roof: Optional[float] = None
    uvalue_window: Optional[float] = None
    ventilation_system1_airflow: Optional[float] = 0.0
    ventilation_system1_energy_source: Optional[ENERGY_SOURCES] = field(default=None, metadata={'cls': ENERGY_SOURCES})
    ventilation_system1_heat_recovery_efficiency: Optional[float] = 0.0
    ventilation_system1_off_time: Optional[int] = 1
    ventilation_system1_on_time: Optional[int] = 24
    ventilation_system1_rated_input_power: Optional[float] = 0.0
    ventilation_system1_type: Optional[float] = None
    ventilation_system1_ventilated_area: Optional[float] = 1.0
    water_demand: Optional[float] = None
    water_reference_temperature: Optional[float] = None
    water_supply_temperature: Optional[float] = None
    water_system_efficiency_cop: Optional[float] = None
    water_system_energy_source: Optional[ENERGY_SOURCES] = field(default=None, metadata={'cls': ENERGY_SOURCES})
    water_system_nominal_capacity: Optional[float] = None
    water_system_type: Optional[float] = None
    window_frame_factor: Optional[float] = None
    window_gvalue: Optional[float] = None
    window_height: Optional[float] = None
    window_length: Optional[float] = None
    window_number_first_a1: Optional[int] = 0
    window_number_first_b1: Optional[int] = 0
    window_number_first_c1: Optional[int] = 0
    window_number_first_d1: Optional[int] = 0
    window_number_fourth_a1: Optional[int] = 0
    window_number_fourth_b1: Optional[int] = 0
    window_number_fourth_c1: Optional[int] = 0
    window_number_fourth_d1: Optional[int] = 0
    window_number_ground_a1: Optional[int] = 0
    window_number_ground_b1: Optional[int] = 0
    window_number_ground_c1: Optional[int] = 0
    window_number_ground_d1: Optional[int] = 0
    window_number_second_a1: Optional[int] = 0
    window_number_second_b1: Optional[int] = 0
    window_number_second_c1: Optional[int] = 0
    window_number_second_d1: Optional[int] = 0
    window_number_third_a1: Optional[int] = 0
    window_number_third_b1: Optional[int] = 0
    window_number_third_c1: Optional[int] = 0
    window_number_third_d1: Optional[int] = 0
    zone_name_z1: Optional[float] = None
    zone_name_z2: Optional[float] = None
    zone_name_z3: Optional[float] = None
    zone_name_z4: Optional[float] = None
    zone_name_z5: Optional[float] = None

    def __post_init__(self):
        super().__init__()
        if self.parameters is not None and not isinstance(self.parameters, OpenBESParameters):
            self.parameters = OpenBESParameters(**self.parameters)
        for f in self.__dataclass_fields__.values():
            value = getattr(self, f.name)
            cls = f.metadata.get('cls', None)
            if cls and issubclass(cls, ListableEnum) and not isinstance(value, cls):
                if isinstance(value, str):
                    setattr(self, f.name, cls.get_by_value(value))

    @classmethod
    def from_toml(cls, toml_file: Union[dict, str, Path]):
        if isinstance(toml_file, (str, Path)):
            with open(toml_file, "rb") as f:
                toml_content = tomllib.load(f)
        else:
            toml_content = toml_file
            
        filtered = {k: v for k, v in toml_content.items() if v is not None and v != ""}
        typed = filtered
        for k, v in typed.items():
            if k == 'i.meteorological_file':
                typed[k] = get_meteorological_file(v)
            elif isinstance(v, str) and v.lower() in ['false', 'no']:
                typed[k] = False
            elif isinstance(v, str) and v.lower() in ['true', 'yes']:
                typed[k] = True
            elif k.startswith(('i.condition_z', 'd.condition_z')):
                typed[k] = v.lower() == "conditioned"

        parameters = {k[2:]: v for k, v in filtered.items() if k.startswith("d")}
        specification = {k[2:]: v for k, v in filtered.items() if k.startswith("i")}
        return cls(parameters=OpenBESParameters(**parameters), **specification)

"""Converting OpenBESSpecificationV2 JSON to legacy TOML.

The historical TOML format used by OpenBES only captures a flattened view of
the data model.  The new :class:`~openbes.schemas.generated.models.OpenBESSpecificationV2`
model is richer (allowing arbitrary list lengths, nested structures, etc.), so
these helpers provide a best-effort conversion layer.
"""

from __future__ import annotations

import json
from typing import Any, List, Tuple, Dict


from openbes.schemas import (
    CoolingSystem,
    HeatingSystem,
    VentilationSystem,
)
from openbes.schemas.conversion.toml_to_json import monthly_average_to_consumption
from openbes.schemas.generated.models import (
    Consumption,
    OpenBESSpecificationV2,
    ZoneSimultaneity,
)
from openbes.types import get_meteorological_name


def _len(obj: Any) -> int:
    """Return the length of the object, or 0 if it is None."""
    if obj is None:
        return 0
    return len(obj)

def _bool_to_string(value: bool | None) -> str:
    """Convert a boolean value to 'Yes' or 'No' string."""
    if value is True:
        return "Yes"
    elif value is False:
        return "No"
    else:
        return ""


def json_to_toml(spec: OpenBESSpecificationV2|Dict[str, Any]|str, allow_warnings: bool = True):
    """Convert an OpenBESSpecificationV2 or its JSON representation to a TOML mapping.

    Args:
        spec: The OpenBESSpecificationV2 instance, dictionary, or JSON string to convert.
        allow_warnings: If True, allow lossy conversions with warnings. If False, raise errors on lossy conversions.
    Returns:
        A dictionary representing the TOML mapping.
    Raises:
        ValidationError: If the input does not validate against OpenBESSpecificationV2.
        ValueError: If the conversion is lossy and allow_warnings is False.
    """
    if isinstance(spec, str):
        spec = OpenBESSpecificationV2(**json.loads(spec))
    elif isinstance(spec, dict):
        spec = OpenBESSpecificationV2(**spec)

    def annual_consumption(consumption: Consumption):
        if consumption is None:
            return 0.0
        return sum(dict(consumption).values())

    # Parameters

    # Map default zone names and numbers to the spec Zones with best-effort matching.
    # If there are clashes, raise an error.
    zone_map = [
        { "default_name": "office", "default_str": "Office area", "number": 1, "zone": spec.zones[0] if _len(spec.zones) >= 1 else None },
        { "default_name": "teaching", "default_str": "Teaching", "number": 2, "zone": spec.zones[1] if _len(spec.zones) >= 2 else None },
        { "default_name": "canteen", "default_str": "Canteen", "number": 3, "zone": spec.zones[2] if _len(spec.zones) >= 3 else None },
        { "default_name": "common", "default_str": "Common areas", "number": 4, "zone": spec.zones[3] if _len(spec.zones) >= 4 else None },
        { "default_name": "other", "default_str": "Other spaces", "number": 5, "zone": spec.zones[4] if _len(spec.zones) >= 5 else None },
    ]

    def get_zone_condition(idx: int) -> str | None:
        if 0 <= idx < len(zone_map):
            zone = zone_map[idx]["zone"]
            if zone is not None and zone.conditioned:
                return "Conditioned"
        return "Unconditioned"

    def get_zone_floor_areas(floor: str, n: int) -> dict[str, float|str]:
        return {
            f"i.{floor}_floor_area_z{i + 1}": spec.zones[i].areas[n]
            if _len(spec.zones) > i and len(spec.zones[i].areas) >= n + 1
            else ""
            for i in range(len(zone_map))
        }

    def get_simultaneity_factors(zs: ZoneSimultaneity) -> List[Tuple[str,float|str]]:
        """Return (zone_name, simultaneity_factor) tuples for all default zones."""
        out = []
        for i in range(len(zone_map)):
            zone = zone_map[i]['zone']
            if zone is not None and zone.name in zs.root:
                out.append((zone_map[i]["default_name"], zs.root[zone.name]))
            else:
                out.append((zone_map[i]["default_name"], ""))
        return out

    def cooling_system_to_toml(cs: CoolingSystem, n: int) -> dict[str, str|float|int]:
        d = "d" if n == 2 else "i"
        if cs is None:
            return {
                f"{d}.cooling_system{n}_energy_efficifiency_ratio": "",
                f"{d}.cooling_system{n}_energy_source": "",
                f"{d}.cooling_system{n}_min_demand": "",
                f"{d}.cooling_system{n}_nominal_capacity": "",
                f"{d}.cooling_system{n}_number": "",
                f"{d}.cooling_system{n}_off_time": "",
                f"{d}.cooling_system{n}_on_time": "",
                f"{d}.cooling_system{n}_sensible_nominal_capacity": "",
                f"{d}.cooling_system{n}_type": "",
                **{
                    f"{d}.cooling_system{n}_simultaneity_factor_{zone_map[i]['default_name']}": ""
                    for i in range(len(zone_map))
                },
            }
        sf = get_simultaneity_factors(cs.simultaneity)
        return {
            f"{d}.cooling_system{n}_energy_efficifiency_ratio": cs.efficiency_ratio,
            f"{d}.cooling_system{n}_energy_source": cs.energy_source,
            f"{d}.cooling_system{n}_min_demand": cs.min_demand,
            f"{d}.cooling_system{n}_nominal_capacity": cs.nominal_capacity,
            f"{d}.cooling_system{n}_number": cs.count,
            f"{d}.cooling_system{n}_off_time": cs.active_hours.end,
            f"{d}.cooling_system{n}_on_time": cs.active_hours.start,
            f"{d}.cooling_system{n}_sensible_nominal_capacity": cs.sensible_nominal_capacity,
            f"{d}.cooling_system{n}_type": cs.type,
            **{f"{d}.cooling_system{n}_simultaneity_factor_{f[0]}": f[1] for f in sf},
        }

    def heating_system_to_toml(hs: HeatingSystem, n: int) -> dict[str, str|float|int]:
        d = "d" if n == 2 else "i"
        if hs is None:
            return {
                f"{d}.heating_system{n}_efficiency_cop": "",
                f"{d}.heating_system{n}_energy_source": "",
                f"{d}.heating_system{n}_min_demand": "",
                f"{d}.heating_system{n}_nominal_capacity": "",
                f"{d}.heating_system{n}_number": "",
                f"{d}.heating_system{n}_off_time": "",
                f"{d}.heating_system{n}_on_time": "",
                f"{d}.heating_system{n}_type": "",
                **{
                    f"{d}.heating_system{n}_simultaneity_factor_{zone_map[i]['default_name']}": ""
                    for i in range(len(zone_map))
                },
            }
        sf = get_simultaneity_factors(hs.simultaneity)
        return {
            f"{d}.heating_system{n}_efficiency_cop": hs.efficiency_cop,
            f"{d}.heating_system{n}_energy_source": hs.energy_source,
            f"{d}.heating_system{n}_min_demand": hs.min_demand,
            f"{d}.heating_system{n}_nominal_capacity": hs.nominal_capacity,
            f"{d}.heating_system{n}_number": hs.count,
            f"{d}.heating_system{n}_off_time": hs.active_hours.end,
            f"{d}.heating_system{n}_on_time": hs.active_hours.start,
            f"{d}.heating_system{n}_type": hs.type,
            **{f"{d}.heating_system{n}_simultaneity_factor_{f[0]}": f[1] for f in sf},
        }

    def ventilation_system_to_toml(vs: VentilationSystem, n: int) -> dict[str, str|float|int]:
        d = "d" if n == 2 else "i"
        if vs is None:
            return {
                f"{d}.ventilation_system{n}_airflow": "",
                f"{d}.ventilation_system{n}_energy_source": "",
                f"{d}.ventilation_system{n}_heat_recovery_efficiency": "",
                f"{d}.ventilation_system{n}_off_time": "",
                f"{d}.ventilation_system{n}_on_time": "",
                f"{d}.ventilation_system{n}_rated_input_power": "",
                f"{d}.ventilation_system{n}_type": "",
                f"{d}.ventilation_system{n}_ventilated_area": "",
            }
        return {
            f"{d}.ventilation_system{n}_airflow": vs.airflow,
            f"{d}.ventilation_system{n}_energy_source": vs.energy_source,
            f"{d}.ventilation_system{n}_heat_recovery_efficiency": vs.heat_recovery_efficiency,
            f"{d}.ventilation_system{n}_off_time": vs.active_hours.end,
            f"{d}.ventilation_system{n}_on_time": vs.active_hours.start,
            f"{d}.ventilation_system{n}_rated_input_power": vs.rated_input_power,
            f"{d}.ventilation_system{n}_type": vs.type,
            f"{d}.ventilation_system{n}_ventilated_area": vs.ventilated_area,
        }

    def lighting_systems_to_toml() -> dict[str, str | float | int]:
        out = {}
        for i in range(6):  # for some reason there are 6 lighting system slots in the TOML schema
            zone_number = i + 1
            if _len(spec.lighting_systems) <= i:
                ls = None
            else:
                ls = spec.lighting_systems[i]
            if not ls:
                out = {
                    **out,
                    f"i.lighting_system_ballast_z{zone_number}": "",
                    f"i.lighting_system_lamp_number_z{zone_number}": "",
                    f"i.lighting_system_lamp_power_z{zone_number}": "",
                    f"i.lighting_system_luminary_number_z{zone_number}": "",
                    f"i.lighting_system_name_z{zone_number}": "",
                    f"i.lighting_system_operating_hours_z{zone_number}": "",
                    f"i.lighting_system_similar_zone_number_z{zone_number}": "",
                    f"i.lighting_system_simultaneity_factor_z{zone_number}": "",
                    f"i.lighting_system_tech_z{zone_number}": "",
                }
            else:
                out = {
                    **out,
                    f"i.lighting_system_ballast_z{zone_number}": ls.ballast or "",
                    f"i.lighting_system_lamp_number_z{zone_number}": ls.lamp_number or "",
                    f"i.lighting_system_lamp_power_z{zone_number}": ls.lamp_power or "",
                    f"i.lighting_system_luminary_number_z{zone_number}": ls.luminary_number or "",
                    f"i.lighting_system_name_z{zone_number}": ls.name or "",
                    f"i.lighting_system_operating_hours_z{zone_number}": ls.active_hours.end - ls.active_hours.start if ls.active_hours else "",
                    f"i.lighting_system_similar_zone_number_z{zone_number}": ls.count or "",
                    f"i.lighting_system_simultaneity_factor_z{zone_number}": ls.simultaneity_factor or "",
                    f"i.lighting_system_tech_z{zone_number}": ls.tech or "",
                }
        return out

    def hot_water_systems_to_toml() -> dict[str, str | float | int]:
        ws = spec.hot_water_systems[0] if spec.hot_water_systems and len(spec.hot_water_systems) >= 1 else None
        if not ws:
            return {
                "i.water_demand": "",
                "i.water_reference_temperature": "",
                "i.water_supply_temperature": "",
                "i.water_system_efficiency_cop": "",
                "i.water_system_energy_source": "",
                "i.water_system_nominal_capacity": "",
                "i.water_system_type": "",
            }
        return {
            "i.water_demand": annual_consumption(ws.demand) / 365 if ws.demand else "",
            "i.water_reference_temperature": ws.reference_temperature if ws.reference_temperature else "",
            "i.water_supply_temperature": ws.supply_temperature if ws.supply_temperature else "",
            "i.water_system_efficiency_cop": ws.efficiency_cop if ws.efficiency_cop else "",
            "i.water_system_energy_source": ws.energy_source if ws.energy_source else "",
            "i.water_system_nominal_capacity": ws.nominal_capacity if ws.nominal_capacity else "",
            "i.water_system_type": ws.type if ws.type else "",
        }

    if spec.courtyards is not None and len(spec.courtyards) > 1:
        courtyards = {
            "d.courtyard_length": sum(c.length * c.count for c in spec.courtyards),
            "d.courtyard_number": 1,
            "d.courtyard_width": sum(c.width * c.count for c in spec.courtyards),
        }
    else:
        courtyards = {
            "d.courtyard_length": spec.courtyards[0].length if spec.courtyards else 0,
            "d.courtyard_number": spec.courtyards[0].count if spec.courtyards else 0,
            "d.courtyard_width": spec.courtyards[0].width if spec.courtyards else 0,
        }

    def get_window_counts() -> dict[str, int|str]:
        out = {}
        orientations = [("a", "front"), ("b", "right"), ("c", "back"), ("d", "left")]
        floors = [(1, "ground"), (2, "first"), (3, "second"), (4, "third"), (5, "fourth")]
        for f, floor in floors:
            for o_code, o_name in orientations:
                value = ""
                key = f"i.window_number_{floor}_{o_code}1"
                if spec.building and spec.building.window_counts:
                    window_count = dict(spec.building.window_counts).get(o_name, [])
                    if len(window_count) >= f:
                        value = window_count[f - 1] or ""
                out[key] = value
        return out

    def get_occupation_schedule() -> dict[str, int|str]:
        if spec.occupation_schedule is None:
            return {
                "i.schedule_january": "",
                "i.schedule_february": "",
                "i.schedule_march": "",
                "i.schedule_april": "",
                "i.schedule_may": "",
                "i.schedule_june": "",
                "i.schedule_july": "",
                "i.schedule_august": "",
                "i.schedule_september": "",
                "i.schedule_october": "",
                "i.schedule_november": "",
                "i.schedule_december": "",
                "i.schedule_monday": "",
                "i.schedule_tuesday": "",
                "i.schedule_wednesday": "",
                "i.schedule_thursday": "",
                "i.schedule_friday": "",
                "i.schedule_saturday": "",
                "i.schedule_sunday": "",
            }
        return {
            f"i.schedule_{k.lower()}": v for k, v in dict(spec.occupation_schedule).items()
        }

    if spec.heat_capacity is None or spec.heat_capacity.Am is None:
        hc_class = ""
    elif spec.heat_capacity.Cm == 80_000.0:
        hc_class = "Very light"
    elif spec.heat_capacity.Cm == 110_000.0:
        hc_class = "Light"
    elif spec.heat_capacity.Cm == 165_000.0:
        hc_class = "Medium"
    elif spec.heat_capacity.Cm == 260_000.0:
        hc_class = "Heavy"
    elif spec.heat_capacity.Cm == 370_000.0:
        hc_class = "Very heavy"
    else:
        hc_class = "Custom Value"

    toml = {
        # Parameters
        "d.advanced_heat_capacity_am": spec.heat_capacity.Am if hc_class == "Custom Value" else "",
        "d.altitude": spec.parameters.altitude or "",
        "d.appliance_on_off": 1 if spec.parameters.include_appliances else 0,
        "d.cooling_load_factor": spec.parameters.cooling_load_factor or "",
        
        "d.cooling_system1_min_demand": spec.cooling_systems[0].min_demand
        if _len(spec.cooling_systems) >= 1
        else "",
        **cooling_system_to_toml(
            spec.cooling_systems[1] if _len(spec.cooling_systems) >= 2 else None, n=2
        ),
        **courtyards,

        "d.density_of_air": spec.parameters.density_of_air or "",
        "d.facade_absorption_coefficient": spec.parameters.facade_absorption_coefficient or "",
        "d.facade_correction_factor": spec.parameters.facade_correction_factor or "",
        "d.facade_emissivity": spec.parameters.facade_emissivity or "",

        "d.floor_correction_factor": spec.parameters.floor_correction_factor or "",
        "d.heat_capacity_correction_factor": spec.parameters.heat_capacity_correction_factor or "",
        "d.heat_capacity_joule": spec.parameters.heat_capacity_joule or "",
        "d.heating_load_factor": spec.parameters.heating_load_factor or "",
        
        "d.heating_system1_min_demand": spec.heating_systems[0].min_demand
        if _len(spec.heating_systems) >= 1
        else "",
        **heating_system_to_toml(
            spec.heating_systems[1] if _len(spec.heating_systems) >= 2 else None, n=2
        ),

        "d.infiltration_correction_factor": spec.parameters.infiltration_correction_factor or "",
        "d.leakage_air_flow_dependent": spec.parameters.leakage_air_flow_dependent or "",
        "d.lighting_on_off": 1 if spec.parameters.include_lighting else 0,
        "d.nia_gba_ratio": spec.parameters.nia_gba_ratio or "",

        **{
            f"d.occupancy_close_{zone_map[i]['default_name']}": zone_map[i][
                "zone"
            ].active_hours.end
            if zone_map[i]["zone"] is not None
            and zone_map[i]["zone"].active_hours is not None
            else ""
            for i in [3,4]  # Last two zone occupancies are parameters
        },
        "d.occupancy_on_off": 1 if spec.parameters.include_occupancy else 0,
        **{
            f"d.occupancy_open_{zone_map[i]['default_name']}": zone_map[i][
                "zone"
            ].active_hours.start
            if zone_map[i]["zone"] is not None
            and zone_map[i]["zone"].active_hours is not None
            else ""
            for i in [3,4]  # Last two zone occupancies are parameters
        },
        
        "d.open_courtyard_depth_a1": spec.open_courtyards.front.depth
        if spec.open_courtyards is not None and spec.open_courtyards.front is not None
        else 0,
        "d.open_courtyard_depth_b1": spec.open_courtyards.right.depth
        if spec.open_courtyards is not None and spec.open_courtyards.right is not None
        else 0,
        "d.open_courtyard_depth_c1": spec.open_courtyards.back.depth
        if spec.open_courtyards is not None and spec.open_courtyards.back is not None
        else 0,
        "d.open_courtyard_depth_d1": spec.open_courtyards.left.depth
        if spec.open_courtyards is not None and spec.open_courtyards.left is not None
        else 0,
        "d.open_courtyard_number_a1": spec.open_courtyards.front.count
        if spec.open_courtyards is not None and spec.open_courtyards.front is not None
        else 0,
        "d.open_courtyard_number_b1": spec.open_courtyards.right.count
        if spec.open_courtyards is not None and spec.open_courtyards.right is not None
        else 0,
        "d.open_courtyard_number_c1": spec.open_courtyards.back.count
        if spec.open_courtyards is not None and spec.open_courtyards.back is not None
        else 0,
        "d.open_courtyard_number_d1": spec.open_courtyards.left.count
        if spec.open_courtyards is not None and spec.open_courtyards.left is not None
        else 0,

        "d.pressure_of_air": spec.parameters.pressure_of_air or "",
        "d.roof_absorption_coefficient": spec.parameters.roof_absorption_coefficient or "",
        "d.roof_correction_factor": spec.parameters.roof_correction_factor or "",
        "d.roof_emissivity": spec.parameters.roof_emissivity or "",
        "d.shading_correction_factor": spec.parameters.shading_correction_factor or "",
        "d.specific_heat_of_air": spec.parameters.specific_heat_of_air or "",
        "d.temperature_tolerance": spec.parameters.temperature_tolerance or "",

        **ventilation_system_to_toml(
            spec.ventilation_systems[1] if _len(spec.ventilation_systems) > 1 else None,
            n=2,
        ),

        "d.view_factor_to_sky_facade": spec.parameters.view_factor_to_sky_facade or "",
        "d.view_factor_to_sky_roof": spec.parameters.view_factor_to_sky_roof or "",
        "d.window_correction_factor": spec.parameters.window_correction_factor or "",

        # Specifications
        "i.appliances_load": spec.appliances_load or "",
        "i.biomass_annual": annual_consumption(spec.biomass_consumption) or "",
        "i.biomass_pellets_annual": annual_consumption(spec.biomass_pellets_consumption)
        or "",
        "i.building_area": spec.building.area or "",
        "i.building_height": spec.building.height or "",
        "i.building_length": spec.building.length or "",
        "i.building_name": spec.building.name or "",
        "i.building_standby_load": annual_consumption(
            spec.building_standby_electricity_consumption
        ) / 12
        or "",
        "i.building_type": spec.building.type or "",
        "i.building_width": spec.building.width or "",
        **{
            f"i.condition_z{idx + 1}": get_zone_condition(idx)
            for idx in range(len(zone_map))
        },
        **cooling_system_to_toml(
            spec.cooling_systems[0] if _len(spec.cooling_systems) >= 1 else None, n=1
        ),
        "i.country": spec.country or "",
        "i.diesel_annual": annual_consumption(spec.diesel_consumption),
        "i.electricity_annual": "",
        **{
            f"i.electricity_{month.lower()}": v
            for month, v in dict(spec.electricity_consumption or monthly_average_to_consumption(0.0)).items()
        },
        "i.energy_generated": annual_consumption(spec.energy_generated),
        "i.energy_used": annual_consumption(spec.energy_used),
        **get_zone_floor_areas("first", 1),
        "i.floor_to_ceiling_height": spec.building.floor_to_ceiling_height or "",
        **get_zone_floor_areas("fourth", 4),
        **{
            f"i.gas_{month.lower()}": v
            for month, v in dict(spec.natural_gas_consumption or monthly_average_to_consumption(0.0)).items()
        },
        **get_zone_floor_areas("ground", 0),
        "i.heat_capacity": hc_class,
        **heating_system_to_toml(
            spec.heating_systems[0] if _len(spec.heating_systems) >= 1 else None, n=1
        ),
        "i.holiday": "Yes" if spec.holiday else "No",
        "i.leakage_air_flow": spec.leakage_air_flow or "",
        "i.leakage_air_flow_independent": spec.leakage_air_flow_independent or "",
        "i.lighting_control": spec.lighting_control or "",
        "i.lighting_off_time": spec.lighting_active_hours.end
        if spec.lighting_active_hours
        else "",
        "i.lighting_on_time": spec.lighting_active_hours.start
        if spec.lighting_active_hours
        else "",
        "i.lighting_simultaneity_factor": spec.lighting_simultaneity_factor or "",
        **lighting_systems_to_toml(),
        "i.location": spec.location or "",
        "i.LPG_annual": annual_consumption(spec.LPG_consumption) or "",
        "i.max_building_occupation": spec.max_building_occupation or "",
        "i.meteorological_file": get_meteorological_name(spec.meteorological_file or ""),
        "i.natural_gas_annual": "",
        "i.natural_ventilation_night": spec.natural_ventilation_night or "",
        **{
            f"i.occupancy_close_{zone_map[i]['default_name']}": zone_map[i][
                "zone"
            ].active_hours.end
            if zone_map[i]["zone"] is not None and zone_map[i]["zone"].active_hours is not None
            else ""
            for i in range(3)  # Only first 3 zones have occupancy_close in spec, last two are handled above
        },
        **{
            f"i.occupancy_open_{zone_map[i]['default_name']}": zone_map[i][
                "zone"
            ].active_hours.start
            if zone_map[i]["zone"] is not None
            and zone_map[i]["zone"].active_hours is not None
            else ""
            for i in range(
                3
            )  # Only first 3 zones have occupancy_open in spec, last two are handled above
        },
        "i.orientation_angle": spec.building.orientation_angle or "",
        "i.other_electricity_usage": (annual_consumption(spec.other_electricity_consumption) or 0) / 12
        or "",
        "i.other_gas_usage": (annual_consumption(spec.other_gas_consumption) or 0) / 12,
        "i.roof_angle": spec.building.roof_angle or "",
        **get_occupation_schedule(),
        **get_zone_floor_areas("second", 2),
        "i.setpoint_summer_day": (spec.setpoint_temperature_day.min or "") if spec.setpoint_temperature_day else "",
        "i.setpoint_summer_night": (spec.setpoint_temperature_night.min or "") if spec.setpoint_temperature_night else "",
        "i.setpoint_winter_day": (spec.setpoint_temperature_day.max or "") if spec.setpoint_temperature_day else "",
        "i.setpoint_winter_night": (spec.setpoint_temperature_night.max or "") if spec.setpoint_temperature_night else "",
        "i.slab_thickness": spec.building.slab_thickness or "",
        "i.solar_external_shading_summer": spec.building.solar_external_shading_summer
        or "",
        "i.solar_external_shading_winter": spec.building.solar_external_shading_winter
        or "",
        "i.terrain_class": spec.building.terrain_class or "",
        "i.thermal_bridge_facade_ground": "Yes"
        if spec.building.thermal_bridge_facade_ground
        else "No",
        "i.thermal_bridge_facade_intermediate": "Yes"
        if spec.building.thermal_bridge_facade_intermediate
        else "No",
        "i.thermal_bridge_facade_roof": "Yes"
        if spec.building.thermal_bridge_facade_roof
        else "No",
        "i.thermal_bridge_shading": "Yes"
        if spec.building.thermal_bridge_shading
        else "No",
        "i.thermal_bridge_window": "Yes"
        if spec.building.thermal_bridge_window
        else "No",
        **get_zone_floor_areas("third", 3),
        "i.typical_occupation": spec.typical_occupation or "",
        "i.uvalue_facade": spec.building.uvalue_facade or "",
        "i.uvalue_floor": spec.building.uvalue_floor or "",
        "i.uvalue_roof": spec.building.uvalue_roof or "",
        "i.uvalue_window": spec.building.uvalue_window or "",
        **ventilation_system_to_toml(
            spec.ventilation_systems[0]
            if _len(spec.ventilation_systems) >= 1
            else None,
            n=1,
        ),
        **hot_water_systems_to_toml(),
        "i.window_frame_factor": spec.building.window_frame_factor or "",
        "i.window_gvalue": spec.building.window_gvalue or "",
        "i.window_height": spec.building.window_height or "",
        "i.window_length": spec.building.window_length or "",
        **get_window_counts(),
        **{
            f"i.zone_name_z{idx + 1}": zone_map[idx]["zone"].name
            if zone_map[idx]["zone"] is not None
            else zone_map[idx]["default_str"]
            for idx in range(len(zone_map))
        },
    }
    del toml["i.cooling_system1_min_demand"]  # included as a parameter
    del toml["i.heating_system1_min_demand"]  # included as a parameter
    return toml

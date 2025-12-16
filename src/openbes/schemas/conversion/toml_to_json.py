"""Converting legacy TOML to JSON.

The historical TOML format used by OpenBES only captures a flattened view of
the data model.  The new JSON Schema-based data
model is richer (allowing arbitrary list lengths, nested structures, etc.), so
these helpers provide a best-effort conversion layer.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any, Dict, Optional, List

from openbes.schemas.generated.models import OpenBESSpecificationV2
from openbes.types import get_meteorological_file


def monthly_average_to_consumption(value: float = None) -> Optional[Dict[str, float]]:
    if value is None:
        return None
    return {
        "January": value, "February": value, "March": value, "April": value,
        "May": value, "June": value, "July": value, "August": value,
        "September": value, "October": value, "November": value, "December": value
    }

def annual_to_consumption(value: float) -> Optional[Dict[str, float]]:
    if value is None:
        return None
    return {k: v / 12.0 for k, v in monthly_average_to_consumption(value).items()}

def toml_to_json(toml: dict|Path|str, allow_warnings: bool = True) -> dict:
    """Convert a TOML dictionary to an OpenBES.schema.json dictionary.

    Args:
        toml: The input TOML dictionary, file path, or string content.
        allow_warnings: If False, any warnings encountered during conversion will raise an exception.

    Returns:
        A dictionary suitable for constructing an OpenBESSpecificationV2. The json.dump() of the dictionary
        will match be valid against the OpenBES.schema.json specification.

    Raises:
        ValueError: If allow_warnings is False and any warnings were encountered during conversion.
        ValidationError: If the resulting dictionary does not validate against OpenBESSpecificationV2.
    """
    warnings: list[str] = []

    content = toml
    if isinstance(toml, (Path, str)):
        if Path(toml).is_file():
            with open(toml, 'r') as f:
                content = tomllib.loads(f.read())
        else:
            content = tomllib.loads(toml)

    # Helper functions
    def get(key: str, default: Any = None) -> Any:
        """Helper to get a value from a TOML dictionary with heuristic coercion."""
        if f"i.{key}" in content:
            value = content[f"i.{key}"]
        elif f"d.{key}" in content:
            value = content[f"d.{key}"]
        else:
            return default
        if value == "" or value is None:
            return default
        if isinstance(value, str):
            # Heuristic coercion: "", "Yes"/"No" and numeric strings
            vs = value.strip()
            if vs.lower() in ("yes", "y", "true", "t", "1"):
                return True
            if vs.lower() in ("no", "n", "false", "f", "0"):
                return False
            # numeric?
            try:
                if "." in vs:
                    return float(vs)
                return int(vs)
            except ValueError:
                return vs
        return value

    def to_range(start_key: str, end_key: str) -> Optional[Dict[str, float]]:
        start = get(start_key)
        end = get(end_key)
        if start is None or end is None:
            if start is not None or end is not None:
                warnings.append(f"Ignoring range because {start_key if start is None else end_key} is not set.")
            return None
        return {"min": start, "max": end}

    def to_duration(start_key: str, end_key: str) -> Optional[Dict[str, float]]:
        start = get(start_key)
        end = get(end_key)
        if start is None or end is None:
            if start is not None or end is not None:
                warnings.append(f"Ignoring duration because {start_key if start is None else end_key} is not set.")
            return None
        return {"start": start, "end": end}

    def has_required_keys(obj: Any, required_keys: List[str], context: str) -> bool:
        missing_keys = [k for k in required_keys if obj.get(k) is None]
        if len(missing_keys) > 0 and len(missing_keys) != len(required_keys):
            warnings.append(
                f"Skipping incomplete {context} definition.\n"
                f"\tSpecified keys: {', '.join([r for r in required_keys if r not in missing_keys])};\n"
                f"\tMissing missing keys: {', '.join(missing_keys)}.")
            return False
        return not any(missing_keys)

    parameters: dict = {}

    # Basic 1:1 conversion key/values
    for k in [
        "altitude",
        "cooling_load_factor",
        "density_of_air",
        "facade_absorption_coefficient",
        "facade_correction_factor",
        "facade_emissivity",
        "floor_correction_factor",
        "heat_capacity_correction_factor",
        "heat_capacity_joule",
        "heating_load_factor",
        "infiltration_correction_factor",
        "leakage_air_flow_dependent",
        "nia_gba_ratio",
        "pressure_of_air",
        "roof_absorption_coefficient",
        "roof_correction_factor",
        "roof_emissivity",
        "shading_correction_factor",
        "specific_heat_of_air",
        "temperature_tolerance",
        "view_factor_to_sky_facade",
        "view_factor_to_sky_roof",
        "window_correction_factor",
    ]:
        parameters[k] = get(k)

    for k in ["lighting", "occupancy"]:
        val = get(f"{k}_on_off")
        if val is not None:
            parameters[f"include_{k}"] = val
    parameters["include_appliances"] = get("appliance_on_off")

    out: dict = {"parameters": parameters}

    for k in [
        "appliances_load",
        "country",
        "holiday",
        "leakage_air_flow",
        "leakage_air_flow_independent",
        "lighting_control",
        "lighting_simultaneity_factor",
        "location",
        "max_building_occupation",
        "natural_ventilation_night",
        "typical_occupation",
    ]:
        out[k] = get(k)

    for k in [
        "biomass", "biomass_pellets", "diesel", "electricity", "LPG", "natural_gas",
    ]:
        annual_value = get(f"{k}_annual")
        if annual_value is not None:
            out[f"{k}_consumption"] = annual_to_consumption(annual_value)
    # Overwrite electricity and gas if monthly values are provided
    monthly_electricity = {k: get(f"electricity_{k.lower()}") for k in monthly_average_to_consumption(0).keys()}
    if any(v is not None for v in monthly_electricity.values()) and sum(v or 0 for v in monthly_electricity.values()) > 0:
        out["electricity_consumption"] = monthly_electricity
    monthly_gas = {k: get(f"gas_{k.lower()}") for k in monthly_average_to_consumption(0).keys()}
    if any(v is not None for v in monthly_gas.values()) and sum(v or 0 for v in monthly_gas.values()) > 0:
        out["natural_gas_consumption"] = monthly_gas

    for k in ["other_electricity_usage", "other_gas_usage"]:
        monthly_value = get(f"{k}")
        if monthly_value is not None:
            out[f"{k.replace('_usage', '')}_consumption"] = monthly_average_to_consumption(monthly_value)
    out["building_standby_electricity_consumption"] = monthly_average_to_consumption(get("building_standby_load", 0))
    for k in ["energy_generated", "energy_used"]:
        monthly_value = get(f"{k}")
        if monthly_value is not None:
            out[k] = monthly_average_to_consumption(monthly_value)

    heat_capacity = get("heat_capacity")
    if heat_capacity == "Very light":
        out["heat_capacity"] = {"Am": 2.5, "Cm": 80_000.0}
    elif heat_capacity == "Light":
        out["heat_capacity"] = {"Am": 2.5, "Cm": 110_000.0}
    if heat_capacity == "Medium":
        out["heat_capacity"] = {"Am": 2.5, "Cm": 165_000.0}
    elif heat_capacity == "Heavy":
        out["heat_capacity"] = {"Am": 3.0, "Cm": 260_000.0}
    elif heat_capacity == "Very heavy":
        out["heat_capacity"] = {"Am": 3.5, "Cm": 370_000.0}
    else:
        out["heat_capacity"] = {
            "Am": heat_capacity,
            "Cm": None
        }

    out["lighting_active_hours"] = to_duration("lighting_on_time", "lighting_off_time")

    mf = get("meteorological_file")
    if mf is not None:
        out["meteorological_file"] = get_meteorological_file(mf)

    for k in ["day", "night"]:
        out[f"setpoint_temperature_{k}"] = to_range(f"setpoint_summer_{k}", f"setpoint_winter_{k}")

    building = {}
    for k in [
        "area",
        "height",
        "length",
        "width",
        "name",
        "type",
    ]:
        building[k] = get(f"building_{k}")
    for k in [
        "floor_to_ceiling_height",
        "slab_thickness",
        "orientation_angle",
        "roof_angle",
        "solar_external_shading_summer",
        "solar_external_shading_winter",
        "terrain_class",
        "thermal_bridge_facade_ground",
        "thermal_bridge_facade_intermediate",
        "thermal_bridge_facade_roof",
        "thermal_bridge_shading",
        "thermal_bridge_window",
        "uvalue_facade",
        "uvalue_roof",
        "uvalue_window",
        "uvalue_floor",
        "window_frame_factor",
        "window_gvalue",
        "window_height",
        "window_length",
    ]:
        building[k] = get(k)

    building["window_counts"] = {}
    for o_code, o_name in [("a", "front"), ("b", "right"), ("c", "back"), ("d", "left")]:
        building["window_counts"][o_name] = []
        for n, f in enumerate(["ground", "first", "second", "third", "fourth"]):
            key = f"window_number_{f}_{o_code}1"
            building["window_counts"][o_name].append(get(key, 0))

    out["building"] = building

    zone_map = ["office", "teaching", "canteen", "common", "other"]
    zones = []
    for i, z in enumerate(zone_map, start=1):
        zone = {
            "name": get(f"zone_name_z{i}"),
            "conditioned": str(get(f"condition_z{i}", "")).lower() == "conditioned",
            "active_hours": to_duration(f"occupancy_open_{z}", f"occupancy_close_{z}"),
        }
        zone_areas = []
        for f in ["ground", "first", "second", "third", "fourth"]:
            zone_areas.append(get(f"{f}_floor_area_z{i}", 0.0))
        zone["areas"] = zone_areas
        zones.append(zone)

    out["zones"] = zones

    out["occupation_schedule"] = {
        k: bool(get(f"schedule_{k.lower()}")) for k in [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
            "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
        ]
    }

    out["heating_systems"] = []

    for i in [1, 2]:
        system = {
            "type": get(f"heating_system{i}_type"),
            "energy_source": get(f"heating_system{i}_energy_source"),
            "efficiency_cop": get(f"heating_system{i}_efficiency_cop"),
            "min_demand": get(f"heating_system{i}_min_demand"),
            "nominal_capacity": get(f"heating_system{i}_nominal_capacity"),
            "count": get(f"heating_system{i}_number"),
            "active_hours": to_duration(f"heating_system{i}_on_time", f"heating_system{i}_off_time"),
            "simultaneity": {
                z["name"]: get(f"heating_system{i}_simultaneity_factor_{zone_map[idx]}", 0.0)
                for idx, z in enumerate(zones)
            }
        }
        if has_required_keys(
                system,
                ["energy_source", "efficiency_cop", "nominal_capacity"],
                f"heating system {i}"
        ):
            out["heating_systems"].append(system)

    out["cooling_systems"] = []

    for i in [1, 2]:
        system = {
            "type": get(f"cooling_system{i}_type"),
            "energy_source": get(f"cooling_system{i}_energy_source"),
            "efficiency_ratio": get(f"cooling_system{i}_energy_efficifiency_ratio"),  # note: typo in TOML key
            "min_demand": get(f"cooling_system{i}_min_demand"),
            "nominal_capacity": get(f"cooling_system{i}_nominal_capacity"),
            "sensible_nominal_capacity": get(f"cooling_system{i}_sensible_nominal_capacity"),
            "count": get(f"cooling_system{i}_number"),
            "active_hours": to_duration(f"cooling_system{i}_on_time", f"cooling_system{i}_off_time"),
            "simultaneity": {
                z["name"]: get(f"cooling_system{i}_simultaneity_factor_{zone_map[idx]}", 0.0)
                for idx, z in enumerate(zones)
            }
        }
        if has_required_keys(
                system,
                ["energy_source", "efficiency_ratio", "nominal_capacity", "sensible_nominal_capacity"],
                f"cooling system {i}"
        ):
            out["cooling_systems"].append(system)

    out["ventilation_systems"] = []

    for i in [1, 2]:
        system = {
            "airflow": get(f"ventilation_system{i}_airflow"),
            "energy_source": get(f"ventilation_system{i}_energy_source"),
            "heat_recovery_efficiency": get(f"ventilation_system{i}_heat_recovery_efficiency"),
            "active_hours": to_duration(f"ventilation_system{i}_on_time", f"ventilation_system{i}_off_time"),
            "rated_input_power": get(f"ventilation_system{i}_rated_input_power"),
            "type": get(f"ventilation_system{i}_type"),
            "ventilated_area": get(f"ventilation_system{i}_ventilated_area"),
        }
        if has_required_keys(
                system,
                ["energy_source", "airflow"],
                f"ventilation system {i}"
        ):
            out["ventilation_systems"].append(system)

    out["lighting_systems"] = []

    for i in range(1, 7):
        system = {
            "tech": get(f"lighting_system_tech_z{i}"),
            "ballast": get(f"lighting_system_ballast_z{i}"),
            "lamp_number": get(f"lighting_system_lamp_number_z{i}"),
            "lamp_power": get(f"lighting_system_lamp_power_z{i}"),
            "luminary_number": get(f"lighting_system_luminary_number_z{i}"),
            "name": get(f"lighting_system_name_z{i}"),
            "active_hours": {"start": 0, "end": get(f"lighting_system_operating_hours_z{i}", 0)},
            "count": get(f"lighting_system_similar_zone_number_z{i}"),
            "simultaneity_factor": get(f"lighting_system_simultaneity_factor_z{i}"),
        }
        if has_required_keys(
                system,
                ["tech", "lamp_number", "lamp_power", "luminary_number", "simultaneity_factor"],
                f"lighting system {i}"
        ):
            out["lighting_systems"].append(system)

    out["hot_water_systems"] = []

    hot_water_system = {
        "demand": annual_to_consumption(get("water_demand", 0) * 365),
        "reference_temperature": get("water_reference_temperature"),
        "supply_temperature": get("water_supply_temperature"),
        "energy_source": get("water_system_energy_source"),
        "efficiency_cop": get("water_system_efficiency_cop"),
        "nominal_capacity": get("water_system_nominal_capacity"),
        "type": get("water_type"),
    }
    if has_required_keys(
            hot_water_system,
            ["demand", "reference_temperature", "supply_temperature", "energy_source", "efficiency_cop", "nominal_capacity"],
            "hot water system"
    ):
        out["hot_water_systems"].append(hot_water_system)

    out["courtyards"] = []

    courtyard = {
        "length": get("courtyard_length"),
        "width": get("courtyard_width"),
        "count": get("courtyard_number"),
    }
    if has_required_keys(courtyard, ["length", "width", "count"], "courtyard") and courtyard["count"] > 0:
        out["courtyards"].append(courtyard)

    out["open_courtyards"] = {}

    for o_code, o_name in [("a", "front"), ("b", "right"), ("c", "back"), ("d", "left")]:
        open_courtyard = {
            "depth": get(f"open_courtyard_depth_{o_code}1"),
            "count": get(f"open_courtyard_number_{o_code}", 0),
        }
        if has_required_keys(open_courtyard, ['depth'], f"open courtyard {o_name}") and open_courtyard["count"] > 0:
            out["open_courtyards"][o_name] = open_courtyard

    OpenBESSpecificationV2.model_validate_json(json.dumps(out))

    if not allow_warnings and len(warnings) > 0:
        raise ValueError("Warnings during TOML to JSON conversion:\n" + "\n".join(warnings))

    return out

"""Converting legacy TOML to JSON.

The historical TOML format used by OpenBES only captures a flattened view of
the data model.  The new JSON Schema-based data
model is richer (allowing arbitrary list lengths, nested structures, etc.), so
these helpers provide a best-effort conversion layer.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, Dict, Optional, List

from openbes.schemas import OpenBESSpecificationV2
from openbes.types import normalize_meteorological_file_path


def monthly_average_to_consumption(value: float = None) -> Optional[Dict[str, float]]:
    if value is None:
        return None
    return {
        "January": value,
        "February": value,
        "March": value,
        "April": value,
        "May": value,
        "June": value,
        "July": value,
        "August": value,
        "September": value,
        "October": value,
        "November": value,
        "December": value,
    }


def annual_to_consumption(value: float) -> Optional[Dict[str, float]]:
    if value is None:
        return None
    return {k: v / 12.0 for k, v in monthly_average_to_consumption(value).items()}


def toml_to_json(toml: dict | Path | str, allow_warnings: bool = True) -> dict:
    """Convert a TOML dictionary to an OpenBES.schema.json dictionary.

    Only keys that are actually present in the TOML input are emitted; no
    synthetic defaults are introduced.  An empty TOML input ({}) therefore
    produces an empty JSON output ({}).

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
            with open(toml, "r") as f:
                content = tomllib.loads(f.read())
        else:
            content = tomllib.loads(toml)

    # Helper functions
    def get(key: str, default: Any = None) -> Any:
        """Helper to get a value from a TOML dictionary with heuristic coercion.
        Returns *default* (None by default) when the key is absent or blank.
        """
        if f"i.{key}" in content:
            value = content[f"i.{key}"]
        elif f"d.{key}" in content:
            value = content[f"d.{key}"]
        else:
            return default
        if value == "" or value is None:
            return default
        if isinstance(value, str):
            vs = value.strip()
            if vs.lower() in ("yes", "y", "true", "t", "1"):
                return True
            if vs.lower() in ("no", "n", "false", "f", "0"):
                return False
            try:
                if "." in vs:
                    return float(vs)
                return int(vs)
            except ValueError:
                return vs
        return value

    def present(key: str) -> bool:
        """Return True if the key exists in the TOML content with a non-blank value."""
        return get(key) is not None

    def to_range(start_key: str, end_key: str) -> Optional[Dict[str, float]]:
        start = get(start_key)
        end = get(end_key)
        if start is None or end is None:
            if start is not None or end is not None:
                warnings.append(
                    f"Ignoring range because {start_key if start is None else end_key} is not set."
                )
            return None
        return {"min": start, "max": end}

    def to_duration(start_key: str, end_key: str) -> Optional[Dict[str, float]]:
        start = get(start_key)
        end = get(end_key)
        if start is None or end is None:
            if start is not None or end is not None:
                warnings.append(
                    f"Ignoring duration because {start_key if start is None else end_key} is not set."
                )
            return None
        return {"start": start, "end": end}

    def has_required_keys(obj: Any, required_keys: List[str], context: str) -> bool:
        missing_keys = [k for k in required_keys if obj.get(k) is None]
        if len(missing_keys) > 0 and len(missing_keys) != len(required_keys):
            warnings.append(
                f"Skipping incomplete {context} definition.\n"
                f"\tSpecified keys: {', '.join([r for r in required_keys if r not in missing_keys])};\n"
                f"\tMissing missing keys: {', '.join(missing_keys)}."
            )
            return False
        return not any(missing_keys)

    out: dict = {}

    # ── parameters ────────────────────────────────────────────────────────────
    parameters: dict = {}

    for k in [
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
        "view_factor_to_sky_facade",
        "view_factor_to_sky_roof",
        "window_correction_factor",
    ]:
        v = get(k)
        if v is not None:
            parameters[k] = v

    for k in ["lighting", "occupancy"]:
        val = get(f"{k}_on_off")
        if val is not None:
            parameters[f"include_{k}"] = val

    appliance_val = get("appliance_on_off")
    if appliance_val is not None:
        parameters["include_appliances"] = appliance_val

    # Only include window_angular_correction_factors when at least one c-value
    # was explicitly set in the TOML.
    wacf_raw = [get(f"window_optical_c{i}") for i in range(1, 6)]
    if any(v is not None for v in wacf_raw):
        parameters["window_angular_correction_factors"] = [v if v is not None else 0.0 for v in wacf_raw]

    if parameters:
        out["parameters"] = parameters

    # ── simple top-level scalars ───────────────────────────────────────────────
    for k in [
        "appliances_load",
        "country",
        "holiday",
        "leakage_air_flow",
        "leakage_air_flow_independent",
        "lighting_control",
        "lighting_simultaneity_factor",
        "max_building_occupation",
        "natural_ventilation_night",
        "typical_occupation",
    ]:
        v = get(k)
        if v is not None:
            out[k] = v

    if get("altitude") is not None:
        out["elevation"] = get("altitude")

    # ── consumption fields ─────────────────────────────────────────────────────
    for k in [
        "biomass",
        "biomass_pellets",
        "diesel",
        "electricity",
        "LPG",
        "natural_gas",
    ]:
        annual_value = get(f"{k}_annual")
        if annual_value is not None:
            out[f"{k}_consumption"] = annual_to_consumption(annual_value)

    # Monthly electricity overrides annual if any monthly value is present and non-zero
    monthly_electricity = {
        k: get(f"electricity_{k.lower()}")
        for k in monthly_average_to_consumption(0).keys()
    }
    if (
        any(v is not None for v in monthly_electricity.values())
        and sum(v or 0 for v in monthly_electricity.values()) > 0
    ):
        out["electricity_consumption"] = monthly_electricity

    monthly_gas = {
        k: get(f"gas_{k.lower()}") for k in monthly_average_to_consumption(0).keys()
    }
    if (
        any(v is not None for v in monthly_gas.values())
        and sum(v or 0 for v in monthly_gas.values()) > 0
    ):
        out["natural_gas_consumption"] = monthly_gas

    for k in ["other_electricity_usage", "other_gas_usage"]:
        monthly_value = get(k)
        if monthly_value is not None:
            out[f"{k.replace('_usage', '')}_consumption"] = (
                monthly_average_to_consumption(monthly_value)
            )

    building_standby_raw = get("building_standby_load")
    if building_standby_raw is not None:
        out["building_standby_electricity_consumption"] = monthly_average_to_consumption(
            building_standby_raw
        )

    for k in ["energy_generated", "energy_used"]:
        monthly_value = get(k)
        if monthly_value is not None:
            out[k] = monthly_average_to_consumption(monthly_value)

    # ── heat_capacity ──────────────────────────────────────────────────────────
    heat_capacity = get("heat_capacity")
    if heat_capacity == "Very light":
        out["heat_capacity"] = {"Am": 2.5, "Cm": 80_000.0}
    elif heat_capacity == "Light":
        out["heat_capacity"] = {"Am": 2.5, "Cm": 110_000.0}
    elif heat_capacity == "Medium":
        out["heat_capacity"] = {"Am": 2.5, "Cm": 165_000.0}
    elif heat_capacity == "Heavy":
        out["heat_capacity"] = {"Am": 3.0, "Cm": 260_000.0}
    elif heat_capacity == "Very heavy":
        out["heat_capacity"] = {"Am": 3.5, "Cm": 370_000.0}
    elif heat_capacity is not None:
        # Custom numeric value — only emit if we actually have it
        out["heat_capacity"] = {"Am": heat_capacity, "Cm": None}

    # ── lighting active hours ──────────────────────────────────────────────────
    lighting_hours = to_duration("lighting_on_time", "lighting_off_time")
    if lighting_hours is not None:
        out["lighting_active_hours"] = lighting_hours

    # ── meteorological file ────────────────────────────────────────────────────
    mf = get("meteorological_file")
    if mf is not None:
        out["meteorological_file_path"] = normalize_meteorological_file_path(mf)

    # ── setpoint temperatures ──────────────────────────────────────────────────
    for k in ["day", "night"]:
        rng = to_range(f"setpoint_summer_{k}", f"setpoint_winter_{k}")
        if rng is not None:
            out[f"setpoint_temperature_{k}"] = rng

    # ── building ───────────────────────────────────────────────────────────────
    building: dict = {}
    for k in ["area", "height", "length", "width", "name", "type"]:
        v = get(f"building_{k}")
        if v is not None:
            building[k] = v

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
        v = get(k)
        if v is not None:
            building[k] = v

    # window_counts: emit a side whenever any of its TOML keys are present
    # (value 0 is valid and must round-trip, so we can't guard on non-zero).
    window_counts: dict = {}
    for o_code, o_name in [
        ("a", "front"),
        ("b", "right"),
        ("c", "back"),
        ("d", "left"),
    ]:
        floors = ["ground", "first", "second", "third", "fourth"]
        if any(present(f"window_number_{f}_{o_code}1") for f in floors):
            window_counts[o_name] = [get(f"window_number_{f}_{o_code}1", 0) for f in floors]
    if window_counts:
        building["window_counts"] = window_counts

    if building:
        out["building"] = building

    # ── zones ─────────────────────────────────────────────────────────────────
    zone_map = ["office", "teaching", "canteen", "common", "other"]
    zones = []
    floor_count = 0
    for i, z in enumerate(zone_map, start=1):
        zone_name = get(f"zone_name_z{i}")
        if zone_name is None:
            # Skip zones with no name set at all
            continue
        zone_areas = [
            get(f"{f}_floor_area_z{i}", 0.0)
            for f in ["ground", "first", "second", "third", "fourth"]
        ]
        floor_count = max(floor_count, sum(1 for a in zone_areas if a is not None and a > 0))
        zone: dict = {
            "name": zone_name,
            "areas": zone_areas,
        }
        condition_val = get(f"condition_z{i}")
        if condition_val is not None:
            zone["conditioned"] = str(condition_val).lower() == "conditioned"
        active = to_duration(f"occupancy_open_{z}", f"occupancy_close_{z}")
        if active is not None:
            zone["active_hours"] = active
        zones.append(zone)

    if zones:
        out["zones"] = zones

    if floor_count > 0:
        out["building"]["floor_count"] = floor_count

    # ── occupation_schedule ────────────────────────────────────────────────────
    schedule_keys = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
        "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
    ]
    occupation_schedule = {}
    for k in schedule_keys:
        v = get(f"schedule_{k.lower()}")
        if v is not None:
            occupation_schedule[k] = bool(v)
    if occupation_schedule:
        out["occupation_schedule"] = occupation_schedule

    # ── heating systems ────────────────────────────────────────────────────────
    heating_systems = []
    for i in [1, 2]:
        system = {
            "type": get(f"heating_system{i}_type"),
            "energy_source": get(f"heating_system{i}_energy_source"),
            "efficiency_cop": get(f"heating_system{i}_efficiency_cop"),
            "min_demand": get(f"heating_system{i}_min_demand"),
            "nominal_capacity": get(f"heating_system{i}_nominal_capacity"),
            "count": get(f"heating_system{i}_number"),
            "active_hours": to_duration(
                f"heating_system{i}_on_time", f"heating_system{i}_off_time"
            ),
            "simultaneity": {
                z["name"]: get(
                    f"heating_system{i}_simultaneity_factor_{zone_map[idx]}", 0.0
                )
                for idx, z in enumerate(zones)
            },
        }
        if has_required_keys(
            system,
            ["energy_source", "efficiency_cop", "nominal_capacity"],
            f"heating system {i}",
        ):
            heating_systems.append(system)
    if heating_systems:
        out["heating_systems"] = heating_systems

    # ── cooling systems ────────────────────────────────────────────────────────
    cooling_systems = []
    for i in [1, 2]:
        system = {
            "type": get(f"cooling_system{i}_type"),
            "energy_source": get(f"cooling_system{i}_energy_source"),
            "efficiency_ratio": get(f"cooling_system{i}_energy_efficifiency_ratio"),
            "min_demand": get(f"cooling_system{i}_min_demand"),
            "nominal_capacity": get(f"cooling_system{i}_nominal_capacity"),
            "sensible_nominal_capacity": get(
                f"cooling_system{i}_sensible_nominal_capacity"
            ),
            "count": get(f"cooling_system{i}_number"),
            "active_hours": to_duration(
                f"cooling_system{i}_on_time", f"cooling_system{i}_off_time"
            ),
            "simultaneity": {
                z["name"]: get(
                    f"cooling_system{i}_simultaneity_factor_{zone_map[idx]}", 0.0
                )
                for idx, z in enumerate(zones)
            },
        }
        if has_required_keys(
            system,
            [
                "energy_source",
                "efficiency_ratio",
                "nominal_capacity",
                "sensible_nominal_capacity",
            ],
            f"cooling system {i}",
        ):
            cooling_systems.append(system)
    if cooling_systems:
        out["cooling_systems"] = cooling_systems

    # ── ventilation systems ────────────────────────────────────────────────────
    ventilation_systems = []
    for i in [1, 2]:
        system = {
            "airflow": get(f"ventilation_system{i}_airflow"),
            "energy_source": get(f"ventilation_system{i}_energy_source"),
            "heat_recovery_efficiency": get(
                f"ventilation_system{i}_heat_recovery_efficiency"
            ),
            "active_hours": to_duration(
                f"ventilation_system{i}_on_time", f"ventilation_system{i}_off_time"
            ),
            "rated_input_power": get(f"ventilation_system{i}_rated_input_power"),
            "type": get(f"ventilation_system{i}_type"),
            "ventilated_area": get(f"ventilation_system{i}_ventilated_area"),
        }
        if has_required_keys(
            system, ["energy_source", "airflow"], f"ventilation system {i}"
        ):
            ventilation_systems.append(system)
    if ventilation_systems:
        out["ventilation_systems"] = ventilation_systems

    # ── lighting systems ───────────────────────────────────────────────────────
    lighting_systems = []
    for i in range(1, 7):
        system = {
            "tech": get(f"lighting_system_tech_z{i}"),
            "ballast": get(f"lighting_system_ballast_z{i}"),
            "lamp_number": get(f"lighting_system_lamp_number_z{i}"),
            "lamp_power": get(f"lighting_system_lamp_power_z{i}"),
            "luminary_number": get(f"lighting_system_luminary_number_z{i}"),
            "name": get(f"lighting_system_name_z{i}"),
            "active_hours": {
                "start": 0,
                "end": get(f"lighting_system_operating_hours_z{i}", 0),
            },
            "count": get(f"lighting_system_similar_zone_number_z{i}"),
            "simultaneity_factor": get(f"lighting_system_simultaneity_factor_z{i}"),
        }
        if has_required_keys(
            system,
            [
                "tech",
                "lamp_number",
                "lamp_power",
                "luminary_number",
                "simultaneity_factor",
            ],
            f"lighting system {i}",
        ):
            lighting_systems.append(system)
    if lighting_systems:
        out["lighting_systems"] = lighting_systems

    # ── hot water systems ──────────────────────────────────────────────────────
    hot_water_systems = []
    water_demand_raw = get("water_demand")
    hot_water_system = {
        "demand": annual_to_consumption(water_demand_raw * 365) if water_demand_raw is not None else None,
        "reference_temperature": get("water_reference_temperature"),
        "supply_temperature": get("water_supply_temperature"),
        "energy_source": get("water_system_energy_source"),
        "efficiency_cop": get("water_system_efficiency_cop"),
        "nominal_capacity": get("water_system_nominal_capacity"),
        "type": get("water_type"),
    }
    if has_required_keys(
        hot_water_system,
        [
            "demand",
            "reference_temperature",
            "supply_temperature",
            "energy_source",
            "efficiency_cop",
            "nominal_capacity",
        ],
        "hot water system",
    ):
        hot_water_systems.append(hot_water_system)
    if hot_water_systems:
        out["hot_water_systems"] = hot_water_systems

    # ── courtyards ─────────────────────────────────────────────────────────────
    courtyards = []
    courtyard = {
        "length": get("courtyard_length"),
        "width": get("courtyard_width"),
        "count": get("courtyard_number"),
    }
    if (
        has_required_keys(courtyard, ["length", "width", "count"], "courtyard")
        and courtyard["count"] > 0
    ):
        courtyards.append(courtyard)
    if courtyards:
        out["courtyards"] = courtyards

    # ── open_courtyards ────────────────────────────────────────────────────────
    open_courtyards: dict = {}
    for o_code, o_name in [
        ("a", "front"),
        ("b", "right"),
        ("c", "back"),
        ("d", "left"),
    ]:
        open_courtyard = {
            "depth": get(f"open_courtyard_depth_{o_code}1"),
            "count": get(f"open_courtyard_number_{o_code}", 0),
        }
        if (
            has_required_keys(open_courtyard, ["depth"], f"open courtyard {o_name}")
            and open_courtyard["count"] > 0
        ):
            open_courtyards[o_name] = open_courtyard
    if open_courtyards:
        out["open_courtyards"] = open_courtyards

    OpenBESSpecificationV2.model_validate(out)

    if not allow_warnings and len(warnings) > 0:
        raise ValueError(
            "Warnings during TOML to JSON conversion:\n" + "\n".join(warnings)
        )

    return out

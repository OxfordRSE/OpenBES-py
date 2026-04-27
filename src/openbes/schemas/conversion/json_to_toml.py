"""Converting OpenBESSpecificationV2 JSON to legacy TOML.

The historical TOML format used by OpenBES only captures a flattened view of
the data model.  The new `openbes.schemas.OpenBESSpecificationV2`
model is richer (allowing arbitrary list lengths, nested structures, etc.), so
these helpers provide a best-effort conversion layer.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, List, Tuple, Dict

from openbes.schemas import (
    CoolingSystem,
    HeatingSystem,
    VentilationSystem,
)
from openbes.schemas import (
    Consumption,
    OpenBESSpecificationV2,
    ZoneSimultaneity,
)
from openbes.types import meteorological_file_path_to_toml_value


def _len(obj: Any) -> int:
    """Return the length of the object, or 0 if it is None."""
    if obj is None:
        return 0
    return len(obj)


def json_to_toml(
    spec: OpenBESSpecificationV2 | Dict[str, Any] | str, allow_warnings: bool = True
) -> dict:
    """Convert an OpenBESSpecificationV2 or its JSON representation to a TOML mapping.

    Only TOML keys that correspond to fields actually present in the incoming JSON are
    emitted.  Pydantic defaults that were not explicitly set are silently skipped, so
    an empty input ({}) produces an empty output ({}).

    Args:
        spec: The OpenBESSpecificationV2 instance, dictionary, or JSON string to convert.
        allow_warnings: If True, allow lossy conversions with warnings. If False, raise errors on lossy conversions.
    Returns:
        A dictionary representing the TOML mapping (empty-string values are not included).
    Raises:
        ValidationError: If the input does not validate against OpenBESSpecificationV2.
        ValueError: If the conversion is lossy and allow_warnings is False.
    """
    if isinstance(spec, str):
        spec = OpenBESSpecificationV2(**json.loads(spec))
    elif isinstance(spec, dict):
        spec = OpenBESSpecificationV2(**spec)

    toml: dict = {}

    def set_if(key: str, value: Any) -> None:
        """Add *key* to the output only when *value* is not None/empty-string."""
        if value is not None and value != "":
            if isinstance(value, Enum):
                value = value.value
            toml[key] = value

    def annual_consumption(consumption: Consumption) -> float:
        if consumption is None:
            return 0.0
        return sum(dict(consumption).values())

    # ── parameters ─────────────────────────────────────────────────────────────
    p = spec.parameters
    if p is not None:
        pset = p.model_fields_set

        # Each parameter field maps 1-to-1 to a TOML d. key.
        for attr, toml_key in [
            ("elevation", "d.altitude"),
            ("cooling_load_factor", "d.cooling_load_factor"),
            ("density_of_air", "d.density_of_air"),
            ("facade_absorption_coefficient", "d.facade_absorption_coefficient"),
            ("facade_correction_factor", "d.facade_correction_factor"),
            ("facade_emissivity", "d.facade_emissivity"),
            ("floor_correction_factor", "d.floor_correction_factor"),
            ("heat_capacity_correction_factor", "d.heat_capacity_correction_factor"),
            ("heat_capacity_joule", "d.heat_capacity_joule"),
            ("heating_load_factor", "d.heating_load_factor"),
            ("infiltration_correction_factor", "d.infiltration_correction_factor"),
            ("leakage_air_flow_dependent", "d.leakage_air_flow_dependent"),
            ("nia_gba_ratio", "d.nia_gba_ratio"),
            ("pressure_of_air", "d.pressure_of_air"),
            ("roof_absorption_coefficient", "d.roof_absorption_coefficient"),
            ("roof_correction_factor", "d.roof_correction_factor"),
            ("roof_emissivity", "d.roof_emissivity"),
            ("shading_correction_factor", "d.shading_correction_factor"),
            ("specific_heat_of_air", "d.specific_heat_of_air"),
            ("view_factor_to_sky_facade", "d.view_factor_to_sky_facade"),
            ("view_factor_to_sky_roof", "d.view_factor_to_sky_roof"),
            ("window_correction_factor", "d.window_correction_factor"),
        ]:
            if attr in pset:
                set_if(toml_key, getattr(p, attr))

        if "include_appliances" in pset:
            toml["d.appliance_on_off"] = 1 if p.include_appliances else 0
        if "include_lighting" in pset:
            toml["d.lighting_on_off"] = 1 if p.include_lighting else 0
        if "include_occupancy" in pset:
            toml["d.occupancy_on_off"] = 1 if p.include_occupancy else 0

        if (
            "window_angular_correction_factors" in pset
            and p.window_angular_correction_factors
        ):
            for idx, val in enumerate(p.window_angular_correction_factors):
                set_if(f"d.window_optical_c{idx + 1}", val)

    # ── building ───────────────────────────────────────────────────────────────
    b = spec.building
    if b is not None:
        bset = b.model_fields_set

        for attr, toml_key in [
            ("area", "i.building_area"),
            ("height", "i.building_height"),
            ("length", "i.building_length"),
            ("width", "i.building_width"),
            ("name", "i.building_name"),
            ("type", "i.building_type"),
        ]:
            if attr in bset:
                set_if(toml_key, getattr(b, attr))

        for attr, toml_key in [
            ("floor_to_ceiling_height", "i.floor_to_ceiling_height"),
            ("slab_thickness", "i.slab_thickness"),
            ("orientation_angle", "i.orientation_angle"),
            ("roof_angle", "i.roof_angle"),
            ("solar_external_shading_summer", "i.solar_external_shading_summer"),
            ("solar_external_shading_winter", "i.solar_external_shading_winter"),
            ("terrain_class", "i.terrain_class"),
            ("uvalue_facade", "i.uvalue_facade"),
            ("uvalue_roof", "i.uvalue_roof"),
            ("uvalue_window", "i.uvalue_window"),
            ("uvalue_floor", "i.uvalue_floor"),
            ("window_frame_factor", "i.window_frame_factor"),
            ("window_gvalue", "i.window_gvalue"),
            ("window_height", "i.window_height"),
            ("window_length", "i.window_length"),
        ]:
            if attr in bset:
                set_if(toml_key, getattr(b, attr))

        # thermal_bridge booleans: only emit when explicitly set
        for attr, toml_key in [
            ("thermal_bridge_facade_ground", "i.thermal_bridge_facade_ground"),
            (
                "thermal_bridge_facade_intermediate",
                "i.thermal_bridge_facade_intermediate",
            ),
            ("thermal_bridge_facade_roof", "i.thermal_bridge_facade_roof"),
            ("thermal_bridge_shading", "i.thermal_bridge_shading"),
            ("thermal_bridge_window", "i.thermal_bridge_window"),
        ]:
            if attr in bset:
                toml[toml_key] = "Yes" if getattr(b, attr) else "No"

        if "window_counts" in bset and b.window_counts is not None:
            for o_code, o_name in [
                ("a", "front"),
                ("b", "right"),
                ("c", "back"),
                ("d", "left"),
            ]:
                counts = getattr(b.window_counts, o_name, None)
                if counts is not None:  # emit even if all-zero; None means side not set
                    floors = ["ground", "first", "second", "third", "fourth"]
                    for f_idx, floor in enumerate(floors):
                        if f_idx < len(counts):
                            # Use toml[] directly so 0 is preserved (set_if skips 0)
                            toml[f"i.window_number_{floor}_{o_code}1"] = counts[f_idx]

    # ── zones ──────────────────────────────────────────────────────────────────
    zone_map = [
        {
            "default_name": "office",
            "default_str": "Office area",
            "zone": spec.zones[0] if _len(spec.zones) >= 1 else None,
        },
        {
            "default_name": "teaching",
            "default_str": "Teaching",
            "zone": spec.zones[1] if _len(spec.zones) >= 2 else None,
        },
        {
            "default_name": "canteen",
            "default_str": "Canteen",
            "zone": spec.zones[2] if _len(spec.zones) >= 3 else None,
        },
        {
            "default_name": "common",
            "default_str": "Common areas",
            "zone": spec.zones[3] if _len(spec.zones) >= 4 else None,
        },
        {
            "default_name": "other",
            "default_str": "Other spaces",
            "zone": spec.zones[4] if _len(spec.zones) >= 5 else None,
        },
    ]

    if spec.zones:
        for idx, zm in enumerate(zone_map):
            zone = zm["zone"]
            n = idx + 1
            if zone is None:
                continue
            toml[f"i.zone_name_z{n}"] = zone.name
            zset = zone.model_fields_set
            if "conditioned" in zset:
                toml[f"i.condition_z{n}"] = (
                    "Conditioned" if zone.conditioned else "Unconditioned"
                )
            if "active_hours" in zset and zone.active_hours is not None:
                z_name = zm["default_name"]
                # First 3 zones: i. prefix; last 2: d. prefix
                prefix = "d" if idx >= 3 else "i"
                toml[f"{prefix}.occupancy_open_{z_name}"] = zone.active_hours.start
                toml[f"{prefix}.occupancy_close_{z_name}"] = zone.active_hours.end
            if "areas" in zset:
                floors = ["ground", "first", "second", "third", "fourth"]
                for f_idx, floor in enumerate(floors):
                    if f_idx < len(zone.areas):
                        set_if(f"i.{floor}_floor_area_z{n}", zone.areas[f_idx])

    # ── occupation schedule ────────────────────────────────────────────────────
    if spec.occupation_schedule is not None:
        oset = spec.occupation_schedule.model_fields_set
        for k, v in dict(spec.occupation_schedule).items():
            if k in oset and v is not None:
                toml[f"i.schedule_{k.lower()}"] = v

    # ── heat capacity ──────────────────────────────────────────────────────────
    if spec.heat_capacity is not None:
        hc = spec.heat_capacity.root
        if isinstance(hc, str):
            # PresetHeatCapacity — pass the string value through directly
            toml["i.heat_capacity"] = hc
        else:
            # CustomHeatCapacity object — reverse-lookup by Cm value
            if hc.Am is not None:
                if hc.Cm == 80_000.0:
                    toml["i.heat_capacity"] = "Very light"
                elif hc.Cm == 110_000.0:
                    toml["i.heat_capacity"] = "Light"
                elif hc.Cm == 165_000.0:
                    toml["i.heat_capacity"] = "Medium"
                elif hc.Cm == 260_000.0:
                    toml["i.heat_capacity"] = "Heavy"
                elif hc.Cm == 370_000.0:
                    toml["i.heat_capacity"] = "Very heavy"
                else:
                    toml["i.heat_capacity"] = "Custom Value"
                    toml["d.advanced_heat_capacity_am"] = hc.Am

    # ── simple top-level scalars ───────────────────────────────────────────────
    sset = spec.model_fields_set

    for attr, toml_key in [
        ("appliances_load", "i.appliances_load"),
        ("leakage_air_flow", "i.leakage_air_flow"),
        ("leakage_air_flow_independent", "i.leakage_air_flow_independent"),
        ("lighting_control", "i.lighting_control"),
        ("lighting_simultaneity_factor", "i.lighting_simultaneity_factor"),
        ("max_building_occupation", "i.max_building_occupation"),
        ("natural_ventilation_night", "i.natural_ventilation_night"),
        ("typical_occupation", "i.typical_occupation"),
    ]:
        if attr in sset:
            set_if(toml_key, getattr(spec, attr))

    # fec_coefficients: if it is a preset country string, write as 'i.country'.
    # Custom coefficient objects have no direct TOML representation (lossy conversion).
    if "fec_coefficients" in sset and spec.fec_coefficients is not None:
        fec = spec.fec_coefficients.root
        if isinstance(fec, str):
            set_if("i.country", fec)
        elif allow_warnings:
            import warnings

            warnings.warn(
                "fec_coefficients with custom values cannot be represented in TOML format; "
                "the country field will be omitted.",
                UserWarning,
                stacklevel=2,
            )
        else:
            raise ValueError(
                "fec_coefficients with custom values cannot be losslessly converted to TOML."
            )

    if "holiday" in sset:
        toml["i.holiday"] = "Yes" if spec.holiday else "No"

    if "lighting_active_hours" in sset and spec.lighting_active_hours is not None:
        toml["i.lighting_on_time"] = spec.lighting_active_hours.start
        toml["i.lighting_off_time"] = spec.lighting_active_hours.end

    if "meteorological_file_path" in sset:
        set_if(
            "i.meteorological_file",
            meteorological_file_path_to_toml_value(spec.meteorological_file_path),
        )

    if "setpoint_temperature_day" in sset and spec.setpoint_temperature_day is not None:
        set_if("i.setpoint_summer_day", spec.setpoint_temperature_day.min)
        set_if("i.setpoint_winter_day", spec.setpoint_temperature_day.max)

    if (
        "setpoint_temperature_night" in sset
        and spec.setpoint_temperature_night is not None
    ):
        set_if("i.setpoint_summer_night", spec.setpoint_temperature_night.min)
        set_if("i.setpoint_winter_night", spec.setpoint_temperature_night.max)

    # ── consumption fields ─────────────────────────────────────────────────────
    for attr, toml_key in [
        ("biomass_consumption", "i.biomass_annual"),
        ("biomass_pellets_consumption", "i.biomass_pellets_annual"),
        ("diesel_consumption", "i.diesel_annual"),
        ("LPG_consumption", "i.LPG_annual"),
    ]:
        if attr in sset and getattr(spec, attr) is not None:
            toml[toml_key] = annual_consumption(getattr(spec, attr))

    if "electricity_consumption" in sset and spec.electricity_consumption is not None:
        for month, v in dict(spec.electricity_consumption).items():
            set_if(f"i.electricity_{month.lower()}", v)

    if "natural_gas_consumption" in sset and spec.natural_gas_consumption is not None:
        for month, v in dict(spec.natural_gas_consumption).items():
            set_if(f"i.gas_{month.lower()}", v)

    if (
        "other_electricity_consumption" in sset
        and spec.other_electricity_consumption is not None
    ):
        toml["i.other_electricity_usage"] = (
            annual_consumption(spec.other_electricity_consumption) / 12
        )

    if "other_gas_consumption" in sset and spec.other_gas_consumption is not None:
        toml["i.other_gas_usage"] = annual_consumption(spec.other_gas_consumption) / 12

    if (
        "building_standby_electricity_consumption" in sset
        and spec.building_standby_electricity_consumption is not None
    ):
        toml["i.building_standby_load"] = (
            annual_consumption(spec.building_standby_electricity_consumption) / 12
        )

    if "energy_generated" in sset and spec.energy_generated is not None:
        toml["i.energy_generated"] = annual_consumption(spec.energy_generated)

    if "energy_used" in sset and spec.energy_used is not None:
        toml["i.energy_used"] = annual_consumption(spec.energy_used)

    # ── heating systems ────────────────────────────────────────────────────────
    def get_simultaneity_factors(zs: ZoneSimultaneity) -> List[Tuple[str, Any]]:
        out = []
        for zm in zone_map:
            zone = zm["zone"]
            if zone is not None and zs is not None and zone.name in zs.root:
                out.append((zm["default_name"], zs.root[zone.name]))
        return out

    def heating_system_to_toml(hs: HeatingSystem, n: int) -> None:
        d = "d" if n == 2 else "i"
        set_if(f"{d}.heating_system{n}_energy_source", hs.energy_source)
        set_if(f"{d}.heating_system{n}_efficiency_cop", hs.efficiency_cop)
        set_if(f"{d}.heating_system{n}_nominal_capacity", hs.nominal_capacity)
        # min_demand is always a d. (parameter) key regardless of system number,
        # because from_toml passes d. keys to OpenBESParameters, not OpenBESSpecification.
        set_if(f"d.heating_system{n}_min_demand", hs.min_demand)
        set_if(f"{d}.heating_system{n}_number", hs.count)
        set_if(f"{d}.heating_system{n}_type", hs.type)
        if hs.active_hours is not None:
            toml[f"{d}.heating_system{n}_on_time"] = hs.active_hours.start
            toml[f"{d}.heating_system{n}_off_time"] = hs.active_hours.end
        for zone_name, factor in get_simultaneity_factors(hs.simultaneity):
            toml[f"{d}.heating_system{n}_simultaneity_factor_{zone_name}"] = factor

    if spec.heating_systems:
        for i, hs in enumerate(spec.heating_systems[:2], start=1):
            heating_system_to_toml(hs, i)

    # ── cooling systems ────────────────────────────────────────────────────────
    def cooling_system_to_toml(cs: CoolingSystem, n: int) -> None:
        d = "d" if n == 2 else "i"
        set_if(f"{d}.cooling_system{n}_energy_source", cs.energy_source)
        set_if(f"{d}.cooling_system{n}_energy_efficifiency_ratio", cs.efficiency_ratio)
        set_if(f"{d}.cooling_system{n}_nominal_capacity", cs.nominal_capacity)
        set_if(
            f"{d}.cooling_system{n}_sensible_nominal_capacity",
            cs.sensible_nominal_capacity,
        )
        # min_demand is always a d. (parameter) key regardless of system number.
        set_if(f"d.cooling_system{n}_min_demand", cs.min_demand)
        set_if(f"{d}.cooling_system{n}_number", cs.count)
        set_if(f"{d}.cooling_system{n}_type", cs.type)
        if cs.active_hours is not None:
            toml[f"{d}.cooling_system{n}_on_time"] = cs.active_hours.start
            toml[f"{d}.cooling_system{n}_off_time"] = cs.active_hours.end
        for zone_name, factor in get_simultaneity_factors(cs.simultaneity):
            toml[f"{d}.cooling_system{n}_simultaneity_factor_{zone_name}"] = factor

    if spec.cooling_systems:
        for i, cs in enumerate(spec.cooling_systems[:2], start=1):
            cooling_system_to_toml(cs, i)

    # ── ventilation systems ────────────────────────────────────────────────────
    def ventilation_system_to_toml(vs: VentilationSystem, n: int) -> None:
        d = "d" if n == 2 else "i"
        set_if(f"{d}.ventilation_system{n}_energy_source", vs.energy_source)
        set_if(f"{d}.ventilation_system{n}_airflow", vs.airflow)
        set_if(
            f"{d}.ventilation_system{n}_heat_recovery_efficiency",
            vs.heat_recovery_efficiency,
        )
        set_if(f"{d}.ventilation_system{n}_rated_input_power", vs.rated_input_power)
        set_if(f"{d}.ventilation_system{n}_type", vs.type)
        set_if(f"{d}.ventilation_system{n}_ventilated_area", vs.ventilated_area)
        if vs.active_hours is not None:
            toml[f"{d}.ventilation_system{n}_on_time"] = vs.active_hours.start
            toml[f"{d}.ventilation_system{n}_off_time"] = vs.active_hours.end

    if spec.ventilation_systems:
        for i, vs in enumerate(spec.ventilation_systems[:2], start=1):
            ventilation_system_to_toml(vs, i)

    # ── lighting systems ───────────────────────────────────────────────────────
    if spec.lighting_systems:
        for i, ls in enumerate(spec.lighting_systems[:6], start=1):
            set_if(f"i.lighting_system_tech_z{i}", ls.tech)
            set_if(f"i.lighting_system_ballast_z{i}", ls.ballast)
            set_if(f"i.lighting_system_lamp_number_z{i}", ls.lamp_number)
            set_if(f"i.lighting_system_lamp_power_z{i}", ls.lamp_power)
            set_if(f"i.lighting_system_luminary_number_z{i}", ls.luminary_number)
            set_if(f"i.lighting_system_name_z{i}", ls.name)
            set_if(f"i.lighting_system_similar_zone_number_z{i}", ls.count)
            set_if(
                f"i.lighting_system_simultaneity_factor_z{i}", ls.simultaneity_factor
            )
            if ls.active_hours is not None:
                toml[f"i.lighting_system_operating_hours_z{i}"] = (
                    ls.active_hours.end - ls.active_hours.start
                )

    # ── hot water systems ──────────────────────────────────────────────────────
    if spec.hot_water_systems:
        ws = spec.hot_water_systems[0]
        if ws.demand is not None:
            toml["i.water_demand"] = annual_consumption(ws.demand) / 365
        set_if("i.water_reference_temperature", ws.reference_temperature)
        set_if("i.water_supply_temperature", ws.supply_temperature)
        set_if("i.water_system_energy_source", ws.energy_source)
        set_if("i.water_system_efficiency_cop", ws.efficiency_cop)
        set_if("i.water_system_nominal_capacity", ws.nominal_capacity)
        set_if("i.water_system_type", ws.type)

    # ── courtyards ─────────────────────────────────────────────────────────────
    if spec.courtyards:
        if len(spec.courtyards) > 1:
            toml["d.courtyard_length"] = sum(
                c.length * c.count for c in spec.courtyards
            )
            toml["d.courtyard_width"] = sum(c.width * c.count for c in spec.courtyards)
            toml["d.courtyard_number"] = 1
        else:
            c = spec.courtyards[0]
            toml["d.courtyard_length"] = c.length
            toml["d.courtyard_width"] = c.width
            set_if("d.courtyard_number", c.count)

    # ── open courtyards ────────────────────────────────────────────────────────
    if spec.open_courtyards is not None:
        for o_code, o_name in [
            ("a", "front"),
            ("b", "right"),
            ("c", "back"),
            ("d", "left"),
        ]:
            oc = getattr(spec.open_courtyards, o_name, None)
            if oc is not None:
                toml[f"d.open_courtyard_depth_{o_code}1"] = oc.depth
                toml[f"d.open_courtyard_number_{o_code}"] = oc.count

    return toml

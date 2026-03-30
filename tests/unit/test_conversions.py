import json
import unittest
from copy import deepcopy
from importlib.resources import files
from pathlib import Path

import jsonschema

from openbes import OpenBESSpecification, SPECIFICATION
from openbes.schemas.conversion import json_to_toml, toml_to_json
from openbes.schemas import OpenBESSpecificationV2
from openbes.simulations.cooling import CoolingSimulation
from openbes.simulations.heating import HeatingSimulation
from openbes.simulations.thermal import ThermalSimulation
from openbes.simulations.ventilation import VentilationSimulation


class Conversions(unittest.TestCase):
    NULLISH = (None, "", [], 0, 0.0, False)

    def json_with_multiple_hvac_systems(self):
        json_spec = deepcopy(self.json)

        heating_system_2 = deepcopy(json_spec["heating_systems"][0])
        heating_system_2["nominal_capacity"] = 24.0
        heating_system_2["efficiency_cop"] = 0.95
        heating_system_2["min_demand"] = 20.0
        heating_system_2["count"] = 1
        heating_system_2["active_hours"] = {"start": 9, "end": 16}
        heating_system_2["simultaneity"] = {
            "Office area": 0.5,
            "Teaching": 0.25,
            "Canteen": 0.5,
            "Common areas": 0.1,
            "Other spaces": 0.0,
        }
        json_spec["heating_systems"].append(heating_system_2)

        cooling_system_2 = deepcopy(json_spec["cooling_systems"][0])
        cooling_system_2["nominal_capacity"] = 48.0
        cooling_system_2["sensible_nominal_capacity"] = 37.5
        cooling_system_2["efficiency_ratio"] = 3.5
        cooling_system_2["min_demand"] = 10.0
        cooling_system_2["active_hours"] = {"start": 9, "end": 16}
        cooling_system_2["simultaneity"] = {
            "Office area": 0.5,
            "Teaching": 0.25,
            "Canteen": 0.5,
            "Common areas": 0.1,
            "Other spaces": 0.0,
        }
        json_spec["cooling_systems"].append(cooling_system_2)

        ventilation_system_2 = deepcopy(json_spec["ventilation_systems"][0])
        ventilation_system_2["airflow"] = 150.0
        ventilation_system_2["heat_recovery_efficiency"] = 0.5
        ventilation_system_2["rated_input_power"] = 0.15
        ventilation_system_2["ventilated_area"] = 50.0
        ventilation_system_2["active_hours"] = {"start": 11, "end": 13}
        json_spec["ventilation_systems"].append(ventilation_system_2)

        return json_spec

    def json_with_minimal_secondary_hvac_systems(self):
        json_spec = deepcopy(self.json)

        json_spec["heating_systems"].append(
            {
                "energy_source": "Natural gas",
                "efficiency_cop": 0.95,
                "nominal_capacity": 24.0,
                "active_hours": {"start": 9, "end": 16},
            }
        )
        json_spec["cooling_systems"].append(
            {
                "energy_source": "Electricity",
                "efficiency_ratio": 3.5,
                "nominal_capacity": 48.0,
                "sensible_nominal_capacity": 37.5,
                "active_hours": {"start": 9, "end": 16},
            }
        )
        json_spec["ventilation_systems"].append(
            {
                "energy_source": "Electricity",
                "airflow": 150.0,
            }
        )

        return json_spec

    def legacy_spec_from_json(self, json_spec):
        return OpenBESSpecification.from_toml(json_to_toml(json_spec))

    def assertJSONEquivalent(self, obj1, obj2, msg_prefix=""):
        """Assert two JSON-compatible values are semantically equivalent.

        A key absent from one dict is treated as equivalent to it being present
        with a nullish value in the other, since the sparse conversion omits
        null/zero/empty values rather than explicitly carrying them.
        """
        if isinstance(obj1, dict) or isinstance(obj2, dict):
            obj1 = obj1 if isinstance(obj1, dict) else {}
            obj2 = obj2 if isinstance(obj2, dict) else {}
            all_keys = set(obj1.keys()) | set(obj2.keys())
            for key in all_keys:
                v1 = obj1.get(key)
                v2 = obj2.get(key)
                self.assertJSONEquivalent(v1, v2, msg_prefix=f"{msg_prefix}['{key}']")
        elif isinstance(obj1, list) or isinstance(obj2, list):
            obj1 = obj1 if isinstance(obj1, list) else []
            obj2 = obj2 if isinstance(obj2, list) else []
            self.assertEqual(len(obj1), len(obj2), msg=msg_prefix)
            for i in range(len(obj1)):
                self.assertJSONEquivalent(
                    obj1[i], obj2[i], msg_prefix=f"{msg_prefix}[{i}]"
                )
        else:
            if obj1 in self.NULLISH and obj2 in self.NULLISH:
                return
            if isinstance(obj1, str) and isinstance(obj2, str):
                self.assertEqual(
                    obj1.strip().lower(), obj2.strip().lower(), msg=msg_prefix
                )
            elif isinstance(obj1, (int, float)) and isinstance(obj2, (int, float)):
                self.assertAlmostEqual(
                    float(obj1), float(obj2), msg=msg_prefix, places=5
                )
            else:
                self.assertEqual(obj1, obj2, msg=msg_prefix)

    def setUp(self):
        with open(
            Path(files("openbes.example_data") / "holywell_house.json"), "r"
        ) as f:
            self.json = json.load(f)

    def test_toml_json_round_trip(self):
        toml_spec = json_to_toml(self.json, False)
        and_back = toml_to_json(toml_spec, False)
        self.assertJSONEquivalent(self.json, and_back)

    def test_converted_toml_loadable(self):
        toml_spec = json_to_toml(self.json)
        self.assertIsInstance(
            OpenBESSpecification.from_toml(toml_spec), OpenBESSpecification
        )

    def test_converted_json_loadable(self):
        toml_spec = json_to_toml(self.json)
        json_spec = toml_to_json(toml_spec)
        self.assertIsInstance(
            OpenBESSpecificationV2(**json_spec), OpenBESSpecificationV2
        )

    def test_spec_vs_schema(self):
        spec = OpenBESSpecificationV2(**self.json)
        jsonschema.validate(spec, self.json)

    def test_schema_is_valid(self):
        jsonschema.validators.Draft202012Validator.check_schema(SPECIFICATION)

    def test_spec_vs_exported_schema(self):
        spec = OpenBESSpecificationV2(**self.json)
        spec_dump = {"inputs": spec.model_dump()}

        # Strip None values for validation
        def strip_none(d):
            if isinstance(d, dict):
                return {k: strip_none(v) for k, v in d.items() if v is not None}
            elif isinstance(d, list):
                return [strip_none(i) for i in d if i is not None]
            else:
                return d

        instance_to_validate = strip_none(spec_dump)
        jsonschema.validate(
            instance=instance_to_validate,
            schema=SPECIFICATION,
            cls=jsonschema.validators.Draft202012Validator,
        )

    def test_mismatched_zone_numbers(self):
        json_spec = self.json.copy()
        json_spec["zones"].pop()
        json_spec["zones"].pop()
        spec = OpenBESSpecificationV2(**json_spec)
        json_to_toml(spec)

    def test_convert_blank_schema(self):
        blank_json = {}
        toml_spec = json_to_toml(blank_json)
        self.assertEqual(
            toml_spec, {}, msg="json_to_toml({}) should produce an empty TOML dict"
        )
        and_back = toml_to_json(toml_spec)
        self.assertEqual(
            and_back, {}, msg="toml_to_json({}) should produce an empty JSON dict"
        )
        self.assertJSONEquivalent(blank_json, and_back)

    def test_blank_schema_stability(self):
        """Repeated json->toml->json->toml... conversions of {} should stay empty."""
        result_json = {}
        result_toml = {}
        for _ in range(3):
            result_toml = json_to_toml(result_json)
            self.assertEqual(result_toml, {})
            result_json = toml_to_json(result_toml)
            self.assertEqual(result_json, {})

    def test_json_to_toml_multiple_hvac_systems_populates_system_2_keys(self):
        json_spec = self.json_with_multiple_hvac_systems()

        toml_spec = json_to_toml(json_spec)

        self.assertEqual(toml_spec["d.heating_system2_nominal_capacity"], 24.0)
        self.assertEqual(toml_spec["d.heating_system2_efficiency_cop"], 0.95)
        self.assertEqual(toml_spec["d.heating_system2_min_demand"], 20.0)
        self.assertEqual(toml_spec["d.heating_system2_on_time"], 9)
        self.assertEqual(toml_spec["d.heating_system2_off_time"], 16)
        self.assertEqual(toml_spec["d.heating_system2_simultaneity_factor_office"], 0.5)

        self.assertEqual(toml_spec["d.cooling_system2_nominal_capacity"], 48.0)
        self.assertEqual(toml_spec["d.cooling_system2_sensible_nominal_capacity"], 37.5)
        self.assertEqual(toml_spec["d.cooling_system2_energy_efficifiency_ratio"], 3.5)
        self.assertEqual(toml_spec["d.cooling_system2_min_demand"], 10.0)
        self.assertEqual(toml_spec["d.cooling_system2_on_time"], 9)
        self.assertEqual(toml_spec["d.cooling_system2_off_time"], 16)
        self.assertEqual(toml_spec["d.cooling_system2_simultaneity_factor_office"], 0.5)

        self.assertEqual(toml_spec["d.ventilation_system2_airflow"], 150.0)
        self.assertEqual(
            toml_spec["d.ventilation_system2_heat_recovery_efficiency"], 0.5
        )
        self.assertEqual(toml_spec["d.ventilation_system2_rated_input_power"], 0.15)
        self.assertEqual(toml_spec["d.ventilation_system2_ventilated_area"], 50.0)
        self.assertEqual(toml_spec["d.ventilation_system2_on_time"], 11)
        self.assertEqual(toml_spec["d.ventilation_system2_off_time"], 13)

    def test_multiple_hvac_systems_survive_json_toml_json_round_trip(self):
        json_spec = self.json_with_multiple_hvac_systems()

        toml_spec = json_to_toml(json_spec, False)
        converted = toml_to_json(toml_spec, False)

        self.assertJSONEquivalent(
            json_spec["heating_systems"], converted["heating_systems"]
        )
        self.assertJSONEquivalent(
            json_spec["cooling_systems"], converted["cooling_systems"]
        )
        self.assertJSONEquivalent(
            json_spec["ventilation_systems"], converted["ventilation_systems"]
        )

    def test_minimal_secondary_hvac_systems_get_runtime_defaults(self):
        spec = self.legacy_spec_from_json(
            self.json_with_minimal_secondary_hvac_systems()
        )

        self.assertEqual(spec.parameters.cooling_system2_min_demand, 15.0)
        self.assertEqual(
            spec.parameters.heating_system2_simultaneity_factor_office, 1.0
        )
        self.assertEqual(
            spec.parameters.cooling_system2_simultaneity_factor_office, 1.0
        )
        self.assertEqual(spec.parameters.ventilation_system2_rated_input_power, 0.0)

    def test_minimal_secondary_heating_system_functions_after_json_to_toml(self):
        spec = self.legacy_spec_from_json(
            self.json_with_minimal_secondary_hvac_systems()
        )

        thermal = ThermalSimulation(spec=spec)
        sim = HeatingSimulation(spec=spec, thermal=thermal)

        self.assertEqual(len(sim.heating_simulations), 2)
        second = sim.report.heating_systems[1]
        self.assertGreater(second.conditioned_area, 0)
        self.assertGreater(second.system_usage, 0)

    def test_minimal_secondary_cooling_system_functions_after_json_to_toml(self):
        spec = self.legacy_spec_from_json(
            self.json_with_minimal_secondary_hvac_systems()
        )

        thermal = ThermalSimulation(spec=spec)
        sim = CoolingSimulation(spec=spec, thermal=thermal)

        self.assertEqual(len(sim.cooling_simulations), 2)
        second = sim.report.cooling_systems[1]
        self.assertGreater(second.conditioned_area, 0)
        self.assertGreater(second.system_usage, 0)

    def test_minimal_secondary_ventilation_system_functions_after_json_to_toml(self):
        spec = self.legacy_spec_from_json(
            self.json_with_minimal_secondary_hvac_systems()
        )

        sim = VentilationSimulation(spec=spec)

        self.assertEqual(len(sim.ventilation_simulations), 2)
        second = sim.report.ventilation_systems[1]
        self.assertGreater(second.mechanical_ventilation_rate, 0)


if __name__ == "__main__":
    unittest.main()

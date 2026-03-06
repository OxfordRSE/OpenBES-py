import json
import unittest
from importlib.resources import files
from pathlib import Path

import jsonschema

from openbes import OpenBESSpecification, SPECIFICATION
from openbes.schemas.conversion import json_to_toml, toml_to_json
from openbes.schemas import OpenBESSpecificationV2


class Conversions(unittest.TestCase):
    NULLISH = (None, "", [], 0, 0.0, False)

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
                self.assertAlmostEqual(float(obj1), float(obj2), msg=msg_prefix, places=5)
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
        self.assertEqual(toml_spec, {}, msg="json_to_toml({}) should produce an empty TOML dict")
        and_back = toml_to_json(toml_spec)
        self.assertEqual(and_back, {}, msg="toml_to_json({}) should produce an empty JSON dict")
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

if __name__ == "__main__":
    unittest.main()

import json
import unittest
from importlib.resources import files
from pathlib import Path

from openbes import OpenBESSpecification
from openbes.schemas.conversion import json_to_toml, toml_to_json
from openbes.schemas import OpenBESSpecificationV2


class Conversions(unittest.TestCase):
    def assertJSONEquivalent(self, obj1, obj2, msg_prefix=''):
        if isinstance(obj1, dict):
            self.assertEqual(set(obj1.keys()), set(obj2.keys()), msg=msg_prefix)
            for key in obj1.keys():
                self.assertJSONEquivalent(obj1[key], obj2[key], msg_prefix=f"{msg_prefix}['{key}']")
        elif isinstance(obj1, list):
            self.assertEqual(len(obj1), len(obj2), msg=msg_prefix)
            for i in range(len(obj1)):
                self.assertJSONEquivalent(obj1[i], obj2[i], msg_prefix=f"{msg_prefix}[{i}]")
        else:
            nullish = [None, '', [], 0, 0.0]
            if obj1 in nullish and obj2 in nullish:
                return
            if isinstance(obj1, str) and isinstance(obj2, str):
                self.assertEqual(obj1.strip().lower(), obj2.strip().lower(), msg=msg_prefix)
            elif isinstance(obj1, float) and isinstance(obj2, float):
                self.assertAlmostEqual(obj1, obj2, msg=msg_prefix, places=5)
            else:
                self.assertEqual(obj1, obj2, msg=msg_prefix)

    def setUp(self):
        with open(Path(files('openbes.example_data') / 'holywell_house.json'), 'r') as f:
            self.json = json.load(f)

    def test_toml_json_round_trip(self):
        toml_spec = json_to_toml(self.json, False)
        and_back = toml_to_json(toml_spec, False)
        self.assertJSONEquivalent(self.json, and_back)

    def test_converted_toml_loadable(self):
        toml_spec = json_to_toml(self.json)
        self.assertIsInstance(OpenBESSpecification.from_toml(toml_spec), OpenBESSpecification)

    def test_converted_json_loadable(self):
        toml_spec = json_to_toml(self.json)
        json_spec = toml_to_json(toml_spec)
        self.assertIsInstance(OpenBESSpecificationV2(**json_spec), OpenBESSpecificationV2)

if __name__ == '__main__':
    unittest.main()

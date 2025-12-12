import os
import tomllib
import unittest

from openbes.schemas.conversion.json_to_toml import json_to_toml
from openbes.schemas.conversion.toml_to_json import toml_to_json


class Conversions(unittest.TestCase):
    def assertTOMLEquivalent(self, obj1, obj2, msg_prefix=''):
        if isinstance(obj1, dict):
            self.assertEqual(set(obj1.keys()), set(obj2.keys()), msg=msg_prefix)
            for key in obj1.keys():
                self.assertTOMLEquivalent(obj1[key], obj2[key], msg_prefix=f"{msg_prefix}['{key}']")
        elif isinstance(obj1, list):
            self.assertEqual(len(obj1), len(obj2), msg=msg_prefix)
            for i in range(len(obj1)):
                self.assertTOMLEquivalent(obj1[i], obj2[i], msg_prefix=f"{msg_prefix}[{i}]")
        else:
            nullish = [None, '', [], 0, 0.0]
            if obj1 in nullish and obj2 in nullish:
                return
            if isinstance(obj1, str) and isinstance(obj2, str):
                self.assertEqual(obj1.strip().lower(), obj2.strip().lower(), msg=msg_prefix)
            self.assertEqual(obj1, obj2, msg=msg_prefix)

    def setUp(self):
        base_path = os.path.dirname(__file__)
        with open(os.path.join(base_path, 'fixtures', 'hh.toml'), 'r') as f:
            self.toml = tomllib.loads(f.read())

    def test_toml_json_round_trip(self):
        json_spec = toml_to_json(self.toml, False)
        and_back = json_to_toml(json_spec)
        self.assertTOMLEquivalent(self.toml, and_back)
        
if __name__ == '__main__':
    unittest.main()

import unittest

from openbes import OpenBESSpecification
from openbes.types import OpenBESParameters, MONTHS, ENERGY_SOURCES


class MiscellaneousUtilities(unittest.TestCase):
    def test_listable_enum_list(self):
        self.assertEqual(MONTHS.list_values()[0], 'Jan')

    def test_listable_enum_by_index(self):
        self.assertEqual(MONTHS.get_by_index(0), MONTHS.Jan)

    def test_listable_enum_from_str(self):
        spec = OpenBESSpecification(cooling_system1_energy_source="Natural gas")
        self.assertEqual(spec.cooling_system1_energy_source, ENERGY_SOURCES.Natural_gas)
        self.assertTrue(isinstance(spec.cooling_system1_energy_source, ENERGY_SOURCES))

    def test_spec_with_param_dict(self):
        params = { "cooling_system2_number": 10 }
        spec = OpenBESSpecification(parameters=params)
        self.assertTrue(isinstance(spec.parameters, OpenBESParameters))
        self.assertEqual(spec.parameters.cooling_system2_number, 10)

if __name__ == '__main__':
    unittest.main()

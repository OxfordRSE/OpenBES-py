import unittest
from src.openbes.types.enums import MONTHS

class MiscellaneousUtilities(unittest.TestCase):
    def test_listable_enum_list(self):
        self.assertEqual(MONTHS.list()[0], 'Jan')

    def test_listable_enum_by_index(self):
        self.assertEqual(MONTHS.get_by_index(0), MONTHS.Jan)

if __name__ == '__main__':
    unittest.main()

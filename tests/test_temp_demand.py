import unittest

from tests.utils import HOLYWELL_HOUSE_SPEC


class TemperatureDemand(unittest.TestCase):
    def setUp(self):
        self.spec = HOLYWELL_HOUSE_SPEC

if __name__ == '__main__':
    unittest.main()

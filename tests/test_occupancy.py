import unittest
from src.openbes.types.enums import DAYS
from src.openbes.simulations.occupancy import (
    day_of_the_week,
    is_weekend,
    is_public_holiday,
    is_occupied_day,
)

class Occupancy(unittest.TestCase):
    def test_day_of_the_week(self):
        days = [DAYS.Mon, DAYS.Tue, DAYS.Wed, DAYS.Thu, DAYS.Fri, DAYS.Sat, DAYS.Sun]
        for i in range(14):
            with self.subTest(i=i):
                self.assertEqual(days[i % 7], day_of_the_week(i))

    def test_is_weekend(self):
        weekends = [DAYS.Sat, DAYS.Sun]
        for i in range(14):
            with self.subTest(i=i):
                if day_of_the_week(i) in weekends:
                    self.assertTrue(is_weekend(i))
                else:
                    self.assertFalse(is_weekend(i))

    def test_is_public_holiday(self):
        days = range(365)
        holidays = [*range(5), *range(357, 365)]
        for i in days:
            with self.subTest(i=i):
                if i in holidays:
                    self.assertTrue(is_public_holiday(i))
                else:
                    self.assertFalse(is_public_holiday(i))

    def test_is_occupied_day(self):
        days = range(365)
        holiday_count = 11
        weekend_count = 104  # 52 weekends * 2 days
        occupied_count = 365 - holiday_count - weekend_count
        self.assertEqual(sum([is_occupied_day(d) for d in days]), occupied_count)
    

if __name__ == '__main__':
    unittest.main()

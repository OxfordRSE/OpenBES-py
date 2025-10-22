"""
Helper functions to simulate occupancy patterns in buildings.
"""
from ..types import DAYS

def day_of_the_week(day_number_in_year: int) -> DAYS:
    """Calculate the day of the week for a given day number in the year.
    Args:
        day_number_in_year (int): The day number in the year (0-364).
    Returns:
        DAYS: The corresponding day of the week.
    """
    return DAYS.get_by_index(day_number_in_year % 7)


def is_weekend(day_number_in_year: int) -> bool:
    """Check if a given day is a weekend.
    Args:
        day_number_in_year (int): The day number in the year (0-364).
    Returns:
        bool: True if the day is Saturday or Sunday, False otherwise.
    """
    return day_of_the_week(day_number_in_year) in (DAYS.Sat, DAYS.Sun)


def is_public_holiday(day_number_in_year: int) -> bool:
    """Check if a given day number in the year is a public holiday.
    Args:
        day_number_in_year (int): The day number in the year (0-364).
    Returns:
        bool: True if the day is a public holiday, False otherwise.
    """
    # Example public holidays (day numbers in the year)
    if day_number_in_year <= 4:
        return True  # First week of January
    return day_number_in_year >= 357  # Every day after Xmas is a holiday


def is_occupied_day(day_number_in_year: int) -> bool:
    """Determine if a given day number in the year is an occupied day.
    Args:
        day_number_in_year (int): The day number in the year (0-364).
    Returns:
        bool: True if the day is occupied, False otherwise.
    """
    if is_weekend(day_number_in_year) or is_public_holiday(day_number_in_year):
        return False
    return True
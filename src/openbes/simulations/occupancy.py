"""
Helper functions to simulate occupancy patterns in buildings.
"""
import logging

from pandas import DataFrame
from ..types import DAYS, OpenBESSpecification, OCCUPATION_ZONES, FLOORS, get_zone_number

logger = logging.getLogger(__name__)

M2_PER_PERSON = DataFrame([
    {"zone": OCCUPATION_ZONES.Office, "m2_per_person": 5},
    {"zone": OCCUPATION_ZONES.Teaching, "m2_per_person": 1.5},
    {"zone": OCCUPATION_ZONES.Canteen, "m2_per_person": 5},
    {"zone": OCCUPATION_ZONES.Common_areas, "m2_per_person": 5},
    {"zone": OCCUPATION_ZONES.Other, "m2_per_person": 5},
]).set_index("zone")


def month_for_day(day_number_in_year: int) -> int:
    """Calculate the month for a given day number in the year.
    Args:
        day_number_in_year (int): The day number in the year (1-365).
    Returns:
        int: The corresponding month (1-12).
    """
    if day_number_in_year <= 31:
        return 1
    elif day_number_in_year <= 59:
        return 2
    elif day_number_in_year <= 90:
        return 3
    elif day_number_in_year <= 120:
        return 4
    elif day_number_in_year <= 151:
        return 5
    elif day_number_in_year <= 181:
        return 6
    elif day_number_in_year <= 212:
        return 7
    elif day_number_in_year <= 243:
        return 8
    elif day_number_in_year <= 273:
        return 9
    elif day_number_in_year <= 304:
        return 10
    elif day_number_in_year <= 334:
        return 11
    else:
        return 12

# Blank DataFrame of each hour with month info, indexed by day of the year
HOURS_DF = DataFrame([
    {
        'month': month_for_day(d),
        'day': d,
        'hour': h,
        'is_daytime': 8 <= h <= 22
    } for d in range(1, 366) for h in range(1, 25)
]).set_index(['month', 'day', 'hour'])


def day_of_the_week(day_number_in_year: int) -> DAYS:
    """Calculate the day of the week for a given day number in the year.
    Args:
        day_number_in_year (int): The day number in the year (1-365).
    Returns:
        DAYS: The corresponding day of the week.
    """
    return DAYS.get_by_index((day_number_in_year - 1) % 7)


def is_public_holiday(day_number_in_year: int) -> bool:
    """Check if a given day number in the year is a public holiday.
    Args:
        day_number_in_year (int): The day number in the year (1-365).
    Returns:
        bool: True if the day is a public holiday, False otherwise.
    """
    # Example public holidays (day numbers in the year)
    if day_number_in_year <= 5:
        return True  # First week of January
    return day_number_in_year >= 358  # Every day after Xmas is a holiday

def is_occupied_month(month: int, spec: OpenBESSpecification) -> bool:
    """Determine if a given month is an occupied month.
    """
    if month == 1:
        return spec.schedule_january
    if month == 2:
        return spec.schedule_february
    if month == 3:
        return spec.schedule_march
    if month == 4:
        return spec.schedule_april
    if month == 5:
        return spec.schedule_may
    if month == 6:
        return spec.schedule_june
    if month == 7:
        return spec.schedule_july
    if month == 8:
        return spec.schedule_august
    if month == 9:
        return spec.schedule_september
    if month == 10:
        return spec.schedule_october
    if month == 11:
        return spec.schedule_november
    if month == 12:
        return spec.schedule_december
    raise ValueError("Invalid month")


def is_occupied_day(day_number_in_year: int, spec: OpenBESSpecification) -> bool:
    """Determine if a given day number in the year is an occupied day.
    Args:
        day_number_in_year (int): The day number in the year (1-365).
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        bool: True if the day is occupied, False otherwise.
    """
    if spec.holiday and is_public_holiday(day_number_in_year):
        return False
    day = day_of_the_week(day_number_in_year)
    if day == DAYS.Mon:
        return spec.schedule_monday
    if day == DAYS.Tue:
        return spec.schedule_tuesday
    if day == DAYS.Wed:
        return spec.schedule_wednesday
    if day == DAYS.Thu:
        return spec.schedule_thursday
    if day == DAYS.Fri:
        return spec.schedule_friday
    if day == DAYS.Sat:
        return spec.schedule_saturday
    if day == DAYS.Sun:
        return spec.schedule_sunday
    raise ValueError("Invalid day number in year")

def get_zone_total_area(spec: OpenBESSpecification, zone: OCCUPATION_ZONES) -> float:
    """Get the total area for a given occupation zone.
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
        zone (OCCUPATION_ZONES): The occupation zone.
    Returns:
        float: The total area of the zone in m².
    """
    z = get_zone_number(zone)
    total_area = 0.0
    for floor in FLOORS:
        area = getattr(spec, f"{floor.value}_floor_area_z{z}") or 0.0
        total_area += area
    return total_area

def get_occupation_ratio(spec: OpenBESSpecification) -> float:
    """Calculate the occupation ratio (occupation/capacity) based on the building schedule.
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        float: The occupation ratio (0.0 to 1.0).
    """
    capacity = spec.max_building_occupation
    current_occupation = spec.typical_occupation
    if current_occupation is None or current_occupation < 0:
        logger.warning(
            "Cannot calculate occupation percentage without `typical_occupation`. Defaulting to 100% occupation."
        )
        return 1.0
    try:
        if capacity > 0 and current_occupation > 0:
            return current_occupation / capacity
    except (ZeroDivisionError, TypeError):
        pass
    zonal_occupation_capacity = [
        get_zone_total_area(spec=spec, zone=zone) / M2_PER_PERSON.loc[zone, "m2_per_person"]
        for zone in OCCUPATION_ZONES
    ]
    return current_occupation / sum(zonal_occupation_capacity)
    
    
def get_occupancy_by_hour(spec: OpenBESSpecification) -> DataFrame:
    """Generate an occupancy schedule by hour for the entire year.
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        DataFrame: HOURS_DF with occupancy status (occupied = True) and ratio (0.0-1.0) for each hour of the year.
    """
    open_times = [spec.occupancy_open_office, spec.occupancy_open_canteen, spec.occupancy_open_teaching]
    close_times = [spec.occupancy_close_office, spec.occupancy_close_canteen, spec.occupancy_close_teaching]
    if all(ot is None for ot in open_times) or all(ct is None for ct in close_times):
        raise ValueError("Occupancy open and close times must be specified in the building specification.")
    open_time = min(ot for ot in open_times if ot is not None)
    close_time = max(ct for ct in close_times if ct is not None)

    df = HOURS_DF.copy()
    df['occupancy_status'] = False
    df['occupancy_ratio'] = 0.0
    # Get a mask for occupied hours in occupied days in occupied months that aren't public holidays
    index_df = df.index.to_frame()
    month_mask = index_df['month'].apply(lambda m: is_occupied_month(m, spec))
    day_mask = index_df['day'].apply(lambda d: is_occupied_day(d, spec))
    hour_mask = (index_df['hour'] >= open_time) & (index_df['hour'] <= close_time)
    mask = month_mask & day_mask & hour_mask
    df.loc[mask, 'occupancy_status'] = True
    df.loc[mask, 'occupancy_ratio'] = get_occupation_ratio(spec)
    return df

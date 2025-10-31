"""
Helper functions to simulate occupancy patterns in buildings.
"""
from pandas import DataFrame
from ..types import DAYS, OpenBESSpecification, OCCUPATION_ZONES, FLOORS

M2_PER_PERSON = DataFrame([
    {"zone": OCCUPATION_ZONES.Office, "m2_per_person": 5},
    {"zone": OCCUPATION_ZONES.Teaching, "m2_per_person": 1.5},
    {"zone": OCCUPATION_ZONES.Canteen, "m2_per_person": 5},
    {"zone": OCCUPATION_ZONES.Common_areas, "m2_per_person": 5},
    {"zone": OCCUPATION_ZONES.Other, "m2_per_person": 5},
]).set_index("zone")

def day_of_the_week(day_number_in_year: int) -> DAYS:
    """Calculate the day of the week for a given day number in the year.
    Args:
        day_number_in_year (int): The day number in the year (0-364).
    Returns:
        DAYS: The corresponding day of the week.
    """
    return DAYS.get_by_index(day_number_in_year % 7)


def month_for_day(day_number_in_year: int) -> int:
    """Calculate the month for a given day number in the year.
    Args:
        day_number_in_year (int): The day number in the year (0-364).
    Returns:
        int: The corresponding month (1-12).
    """
    if day_number_in_year < 31:
        return 1
    elif day_number_in_year < 59:
        return 2
    elif day_number_in_year < 90:
        return 3
    elif day_number_in_year < 120:
        return 4
    elif day_number_in_year < 151:
        return 5
    elif day_number_in_year < 181:
        return 6
    elif day_number_in_year < 212:
        return 7
    elif day_number_in_year < 243:
        return 8
    elif day_number_in_year < 273:
        return 9
    elif day_number_in_year < 304:
        return 10
    elif day_number_in_year < 334:
        return 11
    else:
        return 12


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


def is_occupied_day(day_number_in_year: int, spec: OpenBESSpecification) -> bool:
    """Determine if a given day number in the year is an occupied day.
    Args:
        day_number_in_year (int): The day number in the year (0-364).
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        bool: True if the day is occupied, False otherwise.
    """
    if not spec.holiday and is_public_holiday(day_number_in_year):
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
        area = getattr(spec, f"{zone.value}_floor_{floor.value}_area") or 0.0
        total_area += area
    return total_area

def get_occupation_percentage_by_zone(spec: OpenBESSpecification) -> DataFrame:
    """Calculate the occupation percentage based on the building schedule.
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        DataFrame: The occupation percentage (0.0 to 100.0) by zone.
    """
    capacity = spec.building_max_occupation or 1
    current_occupation = spec.typical_occupation or 1
    data = []
    try:
        if capacity > 0 and current_occupation > 0:
            p = current_occupation / capacity * 100.0
            data = [{"zone": zone, "occupation_percentage": p} for zone in OCCUPATION_ZONES]
    except (ZeroDivisionError, TypeError):
        data = [{
            "zone": zone,
            "occupation_percentage":
                M2_PER_PERSON.loc[zone, "m2_per_person"] * get_zone_total_area(spec=spec, zone=zone)
        } for zone in OCCUPATION_ZONES]

    df = (DataFrame(data)
    df.set_index("zone"))
    return df
    

def get_occupancy_by_hour(spec: OpenBESSpecification) -> DataFrame:
    """Generate an occupancy schedule by hour for the entire year.
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        DataFrame: A DataFrame with occupancy status (1 for occupied, 0 for unoccupied) for each hour of the year for each occupancy zone.
    """
    hours_in_year = 365 * 24
    _data = []
    for zone in OCCUPATION_ZONES:
        if zone == 'office':
            # Special case - in the Excel spreadsheet office uses minimum of heating on time and office open time
            open_time = getattr(spec, f"occupancy_open_{zone}")
            heating_on_time = spec.heating_system1_on_time
            if open_time is not None and heating_on_time is not None:
                open_time = min(open_time, heating_on_time)
            else:
                if open_time is None:
                    open_time = heating_on_time
                else:
                    open_time = heating_on_time
            close_time = getattr(spec, f"occupancy_close_{zone}")
            _data.append({
                "zone": zone,
                "open": open_time - 1,  # systems have to get ready 1 hour before occupancy
                "close": close_time,
            })
        else:
            _data.append({
                "zone": zone,
                "open": getattr(spec, f"occupancy_open_{zone}") - 1,
                "close": getattr(spec, f"occupancy_close_{zone}"),
            })
    occupancy_zone_hours = DataFrame(_data).set_index("zone")

    occupancy_schedule = []
    for day in range(365):
        occupied = is_occupied_day(day, spec=spec)
        for hour in range(24):
            zone_occupancy = get_occupation_percentage_by_zone(spec=spec)
            for zone in OCCUPATION_ZONES:
                zone_occupied = (
                        occupied and
                        (occupancy_zone_hours.loc[zone, "open"] <= hour < occupancy_zone_hours.loc[zone, "close"])
                )
                if not zone_occupied:
                    zone_occupancy.loc[zone, "occupation_percentage"] = 0.0
            occupancy_schedule.append({
                "month": month_for_day(day),
                "day": day,
                "hour": hour,
                **zone_occupancy
            })

    return DataFrame(occupancy_schedule, index=range(hours_in_year), columns=["Occupancy"])
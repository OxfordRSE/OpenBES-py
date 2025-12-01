"""
Helper functions to simulate occupancy patterns in buildings.
"""
import logging

from pandas import DataFrame, Series

from .base import HourlySimulation
from .geometry import BuildingGeometry
from ..types import (
    DAYS,
    OpenBESSpecification,
    OCCUPATION_ZONES,
    FLOORS,
    MONTHS,
)

logger = logging.getLogger(__name__)

# Occupation m2 per person for different zones (CTE DB-SI Table 2.1, Database cells R42:S46)
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


class OccupationSimulation(HourlySimulation):
    geometry: BuildingGeometry
    _occupation_ratio: float
    _occupation_m2_per_person: float
    _metabolic_rate_per_m2: float
    _occupied_days_per_month: Series

    def __init__(self, spec: OpenBESSpecification, geometry: BuildingGeometry = None):
        super().__init__(spec)
        self.geometry = geometry or BuildingGeometry(spec=self.spec)

    def is_occupied_month(self, month: int) -> bool:
        """Determine if a given month is an occupied month.
        """
        if month == 1:
            return self.spec.schedule_january
        if month == 2:
            return self.spec.schedule_february
        if month == 3:
            return self.spec.schedule_march
        if month == 4:
            return self.spec.schedule_april
        if month == 5:
            return self.spec.schedule_may
        if month == 6:
            return self.spec.schedule_june
        if month == 7:
            return self.spec.schedule_july
        if month == 8:
            return self.spec.schedule_august
        if month == 9:
            return self.spec.schedule_september
        if month == 10:
            return self.spec.schedule_october
        if month == 11:
            return self.spec.schedule_november
        if month == 12:
            return self.spec.schedule_december
        raise ValueError("Invalid month")

    def is_occupied_day(self, day_number_in_year: int) -> bool:
        """Determine if a given day number in the year is an occupied day.
        Args:
            day_number_in_year (int): The day number in the year (1-365).
        Returns:
            bool: True if the day is occupied, False otherwise.
        """
        if not self.spec.holiday and is_public_holiday(day_number_in_year):
            return False
        day = day_of_the_week(day_number_in_year)
        if day == DAYS.Mon:
            return self.spec.schedule_monday
        if day == DAYS.Tue:
            return self.spec.schedule_tuesday
        if day == DAYS.Wed:
            return self.spec.schedule_wednesday
        if day == DAYS.Thu:
            return self.spec.schedule_thursday
        if day == DAYS.Fri:
            return self.spec.schedule_friday
        if day == DAYS.Sat:
            return self.spec.schedule_saturday
        if day == DAYS.Sun:
            return self.spec.schedule_sunday
        raise ValueError("Invalid day number in year")

    def get_zone_total_area(self, zone: OCCUPATION_ZONES, floor: FLOORS = None) -> float:
        """Get the total area for a given occupation zone.
        Args:
            zone (OCCUPATION_ZONES): The occupation zone.
            floor: Floor to consider. If None, all floors are considered.
        Returns:
            float: The total area of the zone in m².
        """
        if not hasattr(self, 'geometry') or self.geometry is None:
            self.geometry = BuildingGeometry(spec=self.spec)
        if floor is None:
            return self.geometry.gross_floor_areas.groupby(level='zone').sum().loc[zone]
        return self.geometry.gross_floor_areas.loc[(floor, zone)].sum()

    @property
    def occupation_ratio(self) -> float:
        """Calculate the occupation ratio (occupation/capacity) based on the building schedule.

        Returns:
            float: The occupation ratio (0.0 to 1.0).
        """
        if not hasattr(self, '_occupation_ratio') or self._occupation_ratio is None:
            capacity = self.spec.max_building_occupation
            current_occupation = self.spec.typical_occupation
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
                self.get_zone_total_area(zone=z) / M2_PER_PERSON.loc[z, "m2_per_person"]
                for z in OCCUPATION_ZONES
            ]
            self._occupation_ratio = current_occupation / sum(zonal_occupation_capacity)
        return self._occupation_ratio

    @property
    def occupancy(self) -> DataFrame:
        """Generate an occupancy schedule by hour for the entire year.
        [Hourly Simulation column KH]

        DataFrame: with is_occupied and occupancy_ratio (0.0-1.0) for each hour of the year.
        """
        if 'is_occupied' not in self._hours.columns or 'occupancy_ratio' not in self._hours.columns:
            open_times = [self.spec.occupancy_open_office, self.spec.occupancy_open_canteen, self.spec.occupancy_open_teaching]
            close_times = [self.spec.occupancy_close_office, self.spec.occupancy_close_canteen, self.spec.occupancy_close_teaching]
            if all(ot is None for ot in open_times) or all(ct is None for ct in close_times):
                raise ValueError("Occupancy open and close times must be self.specified in the building specification.")
            open_time = min(ot for ot in open_times if ot is not None)
            close_time = max(ct for ct in close_times if ct is not None)

            self._hours['is_occupied'] = False
            self._hours['occupancy_ratio'] = 0.0
            # Get a mask for occupied hours in occupied days in occupied months that aren't public holidays
            index_df = self._hours.index.to_frame()
            month_mask = index_df['month'].apply(lambda m: self.is_occupied_month(m))
            day_mask = index_df['day'].apply(lambda d: self.is_occupied_day(d))
            hour_mask = (index_df['hour'] >= open_time) & (index_df['hour'] <= close_time)
            mask = month_mask & day_mask & hour_mask
            self._hours.loc[mask, 'is_occupied'] = True
            self._hours.loc[mask, 'occupancy_ratio'] = self.occupation_ratio

        return self._hours[['is_occupied', 'occupancy_ratio']]

    @property
    def occupied_days_per_month(self) -> Series:
        """Calculate the number of occupied days per month based on the building schedule.
        Returns:
            Series: A Series with the number of occupied days for each month.
        """
        if not hasattr(self, '_occupied_days_per_month') or self._occupied_days_per_month is None:
            self._occupied_days_per_month = (
                self.occupancy['is_occupied'].groupby(level=['day', 'month']).any().groupby(level='month').sum()
            )
            self._occupied_days_per_month.index = list(MONTHS)
        return self._occupied_days_per_month

    @property
    def occupation_m2_per_person(self) -> float:
        """Calculate the occupation area per person based on building specifications.
        m2/person [Inputs C139]

        The occupation m2/person is calculated as the building area for zones in which people typically inhabit
        (office and teaching) divided by the typical occupation (number of people).

        People are assumed to inhabit only office and teaching zones, because when they are in canteen zones,
        common zones, etc. they are still generating their metabolic heat load, just in a different location.
        Because locations are amalgamated in OpenBES, we can ignore _where_ people are, and just focus on
        how many people there are in total, and what area is available to them.

        Returns:
            float: The occupation area per person in m2/person.
        """
        if not hasattr(self, '_occupation_m2_per_person') or self._occupation_m2_per_person is None:
            occupied_zone_areas = (
                    self.get_zone_total_area(zone=OCCUPATION_ZONES.Office) +
                    self.get_zone_total_area(zone=OCCUPATION_ZONES.Teaching)
            ) * self.spec.parameters.nia_gba_ratio  # scale by net inhabitable area ratio
            office_population = (
                    self.get_zone_total_area(zone=OCCUPATION_ZONES.Office) /
                    M2_PER_PERSON.loc[OCCUPATION_ZONES.Office, "m2_per_person"] *
                    self.spec.parameters.nia_gba_ratio
            )
            teaching_population = (
                    self.get_zone_total_area(zone=OCCUPATION_ZONES.Teaching) /
                    M2_PER_PERSON.loc[OCCUPATION_ZONES.Teaching, "m2_per_person"] *
                    self.spec.parameters.nia_gba_ratio
            )
            simultaneity_factor = 0.75  # [Inputs cell F137]
            simultaneity_adjusted_population = (office_population + teaching_population) * simultaneity_factor
            self._occupation_m2_per_person = occupied_zone_areas / simultaneity_adjusted_population
        return self._occupation_m2_per_person

    @property
    def metabolic_rate_per_m2(self) -> float:
        """Calculate the metabolic rate per square meter based on building specifications.
        [Inputs cell C140, Database R32: Table G.10 ISO 13790]

        The more space each person has (m2/person), the lower the metabolic rate per square meter (W/m2).
        ISO 13790 provides typical values for metabolic rates based on occupation density.

        Args:
            self.spec (OpenBESSpecification): The building specifications self.spec data class.
        Returns:
            float: The metabolic rate per square meter in W/m2.
        """
        if not hasattr(self, '_metabolic_rate_per_m2') or self._metabolic_rate_per_m2 is None:
            if self.spec.parameters.occupancy_on_off is not None and not self.spec.parameters.occupancy_on_off:
                self._metabolic_rate_per_m2 = 0.0
            else:
                occupation_density = self.occupation_m2_per_person
                occupation_density_thresholds = [
                    {'threshold_m2_per_person': 1, 'metabolic_rate_W_per_m2': 15.0},
                    {'threshold_m2_per_person': 2, 'metabolic_rate_W_per_m2': 10.0},
                    {'threshold_m2_per_person': 5.5, 'metabolic_rate_W_per_m2': 5.0},
                    {'threshold_m2_per_person': 14, 'metabolic_rate_W_per_m2': 3.0},
                    {'threshold_m2_per_person': 20, 'metabolic_rate_W_per_m2': 2.0},
                ]
                for i in range(len(occupation_density_thresholds)):
                    if occupation_density < occupation_density_thresholds[i]['threshold_m2_per_person']:
                        self._metabolic_rate_per_m2 = occupation_density_thresholds[i]['metabolic_rate_W_per_m2']
                        break
            if not hasattr(self, '_metabolic_rate_per_m2') or self._metabolic_rate_per_m2 is None:
                logger.warning("Occupation density lower than 0.05 person/m2. Using minimum metabolic rate of 2 W/m2.")
                self._metabolic_rate_per_m2 = 2.0
        return self._metabolic_rate_per_m2

from pandas import DataFrame

from ..types import OpenBESSpecification, ENERGY_SOURCES


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


class HourlySimulation:
    """
    Base class for hourly simulations.

    Each instance is initialized with an OpenBESSpecification and contains an _hours property
    that holds a DataFrame representing each hour of the year.

    Properties will typically add columns to the _hours DataFrame as needed for various calculations,
    and usually return that DataFrame or specific columns from it.
    """

    spec: OpenBESSpecification
    _hours: DataFrame

    def __init__(self, spec: OpenBESSpecification):
        self.spec = spec
        self._hours = HOURS_DF.copy()


class EnergyUseSimulation(HourlySimulation):
    """
    Base class for hourly energy use simulations.

    Child classes should override the energy_use property to return a DataFrame representing
    the energy use in kW for each hour of the year, with a column for each of the ENERGY_SOURCES.

    The _energy_use property is initialized as a DataFrame of NaNs with the same index as _hours
    and columns for each ENERGY_SOURCES. self.energy_use should populate this DataFrame appropriately.
    """
    def __init__(self, spec: OpenBESSpecification):
        super().__init__(spec)
        self._energy_use = DataFrame(index=self._hours.index, columns=list(ENERGY_SOURCES)).astype(float)

    @property
    def energy_use(self) -> DataFrame:
        """DataFrame of energy use in kW for each hour of the year, with a column for each ENERGY_SOURCES.
        """
        raise NotImplementedError("Child classes must implement the energy_use property.")

    @property
    def annual_energy_use(self) -> DataFrame:
        return self.energy_use.sum().sum()

from __future__ import annotations

from typing import Callable

from pandas import DataFrame, Series

from ..schemas import HourPeak
from ..schemas.generated.models import DayPeak

MONTH_NAMES = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]

_MONTH_START_DAY = {
    1: 1,
    2: 32,
    3: 60,
    4: 91,
    5: 121,
    6: 152,
    7: 182,
    8: 213,
    9: 244,
    10: 274,
    11: 305,
    12: 335,
}


def to_output_csv(
    value: DataFrame | Series,
    precision: int,
    *,
    header: bool = True,
    index: bool = True,
) -> str:
    """Serialize a tabular output to CSV using OpenBES output conventions."""
    return value.round(precision).to_csv(header=header, index=index)


def output_precision(spec) -> int:
    params = getattr(spec, "parameters", None)
    precision = getattr(params, "output_csv_precision", None)
    return 2 if precision is None else precision


def day_of_the_month(day_number_in_year: int, month: int) -> int:
    return day_number_in_year - _MONTH_START_DAY[month] + 1


def find_hour_peak(series: Series, fn: Callable, precision: int) -> HourPeak:
    peak_value = fn(series)
    peak_index = series[series == peak_value].index[0]
    if isinstance(peak_index, tuple):
        month = int(peak_index[0])
        day = day_of_the_month(int(peak_index[1]), month)
        hour = int(peak_index[2])
    else:
        month = int(peak_index.month)
        day = int(peak_index.day)
        hour = int(peak_index.hour) + 1
    return HourPeak(
        month=MONTH_NAMES[month - 1],
        day=day,
        hour=hour,
        value=round(float(peak_value), precision),
    )


def find_day_peak(series: Series, fn: Callable, precision: int) -> DayPeak:
    peak_value = fn(series)
    peak_index = series[series == peak_value].index[0]
    month = int(peak_index[0])
    day = day_of_the_month(int(peak_index[1]), month)
    return DayPeak(
        month=MONTH_NAMES[month - 1],
        day=day,
        value=round(float(peak_value), precision),
    )

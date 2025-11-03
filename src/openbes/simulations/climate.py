from pvlib.iotools import read_epw
from pandas import DataFrame
import os

from .occupancy import HOURS_DF
from ..types import OpenBESSpecification, OpenBESParameters

RELATIVE_HUMIDITY = 55.0  # Percentage

def get_hourly_set_point_temperature(spec: OpenBESSpecification, params: OpenBESParameters) -> DataFrame:
    """Return an HOURS_DF dataframe with set point temperatures for each hour of the year.
    The set point temperatures provide a minimum and maximum temperature for comfortable building occupation.
    This is given by specified target temperatures with an optional tolerance.
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
        params (OpenBESParameters): The simulation parameters.
    Returns:
        DataFrame: HOURS_DF with set point temperatures for each hour of the year.
    """
    df = HOURS_DF.copy()
    tolerance = max(params.temperature_tolerance or 0.0, 0.0)
    

def get_available_epw_files() -> list[str]:
    """
    Returns a list of available EPW climate data files.
    """
    climate_data_dir = os.path.join(
        os.path.dirname(__file__),
        "climate_data"
    )
    return [
        f for f in os.listdir(climate_data_dir)
        if f.endswith('.epw')
    ]

def get_hourly_dry_bulb_temperature(spec: OpenBESSpecification) -> DataFrame:
    """
    Placeholder function to get hourly dry bulb temperature.
    In a real implementation, this would retrieve data from a climate dataset.
    """
    file_name = spec.meteorological_file
    path = os.path.join(
        os.path.dirname(__file__),
        "climate_data",
        file_name
    )
    epw, epw_metadata = read_epw(path)
    return epw

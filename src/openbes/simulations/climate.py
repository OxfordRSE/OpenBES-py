from pvlib.iotools import read_epw
from pandas import DataFrame
import os
from ..types import OpenBESSpecification


RELATIVE_HUMIDITY = 55.0  # Percentage

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

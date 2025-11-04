from math import atan

from pvlib.iotools import read_epw
from pandas import DataFrame
import os

from .geometry import get_conditioned_floor_area, get_window_area, get_window_shading
from .occupancy import HOURS_DF
from ..types import OpenBESSpecification, OpenBESParameters, THERMAL_BREAKS

RELATIVE_HUMIDITY = 55.0  # Percentage

THERMAL_BREAK_TRANSMITTANCE = {
    THERMAL_BREAKS.Facade_ground: 0.54,
    THERMAL_BREAKS.Facade_intermediate: 0.60,
    THERMAL_BREAKS.Facade_roof: 0.44,
    THERMAL_BREAKS.Windows: 0.50,
    THERMAL_BREAKS.Shading: 0.80,
}

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
    df['min_temp_set_point'] = df['is_daytime'].apply(
        lambda x: (spec.setpoint_winter_day - tolerance) if x else (spec.setpoint_winter_night - tolerance)
    )
    df['max_temp_set_point'] = df['is_daytime'].apply(
        lambda x: (spec.setpoint_summer_day + tolerance) if x else (spec.setpoint_summer_night + tolerance)
    )
    return df

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

def get_epw_data(spec: OpenBESSpecification) -> DataFrame:
    """Return a DataFrame with EPW climate data for the specified location.
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        DataFrame: EPW climate data for the specified location.
    """
    file_name = spec.meteorological_file
    path = os.path.join(
        os.path.dirname(__file__),
        "climate_data",
        file_name
    )
    epw, epw_metadata = read_epw(path)
    return epw

def get_heating_and_cooling_degrees_days(spec: OpenBESSpecification, base_temperature: float = 18.0) -> DataFrame:
    """Calculate heating degree days for each month based on dry bulb temperature.
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
        base_temperature (float): The base temperature for heating degree days calculation. Generally 65°F (18°C).
    Returns:
        DataFrame: Heating degree days for each month.
    """
    epw = get_epw_data(spec)
    days = epw[['month', 'day', 'temp_air']].copy()
    days = days.groupby(['month', 'day']).agg(lambda x: (x.max() + x.min()) / 2).reset_index(['month', 'day'])
    days['day'] = days.index + 1
    days = days.set_index(['day'])
    days['heating_degree_day'] = days['temp_air'].apply(lambda x: max(0, base_temperature - x))
    days['cooling_degree_day'] = days['temp_air'].apply(lambda x: max(0, x - base_temperature))
    days = days.drop(columns=['temp_air'])
    return days

def get_internal_air_temp(spec: OpenBESSpecification) -> DataFrame:
    """Return a DataFrame with estimated internal air temperature for each hour of the year.
    Ѳair
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        DataFrame: HOURS_DF with estimated internal air temperature for each hour of the year.
    """
    raise NotImplementedError

def get_heat_transfer_rate_windows(spec: OpenBESSpecification) -> float:
    """Calculate the heat transfer rate through windows (W/m²K).
    Htr_w [Hourly Simulation cell AR97]
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        float: Heat transfer rate through windows (W/m²K).
    """
    conditioned_area = get_conditioned_floor_area(spec=spec)
    correction_factor = spec.parameters.window_correction_factor
    window_area = get_window_area(spec=spec)
    u_value = spec.uvalue_window
    if spec.thermal_bridge_shading:
        shading = get_window_shading(spec=spec) * THERMAL_BREAK_TRANSMITTANCE[THERMAL_BREAKS.Shading]
    else:
        shading = 0.0
    return (
        window_area * u_value +
        shading
    ) * correction_factor / conditioned_area

def get_heat_transfer_rate_opaque(spec: OpenBESSpecification) -> float:
    """Calculate the heat transfer rate through opaque envelope (W/m²K).
    Htr_opaque [Hourly Simulation cell AR93]
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        float: Heat transfer rate through opaque envelope (W/m²K).
    """
    raise NotImplementedError

def get_heat_transfer_ms(spec: OpenBESSpecification) -> float:
    """Calculate the heat transfer coefficient between internal air and internal surface (W/m²K).
    Htr_ms [Hourly Simulation cell AR95] EN ISO 13790 12.2.2
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        float: Heat transfer coefficient between internal air and internal surface (W/m²K).
    """
    factor = 9.1  # Unnamed factor in cell AR95
    return (get_heat_transfer_rate_windows(spec=spec) + get_heat_transfer_rate_opaque(spec=spec)) * factor

def get_internal_surface_temp(spec: OpenBESSpecification) -> DataFrame:
    """Return a DataFrame with estimated internal surface temperature for each hour of the year.
    Ѳs [Hourly Simulation column AX]
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        DataFrame: HOURS_DF with estimated internal surface temperature for each hour of the year.
    """
    Htr_ms = get_heat_transfer_ms(spec=spec)
    (
        $AR$95 * AW118 +
        AS118 +
        $AR$97 * $I118 +
        $AM118 * ($AG118 + (AQ118 + $AR$111) / $AL118)
    ) / ($AR$95 + $AR$97 + $AM118)
    raise NotImplementedError

def get_supply_air_temp(spec: OpenBESSpecification) -> DataFrame:
    """Return a DataFrame with supply air temperature for each hour of the year.
    Ѳsup
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        DataFrame: HOURS_DF with supply air temperature for each hour of the year.
    """
    raise NotImplementedError

def get_relative_humidity(spec: OpenBESSpecification) -> DataFrame:
    """Return a DataFrame with relative humidity for each hour of the year.
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        DataFrame: HOURS_DF with relative humidity for each hour of the year.
    """
    df = HOURS_DF.copy()
    relative_humidity = get_epw_data(spec)['relative_humidity']
    relative_humidity.index = df.index
    df['relative_humidity'] = relative_humidity
    return df[['relative_humidity']]

def get_wet_bulb_temperature(spec: OpenBESSpecification) -> DataFrame:
    """Return a DataFrame with wet bulb temperature for each hour of the year.
    Tw [Hourly Simulation column K]
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        DataFrame: HOURS_DF with wet bulb temperature for each hour of the year.
    """
    df = get_relative_humidity(spec)
    df['temp_air'] = list(get_epw_data(spec)['temp_air'])
    df['wet_bulb_temp'] = df.apply(
        lambda row: row['temp_air'] * \
            atan(0.151977 * (row['relative_humidity'] + 8.313659) ** 0.5) + \
            atan(row['temp_air'] + row['relative_humidity']) - \
            atan(row['relative_humidity'] - 1.676331) + \
            0.00391838 * (row['relative_humidity'] ** 1.5) * atan(0.023101 * row['relative_humidity']) \
            - 4.686035,
        axis=1
    )
    return df[['wet_bulb_temp']]

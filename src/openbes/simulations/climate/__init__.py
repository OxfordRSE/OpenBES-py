from math import atan

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

def get_internal_air_temp(spec: OpenBESSpecification) -> DataFrame:
    """Return a DataFrame with estimated internal air temperature for each hour of the year.
    Ѳair
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        DataFrame: HOURS_DF with estimated internal air temperature for each hour of the year.
    """
    raise NotImplementedError

def get_internal_surface_temp(spec: OpenBESSpecification) -> DataFrame:
    """Return a DataFrame with estimated internal surface temperature for each hour of the year.
    Ѳs
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        DataFrame: HOURS_DF with estimated internal surface temperature for each hour of the year.
    """
    raise NotImplementedError

def get_building_heat_capacitance(spec: OpenBESSpecification) -> float:
    """Calculate the building heat capacitance based on building specifications.
    Cm
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        float: The building heat capacitance in kJ/K.
    """
    raise NotImplementedError

def get_internal_air_heat_capacitance(spec: OpenBESSpecification) -> float:
    """Calculate the internal air heat capacitance based on building specifications.
    Ѳm
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        float: The internal air heat capacitance in kJ/K.
    """
    raise NotImplementedError

def get_heat_transmission_by_ventilation(spec: OpenBESSpecification) -> float:
    """Calculate the heat transmission by ventilation based on building specifications.
    Hve
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        float: The heat transmission by ventilation in kW/K.
    """
    raise NotImplementedError

def get_heat_infilitration_window(spec: OpenBESSpecification) -> float:
    """Calculate the heat transmission by infiltration through windows based on building specifications.
    Htr,w
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        float: The heat transmission by infiltration through windows in kW/K.
    """
    raise NotImplementedError

def get_heat_infiltration_opaque(spec: OpenBESSpecification) -> float:
    """Calculate the heat infiltration through opaque surfaces based on building specifications.
    Htr,op
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        float: The heat infiltration through opaque surfaces in kW/K.
    """
    raise NotImplementedError

def get_heat_transmission_by_infiltration(spec: OpenBESSpecification) -> float:
    """Calculate the heat transmission by infiltration based on building specifications.
    Htr
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        float: The heat transmission by infiltration in kW/K.
    """
    raise NotImplementedError

def get_internal_heat_from_occupants(spec: OpenBESSpecification) -> float:
    """Calculate the internal heat gains from occupants based on building specifications.
    ϕint,oc
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        float: The internal heat gains from occupants in kW.
    """
    raise NotImplementedError

def get_internal_heat_from_appliances(spec: OpenBESSpecification) -> float:
    """Calculate the internal heat gains from appliances based on building specifications.
    ϕint,ap
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        float: The internal heat gains from appliances in kW.
    """
    raise NotImplementedError

def get_internal_heat_from_lighting(spec: OpenBESSpecification) -> float:
    """Calculate the internal heat gains from lighting based on building specifications.
    ϕint,l
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        float: The internal heat gains from lighting in kW.
    """
    raise NotImplementedError

def get_solar_heat_window(spec: OpenBESSpecification) -> float:
    """Calculate the solar heat gains through windows based on building specifications.
    ϕsol,w
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        float: The solar heat gains through windows in kW.
    """
    raise NotImplementedError

def get_solar_heat_opaque(spec: OpenBESSpecification) -> float:
    """Calculate the solar heat gains through opaque surfaces based on building specifications.
    ϕsol,op
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        float: The solar heat gains through opaque surfaces in kW.
    """
    raise NotImplementedError

def get_solar_heat(spec: OpenBESSpecification) -> float:
    """Calculate the solar heat gains based on building specifications.
    ϕsol
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        float: The solar heat gains in kW.
    """
    raise NotImplementedError

def get_internal_heat(spec: OpenBESSpecification) -> float:
    """Calculate the internal heat gains based on building specifications.
    ϕint
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        float: The internal heat gains in kW.
    """
    raise NotImplementedError

def get_temp_change_demand(spec: OpenBESSpecification) -> float:
    """Calculate the temperature change demand based on building specifications.
    ϕHC,nd, W/m2
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        float: The temperature change demand in kW.
    """
    raise NotImplementedError
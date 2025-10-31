import logging
from pandas import DataFrame

from .climate import get_hourly_dry_bulb_temperature, RELATIVE_HUMIDITY
from .utils import OPERATIONAL_DAYS_DF
from ..types import OpenBESSpecification

logger = logging.getLogger(__name__)

MIN_COOLING_CAPACITY = 0.01  # kW
MIN_COOLING_EFFICIENCY = 0.01  # kWh

def get_nominal_cooling_capcaity(spec: OpenBESSpecification) -> float:
    """Return the nominal cooling capacity of the cooling system.
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        float: Nominal cooling capacity in kW.
    """
    try:
        nominal_capacity = spec.cooling_system1_nominal_capacity * spec.cooling_system1_number
        return max(nominal_capacity, MIN_COOLING_CAPACITY)
    except (AttributeError, TypeError):
        logger.warning("No cooling system capacity specified; assuming minimal cooling capacity.")
    return 0.01

def get_sensible_cooling_capacity(spec: OpenBESSpecification) -> float:
    """Return the sensible cooling capacity of the cooling system.
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        float: Sensible cooling capacity in kW.
    """
    try:
        sensible_capacity = spec.cooling_system1_sensible_nominal_capacity * spec.cooling_system1_number
        return max(sensible_capacity, MIN_COOLING_CAPACITY)
    except (AttributeError, TypeError):
        logger.warning("No cooling system sensible capacity specified; assuming minimal sensible cooling capacity.")
    return 0.01

def get_nominal_cooling_consumption(spec: OpenBESSpecification) -> float:
    """Return the nominal cooling energy consumption of the cooling system.
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        float: Nominal cooling energy consumption in kWh.
    """
    try:
        eer = spec.cooling_system1_energy_efficifiency_ratio
    except (AttributeError, TypeError):
        logger.warning("No cooling system energy consumption specified; assuming minimal cooling energy consumption.")
        eer = MIN_COOLING_EFFICIENCY
    return spec.cooling_system1_nominal_capacity * eer

def add_set_point_temperature_column(df: DataFrame, spec: OpenBESSpecification) -> DataFrame:
    """Add a target temperature column to the DataFrame.
    Args:
        df (DataFrame): The DataFrame to add the column to.
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        DataFrame: The DataFrame with the added target temperature column.
    """
    df["target_temperature"] = spec.set_target_temperature
    return df

def get_cooling_consumption_per_hour(spec: OpenBESSpecification) -> DataFrame:
    """Return the hourly cooling energy consumption of the cooling system.""
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        DataFrame: Hourly cooling energy consumption in kWh.
    """
    data = get_hourly_dry_bulb_temperature(spec).rename(columns={'temp_air': 'dry_bulb_temperature'})
    data["reference_consumption_by_temp"] = 0.1117801 + \
      0.028493334 * RELATIVE_HUMIDITY  - \
      0.000411156 * (RELATIVE_HUMIDITY ^ 2) + \
      0.021414276 * data["dry_bulb_temperature"] + \
      0.000161125 * (data["dry_bulb_temperature"] ^ 2) - \
      0.000679104 * data["dry_bulb_temperature"] * RELATIVE_HUMIDITY

    data["target_temperature"] = spec.set_target_temperature...

    data["heat_transfer_rate"] = min(spec.cooling)...

    data["cooling_demand"] = data["heat_transfer_rate"] * spec.building_area / 1000

    # Fan cooling power is demand / capacity
    data["fan_cooling_power"] = data["reference_consumption_by_temp"] / get_sensible_cooling_capacity(spec)

    data["reference_consumption_fcp"] = 0.2012307 - \
      0.0312175 * fan_cooling_power + \
      1.9504979 * (fan_cooling_power^2) - \
      1.1205104 * (fan_cooling_power^3)

    hours_per_day = 24
    result = OPERATIONAL_DAYS_DF.copy()
    result = result * (nominal_consumption / hours_per_day)
    result.index = ["kWh"]
    return result

def get_cooling_per_month(spec: OpenBESSpecification) -> DataFrame:
    """Return the amount of energy used cooling for each month of the year.
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        DataFrame: Ventilation energy consumption in kWh for each month.
    """
    return get_cooling_consumption_per_hour(spec).groupby('month', as_index=True)['kWh'].sum().to_frame().T

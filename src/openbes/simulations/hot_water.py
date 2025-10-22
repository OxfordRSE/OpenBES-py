import logging
from pandas import DataFrame

from .utils import OPERATIONAL_DAYS_DF
from ..types import OpenBESSpecification

logger = logging.getLogger(__name__)

def get_daily_hot_water_nominal(spec: OpenBESSpecification) -> float:
    """Calculate nominal (pre-efficiency scaling) daily hot water energy consumption.
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        float: Nominal daily hot water energy consumption in kWh.
    """
    demand = spec.water_demand  # l/day
    specific_heat_capacity_water = 4.18  # J/g°C
    output_temp = spec.water_reference_temperature  # °C
    input_temp = spec.water_supply_temperature  # °C
    per_hour = 1 / 3_600  # Convert seconds to hours

    if demand is None or output_temp is None or input_temp is None:
        logger.warning("Insufficient data to calculate hot water energy consumption.")
        return 0.0

    temperature_rise = output_temp - input_temp  # °C (from cold to hot water)

    return specific_heat_capacity_water * temperature_rise * demand * per_hour

def get_daily_hot_water(spec: OpenBESSpecification) -> float:
    """
    Adjust nominal hot water energy consumption by heater efficiency.
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        float: Daily hot water energy consumption in kWh.
    """
    if spec.water_system_efficiency_cop is None:
        logger.warning("Insufficient data to calculate hot water energy consumption.")
        return 0.0

    return get_daily_hot_water_nominal(spec) * spec.water_system_efficiency_cop

def get_hot_water_per_month(spec: OpenBESSpecification) -> DataFrame:
    """Return the amount of energy used heating water for each month of the year.
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        DataFrame: Hot water energy consumption in kWh for each month.
    """
    kWh_per_day = get_daily_hot_water(spec)
    result = OPERATIONAL_DAYS_DF * kWh_per_day
    result.index = ["kWh"]
    return result
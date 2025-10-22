import logging
from pandas import DataFrame

from .utils import OPERATIONAL_DAYS_DF
from ..types import OpenBESSpecification

logger = logging.getLogger(__name__)

def get_ventilation_hours_per_day(spec: OpenBESSpecification) -> int:
    """Return the daily mechanical ventilation hours based on the specification.
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        int: Mechanical ventilation hours per day.
    """
    if spec.ventilation_system1_on_time is None or spec.ventilation_system1_off_time is None:
        logger.warning("Insufficient information to calculate ventilation hours.")
        return 0

    if spec.ventilation_system1_off_time < spec.ventilation_system1_on_time:
        logger.warning("Ventilation off time is earlier than on time; assuming zero hours.")
        return 0

    # Inclusive of both on and off hours, so add 1
    return spec.ventilation_system1_off_time - spec.ventilation_system1_on_time + 1

def get_mv_hours_per_month(spec: OpenBESSpecification) -> DataFrame:
    """Return the monthly mechanical ventilation hours based on the specification.
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        DataFrame: A DataFrame with mechanical ventilation hours for each month.
    """
    mv_hours = get_ventilation_hours_per_day(spec)

    mv_hours_df = OPERATIONAL_DAYS_DF.copy()
    mv_hours_df = mv_hours_df * mv_hours
    mv_hours_df.index = ["mv_hours"]
    return mv_hours_df

def get_ventilation_per_month(spec: OpenBESSpecification) -> DataFrame:
    """Return the amount of energy used ventilation for each month of the year.
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        DataFrame: Ventilation energy consumption in kWh for each month.
    """
    if spec.ventilation_system1_rated_input_power is None:
        logger.warning("No ventilation system power specified; assuming zero ventilation energy use.")
        power = 0.0
    else:
        power = spec.ventilation_system1_rated_input_power

    hours = get_mv_hours_per_month(spec)
    result = hours * power
    result.index = ["kWh"]
    return result
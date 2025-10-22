from pandas import DataFrame, Float64Dtype

from src.openbes.types import ENERGY_USE_CATEGORIES


def aggregate_monthly_zonal_energy(monthly_zonal_data: DataFrame, category: ENERGY_USE_CATEGORIES) -> DataFrame:
    """
    Args:
        monthly_zonal_data (DataFrame): A DataFrame containing monthly energy usage data by zone.
    Returns:
        DataFrame: A DataFrame with montly energy usage.
    """
    return monthly_zonal_data.sum(axis=1).to_frame(name=category.value)

def aggregate_energy_totals(energy_data: DataFrame) -> DataFrame:
    """Aggregate energy data to compute yearly totals.
    Args:
        energy_data (DataFrame): A DataFrame containing monthly energy data by use category.
    Returns:
        DataFrame: A DataFrame with yearly energy totals by use category.
    """
    return energy_data.sum(axis=0).to_frame(name="kWh/yr")

def sum_energy_totals(energy_totals: DataFrame) -> Float64Dtype:
    """Sum the energy totals from a DataFrame.
    Args:
        energy_totals (DataFrame): A DataFrame containing energy totals.
    Returns:
        Float64Dtype: The sum of the energy totals.
    """
    return energy_totals["kWh/yr"].sum()
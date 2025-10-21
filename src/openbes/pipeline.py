from pandas import DataFrame, Float64Dtype, concat

from .dataclasses import OpenBESSpecification, OpenBESParameters
from .utils import (
    MONTHS,
    LIGHTING_TECHNOLOGIES,
    LIGHTING_BALLASTS,
    ENERGY_USE_CATEGORIES,
)
from .wip import sum_energy_totals, aggregate_energy_totals
from .simulations import lighting


def pipeline(spec: OpenBESSpecification, parameters: OpenBESParameters) -> Float64Dtype:
    """A sample pipeline function that processes spec DataFrame and returns sum of energy totals.
    Args:
        spec (OpenBESSpecification): Dictionary of building specifications. Usually user-supplied.
        parameters (OpenBESParameters): Dictionary of simulation parameters. Usually fixed.
    Returns:
        Float64Dtype: The sum of the energy totals.
    """
    spec.other_electricity_usage = 1136.0
    spec.building_standby_load = 2321.2

    spec.lighting_system_name_z1 = "First Floor"
    spec.lighting_system_tech_z1 = LIGHTING_TECHNOLOGIES.FT_T8
    spec.lighting_system_lamp_number_z1 = 4
    spec.lighting_system_lamp_power_z1 = 18
    spec.lighting_system_ballast_z1 = LIGHTING_BALLASTS.BE
    spec.lighting_system_luminary_number_z1 = 35
    spec.lighting_system_similar_zone_number_z1 = 1
    spec.lighting_system_operating_hours_z1 = 8
    spec.lighting_system_simultaneity_factor_z1 = 0.7
    spec.lighting_system_name_z2 = "Second Floor"
    spec.lighting_system_tech_z2 = LIGHTING_TECHNOLOGIES.LED
    spec.lighting_system_lamp_number_z2 = 1
    spec.lighting_system_lamp_power_z2 = 40
    spec.lighting_system_luminary_number_z2 = 55
    spec.lighting_system_similar_zone_number_z2 = 1
    spec.lighting_system_operating_hours_z2 = 8
    spec.lighting_system_simultaneity_factor_z2 = 0.7

    lighting_per_month = lighting.get_kwh_per_month(spec)
    lighting_per_month.index = [ENERGY_USE_CATEGORIES.Lighting]

    data = DataFrame(
        {
            "Others": [spec.other_electricity_usage] * 12,
            "Building standby": [spec.building_standby_load] * 12,
            "Hot water": [275.88, 306.533333, 352.513333, 337.186667, 352.513333, 337.186667, 352.513333,
                          352.513333, 337.186667, 352.513333, 337.186667, 260.553333],
            "Ventilation": [27.0, 30.0, 34.5, 33.0, 34.5, 33.0, 34.5, 34.5, 33.0, 34.5, 33.0, 25.5],
            "Cooling": [0.0, 0.0, 0.0, 77.257219, 0.0, 578.141948, 1148.711630, 522.771472, 63.590424, 0.0,
                        0.0, 0.0],
            "Heating": [0.0] * 12,
        },
        index=MONTHS.list()
    ).transpose()

    data = concat([data, lighting_per_month])

    monthly_kwh_by_use = data

    annual_kwh_per_category = aggregate_energy_totals(monthly_kwh_by_use)

    annual_kwh_total = annual_kwh_per_category.sum()

    total_simulated = sum_energy_totals(annual_kwh_total)
    return total_simulated

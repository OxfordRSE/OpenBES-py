from pandas import DataFrame, Float64Dtype, concat

from .types import (
    OpenBESSpecification,
    OpenBESParameters,
    MONTHS,
    ENERGY_USE_CATEGORIES,
    LIGHTING_TECHNOLOGIES,
    LIGHTING_BALLASTS,
    ENERGY_SOURCES,
)
from .wip import sum_energy_totals, aggregate_energy_totals
from .simulations import lighting, hot_water, ventilation



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

    spec.water_system_energy_source = ENERGY_SOURCES.Electricity
    spec.water_system_efficiency_cop = 1.0
    spec.water_demand = 300.0
    spec.water_reference_temperature = 60.0
    spec.water_supply_temperature = 16.0

    spec.ventilation_system1_energy_source = ENERGY_SOURCES.Electricity
    spec.ventilation_system1_rated_input_power = 0.3
    spec.ventilation_system1_on_time = 10
    spec.ventilation_system1_off_time = 14

    lighting_per_month = lighting.get_kwh_per_month(spec)
    lighting_per_month.index = [ENERGY_USE_CATEGORIES.Lighting]

    if spec.water_system_energy_source == ENERGY_SOURCES.Electricity:
        water_per_month = hot_water.get_hot_water_per_month(spec)
        water_per_month.index = [ENERGY_USE_CATEGORIES.Hot_water]
    else:
        water_per_month = DataFrame(
            {
                ENERGY_USE_CATEGORIES.Hot_water: [0.0] * 12
            },
            index=MONTHS.list()
        )

    if spec.ventilation_system1_energy_source == ENERGY_SOURCES.Electricity:
        ventilation_per_month = ventilation.get_ventilation_per_month(spec)
        ventilation_per_month.index = [ENERGY_USE_CATEGORIES.Ventilation]
    else:
        ventilation_per_month = DataFrame(
            {
                ENERGY_USE_CATEGORIES.Ventilation: [0.0] * 12
            },
            index=MONTHS.list()
        )

    data = DataFrame(
        {
            "Others": [spec.other_electricity_usage] * 12,
            "Building standby": [spec.building_standby_load] * 12,
            "Cooling": [0.0, 0.0, 0.0, 77.257219, 0.0, 578.141948, 1148.711630, 522.771472, 63.590424, 0.0,
                        0.0, 0.0],
            "Heating": [0.0] * 12,
        },
        index=MONTHS.list()
    ).transpose()

    data = concat([data, lighting_per_month, water_per_month, ventilation_per_month])

    monthly_kwh_by_use = data

    annual_kwh_per_category = aggregate_energy_totals(monthly_kwh_by_use)

    annual_kwh_total = annual_kwh_per_category.sum()

    total_simulated = sum_energy_totals(annual_kwh_total)
    return total_simulated

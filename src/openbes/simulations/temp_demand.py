import logging
from pandas import DataFrame

from .climate import (
    get_epw_data,
    get_internal_surface_temp,
    get_supply_air_temp,
)
from .geometry import get_conditioned_floor_area
from .lighting import get_lighting_ratio, get_lighting_heat, get_parasitic_heat
from .occupancy import get_occupancy_by_hour, get_metabolic_rate_per_m2, HOURS_DF
from ..types import OpenBESSpecification

logger = logging.getLogger(__name__)

def get_heat_transmission_by_ventilation(spec: OpenBESSpecification) -> float:
    """Calculate the heat transmission by ventilation based on building specifications.
    Hve [Hourly Simulation column AL]
    
    Heat transfer of ventilation (Hve, W/m2 K) is calculated according to
    Eq. (5). It is based on total air flow due to leakage and ventilation
    airflow (qve), and supply air temperature (Ѳsup).

    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        float: The heat transmission by ventilation in kW/K.
    """
    air_density = 1.2110  # kg/m3
    specific_heat_capacity_air = 1.0150  # kJ/kgK
    heat_capacity_air = air_density * specific_heat_capacity_air / 3.6  # W/m3K
    # qv_total = qv_fresh_inf \
    #            + qv_fresh_total + \
    #            qv_mechanical_1 + \
    #            qv_mechanical_2
    # qv_total is in m3/h
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

def get_internal_heat_from_occupants(spec: OpenBESSpecification) -> DataFrame:
    """Calculate the internal heat gains from occupants based on building specifications.
    ϕint,oc [Hourly Simulation column KI]
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        DataFrame: Hourly internal heat gains from occupants in W/m2.
    """
    df = get_occupancy_by_hour(spec)
    df['internal_heat_from_occupants'] = df['occupancy_ratio'] * get_metabolic_rate_per_m2(spec)
    return df[['internal_heat_from_occupants']]


def get_internal_heat_from_appliances(spec: OpenBESSpecification) -> DataFrame:
    """Calculate the internal heat gains from appliances based on building specifications.
    ϕint,ap [Hourly Simulation column KJ]

    Appliance heat generation is modelled as a constant value per m2, scaled by occupation ratio.

    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        DataFrame: Hourly internal heat gains from appliances in W/m2.
    """
    # Constant, Inputs cell C144, Table G.11 ISO 13790
    appliance_W_per_m2 = 1.0
    df = get_occupancy_by_hour(spec)
    df['internal_heat_from_appliances'] = df['occupancy_ratio'] * appliance_W_per_m2
    return df[['internal_heat_from_appliances']]


def get_internal_heat_from_lighting(spec: OpenBESSpecification) -> DataFrame:
    """Calculate the internal heat gains from lighting based on building specifications.
    ϕint,l [Hourly Simulation column KK, KQ]

    Lighting heat generation is modelled using a constant standby (parasitic) output (Wpc) and
    an occupancy-scaled output (Wli).

    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        DataFrame: Hourly internal heat gains from lighting in W/m2.
    """
    df = get_lighting_ratio(spec=spec)
    df['internal_heat_from_lighting'] = (
        (df['lighting_ratio'] * get_lighting_heat(spec=spec)) + get_parasitic_heat(spec=spec)
    )
    return df[['internal_heat_from_lighting']]

def get_internal_heat(spec: OpenBESSpecification) -> DataFrame:
    """Calculate the internal heat gains based on building specifications.
    ϕint [Hourly Simulation column AI; KL]

    Internal heat gains are the sum of internal heat gains from occupants, appliances, and lighting.

    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        DataFrame: The internal heat gains in W/m2.
    """
    df = get_internal_heat_from_lighting(spec=spec).join(
        get_internal_heat_from_occupants(spec=spec)
    ).join(
        get_internal_heat_from_appliances(spec=spec)
    )
    df['internal_heat'] = (
            df['internal_heat_from_occupants'] +
            df['internal_heat_from_appliances'] +
            df['internal_heat_from_lighting']
    )
    return df[['internal_heat']]

def get_internal_heat_adjusted(spec: OpenBESSpecification) -> DataFrame:
    """Calculate the adjusted internal heat gains based on building specifications.""
    ϕia [Hourly Simulation column AQ]

    Adjusted internal heat gains are the internal heat gains multiplied by an adjustment factor.

    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        DataFrame: The adjusted internal heat gains in W/m2.
    """
    adjustment_factor = 0.5  # Hardcoded in spreadsheet column AQ
    df = get_internal_heat(spec=spec)
    df['internal_heat_adjusted'] = df['internal_heat'] * adjustment_factor
    return df[['internal_heat_adjusted']]

def get_air_free_temp_0m(spec: OpenBESSpecification) -> DataFrame:
    """Return a DataFrame with air free temperature at 0m for each hour of the year.
    Ѳair,0 [Hourly Simulation column AY]

    Calculated by considering:
    - Internal surface temperature and its heat transfer rate to air
    - Heat transmission by ventilation and supply air temperature
    - Internal heat gains (adjusted)
    - HC_nd (assumed to be 0)
    and dividing by the total heat transfer rates to air (from surfaces and ventilation).

    This produces a weighted sum of these temperature influences to estimate the air free temperature at 0m height.

    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        DataFrame: HOURS_DF with air free temperature at 0m for each hour of the year.
    """
    df = HOURS_DF.copy()
    temp_air = get_epw_data(spec)['temp_air']
    temp_air.index = df.index
    df = df.join(temp_air)
    df = df.join(get_internal_surface_temp(spec=spec))
    df = df.join(get_heat_transmission_by_ventilation(spec=spec))
    df = df.join(get_supply_air_temp(spec=spec))
    df = df.join(get_internal_heat_adjusted(spec=spec))
    conditioned_area = get_conditioned_floor_area(spec=spec)
    area_at = 4.5  # Hardcoded in Hourly Simulation cell AM84: EN ISO 13790, 7.2.2
    total_area = area_at * conditioned_area
    # Heat transfer rate from air to surfaces in W/K [Hourly simulation cell AR83]
    Htr_is_W_per_K = 3.45 * total_area
    # Heat transfer rate from air to surfaces in W/m2K [Hourly Simulation cell AR98]
    Htr_is = Htr_is_W_per_K / conditioned_area
    HC_nd = 0  # Hardcoded in Hourly Simulation cell AR111
    df['air_free_temp_0m'] = (
                                 Htr_is * df['internal_surface_temp'] +
                                 df['heat_transmission_by_ventilation'] * df['supply_air_temp'] +
                                 df['internal_heat_adjusted'] +
                                 HC_nd
                             ) / ( Htr_is + df['heat_transmission_by_ventilation'] )
    return df[['air_free_temp_0m']]

def get_solar_heat_window(spec: OpenBESSpecification) -> DataFrame:
    """Calculate the solar heat gains through windows based on building specifications.
    ϕsol,w [Hourly Simulation column LF]

    Wattage is given by the sum of solar radiation on each window multiplied by its
    area and solar heat gain coefficient.
    Solar radiation is a function of climate data and building orientation.

    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        DataFrame: Hourly solar heat gains through windows in W/m2.
    """
    kv116 = 22  # Hardcoded in Hourly Simulation cell KV116
    df = get_air_free_temp_0m(spec=spec)
    df['solar_heat_window'] = df.apply(
        lambda row: row
    )
    # if $AY117 < kv116:
    #     rest = (KW$95*(KW$107*($KV118*$KW$100))*M118)-(KW$80*($KS118*KW$104*KW$105*KW$81*$KW$82))
    # else:
    #     rest = (KW$95*(KW$108*($KV118*0.9))*M118)-(KW$80*($KS118*KW$104*KW$105*KW$81*$KW$82))
    # return max(
    #     0,
    #     rest
    # )


def get_solar_heat_opaque(spec: OpenBESSpecification) -> DataFrame:
    """Calculate the solar heat gains through opaque surfaces based on building specifications.
    ϕsol,op [Hourly Simulation column LR]

    Wattage is given by the sum of solar radiation on each opaque surface multiplied by its
    area and solar heat gain coefficient.
    Solar radiation is a function of climate data and building orientation.
    Horizontal solar radiation is also included because of roof surfaces.

    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        DataFrame: Hourly solar heat gains through opaque surfaces in W/m2.
    """
    raise NotImplementedError


def get_solar_heat(spec: OpenBESSpecification) -> DataFrame:
    """Calculate the solar heat gains based on building specifications.
    ϕsol [Hourly Simulation column AJ, KM]

    Wattage per square meter is given by the sum of solar heat gains through windows
    and opaque surfaces, divided by the conditioned floor area.

    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        DataFrame: Hourly solar heat gains in W/m2.
    """
    conditioned_floor_area = get_conditioned_floor_area(spec=spec)
    df = get_solar_heat_window(spec=spec).join(
        get_solar_heat_opaque(spec=spec)
    )
    df['solar_heat'] = (df['solar_heat_window'] + df['solar_heat_opaque']) / conditioned_floor_area
    return df[['solar_heat']]

def get_temp_change_demand(spec: OpenBESSpecification) -> float:
    """Calculate the temperature change demand based on building specifications.
    ϕHC,nd, W/m2
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        float: The temperature change demand in W/m2.
    """
    raise NotImplementedError

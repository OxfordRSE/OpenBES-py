from ..types import OpenBESSpecification


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
    qv_total = qv_fresh_inf \
               + qv_fresh_total + \
               qv_mechanical_1 + \
               qv_mechanical_2
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


def get_internal_heat_from_occupants(spec: OpenBESSpecification) -> float:
    """Calculate the internal heat gains from occupants based on building specifications.
    ϕint,oc [Hourly Simulation column KI]
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        float: The internal heat gains from occupants in W/m2.
    """
    return occupation_fraction * metabolic_rate_pp
    raise NotImplementedError


def get_internal_heat_from_appliances(spec: OpenBESSpecification) -> float:
    """Calculate the internal heat gains from appliances based on building specifications.
    ϕint,ap [Hourly Simulation column KJ]
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        float: The internal heat gains from appliances in W/m2.
    """
    raise NotImplementedError


def get_internal_heat_from_lighting(spec: OpenBESSpecification) -> float:
    """Calculate the internal heat gains from lighting based on building specifications.
    ϕint,l [Hourly Simulation column KK]
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        float: The internal heat gains from lighting in W/m2.
    """
    raise NotImplementedError


def get_solar_heat_window(spec: OpenBESSpecification) -> float:
    """Calculate the solar heat gains through windows based on building specifications.
    ϕsol,w
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        float: The solar heat gains through windows in W/m2.
    """
    raise NotImplementedError


def get_solar_heat_opaque(spec: OpenBESSpecification) -> float:
    """Calculate the solar heat gains through opaque surfaces based on building specifications.
    ϕsol,op
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        float: The solar heat gains through opaque surfaces in W/m2.
    """
    raise NotImplementedError


def get_solar_heat(spec: OpenBESSpecification) -> float:
    """Calculate the solar heat gains based on building specifications.
    ϕsol [Hourly Simulation column AJ]
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        float: The solar heat gains in W/m2.
    """
    raise NotImplementedError


def get_internal_heat(spec: OpenBESSpecification) -> float:
    """Calculate the internal heat gains based on building specifications.
    ϕint [Hourly Simulation column AI; KL]
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        float: The internal heat gains in W/m2.
    """
    return get_internal_heat_from_occupants(spec) + \
              get_internal_heat_from_appliances(spec) + \
              get_internal_heat_from_lighting(spec)

def get_temp_change_demand(spec: OpenBESSpecification) -> float:
    """Calculate the temperature change demand based on building specifications.
    ϕHC,nd, W/m2
    Args:
        spec (OpenBESSpecification): The building specifications spec data class.
    Returns:
        float: The temperature change demand in W/m2.
    """
    raise NotImplementedError

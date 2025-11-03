from src.openbes.types import OpenBESSpecification


def get_window_area(spec: OpenBESSpecification) -> float:
    """Calculate the total window area of the building in square meters.

    Args:
        spec (OpenBESSpecification): The OpenBESS specification containing building details.

    Returns:
        float: Total window area in square meters.
    """
    raise NotImplementedError

def get_opaque_envelope_area(spec: OpenBESSpecification) -> float:
    """Calculate the total opaque envelope area of the building in square meters.

    Args:
        spec (OpenBESSpecification): The OpenBESS specification containing building details.

    Returns:
        float: Total opaque envelope area in square meters.
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

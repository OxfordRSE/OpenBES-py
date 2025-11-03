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


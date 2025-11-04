import math
from typing import List

from src.openbes.simulations.occupancy import get_zone_total_area
from src.openbes.types import (
    OpenBESSpecification,
    OCCUPATION_ZONES,
    get_zone_number,
    COMPASS_POINTS,
    FLOORS,
    ORIENTATIONS,
)


class Rectangle:
    def __init__(self, length: float, width: float):
        self.length = length
        self.width = width

    def __eq__(self, other):
        if not isinstance(other, Rectangle):
            return NotImplemented
        return self.length == other.length and self.width == other.width

    def compare(self, other):
        return f"Length: {self.length} vs {other.length}, Width: {self.width} vs {other.width}"


def get_equivalent_rectangle(spec: OpenBESSpecification) -> Rectangle:
    """Calculate the length and width of the equivalent rectangle of the building.
    [Inputs cells near B49]

    Args:
        spec (OpenBESSpecification): The OpenBESS specification containing building details.

    Returns:
        Rectangle: Equivalent rectangle for the input building geometry.
    """
    if (
        spec.parameters.courtyard_number == 0 and
        spec.parameters.open_courtyard_number_a1 == 0 and
        spec.parameters.open_courtyard_number_b1 == 0 and
        spec.parameters.open_courtyard_number_c1 == 0 and
        spec.parameters.open_courtyard_number_d1 == 0
    ):
        return Rectangle(length=spec.building_length, width=spec.building_width)
    if (
            (spec.parameters.courtyard_number != 0 and spec.parameters.courtyard_length is None) or
            (spec.parameters.open_courtyard_number_a1 != 0 and spec.parameters.open_courtyard_depth_a1 is None) or
            (spec.parameters.open_courtyard_number_b1 != 0 and spec.parameters.open_courtyard_depth_b1 is None) or
            (spec.parameters.open_courtyard_number_c1 != 0 and spec.parameters.open_courtyard_depth_c1 is None) or
            (spec.parameters.open_courtyard_number_d1 != 0 and spec.parameters.open_courtyard_depth_d1 is None)
    ):
        raise ValueError("Courtyard dimensions must be provided if courtyard numbers are greater than zero.")
    length = (
        spec.building_length +
        float(spec.parameters.courtyard_number or 0) * spec.parameters.courtyard_length +
        spec.parameters.open_courtyard_depth_b1 * float(spec.parameters.open_courtyard_number_b1 or 0) +
        spec.parameters.open_courtyard_depth_d1 * float(spec.parameters.open_courtyard_number_d1 or 0)
    )
    width = (
        spec.building_width +
        float(spec.parameters.courtyard_number or 0) * spec.parameters.courtyard_width +
        spec.parameters.open_courtyard_depth_a1 * float(spec.parameters.open_courtyard_number_a1 or 0) +
        spec.parameters.open_courtyard_depth_c1 * float(spec.parameters.open_courtyard_number_c1 or 0)
    )
    return Rectangle(length=length, width=width)

def get_conditioned_floor_area(spec: OpenBESSpecification, floors: List[FLOORS] = None) -> float:
    """Calculate the total conditioned floor area of the building in square meters.
    A,f [Inputs cell N45]
    Args:
        spec (OpenBESSpecification): The OpenBESS specification containing building details.
        floors: List of floors to consider. If None, all floors are considered.
    Returns:
        float: Total conditioned floor area in square meters.
    """
    gross_area = 0.0
    for zone in OCCUPATION_ZONES:
        z = get_zone_number(zone)
        if getattr(spec, f'condition_z{z}'):
            gross_area += get_zone_total_area(spec=spec, zone=zone, floors=floors)
    return gross_area * spec.parameters.nia_gba_ratio

def get_conditioned_external_vertical_envelope_area(
        spec: OpenBESSpecification,
        orientations: List[ORIENTATIONS] = None,
        floors: List[FLOORS] = None,
) -> float:
    """Calculate the total external vertical envelope area of the building in square meters.

    Args:
        spec (OpenBESSpecification): The OpenBESS specification containing building details.
        orientations: List of orientations to consider. If None, all orientations are considered.
        floors: List of floors to consider. If None, all floors are considered.
    Returns:
        float: Total external vertical envelope area in square meters.
    """
    # [Inputs cell C307]
    equivalent_rectangle = get_equivalent_rectangle(spec=spec)
    building_rectangular_ratio = equivalent_rectangle.length / equivalent_rectangle.width
    height = spec.floor_to_ceiling_height + spec.slab_thickness
    if orientations is None:
        orientations = list(ORIENTATIONS)
    if floors is None:
        floors = list(FLOORS)
    area = 0.0
    for orientation in orientations:
        for floor in floors:
            floor_area = get_conditioned_floor_area(spec=spec, floors=[floor])
            if orientation in [ORIENTATIONS.Up, ORIENTATIONS.Down]:
                area += math.sqrt(floor_area * building_rectangular_ratio) * height  # length
            else:
                area += math.sqrt(floor_area / building_rectangular_ratio) * height  # width
    return area

def get_window_count(
        spec: OpenBESSpecification,
        floors: List[FLOORS] = None,
        orientations: List[ORIENTATIONS] = None
) -> int:
    """Calculate the total number of windows in the building.

    Args:
        spec (OpenBESSpecification): The OpenBESS specification containing building details.
        floors: List of floors to consider. If None, all floors are considered.
        orientations: List of orientations to consider. If None, all orientations are considered.

    Returns:
        int: Total number of windows.
    """
    total_windows = 0
    if floors is None:
        floors = list(FLOORS)
    if orientations is None:
        orientations = list(ORIENTATIONS)
    for floor in floors:
        floor_suffix = {
            FLOORS.Ground: "ground",
            FLOORS.First: "first",
            FLOORS.Second: "second",
            FLOORS.Third: "third",
            FLOORS.Fourth: "fourth",
        }[floor]
        for orientation in orientations:
            orientation_suffix = {
                ORIENTATIONS.Up: "a1",
                ORIENTATIONS.Right: "b1",
                ORIENTATIONS.Down: "c1",
                ORIENTATIONS.Left: "d1",
            }[orientation]
            window_count_attr = f'window_number_{floor_suffix}_{orientation_suffix}'
            window_count = getattr(spec, window_count_attr, 0) or 0
            total_windows += window_count
    return total_windows

def get_window_area_envelope(
        spec: OpenBESSpecification,
        orientations: List[ORIENTATIONS] = None,
        floors: List[FLOORS] = None,
) -> float:
    """Calculate the total window area of the building envelope in square meters.

    Args:
        spec (OpenBESSpecification): The OpenBESS specification containing building details.
        orientations: List of orientations to consider. If None, all orientations are considered.
        floors: List of floors to consider. If None, all floors are considered.

    Returns:
        float: Total window area in square meters.
    """
    return get_window_count(spec=spec, floors=floors, orientations=orientations) * spec.window_height

def get_window_area(spec: OpenBESSpecification) -> float:
    """Calculate the window area of the building in square meters.
    [Inputs cells near M120]
    TODO: link with orientation envelope data

    Args:
        spec (OpenBESSpecification): The OpenBESS specification containing building details.

    Returns:
        float: Total window area in square meters.
    """
    
    # (
    #     IF(AND(spec.orientation_angle >=180-18, spec.orientation_angle < 180-18+36), H75 * (H99),0) +
    #     IF(AND(spec.orientation_angle >= 270-18, spec.orientation_angle < (270-18+36)), K75 * (K99),0) +
    #     IF(OR(spec.orientation_angle>360-18,spec.orientation_angle<18), J75 * (J99), 0) +
    #     IF(AND(spec.orientation_angle>=(90-18),spec.orientation_angle<(90-18+36)), I75 * (I99), 0)
    # )
    area = 0.0
    for orientation in COMPASS_POINTS:
        orientation_area = getattr(spec, f'window_area_{orientation.lower()}')
        area += orientation_area
    raise NotImplementedError

def get_window_shading(spec: OpenBESSpecification) -> float:
    """Calculate the total shaded window factor for the building in meters.

    [Inputs cell G265, AB125]

    Calculated as the window area divided by the window height, multiplied by a constant external perimeter rate.

    Args:
        spec (OpenBESSpecification): The OpenBESS specification containing building details.

    Returns:
        float: Total shaded window factor in meters.
    """
    external_permimeter_rate = 0.75  # Constant, hardcoded in Inputs cell X115
    return (get_window_area(spec=spec) / spec.window_height) * external_permimeter_rate

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

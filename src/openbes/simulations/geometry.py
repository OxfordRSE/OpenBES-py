import math
from typing import Optional

from pandas import MultiIndex, DataFrame, Series

from src.openbes.types import (
    OpenBESSpecification,
    OCCUPATION_ZONES,
    get_zone_number,
    COMPASS_POINTS,
    FLOORS,
    ORIENTATIONS,
)

ZONAL_RECTANGLES = DataFrame(
    index=MultiIndex.from_product([list(FLOORS), list(OCCUPATION_ZONES)], names=['floor', 'zone'])
)

ORIENTATION_FACADE = DataFrame(
    index=MultiIndex.from_product([list(FLOORS), list(ORIENTATIONS)], names=['floor', 'orientation'])
)

COMPASS_POINT_FACADE = DataFrame(
    index=MultiIndex.from_product([list(FLOORS), list(COMPASS_POINTS)], names=['floor', 'compass_point'])
)

# Map whether each orientation is exposed to each compass point
EXPOSURES_MAP = DataFrame(
    index=MultiIndex.from_product([list(ORIENTATIONS), list(COMPASS_POINTS)], names=['orientation', 'compass_point'])
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

    @property
    def ratio(self):
        return self.length / self.width

    @property
    def area(self):
        return self.length * self.width


class BuildingGeometry:
    """
    Class to handle building geometry calculations based on OpenBESS specifications.
    Calculates equivalent rectangle, gross floor area, external vertical envelope area,
    window counts, window areas, and other geometry-related metrics.

    """
    spec: OpenBESSpecification
    _equivalent_rectangle: Rectangle
    _gross_floor_area: DataFrame
    _rectangles: DataFrame
    _orientation_facade: DataFrame
    _compass_point_facade: DataFrame
    _exposures: DataFrame
    
    def __init__(self, spec: OpenBESSpecification):
        self.spec = spec
        self._rectangles = ZONAL_RECTANGLES.copy()
        self._orientation_facade = ORIENTATION_FACADE.copy()
        self._compass_point_facade = COMPASS_POINT_FACADE.copy()
        self._exposures = EXPOSURES_MAP.copy()

    @property
    def equivalent_rectangle(self) -> Rectangle:
        """Calculate the length and width of the equivalent rectangle of the building.
        [Inputs cells near B49]
    
        Returns:
            Rectangle: Equivalent rectangle for the input building geometry.
        """
        if not hasattr(self, '_equivalent_rectangle') or not isinstance(self._equivalent_rectangle, Rectangle):
            parameters = self.spec.parameters
            if (
                parameters.courtyard_number == 0 and
                parameters.open_courtyard_number_a1 == 0 and
                parameters.open_courtyard_number_b1 == 0 and
                parameters.open_courtyard_number_c1 == 0 and
                parameters.open_courtyard_number_d1 == 0
            ):
                self._equivalent_rectangle = Rectangle(length=self.spec.building_length, width=self.spec.building_width)
            elif (
                    (parameters.courtyard_number != 0 and parameters.courtyard_length is None) or
                    (parameters.open_courtyard_number_a1 != 0 and parameters.open_courtyard_depth_a1 is None) or
                    (parameters.open_courtyard_number_b1 != 0 and parameters.open_courtyard_depth_b1 is None) or
                    (parameters.open_courtyard_number_c1 != 0 and parameters.open_courtyard_depth_c1 is None) or
                    (parameters.open_courtyard_number_d1 != 0 and parameters.open_courtyard_depth_d1 is None)
            ):
                raise ValueError("Courtyard dimensions must be provided if courtyard numbers are greater than zero.")
            else:
                length = (
                    self.spec.building_length +
                    float(parameters.courtyard_number or 0) * parameters.courtyard_length +
                    parameters.open_courtyard_depth_b1 * float(parameters.open_courtyard_number_b1 or 0) +
                    parameters.open_courtyard_depth_d1 * float(parameters.open_courtyard_number_d1 or 0)
                )
                width = (
                    self.spec.building_width +
                    float(parameters.courtyard_number or 0) * parameters.courtyard_width +
                    parameters.open_courtyard_depth_a1 * float(parameters.open_courtyard_number_a1 or 0) +
                    parameters.open_courtyard_depth_c1 * float(parameters.open_courtyard_number_c1 or 0)
                )
                self._equivalent_rectangle = Rectangle(length=length, width=width)
        return self._equivalent_rectangle

    def _get_gross_floor_area(self, row: Series) -> float:
        """[Reads values from Tool C58:G65]"""
        zone = row.name[1]
        z = get_zone_number(zone)
        if getattr(self.spec, f'condition_z{z}'):
            floor = row.name[0]
            return getattr(self.spec, f"{floor.value}_floor_area_z{z}") or 0.0
        return 0.0

    @property
    def gross_floor_areas(self) -> DataFrame:
        """Calculate the total conditioned floor area of the building in square meters.
        A,f [Inputs cells C39:G45]

        Returns:
            DataFrame: Total gross floor area in square meters for each zone and floor.
        """
        if 'gross_floor_area' not in self._rectangles.columns:
            self._rectangles['gross_floor_area'] = 0.0
            self._rectangles['gross_floor_area'] = self._rectangles.apply(self._get_gross_floor_area, axis=1)

        return self._rectangles[['gross_floor_area']]

    def get_gross_floor_area_for_floor(self, floor: FLOORS) -> float:
        """Calculate the total gross floor area for a specific floor in square meters.
        [Inputs cells I40:44]
        Args:
            floor (FLOORS): The floor to calculate the gross floor area for.

        Returns:
            float: Total gross floor area for the specified floor in square meters.
        """
        return self.gross_floor_areas.xs(floor, level='floor')['gross_floor_area'].sum()

    @property
    def gross_floor_area(self) -> float:
        """Calculate the total gross floor area of the building in square meters.
        A,G [Inputs cell I45]

        Returns:
            float: Total gross floor area in square meters.
        """
        return self.gross_floor_areas['gross_floor_area'].sum()

    def _get_conditioned_floor_area(self, row: Series) -> float:
        z = get_zone_number(row.name[1])
        if not getattr(self.spec, f'condition_z{z}'):
            return 0.0
        return row['gross_floor_area'] * self.spec.parameters.nia_gba_ratio

    @property
    def conditioned_floor_areas(self) -> DataFrame:
        """Calculate the total conditioned floor area of the building in square meters.
        N45 [Inputs cell N45]

        Returns:
            DataFrame: Total conditioned floor area in square meters for each zone and floor.
        """
        if 'conditioned_floor_area' not in self._rectangles.columns:
            self._rectangles['conditioned_floor_area'] = self.gross_floor_areas.apply(
                self._get_conditioned_floor_area, axis=1
            )
        return self._rectangles[['conditioned_floor_area']]

    def get_conditioned_floor_area_for_floor(self, floor: FLOORS) -> float:
        """Calculate the total conditioned floor area for a specific floor in square meters.
        [Inputs cells N40:44]
        Args:
            floor (FLOORS): The floor to calculate the conditioned floor area for.

        Returns:
            float: Total conditioned floor area for the specified floor in square meters.
        """
        return self.conditioned_floor_areas.xs(floor, level='floor')['conditioned_floor_area'].sum()

    @property
    def conditioned_floor_area(self) -> float:
        return self.conditioned_floor_areas['conditioned_floor_area'].sum()

    def _get_external_vertical_envelope_area(self, 
            spec: OpenBESSpecification,
            row: DataFrame,
            conditioned: bool = False
    ) -> float:
        """Calculate the total external vertical envelope area of the building in square meters.
    
        Args:
            row: DataFrame row with MultiIndex including 'floor' and 'orientation'.
            conditioned: If True, calculate conditioned area; if False, calculate gross area.
        Returns:
            float: Total external vertical envelope area in square meters.
        """
        # [Inputs cell C54]
        building_rectangular_ratio = self.equivalent_rectangle.ratio
        height = spec.floor_to_ceiling_height + spec.slab_thickness
        orientation = row.name[1]
        floor = row.name[0]
        if conditioned:
            floor_area = self.get_conditioned_floor_area_for_floor(floor)
        else:
            floor_area = self.get_gross_floor_area_for_floor(floor)

        if orientation in [ORIENTATIONS.Up, ORIENTATIONS.Down]:
            return math.sqrt(floor_area * building_rectangular_ratio) * height  # length
        else:
            return math.sqrt(floor_area / building_rectangular_ratio) * height  # width

    @property
    def external_vertical_envelope_gross_areas(self) -> DataFrame:
        """Calculate the total external vertical envelope gross area of the building in square meters.
        [Input cells C64:F69]

        Returns:
            DataFrame: Total external vertical envelope gross area in square meters for each orientation and floor.
        """
        if 'external_vertical_envelope_gross_area' not in self._orientation_facade.columns:
            self._orientation_facade['external_vertical_envelope_gross_area'] = 0.0
            self._orientation_facade['external_vertical_envelope_gross_area'] = self._orientation_facade.apply(
                lambda row: self._get_external_vertical_envelope_area(
                    spec=self.spec,
                    row=row,
                    conditioned=False
                ),
                axis=1
            )
        return self._orientation_facade[['external_vertical_envelope_gross_area']]

    @property
    def external_vertical_envelope_conditioned_areas(self) -> DataFrame:
        """Calculate the total external vertical envelope conditioned area of the building in square meters.
        [Input cells C74:F79]
        Returns:
            DataFrame: Total external vertical envelope conditioned area in square meters for each orientation and floor.
        """
        if 'external_vertical_envelope_conditioned_area' not in self._orientation_facade.columns:
            self._orientation_facade['external_vertical_envelope_conditioned_area'] = 0.0
            self._orientation_facade['external_vertical_envelope_conditioned_area'] = self._orientation_facade.apply(
                lambda row: self._get_external_vertical_envelope_area(
                    spec=self.spec,
                    row=row,
                    conditioned=True
                ),
                axis=1
            )
        return self._orientation_facade[['external_vertical_envelope_conditioned_area']]

    def _get_window_count(self, row: Series):
        """
        Calculate the number of windows for a specific floor and orientation.

        Args:
            row: Series indexed by floor, orientation.
        """
        floor = row.name[0]
        orientation = row.name[1]
        floor_suffix = {
            FLOORS.Ground: "ground",
            FLOORS.First: "first",
            FLOORS.Second: "second",
            FLOORS.Third: "third",
            FLOORS.Fourth: "fourth",
        }[floor]
        orientation_suffix = {
            ORIENTATIONS.Up: "a1",
            ORIENTATIONS.Right: "b1",
            ORIENTATIONS.Down: "c1",
            ORIENTATIONS.Left: "d1",
        }[orientation]
        window_count_attr = f'window_number_{floor_suffix}_{orientation_suffix}'
        return getattr(self.spec, window_count_attr, 0) or 0

    @property
    def window_count(self) -> DataFrame:
        """DataFrame: Number of windows for each floor and orientation.

        [Inputs cells C90:F94] [Tool cells G72:J76]
        """
        if 'window_count' not in self._orientation_facade.columns:
            self._orientation_facade['window_count'] = 0
            self._orientation_facade['window_count'] = self._orientation_facade.apply(
                self._get_window_count,
                axis=1
            )
        return self._orientation_facade[['window_count']]

    @property
    def window_area_orientation(self) -> DataFrame:
        """Window area in square meters for each floor and orientation.
        """
        if 'window_area_orientation' not in self._orientation_facade.columns:
            if self.spec.window_height is None or self.spec.window_length is None:
                raise ValueError("Window height and length are required to model window area.")
            self._orientation_facade['window_area_orientation'] = (
                self.window_count['window_count'] * self.spec.window_height * self.spec.window_length
            )
        return self._orientation_facade[['window_area_orientation']]

    @property
    def window_ratio(self) -> DataFrame:
        """The proportion of each vertical envelope taken up by windows for each floor and orientation.
        [Inputs cells H90:K94]
        """
        if 'window_ratio' not in self._orientation_facade.columns:
            # Assertions ensure we have the required columns calculated
            assert self.external_vertical_envelope_gross_areas is not None
            assert self.window_area_orientation is not None
            self._orientation_facade['window_ratio'] = self._orientation_facade.apply(
                lambda row: (
                        row['window_area_orientation'] / row['external_vertical_envelope_gross_area']
                        if row['external_vertical_envelope_gross_area'] != 0.0 else None
                ),
                axis=1
            )
            self._orientation_facade['window_ratio'] = self._orientation_facade['window_ratio'].fillna(0.0)
        return self._orientation_facade[['window_ratio']]

    @classmethod
    def get_facing_direction(cls, orientation_angle: float) -> COMPASS_POINTS:
        """Return the compass point that a given orientation angle faces towards."""
        orientation_angle = orientation_angle % 360
        if orientation_angle < 22.5:
            return COMPASS_POINTS.North
        if orientation_angle < (22.5 + 37.5):
            return COMPASS_POINTS.NorthEast
        if orientation_angle < (22.5 + 37.5 + 51):
            return COMPASS_POINTS.East
        if orientation_angle < (22.5 + 37.5 + 51 + 51):
            return COMPASS_POINTS.SouthEast
        if orientation_angle < (22.5 + 37.5 + 51 + 51 + 36):
            return COMPASS_POINTS.South
        if orientation_angle < (22.5 + 37.5 + 51 + 51 + 36 + 51):
            return COMPASS_POINTS.SouthWest
        if orientation_angle < (22.5 + 37.5 + 51 + 51 + 36 + 51 + 51):
            return COMPASS_POINTS.West
        if orientation_angle < (22.5 + 37.5 + 51 + 51 + 36 + 51 + 51 + 37.5):
            return COMPASS_POINTS.NorthWest
        return COMPASS_POINTS.North

    def get_compass_point_for_orientation(self, orientation: ORIENTATIONS) -> COMPASS_POINTS:
        """Return the compass point that a given orientation faces towards."""
        if orientation == ORIENTATIONS.Up:
            return self.get_facing_direction(self.spec.orientation_angle)
        if orientation == ORIENTATIONS.Right:
            return self.get_facing_direction(self.spec.orientation_angle + 90)
        if orientation == ORIENTATIONS.Down:
            return self.get_facing_direction(self.spec.orientation_angle + 180)
        return self.get_facing_direction(self.spec.orientation_angle + 270)

    def get_orientation_for_compass_point(self, compass_point: COMPASS_POINTS) -> Optional[ORIENTATIONS]:
        """Return the orientation that faces towards a given compass point."""
        for orientation in ORIENTATIONS:
            if self.get_compass_point_for_orientation(orientation) == compass_point:
                return orientation
        return None

    def _get_window_area(self, row: Series) -> float:
        """Calculate the window area for a specific floor and compass point.

        Args:
            row: Series indexed by floor, compass_point. Must have 'window_area_orientation' column.

        Returns:
            float: Window area in square meters.
        """
        floor = row.name[0]
        compass_point = row.name[1]
        orientation = self.get_orientation_for_compass_point(compass_point)
        if orientation is None:
            return 0.0
        assert self.window_ratio is not None
        assert self.external_vertical_envelope_conditioned_areas is not None
        r = self._orientation_facade.loc[(floor, orientation)]
        return r['window_ratio'] * r['external_vertical_envelope_conditioned_area']

    @property
    def window_area(self) -> DataFrame:
        """The window area of the building in square meters by floor and compass point.
        [Inputs cells near M120]
        """
        if 'window_area' not in self._compass_point_facade.columns:
            self._compass_point_facade['window_area'] = 0.0
            self._compass_point_facade['window_area'] = self._compass_point_facade.apply(
                self._get_window_area,
                axis=1
            )
        return self._compass_point_facade[['window_area']]

    @property
    def window_shading(self) -> Series:
        """Shaded window factor for each floor.
    
        [Inputs cells AB120:124]
        """
        external_perimeter_rate = 0.75  # Constant, hardcoded in Inputs cell X115
        return (self.window_area.groupby(level='floor').sum() / self.spec.window_height) * external_perimeter_rate

    @property
    def opaque_area(self) -> DataFrame:
        """Opaque area of the building in square meters by floor and compass point.
        """
        raise NotImplementedError
    
    
    def get_building_heat_capacitance(self, spec: OpenBESSpecification) -> float:
        """Calculate the building heat capacitance based on building specifications.
        Cm
        Args:
            spec (OpenBESSpecification): The building specifications spec data class.
        Returns:
            float: The building heat capacitance in kJ/K.
        """
        raise NotImplementedError
    
    
    def get_internal_air_heat_capacitance(self, spec: OpenBESSpecification) -> float:
        """Calculate the internal air heat capacitance based on building specifications.
        Ѳm
        Args:
            spec (OpenBESSpecification): The building specifications spec data class.
        Returns:
            float: The internal air heat capacitance in kJ/K.
        """
        raise NotImplementedError

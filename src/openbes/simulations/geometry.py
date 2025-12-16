import math
from typing import Optional

from pandas import MultiIndex, DataFrame, Series

from ..types import (
    OpenBESSpecification,
    OCCUPATION_ZONES,
    get_zone_number,
    COMPASS_POINTS,
    FLOORS,
    ORIENTATIONS,
    THERMAL_BREAKS, HEAT_CAPACITY_CLASSES,
)

THERMAL_BREAK_TRANSMITTANCE = {
    THERMAL_BREAKS.Facade_ground: 0.54,
    THERMAL_BREAKS.Facade_intermediate: 0.60,
    THERMAL_BREAKS.Facade_roof: 0.44,
    THERMAL_BREAKS.Windows: 0.50,
    THERMAL_BREAKS.Shading: 0.80,
}

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
    _heat_transfer_rate_windows: float
    _heat_infiltration_opaque: float
    _heat_transfer_is: float
    _heat_transfer_ms: float
    _conditioned_floor_perimeters: Series
    _roof_projections: Series
    _roof_factor: float
    _conditioned_floor_area: float
    _building_mass_factor: float
    _heat_capacity_am: float
    _heat_capacity_cm: float

    def __init__(self, spec: OpenBESSpecification):
        self.spec = spec
        self._rectangles = ZONAL_RECTANGLES.copy()
        self._orientation_facade = ORIENTATION_FACADE.copy()
        self._compass_point_facade = COMPASS_POINT_FACADE.copy()
        self._exposures = EXPOSURES_MAP.copy()

    @property
    def heat_capacity_am(self) -> float:
        """Building heat capacity factor Am (m²).
        [Database cells AF5:AF10]
        Frequently appears as Am/Af e.g. in Hourly simulation AM91
        """
        if not hasattr(self, '_heat_capacity_am') or self._heat_capacity_am is None:
            if self.spec.heat_capacity in [
                HEAT_CAPACITY_CLASSES.Very_light,
                HEAT_CAPACITY_CLASSES.Light,
                HEAT_CAPACITY_CLASSES.Medium,
            ]:
                self._heat_capacity_am = 2.5
            elif self.spec.heat_capacity == HEAT_CAPACITY_CLASSES.Heavy:
                self._heat_capacity_am = 3.0
            elif self.spec.heat_capacity == HEAT_CAPACITY_CLASSES.Very_heavy:
                self._heat_capacity_am = 3.5
            elif self.spec.heat_capacity == HEAT_CAPACITY_CLASSES.Custom_value:
                self._heat_capacity_am = self.spec.parameters.advanced_heat_capacity_am
            else:
                raise ValueError(f"Unknown heat capacity class: {self.spec.heat_capacity}")
        return self._heat_capacity_am

    @property
    def heat_capacity_cm(self) -> float:
        """Building heat capacity Cm (kJ/K).
        [Database cells AG5:AG10]
        """
        if not hasattr(self, '_heat_capacity_cm') or self._heat_capacity_cm is None:
            if self.spec.heat_capacity == HEAT_CAPACITY_CLASSES.Very_light:
                self._heat_capacity_cm = 80_000.0
            elif self.spec.heat_capacity == HEAT_CAPACITY_CLASSES.Light:
                self._heat_capacity_cm = 110_000.0
            elif self.spec.heat_capacity == HEAT_CAPACITY_CLASSES.Medium:
                self._heat_capacity_cm = 165_000.0
            elif self.spec.heat_capacity == HEAT_CAPACITY_CLASSES.Heavy:
                self._heat_capacity_cm = 260_000.0
            elif self.spec.heat_capacity == HEAT_CAPACITY_CLASSES.Very_heavy:
                self._heat_capacity_cm = 370_000.0
            elif self.spec.heat_capacity == HEAT_CAPACITY_CLASSES.Custom_value:
                # These formulas come from [BES_Tool cells F8-9, Q8-9, I106]
                internal_area = self.conditioned_floor_area
                air_volume = self.conditioned_floor_area * self.spec.floor_to_ceiling_height
                air_density = self.spec.parameters.density_of_air
                air_spec_heat = self.spec.parameters.specific_heat_of_air
                air_heat_capacity = air_density * air_spec_heat * air_volume * 1000.0 / internal_area
                self._heat_capacity_cm = self.spec.parameters.heat_capacity_joule + air_heat_capacity
            else:
                raise ValueError(f"Unknown heat capacity class: {self.spec.heat_capacity}")
        return self._heat_capacity_cm

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
    def gross_floor_areas(self) -> 'Series[float]':
        """Floor area of the building in square meters for each zone and floor.
        Af [Inputs cells C39:G45]
        """
        if 'gross_floor_area' not in self._rectangles.columns:
            self._rectangles['gross_floor_area'] = 0.0
            self._rectangles['gross_floor_area'] = self._rectangles.apply(self._get_gross_floor_area, axis=1)

        return self._rectangles['gross_floor_area']

    def get_gross_floor_area_for_floor(self, floor: FLOORS) -> float:
        """Calculate the total gross floor area for a specific floor in square meters.
        [Inputs cells I40:44]
        Args:
            floor (FLOORS): The floor to calculate the gross floor area for.

        Returns:
            float: Total gross floor area for the specified floor in square meters.
        """
        return self.gross_floor_areas.xs(floor, level='floor').sum()

    @property
    def gross_floor_area(self) -> float:
        """Calculate the total gross floor area of the building in square meters.
        A,G [Inputs cell I45]

        Returns:
            float: Total gross floor area in square meters.
        """
        return self.gross_floor_areas.sum()

    def _get_conditioned_floor_area(self, row: Series) -> float:
        z = get_zone_number(row.name[1])
        if not getattr(self.spec, f'condition_z{z}'):
            return 0.0
        return row['gross_floor_area'] * self.spec.parameters.nia_gba_ratio

    @property
    def conditioned_floor_areas(self) -> 'Series[float]':
        """Conditioned floor area of the building in square meters for each zone and floor.
        N45 [Inputs cell N45]
        """
        if 'conditioned_floor_area' not in self._rectangles.columns:
            self._rectangles['conditioned_floor_area'] = DataFrame(self.gross_floor_areas).apply(
                self._get_conditioned_floor_area, axis=1
            )
        return self._rectangles['conditioned_floor_area']

    def get_conditioned_floor_area_for_floor(self, floor: FLOORS) -> float:
        """Calculate the total conditioned floor area for a specific floor in square meters.
        [Inputs cells N40:44]
        Args:
            floor (FLOORS): The floor to calculate the conditioned floor area for.

        Returns:
            float: Total conditioned floor area for the specified floor in square meters.
        """
        return self.conditioned_floor_areas.xs(floor, level='floor').sum()

    @property
    def conditioned_floor_area(self) -> float:
        """Total conditioned floor area of the building in square meters.
        Af (in some places Af means gross, others conditioned)
        [Hourly simulation cell AM80]
        """
        if not hasattr(self, '_conditioned_floor_area') or self._conditioned_floor_area is None:
            self._conditioned_floor_area = self.conditioned_floor_areas.sum()
        return self._conditioned_floor_area

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
    def external_vertical_envelope_gross_areas(self) -> 'Series[float]':
        """External vertical envelope gross area of the building in square meters for each orientation and floor.
        [Input cells C64:F69]
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
        return self._orientation_facade['external_vertical_envelope_gross_area']

    @property
    def external_vertical_envelope_conditioned_areas(self) -> 'Series[float]':
        """External vertical envelope conditioned area of the building in square meters for each orientation and floor.
        [Input cells C74:F79]
        """
        if 'external_vertical_envelope_conditioned_area' not in self._orientation_facade.columns:
            self._orientation_facade['external_vertical_envelope_conditioned_area'] = 0.0
            self._orientation_facade['external_vertical_envelope_conditioned_area'] = DataFrame(
                self._orientation_facade
            ).apply(
                lambda row: self._get_external_vertical_envelope_area(
                    spec=self.spec,
                    row=row,
                    conditioned=True
                ),
                axis=1
            )
        return self._orientation_facade['external_vertical_envelope_conditioned_area']

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
    def window_count(self) -> 'Series[int]':
        """Number of windows for each floor and orientation.

        [Inputs cells C90:F94] [Tool cells G72:J76]
        """
        if 'window_count' not in self._orientation_facade.columns:
            self._orientation_facade['window_count'] = 0
            self._orientation_facade['window_count'] = DataFrame(self._orientation_facade).apply(
                self._get_window_count,
                axis=1
            )
        return self._orientation_facade['window_count']

    @property
    def window_area_orientation(self) -> 'Series[float]':
        """Window area in square meters for each floor and orientation.
        """
        if 'window_area_orientation' not in self._orientation_facade.columns:
            if self.spec.window_height is None or self.spec.window_length is None:
                raise ValueError("Window height and length are required to model window area.")
            self._orientation_facade['window_area_orientation'] = (
                    self.window_count * self.spec.window_height * self.spec.window_length
            )
        return self._orientation_facade['window_area_orientation']

    @property
    def window_ratio(self) -> 'Series[float]':
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
        return self._orientation_facade['window_ratio']

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

    @property
    def conditioned_facade_areas(self):
        """The facade areas of the building in square meters by floor and compass point.
        [Inputs cells near M90]
        """
        if 'facade_areas' not in self._compass_point_facade.columns:
            assert self.external_vertical_envelope_conditioned_areas is not None
            self._compass_point_facade['facade_areas'] = 0.0
            for orientation in ORIENTATIONS:
                compass_point = self.get_compass_point_for_orientation(orientation)
                mask = self._compass_point_facade.index.get_level_values('compass_point') == compass_point
                self._compass_point_facade.loc[mask, 'facade_areas'] = (
                    self.external_vertical_envelope_conditioned_areas.xs(orientation, level='orientation')
                ).values
        return self._compass_point_facade['facade_areas']

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
    def window_areas(self) -> 'Series[float]':
        """The window area of the building in square meters by floor and compass point.
        [Inputs cells near M120]
        """
        if 'window_areas' not in self._compass_point_facade.columns:
            self._compass_point_facade['window_areas'] = 0.0
            self._compass_point_facade['window_areas'] = self._compass_point_facade.apply(
                self._get_window_area,
                axis=1
            )
        return self._compass_point_facade['window_areas']

    @property
    def window_area(self) -> float:
        """Total window area of the building in square meters.
        A,w
        """
        return self.window_areas.sum()


    @property
    def window_shading(self) -> 'Series[float]':
        """Shaded window factor for each floor.
    
        [Inputs cells AB120:124]
        """
        external_perimeter_rate = 0.75  # Constant, hardcoded in Inputs cell X115
        return (
                (self.window_areas.groupby(level='floor').sum() / self.spec.window_height) * external_perimeter_rate
        ).squeeze()

    @property
    def opaque_areas(self) -> 'Series[float]':
        """Opaque areas of the building in square meters by floor and compass point.
        """
        return self.conditioned_facade_areas - self.window_areas

    @property
    def opaque_area(self) -> float:
        """Total opaque area of the building in square meters.
        """
        return self.opaque_areas.sum()

    @property
    def building_mass_area(self) -> float:
        """Building mass area in m².
        Am  (sometimes Af????)
        """
        return self.heat_capacity_am * self.conditioned_floor_area

    @property
    def heat_transfer_rate_windows(self) -> float:
        """The heat transfer rate through windows (W/m²K).
        Htr_w [Hourly Simulation cell AR97]
        """
        if not hasattr(self, '_heat_transfer_rate_windows') or self._heat_transfer_rate_windows is None:
            correction_factor = self.spec.parameters.window_correction_factor
            window_area = self.window_area
            u_value = self.spec.uvalue_window
            if self.spec.thermal_bridge_shading:
                shading = self.window_shading * THERMAL_BREAK_TRANSMITTANCE[THERMAL_BREAKS.Shading]
            else:
                shading = 0.0
            self._heat_transfer_rate_windows = (
                    (window_area * u_value + shading) *
                    correction_factor /
                    self.conditioned_floor_area
            )
        return self._heat_transfer_rate_windows

    @property
    def conditioned_floor_perimeters(self) -> 'Series[float]':
        """Perimeter each floor in m.
        [Inputs cells W120:124]
        """
        if not hasattr(self, '_conditioned_floor_perimeters') or self._conditioned_floor_perimeters is None:
            data = []
            for i, floor in enumerate(FLOORS):
                floor_area = self.get_conditioned_floor_area_for_floor(floor)
                floor_length = math.sqrt(floor_area * self.equivalent_rectangle.ratio)
                floor_width = math.sqrt(floor_area / self.equivalent_rectangle.ratio)
                floor_exposure = 2 * floor_length + 2 * floor_width
                data.append(floor_exposure)
            self._conditioned_floor_perimeters = Series(data, index=list(FLOORS))

        return self._conditioned_floor_perimeters

    @property
    def roof_projections(self) -> 'Series[float]':
        """Roof area of the building in square meters by floor.
        [Inputs cells K120:124]
        """
        if not hasattr(self, '_roof_projections') or self._roof_projections is None:
            data = []
            for i, floor in enumerate(FLOORS):
                my_area = self.get_conditioned_floor_area_for_floor(floor)
                if floor == FLOORS.get_by_index(-1):
                    data.append(my_area)
                else:
                    area_above = self.get_conditioned_floor_area_for_floor(FLOORS.get_by_index(i + 1))
                    if my_area >= area_above:
                        data.append(my_area - area_above)
                    else:
                        data.append(0.0)
            self._roof_projections = Series(data, index=list(FLOORS))
        return self._roof_projections

    @property
    def roof_factor(self) -> float:
        """Roof factor for the building (roof area / building area).
        [Inputs cell M37]
        
        Used to convert between ground projection and actual roof area for slanted roofs.
        """
        if not hasattr(self, '_roof_factor') or self._roof_factor is None:
            roof_slope = self.spec.roof_angle  # [Inputs cell M32]
            horizontal = self.equivalent_rectangle.width / 2  # [Inputs cell M33]
            height = roof_slope * horizontal / 100  # [Inputs cell M34]
            slope = math.sqrt(horizontal**2 + height**2)  # [Inputs cell M35]
            roof_area = slope * 2 * self.equivalent_rectangle.length  # [Inputs cell M36]
            self._roof_factor = roof_area / self.equivalent_rectangle.area  # [Inputs cell M37]
        return self._roof_factor
    
    @property
    def conditioned_floor_projection(self) -> 'Series[float]':
        """Projection of each floor of the building in square meters by floor.
        For the ground floor, this is the conditioned floor area.
        For floors above the ground floor, this is the additional area compared to the floor below (i.e. the overhang).
        [Inputs cells L120:124]
        """
        data = []
        for i, floor in enumerate(FLOORS):
            my_area = self.get_conditioned_floor_area_for_floor(floor)
            if floor == FLOORS.Ground:
                data.append(my_area)
            else:
                area_below = self.get_conditioned_floor_area_for_floor(FLOORS.get_by_index(i - 1))
                if my_area <= area_below:
                    data.append(0.0)
                else:
                    data.append(my_area - area_below)
        return Series(data, index=list(FLOORS))

    @property
    def heat_infiltration_opaque(self) -> float:
        """Heat transfer rate through opaque envelope (W/m²K).
        Htr_opaque [Hourly Simulation cell AR81, Inputs C270]

        Calculated for the opaque elements of the building envelope including walls, roof, and ground floor by
        combining surface and linear transfer weighted by their respective areas and lengths.

        Surface transmission is area * U-value.

        Linear transmission is perimeter_length * ψ-value
        """
        if not hasattr(self, '_heat_infiltration_opaque') or self._heat_infiltration_opaque is None:
            floor_surface_area = self.conditioned_floor_projection.sum()  # [Inputs cell E259]
            wall_opaque_surface_area = self.conditioned_facade_areas.sum() - self.window_areas.sum()  # [C259]
            roof_surface_area = self.roof_projections.sum() * self.roof_factor  # [Inputs cell D259]

            floor_surface_transmission = floor_surface_area * self.spec.uvalue_floor  # [Inputs cell E260]
            wall_surface_transmission = wall_opaque_surface_area * self.spec.uvalue_facade  # [C260]
            roof_surface_transmission = roof_surface_area * self.spec.uvalue_roof  # [Inputs cell D260]

            # [Inputs cell C266]
            if self.spec.thermal_bridge_facade_ground:
                floor_transmittance = THERMAL_BREAK_TRANSMITTANCE[THERMAL_BREAKS.Facade_ground]
            else:
                floor_transmittance = 0.0
            if self.spec.thermal_bridge_facade_intermediate:
                other_floors_transmittance = THERMAL_BREAK_TRANSMITTANCE[THERMAL_BREAKS.Facade_intermediate]
            else:
                other_floors_transmittance = 0.0
            if self.spec.thermal_bridge_window:
                window_transmittance = THERMAL_BREAK_TRANSMITTANCE[THERMAL_BREAKS.Windows]
            else:
                window_transmittance = 0.0
            if self.spec.thermal_bridge_facade_roof:
                roof_transmittance = THERMAL_BREAK_TRANSMITTANCE[THERMAL_BREAKS.Facade_roof]
            else:
                roof_transmittance = 0.0

            floor_linear_transmission = self.conditioned_floor_perimeters[FLOORS.Ground] * floor_transmittance

            # intermediate floors have a more complex perimeter calculation for thermal bridging
            # [Inputs cells Y120:125]
            other_floors_thermal_bridge_perimeter = 0.0
            for i, floor in enumerate(FLOORS):
                if floor == FLOORS.Ground:
                    continue
                my_perimeter = self.conditioned_floor_perimeters[floor]
                prev_perimeter = self.conditioned_floor_perimeters[FLOORS.get_by_index(i - 1)]
                if prev_perimeter <= 0:
                    other_floors_thermal_bridge_perimeter += my_perimeter
                else:
                    other_floors_thermal_bridge_perimeter += my_perimeter * (my_perimeter / prev_perimeter)
            other_floors_linear_transmission = other_floors_thermal_bridge_perimeter * other_floors_transmittance
            # Windows get lumped in with other floors
            # [Inputs cells AA120:125]
            window_external_perimeter_rate = 0.75  # [Hardcoded in Inputs cell X115]
            window_perimeter = (
                    (self.window_areas.sum() / self.spec.window_height) +
                    (self.window_areas.sum() / self.spec.window_height * 2) * window_external_perimeter_rate
            )
            windows_linear_transmission = window_perimeter * window_transmittance

            # [Inputs cells D266, F266]
            wall_linear_transmission = (
                other_floors_linear_transmission +
                windows_linear_transmission
            )

            # [Inputs cells Z120:125]
            roof_perimeter = 0.0
            for i, floor in enumerate(FLOORS):
                if floor == FLOORS.get_by_index(-1):
                    roof_perimeter += self.conditioned_floor_perimeters[floor]
                else:
                    next_perimeter = self.conditioned_floor_perimeters[FLOORS.get_by_index(i + 1)]
                    my_perimeter = self.conditioned_floor_perimeters[floor]
                    roof_perimeter += (my_perimeter - next_perimeter)
            # [Inputs cell E266]
            roof_linear_transmission = roof_perimeter * roof_transmittance

            # [Calculated in Inputs C270]
            self._heat_infiltration_opaque = (
                    self.spec.parameters.floor_correction_factor *
                    (floor_surface_transmission + floor_linear_transmission) +
                    self.spec.parameters.facade_correction_factor *
                    (wall_surface_transmission + wall_linear_transmission) +
                    self.spec.parameters.roof_correction_factor * 
                    (roof_surface_transmission + roof_linear_transmission)
            )
        return self._heat_infiltration_opaque

    @property
    def heat_transfer_rate_opaque(self) -> float:
        """Heat transfer rate through opaque envelope (W/m²K).
        Htr_opaque [Hourly Simulation cell AR93]
        """
        return self.heat_infiltration_opaque / self.conditioned_floor_area

    @property
    def heat_transfer_ms(self) -> float:
        """Heat transfer coefficient between external air and external surface (W/m²K).
        Htr_ms [Hourly Simulation cell AR95] EN ISO 13790 12.2.2"""
        if not hasattr(self, '_heat_transfer_ms') or self._heat_transfer_ms is None:
            factor = 9.1  # Unnamed factor hardcoded in cell AR95 formula
            # Am or Am/Af is converted and reconverted several times, but ends up being just the lookup value
            Am = self.heat_capacity_am
            self._heat_transfer_ms = factor * Am
        return self._heat_transfer_ms

    @property
    def heat_transfer_is(self) -> float:
        """Heat transfer coefficient between internal air and internal surface (W/m²K).
        Htr_is [Hourly Simulation cell AR98] EN ISO 13790 12.2.2
        """
        if not hasattr(self, '_heat_transfer_is') or self._heat_transfer_is is None:
            Aat = 4.5  # [Hardcoded in Hourly Simulation cell AM84: EN ISO 13790, 7.2.2]
            Atot = Aat * self.conditioned_floor_area  # [AM85]
            Htr_is = 3.45 * Atot  # 3.45 hardcoded in [AR83]
            self._heat_transfer_is = Htr_is / self.conditioned_floor_area
        return self._heat_transfer_is


import pvlib
import numpy as np
from pandas import DataFrame, Series, DatetimeIndex

from .base import HOURS_DF
from ..types import COMPASS_POINTS


class SolarIrradiationSimulation:
    """
    Simulation class for solar irradiation data from EPW files.

    Uses pvlib but may have to fall back to copying Excel calculations.
    """
    _hours: DataFrame
    location: pvlib.location.Location
    times: DatetimeIndex
    _solarposition: DataFrame
    _solar_irradiation: DataFrame
    _solar_declination_: np.array = None
    _hour_angle_: np.array = None

    def __init__(self, epw_data: DataFrame, epw_metadata: dict):
        self._hours = HOURS_DF.copy()
        self.epw_data = epw_data
        self.epw_metadata = epw_metadata
        tz = epw_metadata['TZ']
        self.location = pvlib.location.Location(
            latitude=epw_metadata['latitude'],
            longitude=epw_metadata['longitude'],
            tz=tz,
            altitude=epw_metadata['altitude']
        )
        self._solar_irradiation = DataFrame()
        self._solar_irradiation.index = self._hours.index

    @property
    def lat(self) -> float:
        """Latitude of the location from EPW metadata."""
        return round(self.epw_metadata.get('latitude'), 3)

    @property
    def lon(self) -> float:
        """Longitude of the location from EPW metadata."""
        return round(self.epw_metadata.get('longitude'), 2)

    @property
    def timezone(self) -> float:
        """Timezone of the location from EPW metadata."""
        return self.epw_metadata.get('TZ')

    @property
    def altitude(self) -> float:
        """Altitude of the location from EPW metadata."""
        return self.epw_metadata.get('altitude')

    @property
    def ghi(self) -> 'Series[float]':
        """Global Horizontal Irradiance (GHI) from EPW data."""
        if 'global_horizontal_irradiance' not in self._hours.columns:
            self._hours['global_horizontal_irradiance'] = list(self.epw_data['ghi'].astype(float))
        return self._hours['global_horizontal_irradiance']

    @property
    def dni(self) -> 'Series[float]':
        """Direct Normal Irradiance (DNI) from EPW data."""
        if 'direct_normal_irradiance' not in self._hours.columns:
            self._hours['direct_normal_irradiance'] = list(self.epw_data['dni'].astype(float))
        return self._hours['direct_normal_irradiance']

    @property
    def dhi(self) -> 'Series[float]':
        """Diffuse Horizontal Irradiance (DHI) from EPW data."""
        if 'diffuse_horizontal_irradiance' not in self._hours.columns:
            self._hours['diffuse_horizontal_irradiance'] = list(self.epw_data['dhi'].astype(float))
        return self._hours['diffuse_horizontal_irradiance']

    @property
    def _hour_angle(self):
        """Hour angle (h) in radians for each hour."""
        if self._hour_angle_ is None:
            local_standard_time = np.array(
                self._hours.index.get_level_values(self._hours.index.names.index('hour'))
            )
            day_of_year = np.array(self._hours.index.get_level_values(self._hours.index.names.index('day')))
            orbital_position = (
                    2 * np.pi *
                    (day_of_year - 1) /
                    365
            )
            equation_of_time = 2.2918 * (
                    0.0075 +
                    0.1868 * np.cos(orbital_position) -
                    3.2077 * np.sin(orbital_position) -
                    1.4615 * np.cos(2 * orbital_position) -
                    4.089 * np.sin(2 * orbital_position)
            )
            longitude_of_local_meridian = 15 * self.timezone
            apparent_solar_time = (
                    local_standard_time +
                    equation_of_time / 60 +
                    (self.lon - longitude_of_local_meridian) / 15
            )
            self._hour_angle_ = np.radians(15 * (apparent_solar_time - 12))
        return self._hour_angle_

    @property
    def _solar_declination(self):
        """Solar declination (delta) in radians for each hour."""
        if self._solar_declination_ is None:
            day_of_year = np.array(self._hours.index.get_level_values(self._hours.index.names.index('day')))
            self._solar_declination_ = np.radians(23.45 * np.sin(2 * np.pi * (284 + day_of_year) / 365))
        return self._solar_declination_

    @property
    def solar_altitude(self) -> 'Series[float]':
        """Solar altitude angle (beta) in degrees for each hour.
        [Solar radiation column P]
        """
        if 'solar_altitude' not in self._hours.columns:
            latitude = np.radians(self.lat)
            sin_solar_altitude = (
                np.cos(latitude) * np.cos(self._solar_declination) * np.cos(self._hour_angle) +
                np.sin(latitude) * np.sin(self._solar_declination)
            )
            self._hours['solar_altitude'] = np.degrees(np.asin(sin_solar_altitude))
        return self._hours['solar_altitude']

    @property
    def solar_zenith(self) -> 'Series[float]':
        """Solar zenith angle (theta) in degrees for each hour.
        """
        return 90.0 - self.solar_altitude

    @property
    def solar_azimuth(self) -> 'Series[float]':
        """Solar azimuth angle (phi) in degrees for each hour.
        [Solar radiation column V]
        """
        if 'solar_azimuth_degrees' not in self._hours.columns:
            altitude_rad = np.radians(self.solar_altitude)
            lat_rad = np.radians(self.lat)
            sin_phi = (
                    np.sin(self._hour_angle) *
                    np.cos(self._solar_declination)
            ) / np.cos(altitude_rad)
            cos_phi = (
                np.cos(self._hour_angle) * np.cos(self._solar_declination) * np.sin(lat_rad) -
                np.sin(self._solar_declination) * np.cos(lat_rad)
            ) / np.cos(altitude_rad)
            phi_from_sin = np.degrees(np.asin(sin_phi))
            phi_from_cos = np.degrees(np.acos(cos_phi))
            from_cos = sin_phi > 0
            from_sin = cos_phi > 0
            others = ~(from_cos | from_sin)
            self._hours['solar_azimuth_degrees'] = (
                phi_from_cos * from_cos +
                phi_from_sin * (from_sin & ~from_cos) +
                (-180 - phi_from_sin) * others
            )
        return self._hours['solar_azimuth_degrees']

    def get_solar_irradiation(self, compass_point: COMPASS_POINTS) -> 'Series[float]':
        """Get the hourly solar irradiation on a vertical surface facing the given compass point in Wh/m2.
        [Hourly simulation columns M:T, Solar radiation BT:CA]
        """
        if compass_point not in self._solar_irradiation.columns:
            # These values in Hourly simulation M114:T114 are used in the map, then adjusted to PVLib convention
            surface_azimuth = {
                COMPASS_POINTS.North: 180,
                COMPASS_POINTS.NorthEast: 360 - 135,
                COMPASS_POINTS.East: 360 - 90,
                COMPASS_POINTS.SouthEast: 360 - 45,
                COMPASS_POINTS.South: 0,
                COMPASS_POINTS.SouthWest: 45,
                COMPASS_POINTS.West: 90,
                COMPASS_POINTS.NorthWest: 135,
            }[compass_point]
            solar_azimuth = self.solar_azimuth
            gamma = abs(solar_azimuth - surface_azimuth)  # [Solar radiation columns W:AD]
            solar_altitude_rad = np.radians(self.solar_altitude)
            aoi = np.cos(solar_altitude_rad) * np.cos(np.radians(gamma))  # [Solar radiation columns AE:AL]
            aoi = np.degrees(np.arccos(aoi))  # [Solar radiation columns AM:AT]
            # [Solar radiation columns AU:BB]
            beam_component = np.logical_not((90 < gamma) & (gamma < 270)) * (aoi >= 0) * (self.dni * np.cos(np.radians(aoi)))
            # [Solar radiation columns BC:BJ]
            diffuse_component_ratio = (
                0.55 +
                0.437 * np.cos(np.radians(aoi)) +
                0.313 * (np.cos(np.radians(aoi)) ** 2)
            )
            # [Solar radiation columns BK:BR; capping is actually done in the previous column set]
            diffuse_component = np.maximum(0.45, diffuse_component_ratio) * self.dhi
            # [Solar radiation column BS]
            ground_component = (self.dni * np.sin(solar_altitude_rad) + self.dhi) * 0.14 / 2
            self._solar_irradiation[compass_point] = beam_component + diffuse_component + ground_component
        return self._solar_irradiation[compass_point]

    @property
    def solar_irradiation(self) -> DataFrame:
        """Hourly solar irradiation on a horizontal surface in Wh/m2, columns are COMPASS_POINTS.
        [Hourly simulation columns M:T, Solar radiation BT:CA]
        """
        if self._solar_irradiation.empty:
            for compass_point in list(COMPASS_POINTS):
                self.get_solar_irradiation(compass_point)
        return self._solar_irradiation
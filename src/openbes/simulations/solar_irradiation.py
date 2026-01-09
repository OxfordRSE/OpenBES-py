
import pvlib
import numpy as np
from pandas import DataFrame, Series, DatetimeIndex

from .base import HOURS_DF
from ..types import COMPASS_POINTS


class SolarIrradiationSimulation:
    """
    Simulation class for solar irradiation data from EPW files.

    Copies the Excel BES solar irradiation calculations.
    Eventually this should be replaced with direct PVLib calls once parity is no longer required.
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
    def day_of_year(self):
        """Day of year for each hour."""
        return np.array(self._hours.index.get_level_values(self._hours.index.names.index('day')))

    @property
    def hour_offset(self):
        """Hour offset from local standard time for each hour."""
        return np.array(
            self._hours.index.get_level_values(self._hours.index.names.index('hour'))
        ) - 0.5

    @property
    def _hour_angle(self):
        """Hour angle (h) in radians for each hour."""
        if self._hour_angle_ is None:
            orbital_position = (
                    2 * np.pi *
                    (self.day_of_year - 1 + (self.hour_offset - 12) / 24) /
                    365
            )
            equation_of_time = 229.18 * (
                    0.000075 +
                    0.001868 * np.cos(orbital_position) -
                    0.032077 * np.sin(orbital_position) -
                    0.014615 * np.cos(2 * orbital_position) -
                    0.040849 * np.sin(2 * orbital_position)
            )
            time_offset_min = equation_of_time + 4 * self.lon - (60 * self.timezone)
            true_solar_time_min = self.hour_offset * 60 + time_offset_min
            hour_angle_degrees = true_solar_time_min / 4 - 180
            self._hour_angle_ = np.radians(hour_angle_degrees)
        return self._hour_angle_

    @property
    def _solar_declination(self):
        """Solar declination (delta) in radians for each hour."""
        if self._solar_declination_ is None:
            gamma = 2 * np.pi / 365 * (self.day_of_year - 1 + (self.hour_offset - 12) / 24)
            self._solar_declination_ = (
                    0.006918
                    - 0.399912 * np.cos(gamma)
                    + 0.070257 * np.sin(gamma)
                    - 0.006758 * np.cos(2 * gamma)
                    + 0.000907 * np.sin(2 * gamma)
                    - 0.002697 * np.cos(3 * gamma)
                    + 0.00148 * np.sin(3 * gamma)
            )
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
            sin_phi = np.sin(np.radians(self.lat))
            cos_phi = np.cos(np.radians(self.lat))
            # NB: Excel ATAN2(y,x) is np.atan2(x,y)
            solar_azimuth = np.degrees(np.atan2(
                np.sin(self._hour_angle),
                np.cos(self._hour_angle) * sin_phi - np.tan(self._solar_declination) * cos_phi
            ))
            solar_azimuth += 180.0
            solar_azimuth %= 360.0
            self._hours['solar_azimuth_degrees'] = solar_azimuth
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
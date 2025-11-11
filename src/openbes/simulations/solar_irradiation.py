import math

import pvlib
from numpy import radians, cos, maximum
from pandas import DataFrame, Series, DatetimeIndex

from .base import HOURS_DF
from ..types import COMPASS_POINTS


def rad_to_deg(rad: Series) -> 'Series[float]':
    """Convert radians to degrees."""
    return rad.apply(lambda r: r * (180.0 / math.pi))

def deg_to_rad(deg: Series) -> 'Series[float]':
    """Convert degrees to radians."""
    return deg.apply(lambda d: d * (math.pi / 180.0))


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

    def __init__(self, epw_data: DataFrame, epw_metadata: dict):
        self._hours = HOURS_DF.copy()
        self.epw_data = epw_data
        self.epw_metadata = epw_metadata
        tz = epw_data.index[0].tzinfo
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
        return self.epw_metadata.get('latitude')

    @property
    def lon(self) -> float:
        """Longitude of the location from EPW metadata."""
        return self.epw_metadata.get('longitude')

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
    def solar_altitude_sin(self) -> 'Series[float]':
        """Solar altitude angle (beta) in radians for each hour.
        [Solar radiation column O]
        """
        if 'solar_altitude_sin' not in self._hours.columns:
            self._hours['solar_altitude_sin'] = (
                math.cos(Series([self.lat] * len(self._hours))) *
                self._hours['solar_declination'].apply(math.cos) *
                self._hours['solar_hour_angle'].apply(math.cos) +
                math.sin(Series([self.lat] * len(self._hours))) *
                self._hours['solar_declination'].apply(math.sin)
            )
        return self._hours['solar_altitude_sin']

    @property
    def solar_altitude_radians(self) -> 'Series[float]':
        """Solar altitude angle (beta) in radians for each hour.
        [Solar radiation column P]
        """
        if 'solar_altitude_radians' not in self._hours.columns:
            self._hours['solar_altitude_radians'] = math.asin(self.solar_altitude_sin)
        return self._hours['solar_altitude_radians']

    @property
    def solarposition(self) -> DataFrame:
        """Solar position for each hour.
        Solar apparent elevation [Solar radiation column Q, Hourly simulation column H]
        """
        if not hasattr(self, '_solarposition') or self._solarposition is None:
            self._solarposition = self.location.get_solarposition(self.epw_data.index)
            self._solarposition = self._solarposition.shift(-1)  # correct for EPW hour ending convention
            self._solarposition.index = self._hours.index
        return self._solarposition

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
            surface_azimuth = surface_azimuth + 180 % 360  # convert to pvlib convention
            surface_tilt = 90.0  # horizontal surface
            solar_zenith = self.solarposition['zenith']
            solar_azimuth = self.solarposition['azimuth']
            poa_irradiance = pvlib.irradiance.get_total_irradiance(
                surface_tilt=surface_tilt,
                surface_azimuth=surface_azimuth,
                solar_zenith=solar_zenith,
                solar_azimuth=solar_azimuth,
                dni=self.dni,
                ghi=self.ghi,
                dhi=self.dhi,
                dni_extra=pvlib.irradiance.get_extra_radiation(self.epw_data.index),
                model='isotropic',
                albedo=0.14  # [Hardcoded in Solar radiation column BS]
            )
            # Excel corrects diffuse sky irradiance for angle of incidence
            aoi = pvlib.irradiance.aoi(
                surface_tilt=surface_tilt,
                surface_azimuth=surface_azimuth,
                solar_zenith=solar_zenith,
                solar_azimuth=solar_azimuth
            )
            cos_aoi = cos(radians(aoi))
            Y = maximum(0.45, 0.55 + 0.437 * cos_aoi + 0.313 * cos_aoi**2)
            poa_irradiance['poa_sky_diffuse_excel'] = self.dhi * Y

            # Excel also uses slightly different calculations for ground reflected irradiance
            poa_irradiance['poa_ground_diffuse_excel'] = (
                (self.dni * self.solarposition['apparent_elevation'].apply(math.radians).apply(math.sin) + self.dhi) *
                0.14 / 2
            )

            poa_irradiance['irradiance'] = (
                    poa_irradiance['poa_direct'] +
                    poa_irradiance['poa_sky_diffuse_excel'] +
                    poa_irradiance['poa_ground_diffuse_excel']
            )
            self._solar_irradiation[compass_point] = poa_irradiance['irradiance']
        return self._solar_irradiation[compass_point]

    @property
    def solar_irradiation(self) -> DataFrame:
        """Hourly solar irradiation on a horizontal surface in Wh/m2, columns are COMPASS_POINTS.
        [Hourly simulation columns M:T, Solar radiation BT:CA]
        """
        return self._solar_irradiation
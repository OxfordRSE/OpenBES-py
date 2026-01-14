
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
    _aoi: DataFrame = None

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
    def cos_zenith(self) -> 'Series[float]':
        if 'cos_zenith' not in self._hours.columns:
            sin_phi = np.sin(np.radians(self.lat))
            cos_phi = np.cos(np.radians(self.lat))
            self._hours['cos_zenith'] = (
                    sin_phi * np.sin(self._solar_declination) +
                    cos_phi * np.cos(self._solar_declination) * np.cos(self._hour_angle)
            )
        return self._hours['cos_zenith']


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

    @property
    def surface_azimuths(self) -> dict[COMPASS_POINTS, float]:
        """Surface azimuth angles in degrees for each compass point."""
        return {
            COMPASS_POINTS.South: 180,
            COMPASS_POINTS.SouthEast: 135,
            COMPASS_POINTS.East: 90,
            COMPASS_POINTS.NorthEast: 45,
            COMPASS_POINTS.North: 0,
            COMPASS_POINTS.NorthWest: -45,
            COMPASS_POINTS.West: -90,
            COMPASS_POINTS.SouthWest: -135,
        }

    def get_aoi(self, compass_point: COMPASS_POINTS) -> 'Series[float]':
        """Get the hourly angle of incidence on a vertical surface facing the given compass point in radians.
        """
        if self._aoi is None:
            self._aoi = DataFrame()
            self._aoi.index = self._hours.index
            r90 = np.radians(90)
            for point in list(COMPASS_POINTS):
                azimuth_component = np.radians(self.solar_azimuth - self.surface_azimuths[point])
                self._aoi[point] = (
                        np.cos(r90) * self.cos_zenith +
                        np.sin(r90) * np.sin(np.radians(self.solar_zenith)) * np.cos(azimuth_component)
                )
        return self._aoi[compass_point]

    def get_aoi_degrees(self, compass_point: COMPASS_POINTS) -> 'Series[float]':
        """Get the hourly angle of incidence on a vertical surface facing the given compass point in degrees.
        """
        return np.degrees(np.acos(np.minimum(np.maximum(self.get_aoi(compass_point), -1), 1)))

    @property
    def dni_extra(self) -> 'Series[float]':
        """Get the hourly extraterrestrial direct normal irradiance in Wh/m2.
        """
        if 'dni_extra' not in self._hours.columns:
            dni_extra = (
                    1367 *
                    (1 + 0.033 * np.cos(2 * np.pi * self.day_of_year / 365))
            )
            self._hours['dni_extra'] = dni_extra
        return self._hours['dni_extra']

    @property
    def relative_air_mass(self) -> 'Series[float]':
        """Get the hourly relative air mass (Kasten & Young).
        """
        if 'relative_air_mass' not in self._hours.columns:
            ram = 1 / (np.cos(np.radians(self.solar_zenith)) + 0.50572 * ((96.07995 - self.solar_zenith) ** -1.6364))
            ram = np.minimum(ram, 40)
            ram = ram * np.where(self.solar_zenith < 90, 1, 0)
            ram = np.where(np.isnan(ram), 0, ram)
            self._hours['relative_air_mass'] = ram
        return self._hours['relative_air_mass']

    @property
    def brightness_delta(self) -> 'Series[float]':
        """Get the hourly brightness.
        """
        if 'brightness_delta' not in self._hours.columns:
            self._hours['brightness_delta'] = (
                    self.dhi * self.relative_air_mass / self.dni_extra
            )
        return self._hours['brightness_delta']

    @property
    def clearness(self) -> 'Series[float]':
        """Get the hourly clearness index.
        """
        if 'clearness' not in self._hours.columns:
            self._hours['clearness'] = np.where(
                self.dhi <= 0,
                99.0,
                (
                        ((self.dhi + self.dni) / self.dhi + 1.041 * np.radians(self.solar_zenith)**3) /
                        (1 + 1.041 * np.radians(self.solar_zenith)**3)
                )
            )
        return self._hours['clearness']

    @property
    def perez_bins(self) -> DataFrame:
        return DataFrame(
            {
                "bin": [1, 2, 3, 4, 5, 6, 7],
                "eps_lo": [1.0, 1.065, 1.230, 1.500, 1.950, 2.800, 4.500],
                "eps_hi": [1.065, 1.230, 1.500, 1.950, 2.800, 4.500, 6.200],
                "perez_f11": [-0.00831170, 0.12994570, 0.32969580, 0.56820530, 0.87302800, 1.13260770, 1.06015910],
                "perez_f12": [0.58772850, 0.68259540, 0.48687350, 0.18745250, -0.39204030, -1.23672840, -1.59991370],
                "perez_f13": [-0.06206360, -0.15137520, -0.22109580, -0.29512900, -0.36161490, -0.41184940, -0.35892210],
                "perez_f21": [-0.05960120, -0.01893250, 0.05541400, 0.10886310, 0.22556470, 0.28778130, 0.26421240],
                "perez_f22": [0.07212490, 0.06596500, -0.06395880, -0.15192290, -0.46204420, -0.82303570, -1.12723400],
                "perez_f23": [-0.02202160, -0.02887480, -0.02605420, -0.01397540, 0.00124480, 0.05586510, 0.13106940]
            }
        )

    def get_perez_coefficient(self, coefficient: str) -> 'Series[float]':
        """Get the hourly Perez coefficient by name.
        """
        if coefficient not in self._hours.columns:
            idx = np.clip(
                np.searchsorted(
                    self.perez_bins['eps_lo'],
                    self.clearness,
                    side='right'
                ) - 1,
                0,
                len(self.perez_bins) - 1
            )
            self._hours[coefficient] = self.perez_bins[coefficient].iloc[idx].values
        return self._hours[coefficient]

    @property
    def perez_f11(self) -> 'Series[float]':
        """Get the hourly Perez f11 coefficient.
        """
        if 'perez_f11' not in self._hours.columns:
            self.get_perez_coefficient('perez_f11')
        return self._hours['perez_f11']

    @property
    def perez_f12(self) -> 'Series[float]':
        """Get the hourly Perez f12 coefficient.
        """
        if 'perez_f12' not in self._hours.columns:
            self.get_perez_coefficient('perez_f12')
        return self._hours['perez_f12']

    @property
    def perez_f13(self) -> 'Series[float]':
        """Get the hourly Perez f13 coefficient.
        """
        if 'perez_f13' not in self._hours.columns:
            self.get_perez_coefficient('perez_f13')
        return self._hours['perez_f13']

    @property
    def perez_f21(self) -> 'Series[float]':
        """Get the hourly Perez f21 coefficient.
        """
        if 'perez_f21' not in self._hours.columns:
            self.get_perez_coefficient('perez_f21')
        return self._hours['perez_f21']

    @property
    def perez_f22(self) -> 'Series[float]':
        """Get the hourly Perez f22 coefficient.
        """
        if 'perez_f22' not in self._hours.columns:
            self.get_perez_coefficient('perez_f22')
        return self._hours['perez_f22']

    @property
    def perez_f23(self) -> 'Series[float]':
        """Get the hourly Perez f23 coefficient.
        """
        if 'perez_f23' not in self._hours.columns:
            self.get_perez_coefficient('perez_f23')
        return self._hours['perez_f23']

    @property
    def perez_F1(self) -> 'Series[float]':
        """Get the hourly Perez F1 coefficient.
        """
        if 'perez_F1' not in self._hours.columns:
            self._hours['perez_F1'] = np.maximum(
                0,
                (
                        self.perez_f11 +
                        self.perez_f12 * self.brightness_delta +
                        (np.pi * self.solar_zenith / 180) * self.perez_f13
                )
            )
        return self._hours['perez_F1']

    @property
    def perez_F2(self) -> 'Series[float]':
        """Get the hourly Perez F2 coefficient.
        """
        if 'perez_F2' not in self._hours.columns:
            self._hours['perez_F2'] = (
                    self.perez_f21 +
                    self.perez_f22 * self.brightness_delta +
                    (np.pi * self.solar_zenith / 180) * self.perez_f23
            )
        return self._hours['perez_F2']

    def get_perez_a(self, point: COMPASS_POINTS) -> 'Series[float]':
        """Get the hourly Perez auxiliary variable A.
        """
        return np.maximum(self.get_aoi(point), 0)

    @property
    def perez_b(self) -> 'Series[float]':
        """Get the hourly Perez auxiliary variable B.
        """
        if 'perez_b' not in self._hours.columns:
            self._hours['perez_b'] = np.maximum(np.cos(np.radians(85)), self.cos_zenith)
        return self._hours['perez_b']

    def get_beam_component(self, point: COMPASS_POINTS) -> 'Series[float]':
        """Get the hourly beam component on a vertical surface facing the given compass point in Wh/m2.
        """
        return np.maximum(0, self.dni * self.get_aoi(point))

    def get_diffuse_component(self, point: COMPASS_POINTS) -> 'Series[float]':
        """Get the hourly diffuse component on a vertical surface facing the given compass point in Wh/m2.
        """
        f1_a = (1 - self.perez_F1) * (1 + np.cos(np.radians(90))) / 2
        f1_b = self.perez_F1 * (self.get_perez_a(point) / self.perez_b)
        f2 = self.perez_F2 * np.sin(np.radians(90))
        return np.maximum(0, self.dhi * (f1_a + f1_b + f2))

    @property
    def ground_reflected_component(self) -> 'Series[float]':
        """Get the hourly ground reflected component on a vertical surface in Wh/m2.
        """
        if 'ground_reflected_component' not in self._hours.columns:
            self._hours['ground_reflected_component'] = self.ghi * 0.2 * (1 - np.cos(np.radians(90))) / 2
        return self._hours['ground_reflected_component']

    def get_solar_irradiation(self, point: COMPASS_POINTS) -> 'Series[float]':
        """Get the hourly solar irradiation on a vertical surface facing the given compass point in Wh/m2.
        """
        if point not in self._solar_irradiation.columns:
            self._solar_irradiation[point] = (
                    self.get_diffuse_component(point) + self.get_beam_component(point) + self.ground_reflected_component
            )
        return self._solar_irradiation[point]

    @property
    def solar_irradiation(self) -> DataFrame:
        """Hourly solar irradiation on a horizontal surface in Wh/m2, columns are COMPASS_POINTS.
        [Hourly simulation columns M:T, Solar radiation BT:CA]
        """
        if self._solar_irradiation.empty:
            for compass_point in list(COMPASS_POINTS):
                self.get_solar_irradiation(compass_point)
        return self._solar_irradiation
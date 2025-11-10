from math import atan

from numpy import nan, isnan
from pvlib.iotools import read_epw
from pandas import DataFrame, Series
import os

from .base import HourlySimulation
from .geometry import BuildingGeometry
from .lighting import LightingSimulation
from .occupancy import OccupationSimulation
from .solar_irradiation import SolarIrradiationSimulation
from .ventilation import VentilationSimulation
from ..types import OpenBESSpecification, TERRAINS

RELATIVE_HUMIDITY = 55.0  # Percentage

TERRAIN_VSITE_BY_VMETRO = {
    TERRAINS.Open: 1.0,
    TERRAINS.Country: 0.9,
    TERRAINS.Urban: 0.8
}

def get_available_epw_files() -> list[str]:
    """
    Returns a list of available EPW climate data files.
    """
    climate_data_dir = os.path.join(
        os.path.dirname(__file__),
        "climate_data"
    )
    return [
        f for f in os.listdir(climate_data_dir)
        if f.endswith('.epw')
    ]

class ClimateSimulation(HourlySimulation):
    """
    Unlike other simulations, ClimateSimulation's Hourly data depend on the previous hourly data.
    This means that the class must calculate all hourly data in sequence, not just on demand.

    Consequently, the entire simulation is run in the __init__ method, which may take some time.
    """
    geometry: BuildingGeometry
    occupancy: OccupationSimulation
    lighting: LightingSimulation
    ventilation: VentilationSimulation
    _solar_irradiation: SolarIrradiationSimulation
    _epw_metadata: dict
    _epw_data: DataFrame
    _heating_and_cooling_degree_days: DataFrame
    _heat_infiltration_window: float
    _heat_infiltration_opaque: float
    _heat_transmission_by_infiltration: float
    _temp_change_demand: float
    _building_thermal_mass_at_hour: Series

    def __init__(
            self,
            spec: OpenBESSpecification,
            geometry: BuildingGeometry = None,
            occupancy: OccupationSimulation = None,
            lighting: LightingSimulation = None,
            ventilation: VentilationSimulation = None,
    ):
        super().__init__(spec=spec)
        self.geometry = geometry or BuildingGeometry(spec=spec)
        self.occupancy = occupancy or OccupationSimulation(spec=spec, geometry=self.geometry)
        self.lighting = lighting or LightingSimulation(spec=spec, occupancy=self.occupancy)
        self.ventilation = ventilation or VentilationSimulation(
            spec=spec, geometry=self.geometry, occupancy=self.occupancy
        )
        nan_series = Series([nan] * len(self._hours), index=self._hours.index)
        self._hours['air_free_temp_0m'] = nan_series
        self._hours['internal_surface_temp'] = nan_series
        self._hours['heat_transmission_by_ventilation'] = nan_series
        self._hours['supply_air_temp'] = nan_series
        self._hours['internal_heat_adjusted'] = nan_series
        self._hours['building_thermal_mass'] = nan_series
        self._hours['htr_1'] = nan_series
        self._hours['htr_2'] = nan_series
        self._hours['htr_3'] = nan_series
        self._hours['air_flow'] = nan_series
        self._hours['solar_heat_windows'] = nan_series
        for i in range(len(self._hours)):
            self.calculate_hour(row_index=i)

    def calculate_hour(self, row_index: int):
        """Calculate all hourly data for a specific hour.

        Args:
            row_index (int): The index of the hour to calculate (0-8759).
        """
        # Trigger calculation of the properties of this hour that depend on the previous hour results
        self.get_solar_heat_windows_at_index(row_index)

    @property
    def set_point_temperature(self) -> DataFrame:
        """Set point temperatures for each hour of the year.

        DataFrame with columns ['min_temp_set_point', 'max_temp_set_point'] for each hour.

        The set point temperatures provide a minimum and maximum temperature for comfortable building occupation.
        This is given by specified target temperatures with an optional tolerance.
        """
        if 'min_temp_set_point' not in self._hours.columns or 'max_temp_set_point' not in self._hours.columns:
            tolerance = max(self.spec.parameters.temperature_tolerance or 0.0, 0.0)
            self._hours['min_temp_set_point'] = self._hours['is_daytime'].apply(
                lambda x: (self.spec.setpoint_winter_day - tolerance) if x else (self.spec.setpoint_winter_night - tolerance)
            )
            self._hours['max_temp_set_point'] = self._hours['is_daytime'].apply(
                lambda x: (self.spec.setpoint_summer_day + tolerance) if x else (self.spec.setpoint_summer_night + tolerance)
            )
        return self._hours[['min_temp_set_point', 'max_temp_set_point']]

    @property
    def epw_data(self) -> DataFrame:
        """DataFrame with EPW climate data for the specified location.
        """
        if not hasattr(self, '_epw_data') or self._epw_data is None:
            file_name = self.spec.meteorological_file
            path = os.path.join(
                os.path.dirname(__file__),
                "climate_data",
                file_name
            )
            self._epw_data, self._epw_metadata = read_epw(path)
        return self._epw_data

    @property
    def epw_metadata(self) -> dict:
        """Dict with EPW metadata for the specified location."""
        if not hasattr(self, '_epw_metadata') or self._epw_metadata is None:
            assert self.epw_data is not None  # Trigger loading of EPW data and metadata
        return self._epw_metadata

    @property
    def solar_irradiation(self) -> SolarIrradiationSimulation:
        """Solar irradiation simulation for the building."""
        if not hasattr(self, '_solar_irradiation') or self._solar_irradiation is None:
            self._solar_irradiation = SolarIrradiationSimulation(
                epw_data=self.epw_data,
                epw_metadata=self.epw_metadata,
            )
        return self._solar_irradiation

    def get_heating_and_cooling_degrees_days(self, base_temperature: float = 18.0) -> DataFrame:
        """Calculate heating degree days for each month based on dry bulb temperature.
        Args:
            spec (OpenBESSpecification): The building specifications spec data class.
            base_temperature (float): The base temperature for heating degree days calculation. Generally 65°F (18°C).
        Returns:
            DataFrame: Heating degree days for each month.
        """
        epw = self.epw_data
        days = epw[['month', 'day', 'temp_air']].copy()
        days = days.groupby(['month', 'day']).agg(lambda x: (x.max() + x.min()) / 2).reset_index(['month', 'day'])
        days['day'] = days.index + 1
        days = days.set_index(['day'])
        days['heating_degree_day'] = days['temp_air'].apply(lambda x: max(0, base_temperature - x))
        days['cooling_degree_day'] = days['temp_air'].apply(lambda x: max(0, x - base_temperature))
        days = days.drop(columns=['temp_air'])
        return days

    @property
    def internal_air_temp(self) -> 'Series[float]':
        """Hourly internal air temperature in degrees C.
        Ѳia [Hourly simulation column AQ]
        """
        if 'internal_air_temp' not in self._hours.columns:
            raise NotImplementedError
        return self._hours['internal_air_temp']

    def get_htr_1_at_index(self, i: int) -> float:
        """Hourly heat transfer rate 1?????? in kW/K.
        Htr_1 [Hourly Simulation column AM]
        """
        if isnan(self.htr_1.iat[i]):
            self._hours['htr_1'] = (
                    1 /
                    (
                            1 / self.get_heat_transmission_by_ventilation_at_index(i) +
                            1 / self.geometry.heat_transfer_is
                    )
            )
        return self.htr_1.iat[i]

    @property
    def htr_1(self) -> 'Series[float]':
        """Hourly heat transfer rate 1?????? in kW/K.
        Htr_1 [Hourly Simulation column AM]
        """
        return self._hours['htr_1']

    def get_htr_2_at_index(self, i: int) -> float:
        """Hourly heat transfer rate 2?????? in kW/K.
        Htr_2 [Hourly Simulation column AN]
        """
        if isnan(self.htr_2.iat[i]):
            self._hours.at[self._hours.index[i], 'htr_2'] = (
                    self.get_htr_1_at_index(i) + self.geometry.heat_transfer_rate_windows
            )
        return self.htr_2.iat[i]

    @property
    def htr_2(self) -> 'Series[float]':
        """Hourly heat transfer rate 2?????? in kW/K.
        Htr_2 [Hourly Simulation column AN]
        """
        return self._hours['htr_2']

    def get_htr_3_at_index(self, i: int) -> float:
        """Hourly heat transfer rate 3?????? in kW/K.
        Htr_3 [Hourly Simulation column AO]
        """
        if isnan(self.htr_3.iat[i]):
            self._hours.at[self._hours.index[i], 'htr_3'] = 1 / (
                    (1 / self.get_htr_2_at_index(i)) + (1/ self.geometry.heat_transfer_ms)
            )
        return self.htr_3.iat[i]

    @property
    def htr_3(self) -> 'Series[float]':
        """Hourly heat transfer rate 3?????? in kW/K.
        Htr_3 [Hourly Simulation column AO]
        """
        return self._hours['htr_3']


    def get_internal_surface_temp_at_index(self, i: int) -> float:
        """Hourly internal surface temperature in degrees C.
        Ѳs [Hourly Simulation column AX]
        """
        if isnan(self.internal_surface_temp.iat[i]):
            Htr_is = self.geometry.heat_transfer_is
            Htr_w = self.geometry.heat_transfer_rate_windows / self.geometry.conditioned_floor_area
            Hc_nd = 0  # [Hardcoded in AR111]
            self._hours['internal_surface_temp'] = \
                (
                        Htr_is * self.get_building_thermal_mass_at_index(i) +
                        self.temp_st.iat[i] +
                        Htr_w * self.dry_bulb_temp.iat[i] +
                        self.htr_1.iat[i] *
                        (
                                self.supply_air_temp.iat[i] + (self.internal_air_temp.iat[i] + Hc_nd) /
                                self.heat_transmission_by_ventilation.iat[i]
                        )
                ) / (Htr_is + Htr_w + self.htr_1.iat[i])
        return self.internal_surface_temp.iat[i]

    @property
    def internal_surface_temp(self) -> 'Series[float]':
        """Hourly internal surface temperature in degrees C.
        Ѳs [Hourly Simulation column AX]
        """
        return self._hours['internal_surface_temp']

    @property
    def temp_st(self) -> 'Series[float]':
        """Hourly temperature for ????? in degrees C.
        Ѳst [Hourly Simulation column AS]
        """
        if 'temp_st' not in self._hours.columns:
            raise NotImplementedError
        return self._hours['temp_st']

    @property
    def internal_heat_capacity(self) -> float:
        """Calculate the internal heat capacity of the building in J/K.
        [Inputs cell C275]
        """
        return (
                self.spec.parameters.heat_capacity_correction_factor *
                self.geometry.building_heat_capacitance
        )

    @property
    def m(self) -> 'Series[float]':
        """Hourly m?????? in W/m2.
         Φm [Hourly Simulation column AR]
        """
        if 'm' not in self._hours.columns:
            A_at = 4.5  # [Hardcoded in Hourly Simulation cell AM84]
            self._hours['m'] = (
                    (self.geometry.building_mass_factor / A_at) * (0.5 * self.internal_heat + self.solar_heat)
            )
        return self._hours['m']

    @property
    def m_tot(self) -> 'Series[float]':
        """Hourly m_tot?????? in W/m2.
        [Hourly Simulation column AT]
        """
        if 'm_tot' not in self._hours.columns:
            Htr_op = self.geometry.heat_transfer_rate_opaque  # AR93
            Htr_ms = self.geometry.heat_transfer_ms  # AM94
            Htr_em = 1 / ((1 / Htr_op) - (1 / Htr_ms))  # AR94
            HC_nd = 0  # Hardcoded in AR111
            self._hours['m_tot'] = (
                    self.m +
                    Htr_em * self.dry_bulb_temp +
                    self.htr_3 * (
                            self.temp_st + self.geometry.heat_transfer_rate_windows *
                            self.dry_bulb_temp + self.htr_1 *
                            (
                                    ((self.internal_air_temp + HC_nd) / self.heat_transmission_by_ventilation) +
                                    self.supply_air_temp
                            )
                    ) / self.htr_2
            )
        return self._hours['m_tot']

    def get_building_thermal_mass_at_index(self, i: int) -> float:
        """Calculate the building thermal mass for a specific hour.

        Args:
            i (int): The hour of the year (0-8759).
        Returns:
            float: The building thermal mass in degrees C.
        """
        if isnan(self.building_thermal_mass.iat[i]):
            starting_thermal_mass = 17.4  # Hardcoded in Hourly Simulation cell AV117
            prev_thermal_mass = self.building_thermal_mass.iat[i - 1] if i > 0 else starting_thermal_mass
            internal_heat_capacity_w = self.internal_heat_capacity / 3600  # Convert J/K to W/K  AM93
            Htr_op = self.geometry.heat_transfer_rate_opaque  # AR93
            Htr_ms = self.geometry.heat_transfer_ms  # AR95
            Htr_em = 1 / ((1 / Htr_op) - (1 / Htr_ms))  # AR94
            htr_3 = self.get_htr_3_at_index(i)
            current_thermal_mass = (
                    (
                            prev_thermal_mass *
                            (internal_heat_capacity_w - 0.5 * (htr_3 + Htr_em)) +
                            self.m_tot
                    ) /
                    (internal_heat_capacity_w + 0.5 * (htr_3 + Htr_em))
            )
            self._hours.at[self._hours.index[i], 'building_thermal_mass'] = (
                    (prev_thermal_mass + current_thermal_mass) / 2
            )
        return self.building_thermal_mass.iat[i]


    @property
    def building_thermal_mass(self) -> 'Series[float]':
        """Hourly building thermal mass in degrees C.
        Ѳm [Hourly Simulation column AW]
        """
        return self._hours['building_thermal_mass']

    @property
    def supply_air_temp(self) -> 'Series[float]':
        """Hourly supply air temperature in degrees C.
        Ѳsup = Te [Hourly simulation column AG]
        """
        if 'supply_air_temp' not in self._hours.columns:
            self._hours['supply_air_temp'] = list(self.epw_data['temp_air'])
        return self._hours['supply_air_temp']

    @property
    def relative_humidity(self) -> 'Series[float]':
        """Relative humidity for each hour of the year.
        """
        if 'relative_humidity' not in self._hours.columns:
            relative_humidity = self.epw_data['relative_humidity']
            relative_humidity.index = self._hours.index
            self._hours['relative_humidity'] = relative_humidity
        return self._hours['relative_humidity']

    @property
    def wet_bulb_temp(self) -> 'Series[float]':
        """Wet bulb temperature for each hour of the year.
        Tw [Hourly Simulation column K]
        """
        if 'wet_bulb_temp' not in self._hours.columns:
            df = self.relative_humidity.to_frame()
            df['temp_air'] = list(self.epw_data['temp_air'])
            self._hours['wet_bulb_temp'] = df.apply(
                lambda row: row['temp_air'] * \
                            atan(0.151977 * (row['relative_humidity'] + 8.313659) ** 0.5) + \
                            atan(row['temp_air'] + row['relative_humidity']) - \
                            atan(row['relative_humidity'] - 1.676331) + \
                            0.00391838 * (row['relative_humidity'] ** 1.5) * atan(0.023101 * row['relative_humidity']) \
                            - 4.686035,
                axis=1
            )
        return self._hours['wet_bulb_temp']

    @property
    def dry_bulb_temp(self) -> 'Series[float]':
        """Dry bulb temperature for each hour of the year.
        [Hourly simulation column I]
        """
        if 'dry_bulb_temp' not in self._hours.columns:
            self._hours['dry_bulb_temp'] = list(self.epw_data['temp_air'])
        return self._hours['dry_bulb_temp']

    @property
    def night_ventilation_enabled(self) -> 'Series[bool]':
        """Whether night ventilation is active for each hour of the year.
        [Hourly simulation column JL]

        Night ventilation is active between June 1st and September 1st inclusive, between sunset and dawn,
        if the air free temperature at 0m is above the dry bulb temperature.
        """
        if 'night_ventilation_enabled' not in self._hours.columns:
            self._hours['night_ventilation_enabled'] = Series(range(len(self._hours))).apply(
                lambda i: (
                        (
                                (6 <= self.epw_data['month'].iloc[i] < 9) or
                                self.epw_data['month'].iloc[i] == 9 and self.epw_data['day'].iloc[i] == 1
                        ) and
                        self.solar_irradiation.solarposition['apparent_elevation'].iloc[i] < 0 and  # JK
                        (self.air_free_temp_0m.iloc[i] > self.epw_data['temp_air'].iloc[i])
                )
            ).values
        return self._hours['night_ventilation_enabled']

    @property
    def air_flow_base(self) -> 'Series[float]':
        """Hourly base air flow in m3/h/m2.
        qv,base [Hourly simulation column JO]

        Base airflow is the infiltration airflow independent of other variables.

        Calculated by Q4Pa + night ventilation (qv,inf + qv,NV)
        """
        if 'air_flow_base' not in self._hours.columns:
            infiltration = self.spec.leakage_air_flow_independent * self.spec.parameters.infiltration_correction_factor
            threshold = 24  # [Hardcoded in Hourly simulation cell JK116]
            on_hours = self.air_free_temp_0m >= threshold  # JM
            # [Hourly simulation column JM]
            night_ventilation = (
                    on_hours *
                    self.spec.natural_ventilation_night *
                    self.night_ventilation_enabled
            )
            self._hours['air_flow_base'] = on_hours * night_ventilation + infiltration
            raise NotImplementedError
        return self._hours['air_flow_base']

    @property
    def air_set_temp(self) -> 'Series[float]':
        """Hourly air set temperature in degrees C.
        Ѳair,set [Hourly simulation column CE]
        """
        if 'air_set_temp' not in self._hours.columns:
            assert self.set_point_temperature is not None
            assert self.air_free_temp_0m is not None
            self._hours['air_set_temp'] = self._hours.apply(
                lambda row: self.set_point_temperature.at[row.name, 'max_temp_set_point']
                if row['air_free_temp_0m'] > self.set_point_temperature.at[row.name, 'max_temp_set_point']
                else (
                    self.set_point_temperature.at[row.name, 'min_temp_set_point']
                    if row['air_free_temp_0m'] < self.set_point_temperature.at[row.name, 'min_temp_set_point']
                    else row['air_free_temp_0m']
                ),
                axis=1
            )
        return self._hours['air_set_temp']

    @property
    def wind_speed(self) -> 'Series[float]':
        """Hourly wind speed in m/s.
        [Hourly simulation column W]
        """
        if 'wind_speed' not in self._hours.columns:
            self._hours['wind_speed'] = list(self.epw_data['wind_speed'])
        return self._hours['wind_speed']

    def get_air_flow_dependent_at_index(self, i: int) -> float:
        """Hourly air flow in m3/h/m2, dependent on other variables.
        qv,inf [Hourly simulation column JH]
        """
        if isnan(self.air_flow_dependent.iat[i]):
            qv_diff = 0.0  # [Hardcoded as blank in Hourly simulation column IU]
            # [Hourly simulation column JD]
            q4pa = self.spec.parameters.leakage_air_flow_dependent  # JE97
            Hstack = 10  # [Hardcoded in JE101: ISO 15242:2007. 6.7.1]
            air_set_temp = 20.0 if i == 0 else self.air_set_temp.iat[i - 1]  # CE117 is used for first hour
            qv_stack = max(
                0.0146 * q4pa * (((0.7 * Hstack) * (abs(self.dry_bulb_temp.iat[i] - air_set_temp))) ^ 0.667),
                0.001
            )
            # [Hourly simulation column JE]
            dcp = 0.75  # [Hardcoded in JE103]
            vsite_by_vmetro = TERRAIN_VSITE_BY_VMETRO[self.spec.terrain_class] # JE104
            qv_wind = 0.0769 * q4pa * (dcp * (vsite_by_vmetro * self.wind_speed.iat[i]) ^ 2) ^ 0.667
            # [Hourly simulation column JF]
            qv_sw = max(qv_stack, qv_wind) + (0.14 * qv_stack * qv_wind / q4pa)
            # [Hourly simulation column JG]
            qv_infred = max(
                qv_sw,
                (qv_stack * abs(qv_diff / 2) + qv_wind * 2 * abs(qv_diff / 3) / (qv_stack + qv_wind))
            )
            self._hours.at[self._hours.index[i], 'air_flow_dependent'] = qv_diff + qv_infred
        return self.air_flow_dependent.iat[i]

    @property
    def air_flow_dependent(self) -> 'Series[float]':
        """Hourly air flow in m3/h/m2, dependent on other variables.
        qv,inf [Hourly simulation column JH]
        """
        return self._hours['air_flow_dependent']

    def get_air_flow_at_index(self, i: int) -> float:
        """Hourly air flow in m3/h/m2.
        qv,tot [Hourly simulation column JZ]
        """
        if isnan(self.air_flow.iat[i]):
            self._hours.at[self._hours.index[i], 'air_flow'] = (
                    self.ventilation.air_supply_rate.iat[i] +
                    self.air_flow_dependent.iat[i] +
                    self.air_flow_base.iat[i]
            )
        return self.air_flow.iat[i]

    @property
    def air_flow(self) -> 'Series[float]':
        """Hourly air flow in m3/h/m2.
        qv,tot [Hourly simulation column JZ]

        Total airflow is
        air infiltration adjusted for other variables +
        air infiltration base +
        mechanical supply 1 +
        mechanical supply 2
        """
        return self._hours['air_flow']

    def get_heat_transmission_by_ventilation_at_index(self, i: int) -> float:
        """Calculate the heat transmission by ventilation for a specific hour index in kW/K.
        Hve [Hourly Simulation column AL]
        """
        if isnan(self.heat_transmission_by_ventilation.iat[i]):
            # heat capacity of air in W/m3K [Hourly Simulation cell AM105]
            heat_capacity_air = self.spec.parameters.density_of_air * self.spec.parameters.specific_heat_of_air / 3.6
            self._hours.at[self._hours.index[i], 'heat_transmission_by_ventilation'] = \
                heat_capacity_air * self.air_flow.iat[i]
        return self.heat_transmission_by_ventilation.iat[i]

    @property
    def heat_transmission_by_ventilation(self) -> 'Series[float]':
        """Calculate the heat transmission by ventilation in kW/K.
        Hve [Hourly Simulation column AL]

        Heat transfer of ventilation (Hve, W/m2 K) is calculated according to
        Eq. (5). It is based on total air flow due to leakage and ventilation
        airflow (qve), and supply air temperature (Ѳsup).
        """
        return self._hours['heat_transmission_by_ventilation']

    @property
    def heat_infiltration_window(self) -> float:
        """Calculate the heat transmission by infiltration through windows in kW/K.
        Htr,w
        """
        if not hasattr(self, '_heat_infiltration_window') or self._heat_infiltration_window is None:
            raise NotImplementedError
        return self._heat_infiltration_window

    @property
    def heat_transmission_by_infiltration(self) -> float:
        """Calculate the heat transmission by infiltration in kW/K.
        Htr
        """
        if not hasattr(self, '_heat_transmission_by_infiltration') or self._heat_transmission_by_infiltration is None:
            raise NotImplementedError
        return self._heat_transmission_by_infiltration

    @property
    def internal_heat_from_occupants(self) -> 'Series[float]':
        """Hourly internal heat gains from occupants in W/m2.
        ϕint,oc [Hourly Simulation column KI]
        """
        if 'internal_heat_from_occupants' not in self._hours.columns:
            self._hours['internal_heat_from_occupants'] = (
                    self.occupancy.occupancy['occupancy_ratio'] *
                    self.occupancy.metabolic_rate_per_m2
            )
        return self._hours['internal_heat_from_occupants']

    @property
    def internal_heat_from_appliances(self) -> 'Series[float]':
        """Hourly internal heat gains from appliances in W/m2.
        ϕint,ap [Hourly Simulation column KJ]
        """
        if 'internal_heat_from_appliances' not in self._hours.columns:
            # Constant, Inputs cell C144, Table G.11 ISO 13790
            appliance_W_per_m2 = 1.0
            self._hours['internal_heat_from_appliances'] = (
                    self.occupancy.occupancy['occupancy_ratio'] *
                    appliance_W_per_m2
            )
        return self._hours['internal_heat_from_appliances']

    @property
    def internal_heat_from_lighting(self) -> 'Series[float]':
        """Hourly internal heat gains from lighting in W/m2.
        ϕint,l [Hourly Simulation column KK, KQ]

        Lighting heat generation is modelled using a constant standby (parasitic) output (Wpc) and
        an occupancy-scaled output (Wli).
        """
        if 'internal_heat_from_lighting' not in self._hours.columns:
            self._hours['internal_heat_from_lighting'] = (
                    (self.lighting.lighting_ratio * self.lighting.lighting_heat) +
                    self.lighting.parasitic_heat
            )
        return self._hours['internal_heat_from_lighting']

    @property
    def internal_heat(self) -> 'Series[float]':
        """Hourly internal heat gains in W/m2.
        ϕint [Hourly Simulation column AI; KL]

        Internal heat gains are the sum of internal heat gains from occupants, appliances, and lighting.
        """
        if 'internal_heat' not in self._hours.columns:
            # calculate prerequisites
            self._hours['internal_heat'] = (
                    self.internal_heat_from_occupants +
                    self.internal_heat_from_appliances +
                    self.internal_heat_from_lighting
            )
        return self._hours['internal_heat']

    @property
    def internal_heat_adjusted(self) -> 'Series[float]':
        """Hourly adjusted internal heat gains in W/m2.""
        ϕia [Hourly Simulation column AQ]

        Adjusted internal heat gains are the internal heat gains multiplied by an adjustment factor.
        """
        if 'internal_heat_adjusted' not in self._hours.columns:
            adjustment_factor = 0.5  # Hardcoded in spreadsheet column AQ
            self._hours['internal_heat_adjusted'] = self.internal_heat * adjustment_factor
        return self._hours['internal_heat_adjusted']

    def get_air_free_temp_0m_at_index(self, i: int) -> float:
        """Get the air free temperature at 0m for a specific hour index.
        Ѳair,0 [Hourly Simulation column AY]

        Args:
            i (int): The hour index (0-8759).
        Returns:
            float: The air free temperature at 0m in degrees C.
        """
        if isnan(self.air_free_temp_0m.iat[i]):
            conditioned_area = self.geometry.conditioned_floor_area
            area_at = 4.5  # Hardcoded in Hourly Simulation cell AM84: EN ISO 13790, 7.2.2
            total_area = area_at * conditioned_area
            # Heat transfer rate from air to surfaces in W/K [Hourly simulation cell AR83]
            Htr_is_W_per_K = 3.45 * total_area
            # Heat transfer rate from air to surfaces in W/m2K [Hourly Simulation cell AR98]
            Htr_is = Htr_is_W_per_K / conditioned_area
            HC_nd = 0  # Hardcoded in Hourly Simulation cell AR111
            self._hours['air_free_temp_0m'] = \
                (
                        Htr_is * self.get_internal_surface_temp_at_index(i) +
                        self.get_heat_transmission_by_ventilation_at_index(i) * self.supply_air_temp.iat[i] +
                        self.internal_heat_adjusted.iat[i] +
                        HC_nd
                ) / ( Htr_is + self.heat_transmission_by_ventilation.iat[i] )

        return self.air_free_temp_0m.iat[i]

    @property
    def air_free_temp_0m(self) -> 'Series[float]':
        """Hourly air free temperature at 0m.
        Ѳair,0 [Hourly Simulation column AY]

        Calculated by considering:
        - Internal surface temperature and its heat transfer rate to air
        - Heat transmission by ventilation and supply air temperature
        - Internal heat gains (adjusted)
        - HC_nd (assumed to be 0)
        and dividing by the total heat transfer rates to air (from surfaces and ventilation).

        This produces a weighted sum of these temperature influences to estimate the air free temperature at 0m height.
        """
        return self._hours['air_free_temp_0m']

    def rse_for_wind_speed(self, wind_speed: float) -> float:
        if wind_speed <= 1.5:
            return 0.08
        if wind_speed <= 2.5:
            return 0.06
        if wind_speed <= 3.5:
            return 0.05
        if wind_speed <= 4.5:
            return 0.04
        if wind_speed <= 6.0:
            return 0.04
        if wind_speed <= 8.0:
            return 0.03
        return 0.02

    @property
    def rse(self) -> 'Series[float]':
        """Hourly??????#
        [Hourly simulation column KU]
        """
        return self.wind_speed.apply(self.rse_for_wind_speed)

    def get_solar_heat_windows_for_orientation_at_index(self, row: Series, i: int) -> float:
        """Calculate solar heat gains through windows for a specific orientation.
        [Hourly Simulation columns KY:LF]
        """
        kx116 = 22  # Hardcoded in Hourly Simulation cell KX116
        orientation = row.name
        compass_point = self.geometry.get_compass_point_for_orientation(orientation=orientation)
        view_factor = self.spec.parameters.view_factor_to_sky_facade  # KY80:LF80
        hr = 5 * 0.9  # [Hardcoded in KY81:LF81 via Inputs G230]
        delta_theta_er = 11  # [Hardcoded in KY82: ISO 13790, 11.4.6]
        Fsh_ob_overhand = 0.0  # LF87 [Hardcoded in Inputs N108:U108]
        Fsh_ob_fin = 0.0  # LF90 [Hardcoded in Inputs N110:U110]
        Fsh_ob_horizon = 0.0  # LF93 [Hardcoded in Inputs N112:U112]
        solar_lost_through_windows = 0.0  # [Hardcoded in KY84]
        # LF95: ISO 13790, 11.4.4
        Fsh_ob_horizon = Fsh_ob_overhand * Fsh_ob_fin * Fsh_ob_horizon - solar_lost_through_windows
        window_area = row['window_area']  # KY105:LF105
        solar_radiation = self.solar_irradiation.get_solar_irradiation(compass_point).iat[i]
        air_temp = self.get_air_free_temp_0m_at_index(i - 1) if i > 1 else 0.0
        Rse = self.rse.iat[i]  # KU: ISO 6946
        if air_temp < kx116:
            # KY107:LF107 (winter)
            Asol_w = (
                    (self.spec.solar_external_shading_winter * self.spec.parameters.shading_correction_factor) *
                    (1 - self.spec.window_frame_factor) *
                    window_area
            )
            g_value = 1.0  # [Hardcoded in KY100]
        else:
            # KY108:LF108 (summer)
            Asol_w = (
                    (self.spec.solar_external_shading_summer * self.spec.parameters.shading_correction_factor) *
                    (1 - self.spec.window_frame_factor) *
                    window_area
            )
            g_value = 0.9  # [Hardcoded in KY:LF]
        solar_altitude = self.solar_irradiation.solarposition['apparent_elevation'].iat[i]
        # KX
        if 0 < solar_altitude < 90:
            g_gl = (
                    (-0.000003 * solar_altitude ^ 3 + 0.0002 * solar_altitude ^ 2 - 0.0053 * solar_altitude + 0.9986) *
                    self.spec.window_gvalue
            )
        else:
            g_gl = 0.0
        x = (
                (Fsh_ob_horizon * (Asol_w * (g_gl * g_value)) * solar_radiation) -
                (view_factor * (Rse * self.spec.uvalue_window * window_area * hr * delta_theta_er))
        )
        return max(0, x)

    def get_solar_heat_windows_at_index(self, i: int) -> float:
        """Calculate solar heat gains through windows for a specific hour index.
        [Hourly Simulation columns KY:LF]
        """
        if isnan(self.solar_heat_windows.iat[i]):
            windows_by_orientation = (
                self.geometry.window_area_orientation
                .to_frame('window_area')
                .groupby('orientation')
                .sum()
            )
            wattage = windows_by_orientation.apply(
                lambda row: self.get_solar_heat_windows_for_orientation_at_index(row, i), axis=1
            )
            self._hours.at[self._hours.index[i], 'solar_heat_windows'] = wattage.sum(axis=1)
        return self.solar_heat_windows.iat[i]

    @property
    def solar_heat_windows(self) -> 'Series[float]':
        """Hourly solar heat gains through windows in W/m2.
        ϕsol,w [Hourly Simulation column LH]

        Wattage is given by the sum of solar radiation on each window multiplied by its
        area and solar heat gain coefficient.
        Solar radiation is a function of climate data and building orientation.
        """
        return self._hours['solar_heat_windows']

    def get_solar_heat_opaque(self, row: Series) -> 'Series[float]':
        """Calculate solar heat gains through opaque surfaces for a specific orientation.
        [Hourly Simulation columns LK:LR]
        """
        compass_point = row.name
        solar_radiation = self.solar_irradiation.get_solar_irradiation(compass_point)  # M:T

        absorption = self.spec.parameters.facade_absorption_coefficient  # LK78:LR78
        view_factor = self.spec.parameters.view_factor_to_sky_facade  # LK80:LR80
        hr = 5 * self.spec.parameters.facade_emissivity  # [LK81:LR81 via Inputs E224]
        delta_theta_er = 11  # [Hardcoded in LK82: ISO 13790, 11.4.6]
        Fsh_ob_overhand = 0.0  # LR87 [Hardcoded in LK87:LR87 via Inputs C108:J108]
        # LR90 via Inputs C115:J115
        Fsh_ob_own = (
                (self.spec.building_length + self.spec.building_width) /
                (self.geometry.equivalent_rectangle.length + self.geometry.equivalent_rectangle.width)
        )
        Fsh_ob = Fsh_ob_overhand * Fsh_ob_own # LK95:LR95
        u_value = self.spec.uvalue_facade  # LK104:LR104
        opaque_area = row['opaque_area']  # LK105:LR105
        Rse = self.rse  # KU: ISO 6946
        return (
                Fsh_ob *
                (absorption * Rse * opaque_area * u_value) *
                solar_radiation - (
                        view_factor * (Rse * u_value * opaque_area * hr * delta_theta_er)
                )
        ).apply(lambda x: max(0.0, x))

    @property
    def solar_heat_roof(self):
        """Calculate solar heat gains through roof surfaces in W.
        HOR [Hourly Simulation column LS]
        """
        absorption = self.spec.parameters.roof_absorption_coefficient  # LS78
        view_factor = self.spec.parameters.view_factor_to_sky_roof  # LS80
        hr = 5 * self.spec.parameters.facade_emissivity  # [LS81 via Inputs E224]
        delta_theta_er = 11  # [Hardcoded in LK82: ISO 13790, 11.4.6]
        Fsh_ob = 1  # [Hardcoded in LS95 ISO 13790, 11.4.4]
        u_value = self.spec.uvalue_roof # LS104
        area = self.geometry.roof_projections.sum()  # LS105
        rse = self.rse  # KU
        irradiation = self.solar_irradiation.ghi  # Hourly simulation column U
        return (
                    Fsh_ob * (absorption * rse * area * u_value) * irradiation -
                    (view_factor * (rse * u_value * area * hr * delta_theta_er))
            ).apply(lambda x: max(0, x))

    @property
    def solar_heat_opaque(self) -> 'Series[float]':
        """Hourly solar heat gains through opaque surfaces in W/m2.
        ϕsol,op [Hourly Simulation column LT]

        Wattage is given by the sum of solar radiation on each opaque surface multiplied by its
        area and solar heat gain coefficient.
        Solar radiation is a function of climate data and building orientation.
        Horizontal solar radiation is also included because of roof surfaces.
        """
        if 'solar_heat_opaque' not in self._hours.columns:
            opaque_facade_by_orientation = (
                self.geometry.opaque_areas
                .to_frame('opaque_area')
                .groupby('compass_point')
                .sum()
                .apply(
                    self.get_solar_heat_opaque,
                    axis=1
                )
            )
            self._hours['solar_heat_opaque'] = opaque_facade_by_orientation.sum() + self.solar_heat_roof
        return self._hours['solar_heat_opaque']

    @property
    def solar_heat(self) -> 'Series[float]':
        """Hourly solar heat gains in W/m2.
        ϕsol [Hourly Simulation column AJ, KO]

        Wattage per square meter is given by the sum of solar heat gains through windows
        and opaque surfaces, divided by the conditioned floor area.
        """
        if 'solar_heat' not in self._hours.columns:
            conditioned_floor_area = self.geometry.conditioned_floor_area
            assert self.solar_heat_opaque is not None
            assert self.solar_heat_windows is not None
            self._hours['solar_heat'] = (
                    (self.solar_heat_windows + self.solar_heat_opaque) /
                    conditioned_floor_area
            )
        return self._hours['solar_heat']

    @property
    def temp_change_demand(self) -> float:
        """Temperature change demand based in W/m2.
        ϕHC,nd, W/m2
        """
        if 'temp_change_demand' not in self._hours.columns:
            raise NotImplementedError
        return self._hours['temp_change_demand']
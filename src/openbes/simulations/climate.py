from math import atan

from pvlib.iotools import read_epw
from pandas import DataFrame, Series
import os

from .base import HourlySimulation
from .geometry import BuildingGeometry
from .lighting import LightingSimulation
from .occupancy import OccupationSimulation
from .ventilation import VentilationSimulation
from ..types import OpenBESSpecification

RELATIVE_HUMIDITY = 55.0  # Percentage

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
    geometry: BuildingGeometry
    occupancy: OccupationSimulation
    lighting: LightingSimulation
    ventilation: VentilationSimulation
    _epw_data: DataFrame
    _heating_and_cooling_degree_days: DataFrame
    _heat_infiltration_window: float
    _heat_infiltration_opaque: float
    _heat_transmission_by_infiltration: float
    _temp_change_demand: float

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
        """Return a DataFrame with EPW climate data for the specified location.
        Args:
            spec (OpenBESSpecification): The building specifications spec data class.
        Returns:
            DataFrame: EPW climate data for the specified location.
        """
        if not hasattr(self, '_epw_data') or self._epw_data is None:
            file_name = self.spec.meteorological_file
            path = os.path.join(
                os.path.dirname(__file__),
                "climate_data",
                file_name
            )
            self._epw_data, _ = read_epw(path)
        return self._epw_data

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
    def internal_air_temp(self) -> Series:
        """Hourly internal air temperature in degrees C.
        Ѳia [Hourly simulation column AQ]
        """
        if 'internal_air_temp' not in self._hours.columns:
            raise NotImplementedError
        return self._hours['internal_air_temp']

    @property
    def htr_1(self) -> Series:
        """Hourly heat transfer rate 1?????? in kW/K.
        Htr_1 [Hourly Simulation column AY]
        """
        if 'htr_1' not in self._hours.columns:
            self._hours['htr_1'] = (
                    1 /
                    (
                            1 / self.heat_transmission_by_ventilation +
                            1 / self.geometry.heat_transfer_is
                    )
            )
        return self._hours['htr_1']

    @property
    def internal_surface_temp(self) -> Series:
        """Hourly internal surface temperature in degrees C.
        Ѳs [Hourly Simulation column AX]
        """
        if 'internal_surface_temp' not in self._hours.columns:
            Htr_is = self.geometry.heat_transfer_is
            Htr_w = self.geometry.heat_transfer_rate_windows / self.geometry.conditioned_floor_area
            Htr_1 = self.htr_1
            Hc_nd = 0  # [Hardcoded in AR111]
            self._hours['internal_surface_temp'] = (
                                                           Htr_is * self.building_thermal_mass +
                                                           self.temp_st +
                                                           Htr_w * self.dry_bulb_temp +
                                                           self.htr_1 * (self.supply_air_temp + (self.internal_air_temp + Hc_nd) / self.heat_transmission_by_ventilation)
                                                   ) / (Htr_is + Htr_w + self.htr_1)
        return self._hours['internal_surface_temp']

    @property
    def temp_st(self) -> Series:
        """Hourly temperature for ????? in degrees C.
        Ѳst [Hourly Simulation column AS]
        """
        if 'temp_st' not in self._hours.columns:
            raise NotImplementedError
        return self._hours['temp_st']

    @property
    def building_thermal_mass(self) -> Series:
        """Hourly building thermal mass in degrees C.
        Ѳm [Hourly Simulation column AW]
        """
        if 'building_thermal_mass' not in self._hours.columns:
            raise NotImplementedError
        return self._hours['building_thermal_mass']

    @property
    def supply_air_temp(self) -> Series:
        """Hourly supply air temperature in degrees C.
        Ѳsup
        """
        if 'supply_air_temp' not in self._hours.columns:
            raise NotImplementedError
        return self._hours['supply_air_temp']

    @property
    def relative_humidity(self) -> Series:
        """Relative humidity for each hour of the year.
        """
        if 'relative_humidity' not in self._hours.columns:
            relative_humidity = self.epw_data['relative_humidity']
            relative_humidity.index = self._hours.index
            self._hours['relative_humidity'] = relative_humidity
        return self._hours['relative_humidity']

    @property
    def wet_bulb_temp(self) -> Series:
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
    def dry_bulb_temp(self) -> Series:
        """Dry bulb temperature for each hour of the year.
        [Hourly simulation column I]
        """
        if 'dry_bulb_temp' not in self._hours.columns:
            self._hours['dry_bulb_temp'] = list(self.epw_data['temp_air'])
        return self._hours['dry_bulb_temp']

    @property
    def night_ventilation_enabled(self) -> Series:
        """Whether night ventilation is active for each hour of the year.
        [Hourly simulation column JL]

        Night ventilation is active between June 1st and September 1st inclusive, between sunset and dawn,
        if the air free temperature at 0m is above the dry bulb temperature.
        """
        if 'night_ventilation_enabled' not in self._hours.columns:
            self._hours['night_ventilation_enabled'] = list(self.epw_data.apply(
                lambda row: (
                        ((6 <= row['month'] < 9) or row['month'] == 9 and row['day'] == 1) and
                        row['solar'] < 0 and
                        (self.air_free_temp_0m[(row['month'], row['day'], row['hour'])] > row['temp_air'])
                ), axis=1
            ))
        return self._hours['night_ventilation_enabled']

    @property
    def air_flow_base(self) -> Series:
        """Hourly base air flow in m3/h/m2.
        qv,base [Hourly simulation column JO]

        Base airflow is the infiltration airflow independent of other variables.

        Calculated by Q4Pa + night ventilation (qv,inf + qv,NV)
        """
        if 'air_flow_base' not in self._hours.columns:
            infiltration = self.spec.leakage_air_flow_independent * self.spec.parameters.infiltration_correction_factor

            threshold = 24  # [Hardcoded in Hourly simulation cell JK116
            on_hours = self.air_free_temp_0m >= threshold
            night_ventilation = (
                    on_hours *
                    self.spec.natural_ventilation_night *
                    self.night_ventilation_enabled
            )
            self._hours['air_flow_base'] = on_hours * night_ventilation + infiltration
            raise NotImplementedError
        return self._hours['air_flow_base']

    @property
    def air_flow(self) -> Series:
        """Hourly air flow in m3/h/m2.
        qv,tot [Hourly simulation column JZ]

        Total airflow is
        air infiltration adjusted for other variables +
        air infiltration base +
        mechanical supply 1 +
        mechanical supply 2
        """
        if 'air_flow' not in self._hours.columns:
            self._hours['air_flow'] = (
                    self.ventilation.air_supply_rate +
                    self.air_flow_adjusted +
                    self.air_flow_base
            )
        return self._hours['air_flow']


    @property
    def heat_transmission_by_ventilation(self) -> Series:
        """Calculate the heat transmission by ventilation in kW/K.
        Hve [Hourly Simulation column AL]

        Heat transfer of ventilation (Hve, W/m2 K) is calculated according to
        Eq. (5). It is based on total air flow due to leakage and ventilation
        airflow (qve), and supply air temperature (Ѳsup).
        """
        if 'heat_transmission_by_ventilation' not in self._hours.columns:
            # heat capacity of air in W/m3K
            heat_capacity_air = self.spec.parameters.density_of_air * self.spec.parameters.specific_heat_of_air / 3.6
            # qv_total = qv_fresh_inf \
            #            + qv_fresh_total + \
            #            qv_mechanical_1 + \
            #            qv_mechanical_2
            # qv_total is in m3/h
            raise NotImplementedError
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
    def heat_infiltration_opaque(self) -> float:
        """Calculate the heat infiltration through opaque surfaces in kW/K.
        Htr,op
        """
        if not hasattr(self, '_heat_infiltration_opaque') or self._heat_infiltration_opaque is None:
            raise NotImplementedError
        return self._heat_infiltration_opaque

    @property
    def heat_transmission_by_infiltration(self) -> float:
        """Calculate the heat transmission by infiltration in kW/K.
        Htr
        """
        if not hasattr(self, '_heat_transmission_by_infiltration') or self._heat_transmission_by_infiltration is None:
            raise NotImplementedError
        return self._heat_transmission_by_infiltration

    @property
    def internal_heat_from_occupants(self) -> Series:
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
    def internal_heat_from_appliances(self) -> Series:
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
    def internal_heat_from_lighting(self) -> Series:
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
    def internal_heat(self) -> Series:
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
    def internal_heat_adjusted(self) -> Series:
        """Hourly adjusted internal heat gains in W/m2.""
        ϕia [Hourly Simulation column AQ]

        Adjusted internal heat gains are the internal heat gains multiplied by an adjustment factor.
        """
        if 'internal_heat_adjusted' not in self._hours.columns:
            adjustment_factor = 0.5  # Hardcoded in spreadsheet column AQ
            self._hours['internal_heat_adjusted'] = self.internal_heat * adjustment_factor
        return self._hours['internal_heat_adjusted']

    @property
    def air_free_temp_0m(self) -> Series:
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
        if 'air_free_temp_0m' not in self._hours.columns:
            assert self.internal_surface_temp is not None
            assert self.heat_transmission_by_ventilation is not None
            assert self.supply_air_temp is not None
            assert self.internal_heat_adjusted is not None

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
                        Htr_is * self._hours['internal_surface_temp'] +
                        self._hours['heat_transmission_by_ventilation'] * self._hours['supply_air_temp'] +
                        self._hours['internal_heat_adjusted'] +
                        HC_nd
                ) / ( Htr_is + self._hours['heat_transmission_by_ventilation'] )
        return self._hours[['air_free_temp_0m']]

    @property
    def solar_heat_windows(self) -> DataFrame:
        """Hourly solar heat gains through windows in W/m2.
        ϕsol,w [Hourly Simulation column LF]

        Wattage is given by the sum of solar radiation on each window multiplied by its
        area and solar heat gain coefficient.
        Solar radiation is a function of climate data and building orientation.
        """
        if 'solar_heat_windows' not in self._hours.columns:
            kv116 = 22  # Hardcoded in Hourly Simulation cell KV116
            df = self.air_free_temp_0m
            df['solar_heat_window'] = df.apply(
                lambda row: row
            )
            # if $AY117 < kv116:
            #     rest = (KW$95*(KW$107*($KV118*$KW$100))*M118)-(KW$80*($KS118*KW$104*KW$105*KW$81*$KW$82))
            # else:
            #     rest = (KW$95*(KW$108*($KV118*0.9))*M118)-(KW$80*($KS118*KW$104*KW$105*KW$81*$KW$82))
            # return max(
            #     0,
            #     rest
            # )
        raise NotImplementedError

    @property
    def solar_heat_opaque(self) -> DataFrame:
        """Hourly solar heat gains through opaque surfaces in W/m2.
        ϕsol,op [Hourly Simulation column LR]

        Wattage is given by the sum of solar radiation on each opaque surface multiplied by its
        area and solar heat gain coefficient.
        Solar radiation is a function of climate data and building orientation.
        Horizontal solar radiation is also included because of roof surfaces.
        """
        if 'solar_heat_opaque' not in self._hours.columns:
            pass
        raise NotImplementedError

    @property
    def solar_heat(self) -> DataFrame:
        """Hourly solar heat gains in W/m2.
        ϕsol [Hourly Simulation column AJ, KM]

        Wattage per square meter is given by the sum of solar heat gains through windows
        and opaque surfaces, divided by the conditioned floor area.
        """
        if 'solar_heat' not in self._hours.columns:
            conditioned_floor_area = self.geometry.conditioned_floor_area
            assert self.solar_heat_opaque is not None
            assert self.solar_heat_windows is not None
            self._hours['solar_heat'] = (
                    (self._hours['solar_heat_window'] + self._hours['solar_heat_opaque']) /
                    conditioned_floor_area
            )
        return self._hours[['solar_heat']]

    @property
    def temp_change_demand(self) -> float:
        """Temperature change demand based in W/m2.
        ϕHC,nd, W/m2
        """
        if not hasattr(self, '_temp_change_demand') or self._temp_change_demand is None:
            pass
        raise NotImplementedError
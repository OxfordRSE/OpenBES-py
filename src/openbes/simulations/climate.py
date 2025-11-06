from math import atan

from pvlib.iotools import read_epw
from pandas import DataFrame, Series
import os

from .base import HourlySimulation
from .geometry import BuildingGeometry
from .lighting import LightingSimulation
from .occupancy import OccupationSimulation
from ..types import THERMAL_BREAKS, OpenBESSpecification

RELATIVE_HUMIDITY = 55.0  # Percentage

THERMAL_BREAK_TRANSMITTANCE = {
    THERMAL_BREAKS.Facade_ground: 0.54,
    THERMAL_BREAKS.Facade_intermediate: 0.60,
    THERMAL_BREAKS.Facade_roof: 0.44,
    THERMAL_BREAKS.Windows: 0.50,
    THERMAL_BREAKS.Shading: 0.80,
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
    geometry: BuildingGeometry
    occupancy: OccupationSimulation
    lighting: LightingSimulation
    _epw_data: DataFrame
    _heating_and_cooling_degree_days: DataFrame
    _heat_transfer_rate_windows: float
    _heat_transfer_rate_opaque: float
    _heat_transfer_ms: float
    _heat_transmission_by_ventilation: float
    _heat_infiltration_window: float
    _heat_infiltration_opaque: float
    _heat_transmission_by_infiltration: float
    
    def __init__(
            self,
            spec: OpenBESSpecification,
            geometry: BuildingGeometry = None,
            occupancy: OccupationSimulation = None,
            lighting: LightingSimulation = None,
    ):
        super().__init__(spec=spec)
        self.geometry = geometry or BuildingGeometry(spec=spec)
        self.occupancy = occupancy or OccupationSimulation(spec=spec, geometry=self.geometry)
        self.lighting = lighting or LightingSimulation(spec=spec, occupancy=self.occupancy)

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
    def internal_air_temp(self) -> DataFrame:
        """Return a DataFrame with estimated internal air temperature for each hour of the year.
        Ѳair
        """
        raise NotImplementedError

    @property
    def heat_transfer_rate_windows(self) -> float:
        """The heat transfer rate through windows (W/m²K).
        Htr_w [Hourly Simulation cell AR97]
        """
        if not hasattr(self, '_heat_transfer_rate_windows') or self._heat_transfer_rate_windows is None:
            conditioned_area = self.geometry.conditioned_floor_area
            correction_factor = self.spec.parameters.window_correction_factor
            window_area = self.geometry.window_area
            u_value = self.spec.uvalue_window
            if self.spec.thermal_bridge_shading:
                shading = self.geometry.window_shading * THERMAL_BREAK_TRANSMITTANCE[THERMAL_BREAKS.Shading]
            else:
                shading = 0.0
            self._heat_transfer_rate_windows = (window_area * u_value + shading) * correction_factor / conditioned_area
        return self._heat_transfer_rate_windows

    @property
    def heat_transfer_rate_opaque(self) -> float:
        """Calculate the heat transfer rate through opaque envelope (W/m²K).
        Htr_opaque [Hourly Simulation cell AR93]
        Args:
            spec (OpenBESSpecification): The building specifications spec data class.
        Returns:
            float: Heat transfer rate through opaque envelope (W/m²K).
        """
        raise NotImplementedError

    @property
    def heat_transfer_ms(self) -> float:
        """Calculate the heat transfer coefficient between internal air and internal surface (W/m²K).
        Htr_ms [Hourly Simulation cell AR95] EN ISO 13790 12.2.2
        """
        if not hasattr(self, '_heat_transfer_ms') or self._heat_transfer_ms is None:
            factor = 9.1  # Unnamed factor hardcoded in cell AR95 formula
            self._heat_transfer_ms = (self.heat_transfer_rate_windows + self.heat_transfer_rate_opaque) * factor
        return self._heat_transfer_ms

    @property
    def internal_surface_temp(self) -> DataFrame:
        """Return a DataFrame with estimated internal surface temperature for each hour of the year.
        Ѳs [Hourly Simulation column AX]
        """
        Htr_ms = self.heat_transfer_ms
        # (
        #     $AR$95 * AW118 +
        #     AS118 +
        #     $AR$97 * $I118 +
        #     $AM118 * ($AG118 + (AQ118 + $AR$111) / $AL118)
        # ) / ($AR$95 + $AR$97 + $AM118)
        raise NotImplementedError

    @property
    def supply_air_temp(self) -> DataFrame:
        """Return a DataFrame with supply air temperature for each hour of the year.
        Ѳsup
        """
        raise NotImplementedError

    @property
    def relative_humidity(self) -> Series:
        """Return a DataFrame with relative humidity for each hour of the year.
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
    def heat_transmission_by_ventilation(self) -> float:
        """Calculate the heat transmission by ventilation in kW/K.
        Hve [Hourly Simulation column AL]

        Heat transfer of ventilation (Hve, W/m2 K) is calculated according to
        Eq. (5). It is based on total air flow due to leakage and ventilation
        airflow (qve), and supply air temperature (Ѳsup).
        """
        if not hasattr(self, '_heat_transmission_by_ventilation') or self._heat_transmission_by_ventilation is None:
            air_density = 1.2110  # kg/m3
            specific_heat_capacity_air = 1.0150  # kJ/kgK
            heat_capacity_air = air_density * specific_heat_capacity_air / 3.6  # W/m3K
            # qv_total = qv_fresh_inf \
            #            + qv_fresh_total + \
            #            qv_mechanical_1 + \
            #            qv_mechanical_2
            # qv_total is in m3/h
            raise NotImplementedError
        return self._heat_transmission_by_ventilation

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
                    (self.lighting.lighting_ratio['lighting_ratio'] * self.lighting.lighting_heat) +
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
                self.internal_heat_from_occupants['internal_heat_from_occupants'] +
                self.internal_heat_from_appliances['internal_heat_from_appliances'] +
                self.internal_heat_from_lighting['internal_heat_from_lighting']
            )
        return self._hours['internal_heat']

    def get_internal_heat_adjusted(self) -> Series:
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
    !!!!!!
        df = HOURS_DF.copy()
        temp_air = get_epw_data(spec)['temp_air']
        temp_air.index = df.index
        df = df.join(temp_air)
        df = df.join(get_internal_surface_temp(spec=spec))
        df = df.join(get_heat_transmission_by_ventilation(spec=spec))
        df = df.join(get_supply_air_temp(spec=spec))
        df = df.join(get_internal_heat_adjusted(spec=spec))
        conditioned_area = get_conditioned_floor_area(spec=spec)
        area_at = 4.5  # Hardcoded in Hourly Simulation cell AM84: EN ISO 13790, 7.2.2
        total_area = area_at * conditioned_area
        # Heat transfer rate from air to surfaces in W/K [Hourly simulation cell AR83]
        Htr_is_W_per_K = 3.45 * total_area
        # Heat transfer rate from air to surfaces in W/m2K [Hourly Simulation cell AR98]
        Htr_is = Htr_is_W_per_K / conditioned_area
        HC_nd = 0  # Hardcoded in Hourly Simulation cell AR111
        df['air_free_temp_0m'] = (
                                         Htr_is * df['internal_surface_temp'] +
                                         df['heat_transmission_by_ventilation'] * df['supply_air_temp'] +
                                         df['internal_heat_adjusted'] +
                                         HC_nd
                                 ) / ( Htr_is + df['heat_transmission_by_ventilation'] )
        return df[['air_free_temp_0m']]

    def get_solar_heat_window(self) -> DataFrame:
        """Calculate the solar heat gains through windows based on building specifications.
        ϕsol,w [Hourly Simulation column LF]

        Wattage is given by the sum of solar radiation on each window multiplied by its
        area and solar heat gain coefficient.
        Solar radiation is a function of climate data and building orientation.

        Args:
            spec (OpenBESSpecification): The building specifications spec data class.
        Returns:
            DataFrame: Hourly solar heat gains through windows in W/m2.
        """
        kv116 = 22  # Hardcoded in Hourly Simulation cell KV116
        df = get_air_free_temp_0m(spec=spec)
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


    def get_solar_heat_opaque(self) -> DataFrame:
        """Calculate the solar heat gains through opaque surfaces based on building specifications.
        ϕsol,op [Hourly Simulation column LR]

        Wattage is given by the sum of solar radiation on each opaque surface multiplied by its
        area and solar heat gain coefficient.
        Solar radiation is a function of climate data and building orientation.
        Horizontal solar radiation is also included because of roof surfaces.

        Args:
            spec (OpenBESSpecification): The building specifications spec data class.
        Returns:
            DataFrame: Hourly solar heat gains through opaque surfaces in W/m2.
        """
        raise NotImplementedError


    def get_solar_heat(self) -> DataFrame:
        """Calculate the solar heat gains based on building specifications.
        ϕsol [Hourly Simulation column AJ, KM]

        Wattage per square meter is given by the sum of solar heat gains through windows
        and opaque surfaces, divided by the conditioned floor area.

        Args:
            spec (OpenBESSpecification): The building specifications spec data class.
        Returns:
            DataFrame: Hourly solar heat gains in W/m2.
        """
        conditioned_floor_area = get_conditioned_floor_area(spec=spec)
        df = get_solar_heat_window(spec=spec).join(
            get_solar_heat_opaque(spec=spec)
        )
        df['solar_heat'] = (df['solar_heat_window'] + df['solar_heat_opaque']) / conditioned_floor_area
        return df[['solar_heat']]

    def get_temp_change_demand(self) -> float:
        """Calculate the temperature change demand based on building specifications.
        ϕHC,nd, W/m2
        Args:
            spec (OpenBESSpecification): The building specifications spec data class.
        Returns:
            float: The temperature change demand in W/m2.
        """
        raise NotImplementedError
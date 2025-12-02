from importlib.resources import files
from math import atan
from pathlib import Path
from typing import Tuple
from numpy import nan, select, outer, array, maximum, isnan
from pvlib.iotools import read_epw
from pandas import DataFrame, Series
import os

from .base import HourlySimulation
from .geometry import BuildingGeometry
from .lighting import LightingSimulation
from .occupancy import OccupationSimulation
from .solar_irradiation import SolarIrradiationSimulation
from .ventilation import VentilationSimulation
from ..types import OpenBESSpecification, TERRAINS, ORIENTATIONS

# Optional dependencies
try:
    import numba
    USE_JIT = True
except (ImportError, ModuleNotFoundError):
    numba = None
    USE_JIT = False
try:
    import line_profiler
    USE_PROFILER = os.environ.get('LINE_PROFILE', '0') == '1'
except (ImportError, ModuleNotFoundError):
    line_profiler = None
    USE_PROFILER = False

def jit_if_available(_fn=None, **jit_kwargs):
    def decorator(fn):
        if not USE_JIT:
            return fn
        return numba.jit(**jit_kwargs)(fn)
    return decorator if _fn is None else decorator(_fn)

def profile_if_available(_fn=None, **profile_kwargs):
    """Profile if line_profiler is installed and enabled via LINE_PROFILE=1 environment variable."""
    def decorator(fn):
        if not USE_PROFILER:
            return fn
        return line_profiler.profile(**profile_kwargs)(fn)
    return decorator if _fn is None else decorator(_fn)

def profile_or_jit(_fn=None, jit_kwargs: dict = None, profile_kwargs: dict = None):
    """
    Can't have both JIT and line profiler at the same time, so this decorator applies one or the other if available.
    """
    def decorator(fn):
        if USE_PROFILER:
            return line_profiler.profile(**profile_kwargs)(fn)
        elif USE_JIT:
            return numba.jit(**jit_kwargs)(fn)
        else:
            return fn
    return decorator if _fn is None else decorator(_fn)
    

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
    climate_data_dir = Path(str(files("openbes.simulations.climate_data")))
    return [
        f for f in os.listdir(climate_data_dir)
        if f.endswith('.epw')
    ]

@profile_or_jit(jit_kwargs={'nopython': True})
def _calculate_temperatures(
        prev_thermal_mass: float,
        Hc_nd: float,
        m: float,
        internal_heat_capacity_w: float,
        htr_1: float,
        htr_2: float,
        htr_3: float,
        Htr_em: float,
        dry_bulb_temp: float,
        Htr_is: float,
        Htr_ms: float,
        Htr_w: float,
        temp_st: float,
        internal_heat_adjusted: float,
        heat_transmission_by_ventilation: float,
        supply_air_temp: float,
):
    """Return a tuple of
    (m_tot, building_thermal_mass_t, internal_surface_temp, air_free_temp)
    for the given inputs.
    """
    m_tot = (
            m
            + Htr_em * dry_bulb_temp
            + htr_3 * (
                    temp_st +
                    Htr_w * dry_bulb_temp +
                    htr_1 * (
                            (internal_heat_adjusted + Hc_nd) / heat_transmission_by_ventilation +
                            supply_air_temp
                    )
            ) / htr_2
    )
    # Hourly variables are prev_thermal_mass, htr_3, m_tot
    building_thermal_mass_t = (
                                      prev_thermal_mass * (internal_heat_capacity_w - 0.5 * (htr_3 + Htr_em))
                                      + m_tot
                              ) / (internal_heat_capacity_w + 0.5 * (htr_3 + Htr_em))
    building_thermal_mass = (prev_thermal_mass + building_thermal_mass_t) / 2
    internal_surface_temp = (
                                    Htr_ms * building_thermal_mass
                                    + temp_st
                                    + Htr_w * dry_bulb_temp
                                    + htr_1
                                    * (
                                            supply_air_temp
                                            + (internal_heat_adjusted + Hc_nd)
                                            / heat_transmission_by_ventilation
                                    )
                            ) / (Htr_ms + Htr_w + htr_1)
    air_free_temp = (
                            Htr_is * internal_surface_temp
                            + heat_transmission_by_ventilation * supply_air_temp
                            + internal_heat_adjusted
                            + Hc_nd
                    ) / (Htr_is + heat_transmission_by_ventilation)
    return m_tot, building_thermal_mass_t, internal_surface_temp, air_free_temp

@profile_if_available
class ClimateSimulation(HourlySimulation):
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
    _theta_st_partial: float

    def __init__(
            self,
            spec: OpenBESSpecification,
            geometry: BuildingGeometry = None,
            occupancy: OccupationSimulation = None,
            lighting: LightingSimulation = None,
            ventilation: VentilationSimulation = None,
    ):
        """
        Unlike other simulations, ClimateSimulation's Hourly data depend on the previous hourly data.
        This means that the class must calculate all hourly data in sequence, not just on demand.

        Consequently, the entire simulation is run in the __init__ method, which may take some time.
        """
        super().__init__(spec=spec)
        self.geometry = geometry or BuildingGeometry(spec=spec)
        self.occupancy = occupancy or OccupationSimulation(spec=spec, geometry=self.geometry)
        self.lighting = lighting or LightingSimulation(spec=spec, occupancy=self.occupancy)
        self.ventilation = ventilation or VentilationSimulation(
            spec=spec, geometry=self.geometry, occupancy=self.occupancy
        )
        # Pre-calculate all hour-dependent values in sequence
        n = len(self._hours)
        results = []
        row = None
        self._cache = self._populate_cache()
        for i in range(n):
            row = self._calculate_hour_row(i=i, prev_row=row)
            results.append(row)
        results_df = DataFrame(results, index=self._hours.index)
        self._hours = self._hours.join(results_df)
        # clear cache
        del self._cache

    def _populate_cache(self) -> dict:
        """
        Calculate the static values used in hourly row calculation that do not depend on the hour index.
        """
        # Make sure min/max set points are calculated
        assert self.set_point_temperature is not None
        # Window mask
        compass_points = sorted([self.geometry.get_compass_point_for_orientation(o) for o in ORIENTATIONS])
        window_mask = self.geometry.window_areas.index.get_level_values('compass_point').isin(compass_points)
        # [Hourly simulation cells KY105:LF105]
        window_area = self.geometry.window_areas[window_mask].groupby('compass_point').sum()
        # Solar heat windows reduction precaculated for all rows
        view_factor = self.spec.parameters.view_factor_to_sky_facade  # KY80:LF80
        hr = 5 * 0.9  # [Hardcoded in KY81:LF81 via Inputs G230]
        delta_theta_er = 11  # [Hardcoded in KY82: ISO 13790, 11.4.6]
        solar_heat_windows_reduction = DataFrame(
            outer(self.rse.values, window_area),
            index=self.rse.index,
            columns=window_area.index
        ) * view_factor * self.spec.uvalue_window * hr * delta_theta_er
        # Solar g_gl precalculated for all rows [Hourly simulation cell KX]
        solar_altitude = self.solar_irradiation.solar_altitude
        solar_g_gl = (
                             (-0.000003 * solar_altitude**3 + 0.0002 * solar_altitude**2 - 0.0053 * solar_altitude + 0.9986) *
                             self.spec.window_gvalue
                     ) * (solar_altitude > 0) * (solar_altitude < 90)
        # Asol for summer and winter [Hourly simulation cells KY107:LF108]
        solar_a_sol_w_winter = (
                (self.spec.solar_external_shading_winter * self.spec.parameters.shading_correction_factor) *
                (1 - self.spec.window_frame_factor) *
                window_area
        )
        solar_a_sol_w_summer = (
                (self.spec.solar_external_shading_summer * self.spec.parameters.shading_correction_factor) *
                (1 - self.spec.window_frame_factor) *
                window_area
        )
        # Solar area differs for summer and winter because of shading
        solar_area_summer = DataFrame(
            outer(solar_g_gl.values, solar_a_sol_w_summer.values),
            index=solar_heat_windows_reduction.index,
            columns=solar_a_sol_w_summer.index
        ) * 0.9  # [Hardcoded in KY:LF]
        solar_area_winter = DataFrame(
            outer(solar_g_gl.values, solar_a_sol_w_winter.values),
            index=solar_heat_windows_reduction.index,
            columns=solar_a_sol_w_winter.index
        ) * 1.0  # [Hardcoded in KY100]
        solar_radiation = self.solar_irradiation.solar_irradiation[compass_points]
        # Occupancy
        is_occupied = self.occupancy.occupancy['is_occupied']

        static = {
            "infiltration": (
                    self.spec.leakage_air_flow_independent * self.spec.parameters.infiltration_correction_factor
            ),
            "heat_capacity_air": (
                    self.spec.parameters.density_of_air
                    * self.spec.parameters.specific_heat_of_air
                    / 3.6
            ),
            "solar_heat_windows_reduction": array(solar_heat_windows_reduction),
            "solar_area_summer": array(solar_area_summer),
            "solar_area_winter": array(solar_area_winter),
            "solar_radiation": array(solar_radiation),
            # [Hourly simulation AR94]
            "Htr_em": 1 / (
                    (1 / self.geometry.heat_transfer_rate_opaque) -  # [AR93]
                    (1 / self.geometry.heat_transfer_ms)  # [AM94]
            ),
            "internal_heat_capacity_w": self.internal_heat_capacity / 3600,  # J/K to W/K [Hourly simulation AM93]
            "mass_factor_scaled": (
                    self.geometry.heat_capacity_am /
                    4.5  # [A_at hardcoded as 4.5 in Hourly Simulation cell AM84]
            ),
            # Arrayify some Series for performance
            "min_temp": array(self.set_point_temperature['min_temp_set_point'].values),
            "max_temp": array(self.set_point_temperature['max_temp_set_point'].values),
            "month": array(self.epw_data['month'].values),
            "day": array(self.epw_data['day'].values),
            "hour": array(self.epw_data['hour'].values),
            "solar_altitude": array(self.solar_irradiation.solar_altitude.values),
            "dry_bulb_temp": array(self.dry_bulb_temp.values),
            "wind_speed": array(self.wind_speed.values),
            "ventilation_air_supply_rate": array(self.ventilation.air_supply_rate.values),
            "solar_heat_opaque": array(self.solar_heat_opaque.values),
            "internal_heat": array(self.internal_heat.values),
            "internal_heat_adjusted": array(self.internal_heat_adjusted.values),
            "supply_air_temp": array(self.supply_air_temp.values),
            "is_occupied": array(is_occupied),
        }
        return static

    def _calculate_hour_row(self, i: int, prev_row: dict = None) -> dict:
        """
        Calculate all hour-dependent values for a given hour index.
        Optionally takes the previous row as input for recursive dependencies.
        """

        # Optionally use prev_row for values at i-1
        def get_prev(key, default=nan):
            return prev_row[key] if prev_row else default

        # --- Calculate all hour-dependent values ---
        min_temp = self._cache['min_temp'][i]
        max_temp = self._cache['max_temp'][i]

        """
        1. Night ventilation enabled [Hourly simulation column JL]

        Night ventilation is active between June 1st and September 1st inclusive, between sunset and dawn,
        if the air free temperature is above the dry bulb temperature.
        """
        prev_air_free_temp = get_prev("air_free_temp", 0.0)
        month = self._cache["month"][i]
        day = self._cache["day"][i]
        solar_altitude = self._cache["solar_altitude"][i]
        dry_bulb_temp = self._cache["dry_bulb_temp"][i]
        prev_dry_bulb_temp = 0.0 if i == 0 else self._cache["dry_bulb_temp"][i - 1]
        night_ventilation_enabled = (
            # [1st September 1am is coded to allow ventilation at Hourly Simulation cell JK5950]
                ((6 <= month < 9) or (month == 9 and day == 1 and self._cache['hour'][i] == 1))
                and (solar_altitude < 0)
                and (prev_air_free_temp > prev_dry_bulb_temp)
        )

        """
        2. Air flow base [Hourly simulation column JO]
        """
        threshold = 24
        on_hours = prev_air_free_temp >= threshold
        night_ventilation = (
                on_hours * self.spec.natural_ventilation_night * night_ventilation_enabled
        )
        air_flow_base = on_hours * night_ventilation + self._cache['infiltration']

        """
        3. Air flow dependent [Hourly simulation column JH]
        """
        qv_diff = 0.0  # [Hardcoded as blank in Hourly simulation column IU]
        q4pa = max(self.spec.parameters.leakage_air_flow_dependent, 0.0001)  # JE97
        Hstack = 10  # [Hardcoded in JE101: ISO 15242:2007. 6.7.1]
        air_set_temp_prev = get_prev("air_set_temp", 20.0)
        temp_diff = abs(dry_bulb_temp - air_set_temp_prev)
        qv_stack = max(0.0146 * q4pa * (((0.7 * Hstack) * temp_diff)**0.667), 0.001)
        dcp = 0.75  # [Hardcoded in JE103]
        vsite_by_vmetro = TERRAIN_VSITE_BY_VMETRO[self.spec.terrain_class]  # JE104
        qv_wind = (
                0.0769
                * q4pa
                * (dcp * (vsite_by_vmetro * self._cache['wind_speed'][i])**2)**0.667
        )
        qv_sw = max(qv_stack, qv_wind) + (0.14 * qv_stack * qv_wind / q4pa)
        qv_infred = max(
            qv_sw,
            (
                    qv_stack * abs(qv_diff / 2)
                    + qv_wind * 2 * abs(qv_diff / 3) / (qv_stack + qv_wind)
            ),
        )
        air_flow_dependent = qv_diff + qv_infred

        """
        4. Air flow [Hourly simulation column JZ]
        """
        air_flow = (
                self._cache["ventilation_air_supply_rate"][i]
                + air_flow_dependent
                + air_flow_base
        )

        """
        5. Heat transmission by ventilation [Hourly Simulation column AL]
        """
        heat_transmission_by_ventilation = self._cache['heat_capacity_air'] * air_flow

        """
        6. Htr_1 [Hourly Simulation column AM]
        """
        htr_1 = 1 / (
                1 / heat_transmission_by_ventilation + 1 / self.geometry.heat_transfer_is
        )

        """
        7. Htr_2 [Hourly Simulation column AN]
        """
        htr_2 = htr_1 + self.geometry.heat_transfer_rate_windows

        """
        8. Htr_3 [Hourly Simulation column AO]
        """
        htr_3 = 1 / ((1 / htr_2) + (1 / self.geometry.heat_transfer_ms))

        """
        9. Solar heat windows [Hourly Simulation columns KY:LF]
        """
        kx116 = 22  # Hardcoded in Hourly Simulation cell KX116
        Fsh_ob_overhand = 1.0  # LF87 [Hardcoded via 0 in Inputs N108:U108]
        Fsh_ob_fin = 1.0  # LF90 [Hardcoded via 0 in Inputs N110:U110]
        Fsh_ob_horizon = 1.0  # LF93 [Hardcoded via 0 in Inputs N112:U112]
        solar_lost_through_windows = 0.0  # [Hardcoded in KY84]
        # LF95: ISO 13790, 11.4.4
        Fsh_ob_horizon = Fsh_ob_overhand * Fsh_ob_fin * Fsh_ob_horizon - solar_lost_through_windows
        solar_radiation = self._cache["solar_radiation"][i]
        if prev_air_free_temp < kx116:
            solar_area = self._cache["solar_area_winter"][i]
        else:
            solar_area = self._cache["solar_area_summer"][i]

        solar_heat_base = solar_area * solar_radiation
        solar_heat_windows = (
                (Fsh_ob_horizon * solar_heat_base) -
                self._cache['solar_heat_windows_reduction'][i]
        )
        solar_heat_windows = solar_heat_windows * (solar_heat_windows > 0.0)
        solar_heat_windows = solar_heat_windows.sum()

        """
        10. Solar heat [Hourly Simulation column AJ, KO]
        """
        solar_heat_opaque = self._cache['solar_heat_opaque'][i]
        conditioned_floor_area = self.geometry.conditioned_floor_area
        solar_heat = (solar_heat_windows + solar_heat_opaque) / conditioned_floor_area

        """
        11. m [Hourly Simulation column AR]
        """
        internal_heat = self._cache['internal_heat'][i]
        internal_heat_adjusted = self._cache['internal_heat_adjusted'][i]
        m = self._cache['mass_factor_scaled'] * (
                0.5 * internal_heat +
                (
                        (solar_heat_windows + solar_heat_opaque) /
                        conditioned_floor_area
                )
        )

        """
        12. temp_st [Hourly Simulation column AS]
        """
        temp_st = self.theta_st_partial * (
                0.5 * internal_heat + solar_heat
        )

        """
        13. m_tot [Hourly Simulation column AT]
        14. Building thermal mass, Building thermal mass@t [Hourly Simulation columns AW, AV]
        15. Internal surface temp [Hourly Simulation column AX]
        16. Air free temp [Hourly Simulation column AY]
        """
        # m_tot parameters
        supply_air_temp = self._cache['supply_air_temp'][i]
        Htr_is = self.geometry.heat_transfer_is
        Hc_nd = 0.0  # Heating/cooling need [Hardcoded in AR111]
        Htr_em = self._cache["Htr_em"]
        # building_thermal_mass parameters
        starting_thermal_mass = 17.4  # [Hardcoded in Hourly Simulation cell AV117]
        internal_heat_capacity_w = self._cache["internal_heat_capacity_w"]
        prev_thermal_mass = get_prev("building_thermal_mass_t", starting_thermal_mass)

        # semi-curry _calculate_temperatures function now all fixed parameters are known
        def calculate_temperatures(hc_need: float, prev_tm: float) -> Tuple[float, float, float, float]:
            """Returns (m_tot, building_thermal_mass_t, internal_surface_temp, air_free_temp)"""
            return _calculate_temperatures(
                Hc_nd=hc_need,
                prev_thermal_mass=prev_tm,
                m=m,
                dry_bulb_temp=dry_bulb_temp,
                htr_1=htr_1,
                htr_2=htr_2,
                htr_3=htr_3,
                temp_st=temp_st,
                internal_heat_adjusted=internal_heat_adjusted,
                heat_transmission_by_ventilation=heat_transmission_by_ventilation,
                supply_air_temp=supply_air_temp,
                Htr_em=Htr_em,
                Htr_is=Htr_is,
                Htr_ms=9.1 * self.geometry.heat_capacity_am,  # [Hardcoded in Hourly Simulation cell AR95]
                Htr_w=self.geometry.heat_transfer_rate_windows,
                internal_heat_capacity_w=internal_heat_capacity_w,
            )

        m_tot, building_thermal_mass_t, internal_surface_temp, air_free_temp = calculate_temperatures(
            hc_need=Hc_nd,
            prev_tm=prev_thermal_mass
        )
        building_thermal_mass = (prev_thermal_mass + building_thermal_mass_t) / 2

        """
        17. Air free temp with heating/cooling to meet set point, heating/cooling need = 0 [Hourly Simulation column BK]
        """
        # Air free temps HC_0 and HC_10 are single-hour forward simulations if heating is on/off.
        #  They use the simulated temperature for the previous hour from the full HC_actual model.
        prev_thermal_mass_hc_actual = get_prev('building_thermal_mass_hc_actual_t', starting_thermal_mass)
        _, _, _, air_free_temp_hc_0 = calculate_temperatures(hc_need=0.0, prev_tm=prev_thermal_mass_hc_actual)

        """
        18. Air set temp [Hourly Simulation column CE]
        """
        if air_free_temp_hc_0 < max_temp:
            air_set_temp = max_temp
        elif air_free_temp_hc_0 > min_temp:
            air_set_temp = min_temp
        else:
            air_set_temp = air_free_temp_hc_0

        """
        19. Air temp with heating/cooling need = 10W/m2 [Hourly Simulation column BY]
        """
        # [HC,nd hardcoded as 10 in cell BP114]
        _, _, _, air_free_temp_hc_10 = calculate_temperatures(hc_need=10.0, prev_tm=prev_thermal_mass_hc_actual)

        """
        20. Building thermal mass/@t with heating/cooling need = actual need [Hourly Simulation columns CR, CQ]
        21. Air temp with heating/cooling need = actual need [Hourly Simulation column CT]
        Note: The heating/cooling need is an interpretation of the Excel spreadsheet's winter/summer set point temps.
        22. Heating/cooling need [Hourly Simulation column DB]
        """
        # [Hourly simulation column CK]
        is_occupied = self._cache['is_occupied'][i]
        needs_heating = air_free_temp_hc_0 < max_temp
        needs_cooling = air_free_temp_hc_0 > min_temp
        if is_occupied and (needs_heating or needs_cooling):
            heating_cooling_demand = (
                    10 * (air_set_temp - air_free_temp_hc_0) / (air_free_temp_hc_10 - air_free_temp_hc_0)
            )
        else:
            heating_cooling_demand = 0.0
        _, building_thermal_mass_hc_actual_t, _, air_free_temp_hc_actual = calculate_temperatures(
            hc_need=heating_cooling_demand,
            prev_tm=prev_thermal_mass_hc_actual
        )

        building_thermal_mass_hc_actual = (prev_thermal_mass_hc_actual + building_thermal_mass_hc_actual_t) / 2

        # --- Return all calculated values as a dict ---
        values = {
            "night_ventilation_enabled": night_ventilation_enabled,
            "air_flow_dependent": air_flow_dependent,
            "air_flow": air_flow,
            "heat_transmission_by_ventilation": heat_transmission_by_ventilation,
            "htr_1": htr_1,
            "htr_2": htr_2,
            "htr_3": htr_3,
            "solar_heat_windows": solar_heat_windows,
            "solar_heat": solar_heat,
            "m": m,
            "temp_st": temp_st,
            "m_tot": m_tot,
            "building_thermal_mass": building_thermal_mass,
            "building_thermal_mass_t": building_thermal_mass_t,
            "internal_surface_temp": internal_surface_temp,
            "air_free_temp": air_free_temp,
            "air_set_temp": air_set_temp,
            "air_free_temp_hc_0": air_free_temp_hc_0,
            "air_free_temp_hc_10": air_free_temp_hc_10,
            "building_thermal_mass_hc_actual": building_thermal_mass_hc_actual,
            "building_thermal_mass_hc_actual_t": building_thermal_mass_hc_actual_t,
            "air_free_temp_hc_actual": air_free_temp_hc_actual,
            "heating_cooling_demand": heating_cooling_demand,
        }

        if i == 1 and any(isnan(v) for v in values.values()):
            raise ValueError(f"NaN values:\n{DataFrame([values])}")

        return values

    @property
    def set_point_temperature(self) -> DataFrame:
        """Set point temperatures for each hour of the year.

        DataFrame with columns ['min_temp_set_point', 'max_temp_set_point'] for each hour.

        The set point temperatures provide a minimum and maximum temperature for comfortable building occupation.
        This is given by specified target temperatures with an optional tolerance.
        """
        if 'min_temp_set_point' not in self._hours.columns or 'max_temp_set_point' not in self._hours.columns:
            tolerance = max(self.spec.parameters.temperature_tolerance or 0.0, 0.0)
            self._hours['max_temp_set_point'] = self._hours['is_daytime'].apply(
                lambda x: (self.spec.setpoint_winter_day - tolerance) if x else (self.spec.setpoint_winter_night - tolerance)
            )
            self._hours['min_temp_set_point'] = self._hours['is_daytime'].apply(
                lambda x: (self.spec.setpoint_summer_day + tolerance) if x else (self.spec.setpoint_summer_night + tolerance)
            )
        return self._hours[['min_temp_set_point', 'max_temp_set_point']]

    @property
    def epw_data(self) -> DataFrame:
        """DataFrame with EPW climate data for the specified location.
        """
        if not hasattr(self, '_epw_data') or self._epw_data is None:
            file_name = self.spec.meteorological_file
            path = Path(str(files("openbes.simulations.climate_data") / file_name))
            self._epw_data, self._epw_metadata = read_epw(path)
            self._hours['wind_speed'] = array(self._epw_data['wind_speed'])
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
    def htr_1(self) -> 'Series[float]':
        """Hourly heat transfer rate 1?????? in kW/K.
        Htr_1 [Hourly Simulation column AM]
        """
        return self._hours['htr_1']

    @property
    def htr_2(self) -> 'Series[float]':
        """Hourly heat transfer rate 2?????? in kW/K.
        Htr_2 [Hourly Simulation column AN]
        """
        return self._hours['htr_2']

    @property
    def htr_3(self) -> 'Series[float]':
        """Hourly heat transfer rate 3?????? in kW/K.
        Htr_3 [Hourly Simulation column AO]
        """
        return self._hours['htr_3']

    @property
    def internal_surface_temp(self) -> 'Series[float]':
        """Hourly internal surface temperature in degrees C.
        Ѳs [Hourly Simulation column AX]
        """
        return self._hours['internal_surface_temp']

    @property
    def theta_st_partial(self) -> float:
        """?????#
        Ѳst [Hourly simulation cell AR103]

        Eq. C.3 (partial)
        """
        if not hasattr(self, '_theta_st_partial') or self._theta_st_partial is None:
            A_at = 4.5  # [Hardcoded in Hourly Simulation cell AM84]
            self._theta_st_partial = (
                    1 -
                    (self.geometry.heat_capacity_am / A_at) -
                    (self.geometry.heat_transfer_rate_windows / (9.1 * A_at))
            )
        return self._theta_st_partial

    @property
    def temp_st(self) -> 'Series[float]':
        """Hourly temperature for ????? in degrees C.
        Ѳst [Hourly Simulation column AS]
        """
        return self._hours['temp_st']

    @property
    def internal_heat_capacity(self) -> float:
        """Calculate the internal heat capacity of the building in J/K.
        [Inputs cell C275]
        """
        return (
                self.spec.parameters.heat_capacity_correction_factor *
                self.geometry.heat_capacity_cm
        )

    @property
    def m(self) -> 'Series[float]':
        """Hourly m?????? in W/m2.
         Φm [Hourly Simulation column AR]
        """
        return self._hours['m']

    @property
    def m_tot(self) -> 'Series[float]':
        """Hourly m_tot?????? in W/m2.
        [Hourly Simulation column AT]
        """
        return self._hours['m_tot']

    @property
    def building_thermal_mass(self) -> 'Series[float]':
        """Hourly building thermal mass in degrees C.
        Ѳm [Hourly Simulation column AW]
        """
        return self._hours['building_thermal_mass']

    @property
    def building_thermal_mass_hc_actual(self) -> 'Series[float]':
        """Building thermal mass with heating/cooling need = actual need
        Ѳm [Hourly Simulation column CQ]
        """
        return self._hours['building_thermal_mass_hc_actual']

    @property
    def supply_air_temp(self) -> 'Series[float]':
        """Hourly supply air temperature in degrees C.
        Ѳsup = Te [Hourly simulation column AG]
        """
        if 'supply_air_temp' not in self._hours.columns:
            self._hours['supply_air_temp'] = array(self.epw_data['temp_air'])
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
                            atan(0.151977 * (row['relative_humidity'] + 8.313659)**0.5) + \
                            atan(row['temp_air'] + row['relative_humidity']) - \
                            atan(row['relative_humidity'] - 1.676331) + \
                            0.00391838 * (row['relative_humidity']**1.5) * atan(0.023101 * row['relative_humidity']) \
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
            self._hours['dry_bulb_temp'] = array(self.epw_data['temp_air'])
        return self._hours['dry_bulb_temp']

    @property
    def night_ventilation_enabled(self) -> 'Series[bool]':
        """Whether night ventilation is active for each hour of the year.
        [Hourly simulation column JL]

        Night ventilation is active between June 1st and August 31st inclusive, between sunset and dawn,
        if the air free temperature is above the dry bulb temperature.

        Note: The spreadsheet has night ventilation enabled on September 1st at 1am, which may be a mistake.
         We reproduce this behaviour here for consistency.
        """
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
            on_hours = self.air_free_temp >= threshold  # JM
            # [Hourly simulation column JM]
            night_ventilation = (
                    on_hours *
                    self.spec.natural_ventilation_night *
                    self.night_ventilation_enabled
            )
            self._hours['air_flow_base'] = on_hours * night_ventilation + infiltration
        return self._hours['air_flow_base']

    @property
    def air_set_temp(self) -> 'Series[float]':
        """Hourly air set temperature in degrees C.
        Ѳair,set [Hourly simulation column CE]

        This is the temperature that the heating/cooling systems will try to attain.
        """
        return self._hours['air_set_temp']

    @property
    def wind_speed(self) -> 'Series[float]':
        """Hourly wind speed in m/s.
        [Hourly simulation column W]
        """
        if 'wind_speed' not in self._hours.columns:
            self._hours['wind_speed'] = array(self.epw_data['wind_speed'])
        return self._hours['wind_speed']

    @property
    def air_flow_dependent(self) -> 'Series[float]':
        """Hourly air flow in m3/h/m2, dependent on other variables.
        qv,inf [Hourly simulation column JH]
        """
        return self._hours['air_flow_dependent']

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
            # Inputs cell C144, Table G.11 ISO 13790
            appliance_W_per_m2 = self.spec.appliances_load * self.spec.parameters.appliance_on_off
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
            ratio = array(self.lighting.lighting_ratio)
            heat = array(self.lighting.lighting_heat)
            parasitic = array(self.lighting.parasitic_heat)
            self._hours['internal_heat_from_lighting'] = (
                    (ratio * heat) + parasitic
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
        if "internal_heat_adjusted" not in self._hours.columns:
            adjustment_factor = 0.5  # Hardcoded in spreadsheet column AQ
            self._hours['internal_heat_adjusted'] = self.internal_heat * adjustment_factor
        return self._hours['internal_heat_adjusted']

    @property
    def air_free_temp(self) -> 'Series[float]':
        """Hourly air free temperature with no heating or cooling adjustments.
        Ѳair,0 [Hourly Simulation column AY]

        Calculated by considering:
        - Internal surface temperature and its heat transfer rate to air
        - Heat transmission by ventilation and supply air temperature
        - Internal heat gains (adjusted)
        - HC_nd (assumed to be 0)
        and dividing by the total heat transfer rates to air (from surfaces and ventilation).

        This produces a weighted sum of these temperature influences to estimate the air free temperature.
        """
        return self._hours['air_free_temp']

    @property
    def air_free_temp_hc_0(self) -> 'Series[float]':
        """Hourly air free temperature with heating/cooling adjustments set to 0W/m2.
        Ѳair,0 [Hourly Simulation column BK]
        """
        return self._hours['air_free_temp_hc_0']

    @property
    def air_free_temp_hc_10(self) -> 'Series[float]':
        """Hourly air free temperature with heating/cooling adjustments set to 10W/m2.
        Ѳair,10 [Hourly Simulation column BY]
        """
        return self._hours['air_free_temp_hc_10']

    @property
    def air_free_temp_hc_actual(self) -> 'Series[float]':
        """Hourly air free temperature with heating/cooling adjustments set to actual requirements in W/m2.
        Ѳair,ac [Hourly Simulation column CT]
        """
        return self._hours['air_free_temp_hc_actual']

    @property
    def theta_m(self) -> 'Series[float]':
        """Hourly building thermal mass in degrees C.
        Ѳm [Hourly Simulation column BI]
        """
        return self._hours['theta_m']

    @property
    def rse(self) -> 'Series[float]':
        """Hourly external surface thermal resistance in m2K/W.
        [Hourly simulation column KU]  ISO 6946
        """
        if 'rse' not in self._hours.columns:
            conditions = [
                self.wind_speed <= 1.5,
                (self.wind_speed > 1.5) & (self.wind_speed <= 2.5),
                (self.wind_speed > 2.5) & (self.wind_speed <= 3.5),
                (self.wind_speed > 3.5) & (self.wind_speed <= 4.5),
                (self.wind_speed > 4.5) & (self.wind_speed <= 6.0),
                (self.wind_speed > 6.0) & (self.wind_speed <= 8.5),
                self.wind_speed > 8.0,
                ]
            choices = [
                0.08,
                0.06,
                0.05,
                0.04,
                0.04,
                0.03,
                0.02,
            ]
            self._hours['rse'] = select(conditions, choices, default=0.02)
        return self._hours['rse']

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
        Fsh_ob_overhand = 1.0  # [Hardcoded in LK87:LR87 via Inputs C108:J108 = 0]
        # LR90 via Inputs C115:J115
        Fsh_ob_own = (
                (self.spec.building_length + self.spec.building_width) /
                (self.geometry.equivalent_rectangle.length + self.geometry.equivalent_rectangle.width)
        )
        Fsh_ob = Fsh_ob_overhand * Fsh_ob_own # LK95:LR95
        u_value = self.spec.uvalue_facade  # LK104:LR104
        opaque_area = row['opaque_area']  # LK105:LR105
        Rse = self.rse  # KU: ISO 6946
        return maximum(
            Fsh_ob *
            (absorption * Rse * opaque_area * u_value) *
            solar_radiation - (
                    view_factor * (Rse * u_value * opaque_area * hr * delta_theta_er)
            ),
            0.0
        )

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
        return self._hours['solar_heat']

    @property
    def heating_cooling_demand(self) -> 'Series[float]':
        """Hourly temperature change demand based in W.
        ϕHC,nd W [Hourly simulation column DB * zone area]

        Has columns for heating and cooling demand because they need to be weighted by their scaling factors.

        This is used for the ASHRAE140 test cases to determine the heating and cooling demand.
        """
        return self._hours['heating_cooling_demand']

    @property
    def heating_demand(self) -> 'Series[float]':
        """Hourly heating need in W/m2.
        Represents values from heating_cooling_demand clipped to only positive values.
        """
        if 'heating_need' not in self._hours.columns:
            self._hours['heating_need'] = self.heating_cooling_demand.clip(0, None)
        return self._hours['heating_need']

    @property
    def cooling_demand(self) -> 'Series[float]':
        """Hourly cooling need in W/m2.
        Represents values from heating_cooling_demand clipped to only negative values, then inverted.
        """
        if 'cooling_need' not in self._hours.columns:
            self._hours['cooling_need'] = self.heating_cooling_demand.clip(None, 0)
            self._hours['cooling_need'] = -self._hours['cooling_need']
        return self._hours['cooling_need']
import logging
from math import atan
from typing import List

import numpy as np
from pandas import Series

from .base import EnergyUseSimulation
from .climate import ClimateSimulation, RELATIVE_HUMIDITY
from .geometry import BuildingGeometry
from .lighting import LightingSimulation
from .occupancy import OccupationSimulation
from .ventilation import VentilationSimulation
from ..types import OpenBESSpecification, COOLING_SYSTEM_TYPES

logger = logging.getLogger(__name__)

MIN_COOLING_CAPACITY = 0.01  # kW
MIN_COOLING_EFFICIENCY = 0.01  # kWh


class CoolingSystemSimulation(EnergyUseSimulation):
    """A class to simulate a cooling system's energy consumption.

    [Cell references are for System 1]
    """
    system_number: int
    _nominal_consumption: float = None
    _nominal_capacity: float = None
    _sensible_nominal_capacity: float = None
    _efficiency: float = None
    _area: float = None
    _Ts_int: float = None
    _Th_int: float = None

    def __init__(
            self,
            spec: OpenBESSpecification,
            system_number: int = 1,
            climate: ClimateSimulation = None,
    ):
        super().__init__(spec)
        self.system_number = system_number
        self.climate = climate or ClimateSimulation(spec)
        self.geometry = climate.geometry
        self.occupancy = climate.occupancy

    def _attr(self, attr_name: str):
        return getattr(self.spec, f"cooling_system{self.system_number}_{attr_name}")

    @property
    def area(self) -> float:
        """Total area affected by cooling system in m2."""
        if self._area is None:
            areas = self.geometry.conditioned_floor_areas.groupby('zone').sum()
            simultaneity = [self._attr(f"simultaneity_factor_{z.value.split('_')[0]}") for z in areas.index]
            self._area = (areas * simultaneity).sum()
        return self._area

    @property
    def ratio(self) -> 'Series[float]':
        """Hourly proportion of total cooling capacity that is enabled.

        The system will typically be 100% enabled during occupied hours.
        """
        return self.occupancy.occupancy['is_occupied'].astype(float)

    def _get_target_temp(self) -> 'np.array[float]':
        """Get the target temperature for cooling based on thresholds and air temperature."""
        summer_temp = np.array(self.climate.set_point_temperature['min_temp_set_point'])
        winter_temp = np.array(self.climate.set_point_temperature['max_temp_set_point'])
        return np.where(
            self.climate.air_free_temp < winter_temp,
            winter_temp,
            np.where(
                self.climate.air_free_temp > summer_temp,
                summer_temp,
                self.climate.air_free_temp
            )
        )

    @property
    def phi_hc_nd_actual(self) -> 'Series[float]':
        """Cooling load per unit area in W/m2.
        [Hourly simulation column GW]

        The system is on when
        - the system is enabled (ratio > 0.0)
        - temperature > target temperature

        When on, the system operates at the capacity required to bring the temperature within tolerance.
        """
        if 'phi_hc_nd_actual' not in self._hours.columns:
            target_temp = self._get_target_temp()
            self._hours['phi_hc_nd_actual'] = (
                10 *
                (target_temp - self.climate.air_free_temp_hc_0) /
                (self.climate.air_free_temp_hc_10 - self.climate.air_free_temp_hc_0)
            ) * self.ratio * (target_temp < self.climate.air_free_temp)
        return self._hours['phi_hc_nd_actual']

    @property
    def phi_c_nd_ac(self) -> float:
        """Cooling load per unit area in W/m2.
        [Hourly simulation column GY]
        """
        if 'phi_c_nd_ac' not in self._hours.columns:
            self._hours['phi_c_nd_ac'] = self.phi_hc_nd_actual.apply(
                lambda r: min(r, 0.0) if r < (
                        getattr(self.spec.parameters, f"cooling_system{self.system_number}_min_demand") * -1
                ) else 0.0
            ) * self.spec.parameters.cooling_load_factor
        return self._hours['phi_c_nd_ac']

    @property
    def demand(self) -> 'Series[float]':
        """Hourly cooling demand in kW.
        [Hourly simulation column HA]
        """
        if 'demand' not in self._hours.columns:
            self._hours['demand'] = - (
                self.phi_c_nd_ac * self.area
            ) / 1000  # W -> kW
        return self._hours['demand']

    @property
    def Ts_int(self) -> float:
        """Internal set point temperature. ???????
        [HD102]
        """
        if self._Ts_int is None:
            self._Ts_int = self.spec.setpoint_summer_day - self.spec.parameters.temperature_tolerance
        return self._Ts_int

    @property
    def Th_int(self) -> float:
        """Internal heat temperature. ???????
        [HD101]
        """
        if self._Th_int is None:
            self._Th_int = (
                    self.Ts_int * atan(0.151977 * (RELATIVE_HUMIDITY + 8.313659)**0.5) +
                    atan(self.Ts_int + RELATIVE_HUMIDITY) -
                    atan(RELATIVE_HUMIDITY - 1.676331) +
                    0.00391838 * RELATIVE_HUMIDITY**1.5 * atan(0.023101 * RELATIVE_HUMIDITY) -
                    4.686035
            )
        return self._Th_int

    @property
    def fan_cooling_power(self) -> 'Series[float]':
        """Hourly fan cooling power (reference value).
        [Hourly simulation column HF, HN]
        """
        if 'fan_cooling_power' not in self._hours.columns:
            self._hours['fan_cooling_power'] = self.demand / self.cap_sen_ref
        return self._hours['fan_cooling_power']

    @property
    def cap_sen_ref(self) -> 'Series[float]':
        """Reference sensible cooling capacity. ???????
        [Hourly simulation column HH]
        """
        if 'cap_sen_ref' not in self._hours.columns:
            return self.sensible_nominal_capacity * self.cap_ref_t
        return self._hours['cap_sen_ref']

    @property
    def cap_ref_t(self) -> 'Series[float]':
        """Reference cooling capacity given the temperature difference. ???????
        [Hourly simulation column HI]
        """
        if 'cap_ref_t' not in self._hours.columns:
            self._hours['cap_ref_t'] = (
               0.500601825 -
               0.046438331 * self.Th_int -
               0.000324724 * (self.Th_int**2) +
               0.069957819 * self.Ts_int -
               0.0000342756 * (self.Ts_int**2) -
               0.013202081 * self.climate.dry_bulb_temp +
               0.0000793065 * (self.climate.dry_bulb_temp**2)
            )
        return self._hours['cap_ref_t']

    @property
    def con_ref_t(self) -> 'Series[float]':
        """Reference consumption given the temperature difference. ???????
        [Hourly simulation column HL]
        """
        if 'con_ref_t' not in self._hours.columns:
            self._hours['con_ref_t'] = (
               0.1117801 +
               0.028493334 * self.Th_int -
               0.000411156 * (self.Th_int**2) +
               0.021414276 * self.climate.dry_bulb_temp + 0.000161125 * (self.climate.dry_bulb_temp**2) -
               0.000679104 * self.climate.dry_bulb_temp * self.Th_int
            )
        return self._hours['con_ref_t']

    @property
    def con_ref_fcp(self) -> 'Series[float]':
        """Reference consumption fan cooling power. ????????
        [Hourly simulation column HM]
        """
        if 'con_ref_fcp' not in self._hours.columns:
            self._hours["con_ref_fcp"] = (
                0.2012307 -
                0.0312175 * self.fan_cooling_power +
                1.9504979 * (self.fan_cooling_power**2) -
                1.1205104 * (self.fan_cooling_power**3)
            )
        return self._hours['con_ref_fcp']

    @property
    def number(self) -> int:
        """Number of systems of this type installed.
        """
        return self._attr('number')

    @property
    def nominal_capacity(self) -> float:
        """
        """
        if self._nominal_capacity is None:
            self._nominal_capacity = max(self._attr('nominal_capacity'), MIN_COOLING_CAPACITY) * self.number
        return self._nominal_capacity

    @property
    def sensible_nominal_capacity(self) -> float:
        """Cooling system nominal sensible refrigeration capacity in kW.
        [Hourly simulation cell HD91]
        """
        if self._sensible_nominal_capacity is None:
            self._sensible_nominal_capacity = max(
                self._attr('sensible_nominal_capacity'),
                MIN_COOLING_CAPACITY
            ) * self.number
        return self._sensible_nominal_capacity

    @property
    def efficiency(self) -> float:
        """
        """
        if self._efficiency is None:
            # NB: Typo in 'energy_efficifiency_ratio' is in the original spec
            self._efficiency = max(self._attr('energy_efficifiency_ratio'), MIN_COOLING_EFFICIENCY)
        return self._efficiency
    
    @property
    def nominal_consumption(self) -> float:
        """Cooling system nominal refrigeration consumption in kWh.
        [Hourly simulation cell HD92]
        """
        if self._nominal_consumption is None:
            self._nominal_consumption = self.nominal_capacity / self.efficiency
        return self._nominal_consumption


    @property
    def energy_use(self) -> 'Series[float]':
        """Cooling system energy use in kWh for each hour of the year for each ENERGY_SOURCES.
        [Hourly outputs column Q, disaggregated; Hourly simulation column HK]
        """
        if self._energy_use[self._attr('energy_source')].hasnans:
            self._energy_use = self._energy_use.fillna(0.0).infer_objects(copy=False)
            if self._attr('type') == COOLING_SYSTEM_TYPES.Heat_pump:
                self._energy_use[self._attr('energy_source')] = (
                        (self.demand != 0.0) * self.con_ref_t * self.con_ref_fcp * self.nominal_consumption
                )
        return self._energy_use


class CoolingSimulation(EnergyUseSimulation):
    """A class to simulate cooling energy consumption based on building specifications."""
    cooling_simulations: List[CoolingSystemSimulation]

    def __init__(
            self,
            spec: OpenBESSpecification,
            geometry: BuildingGeometry = None,
            occupancy: OccupationSimulation = None,
            lighting: LightingSimulation = None,
            ventilation: VentilationSimulation = None,
            climate: ClimateSimulation = None,
    ):
        super().__init__(spec)
        geometry = geometry or BuildingGeometry(self.spec)
        occupancy = occupancy or OccupationSimulation(self.spec, geometry=geometry)
        lighting = lighting or LightingSimulation(self.spec, occupancy=occupancy)
        ventilation = ventilation or VentilationSimulation(self.spec, occupancy=occupancy, geometry=geometry)
        self.climate_simulation = climate or ClimateSimulation(
            spec,
            geometry=geometry,
            occupancy=occupancy,
            lighting=lighting,
            ventilation=ventilation,
        )
        self.cooling_simulations = []
        while True:
            system_number = len(self.cooling_simulations) + 1
            attr_name = f"cooling_system{system_number}_type"
            if not hasattr(spec, attr_name):
                break
            self.cooling_simulations.append(
                CoolingSystemSimulation(
                    spec=spec,
                    system_number=system_number,
                    climate=self.climate_simulation
                )
            )
    
    @property
    def energy_use(self) -> 'Series[float]':
        """Cooling energy use in kWh for each hour of the year for each ENERGY_SOURCES.
        [Hourly outputs column Q], disaggregated
        """
        return sum([x.energy_use for x in self.cooling_simulations])

import logging
from typing import List

import numpy as np
from pandas import Series

from .base import EnergyUseSimulation
from .climate import ClimateSimulation
from .geometry import BuildingGeometry
from .lighting import LightingSimulation
from .occupancy import OccupationSimulation
from .ventilation import VentilationSimulation
from ..types import (
    OpenBESSpecification,
    HEATING_SYSTEM_TYPES,
)

logger = logging.getLogger(__name__)

MIN_HEATING_CAPACITY = 0.01  # [Hardcoded in Inputs cell F287]
MAX_HEATING_CAPACITY_LIMIT = 1.5  # [Hardcoded in Hourly Simulation cell ES114]

class HeatingSystemSimulation(EnergyUseSimulation):
    """A class to simulate a heating system's energy consumption.

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
        return getattr(self.spec, f"heating_system{self.system_number}_{attr_name}")

    @property
    def area(self) -> float:
        """Total area affected by heating system in m2."""
        if self._area is None:
            areas = self.geometry.conditioned_floor_areas.groupby('zone').sum()
            simultaneity = [self._attr(f"simultaneity_factor_{z.value.split('_')[0]}") for z in areas.index]
            self._area = (areas * simultaneity).sum()
        return self._area

    @property
    def ratio(self) -> 'Series[float]':
        """Hourly proportion of total heating capacity that is enabled.

        The system will typically be 100% enabled during occupied hours.
        """
        return self.occupancy.occupancy['is_occupied'].astype(float)

    def _get_target_temp(self) -> 'np.array[float]':
        """Get the target temperature for heating based on thresholds and air temperature."""
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
        """Heating load per unit area in W/m2.
        [Hourly simulation column EO]

        The system is on when
        - the system is enabled (ratio > 0.0)
        - temperature < target temperature

        When on, the system operates at the capacity required to bring the temperature within tolerance.
        """
        if 'phi_hc_nd_actual' not in self._hours.columns:
            target_temp = self._get_target_temp()
            self._hours['phi_hc_nd_actual'] = (
                                                      10 *
                                                      (target_temp - self.climate.air_free_temp_hc_0) /
                                                      (self.climate.air_free_temp_hc_10 - self.climate.air_free_temp_hc_0)
                                              ) * self.ratio * (target_temp > self.climate.air_free_temp)
        return self._hours['phi_hc_nd_actual']

    @property
    def phi_h_nd_ac(self) -> float:
        """Heating load per unit area in W/m2.
        [Hourly simulation column EP]
        """
        if 'phi_h_nd_ac' not in self._hours.columns:
            self._hours['phi_h_nd_ac'] = self.phi_hc_nd_actual.apply(
                lambda r: max(r, 0.0) if r > getattr(
                    self.spec.parameters,
                    f"heating_system{self.system_number}_min_demand"
                ) else 0.0
            ) * self.spec.parameters.heating_load_factor
        return self._hours['phi_h_nd_ac']

    @property
    def demand(self) -> 'Series[float]':
        """Hourly heating demand in kW.
        [Hourly simulation column HA]
        """
        if 'demand' not in self._hours.columns:
            self._hours['demand'] = (self.phi_h_nd_ac * self.area) / 1000  # W -> kW
            self._hours['demand'] = self._hours['demand'].clip(upper=MAX_HEATING_CAPACITY_LIMIT * self.capacity)
        return self._hours['demand']

    @property
    def capacity(self):
        """Heating system capacity in kW.
        [Hourly simulation cell EY92]
        """
        return self.nominal_capacity * 1  # [1 is the capacity factor, hardcoded in EY93]

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
            self._nominal_capacity = max(self._attr('nominal_capacity'), MIN_HEATING_CAPACITY) * self.number
        return self._nominal_capacity

    @property
    def ren_fcp_potential(self) -> 'Series[float]':
        """Part-load efficiency factor for heating system. ??????
        [Hourly simulation column EY]
        """
        if 'ren_fcp_potential' not in self._hours.columns:
            f1 = 1.0914  # [Hardcoded in Hourly simulation cell EY102]
            f2 = -0.0914  # [Hardcoded in Hourly simulation cell EY103]
            self._hours['ren_fcp_potential'] = (
                    (self.demand > 0.0) *
                    f1 + f2 * self.fcp_p
            )
        return self._hours['ren_fcp_potential']

    @property
    def Rend(self) -> 'Series[float]':
        """Efficiency of the heating system.
        [Hourly simulation column EZ]
        """
        if 'Rend' not in self._hours.columns:
            ren_T = 1.0  # [Hardcoded in Hourly simulation cell EY96]
            ren_fcp_t = 1.0  # [Hardcoded in Hourly simulation cell EY98]
            self._hours['Rend'] = (
                    self._attr('efficiency_cop') *
                    ren_T *
                    self.ren_fcp_potential *
                    ren_fcp_t
            )
        return self._hours['Rend']

    @property
    def fcp_p(self) -> 'Series[float]':
        """Part-load factor for heating system. ??????
        [Hourly simulation column EX]
        """
        if 'fcp_p' not in self._hours.columns:
            self._hours['fcp_p'] = self.demand / self.capacity
        return self._hours['fcp_p']

    @property
    def cons_nom_calef(self) -> 'Series[float]':
        """Nominal consumption for heating in kW.
        [Hourly simulation cell FG93]
        """
        return self.nominal_capacity / self._attr('efficiency_cop')

    @property
    def con_cal_t(self) -> 'Series[float]':
        """Temperature-dependent consumption. ??????
        [Hourly simulation column FJ]
        """
        if 'con_cal_t' not in self._hours.columns:
            self._hours['con_cal_t'] = (
                    1.201222828 -
                    0.040063338 * self.climate.wet_bulb_temp +
                    0.0010877 * self.climate.wet_bulb_temp ** 2
            )
        return self._hours['con_cal_t']

    @property
    def con_cal_fcp(self) -> 'Series[float]':
        """Part-load factor for heating system. ??????
        [Hourly simulation column FK]
        """
        if 'con_cal_fcp' not in self._hours.columns:
            self._hours['con_cal_fcp'] = (
                    0.08565215 +
                    0.93881371 * self.fcp_cal -
                    0.1834361 * self.fcp_cal ** 2 +
                    0.15897022 * self.fcp_cal ** 3
            )
        return self._hours['con_cal_fcp']

    @property
    def fcp_cal(self) -> 'Series[float]':
        """Part-load factor for heating system. ??????
        [Hourly simulation column FL]
        """
        if 'fcp_cal' not in self._hours.columns:
            self._hours['fcp_cal'] = self.demand / self.nominal_capacity
        return self._hours['fcp_cal']

    @property
    def energy_use(self) -> 'Series[float]':
        """Heating system energy use in kWh for each hour of the year for each ENERGY_SOURCES.
        [Hourly outputs column P, disaggregated]
        """
        if self._energy_use[self._attr('energy_source')].hasnans:
            self._energy_use = self._energy_use.fillna(0.0).infer_objects(copy=False)
            # Radiators [Hourly simulation column EU]
            if self._attr('type') == HEATING_SYSTEM_TYPES.Electric_heating_radiators:
                # Excel divides demand by nominal capacity in Hourly simulation column EV
                #  Then multiplies again in column EU. These cancel out.
                energy_use = self.demand
            elif self._attr('type') == HEATING_SYSTEM_TYPES.Heat_pump:
                # Heat pump [Hourly simulation column FI]
                energy_use = (self.demand > 0.0) * (
                        self.cons_nom_calef * self.con_cal_t * self.con_cal_fcp
                )
            else:
                # Boilers [Hourly simulation column FB]
                energy_use = (self.Rend != 0.0) * (self.demand / self.Rend)
            self._energy_use[self._attr('energy_source')] = energy_use
        return self._energy_use

class HeatingSimulation(EnergyUseSimulation):
    """A class to simulate heating energy consumption based on building specifications."""
    heating_simulations: List[HeatingSystemSimulation]

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
        self.heating_simulations = []
        while True:
            system_number = len(self.heating_simulations) + 1
            attr_name = f"heating_system{system_number}_type"
            if not hasattr(spec, attr_name):
                break
            self.heating_simulations.append(
                HeatingSystemSimulation(
                    spec=spec,
                    system_number=system_number,
                    climate=self.climate_simulation
                )
            )

    @property
    def energy_use(self) -> 'Series[float]':
        """Heating energy use in kWh for each hour of the year for each ENERGY_SOURCES.
        [Hourly outputs column P], disaggregated
        """
        return sum([x.energy_use for x in self.heating_simulations])
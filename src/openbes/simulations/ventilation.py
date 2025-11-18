from typing import List

from pandas import Series
import logging
from pandas import DataFrame

from .base import EnergyUseSimulation
from .geometry import BuildingGeometry
from .occupancy import OccupationSimulation
from ..types import OpenBESSpecification

logger = logging.getLogger(__name__)

class VentilationSystemSimulation(EnergyUseSimulation):
    system_number: int
    geometry: BuildingGeometry
    _air_supply_rate_adjusted: float

    def __init__(
            self,
            spec: OpenBESSpecification,
            system_number: int = 1,
            occupancy: OccupationSimulation = None,
            geometry: BuildingGeometry = None
    ):
        super().__init__(spec=spec)
        self.system_number = system_number
        self.geometry = geometry or BuildingGeometry(spec=self.spec)
        self.occupancy = occupancy or OccupationSimulation(spec=spec)

    def _attr(self, attr_name: str):
        return getattr(self.spec, f"ventilation_system{self.system_number}_{attr_name}")

    @property
    def air_supply_rate_adjusted(self) -> float:
        """Air supply rate (m3/h/m2) adjusted for system efficiency.
        [Hourly simulation cells IV99, JB99]
        """
        if not hasattr(self, '_air_supply_rate_adjusted') or self._air_supply_rate_adjusted is None:
            rated_flow_rate = self._attr('airflow') / self._attr('ventilated_area')  # m3/h/m2
            efficiency = self._attr('heat_recovery_efficiency')
            if rated_flow_rate is None or efficiency is None:
                self._air_supply_rate_adjusted = 0.0
            else:
                self._air_supply_rate_adjusted = rated_flow_rate * (1 - efficiency)
        return self._air_supply_rate_adjusted

    @property
    def ventilation_on(self) -> 'Series[bool]':
        """Hourly ventilation status (on/off) throughout the year.
        [Hourly simulation columns IR, IX]

        Ventilation only runs between the specified on and off times,
        and only while the building is occupied.
        """
        if 'ventilation_on' not in self._hours.columns:
            on_time = self._attr('on_time')
            off_time = self._attr('off_time')
            self._hours['ventilation_on'] = list(
                map(lambda x: on_time <= x <= off_time, self._hours.index.get_level_values('hour').values)
            )
            self._hours['ventilation_on'] = self._hours['ventilation_on'] * self.occupancy.occupancy['is_occupied']
        return self._hours['ventilation_on']

    @property
    def air_supply_rate(self) -> 'Series[float]':
        """Hourly air supply rate (m3/h/m2) throughout the year.
        [Hourly simulation columns IV, JB]
        """
        if 'air_supply_rate' not in self._hours.columns:
            area = self.geometry.conditioned_floor_area
            rated_flow_rate = self.air_supply_rate_adjusted * self._attr('ventilated_area')
            if rated_flow_rate is None or area == 0:
                self._hours['air_supply_rate'] = 0.0
            else:
                self._hours['air_supply_rate'] = (
                        (rated_flow_rate / area) *
                        self.ventilation_on.astype(float)
                )
        return self._hours['air_supply_rate']

    @property
    def energy_use(self) -> DataFrame:
        """Ventilation energy use in kWh for each hour of the year for each ENERGY_SOURCE.
        """
        if self._energy_use[self._attr('energy_source')].hasnans:
            self._energy_use[self._attr('energy_source')] = (
                self.ventilation_on.astype(float) * self._attr('rated_input_power')
            )
        return self._energy_use


class VentilationSimulation(EnergyUseSimulation):
    ventilation_simulations: List[VentilationSystemSimulation]

    def __init__(
            self,
            spec: OpenBESSpecification,
            occupancy: OccupationSimulation = None,
            geometry: BuildingGeometry = None
    ):
        super().__init__(spec=spec)
        self.geometry = geometry or BuildingGeometry(spec=self.spec)
        self.occupancy = occupancy or OccupationSimulation(spec=self.spec, geometry=self.geometry)
        self.ventilation_simulations = []
        while True:
            system_number = len(self.ventilation_simulations) + 1
            if not hasattr(spec, f"ventilation_system{system_number}_rated_input_power"):
                break
            self.ventilation_simulations.append(
                VentilationSystemSimulation(
                    spec=spec,
                    system_number=system_number,
                    occupancy=self.occupancy,
                    geometry=self.geometry
                )
            )

    @property
    def air_supply_rate(self) -> 'Series[float]':
        """Total hourly air supply rate (m3/h/m2) from all ventilation systems.
        [Hourly simulation column JA]
        """
        if 'air_supply_rate' not in self._hours.columns:
            total_air_supply = Series([0.0] * len(self._hours), index=self._hours.index)
            for sim in self.ventilation_simulations:
                total_air_supply += sim.air_supply_rate
            self._hours['air_supply_rate'] = total_air_supply
        return self._hours['air_supply_rate']

    @property
    def energy_use(self) -> 'Series[float]':
        """Ventilation energy use in kWh for each hour of the year for each ENERGY_SOURCES.
        """
        return sum([x.energy_use for x in self.ventilation_simulations])
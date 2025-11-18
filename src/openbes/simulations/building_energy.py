import logging
from typing import Dict

from pandas import DataFrame

from .base import EnergyUseSimulation
from .climate import ClimateSimulation
from .cooling import CoolingSimulation
from .geometry import BuildingGeometry
from .heating import HeatingSimulation
from .hot_water import HotWaterSimulation
from .lighting import LightingSimulation
from .occupancy import OccupationSimulation
from .ventilation import VentilationSimulation
from ..types import (
    OpenBESSpecification,
    ENERGY_USE_CATEGORIES,
    ENERGY_SOURCES,
)

logger = logging.getLogger(__name__)

class BuildingEnergySimulation(EnergyUseSimulation):
    """
    A building energy simulation takes a building specification and model parameters and produces a report
    on the energy use of the building.
    """

    def __init__(
            self,
            spec: OpenBESSpecification,
            hot_water: HotWaterSimulation = None,
            geometry: BuildingGeometry = None,
            occupancy: OccupationSimulation = None,
            lighting: LightingSimulation = None,
            ventilation: VentilationSimulation = None,
            climate: ClimateSimulation = None,
            cooling: CoolingSimulation = None,
            heating: HeatingSimulation = None,
    ):
        super().__init__(spec)
        self._standby_energy_use = self._energy_use.copy()
        self._standby_energy_use[ENERGY_SOURCES.Electricity] = (spec.building_standby_load * 12) / len(self._energy_use)
        self._other_energy_use = self._energy_use.copy()
        self._other_energy_use[ENERGY_SOURCES.Electricity] = (spec.other_electricity_usage * 12) / len(self._energy_use)
        self._other_energy_use[ENERGY_SOURCES.Natural_gas] = (spec.other_gas_usage * 12) / len(self._energy_use)
        self.hot_water = hot_water or HotWaterSimulation(self.spec)
        self.geometry = geometry or BuildingGeometry(self.spec)
        self.occupancy = occupancy or OccupationSimulation(self.spec, geometry=self.geometry)
        self.lighting = lighting or LightingSimulation(self.spec, occupancy=self.occupancy)
        self.ventilation = ventilation or VentilationSimulation(
            self.spec,
            occupancy=self.occupancy,
            geometry=self.geometry
        )
        self.climate = climate or ClimateSimulation(
            spec,
            geometry=self.geometry,
            occupancy=self.occupancy,
            lighting=self.lighting,
            ventilation=self.ventilation,
        )
        self.cooling = cooling or CoolingSimulation(
            spec,
            geometry=self.geometry,
            occupancy=self.occupancy,
            lighting=self.lighting,
            ventilation=self.ventilation,
            climate=self.climate,
        )
        self.heating = heating or HeatingSimulation(
            spec,
            geometry=self.geometry,
            occupancy=self.occupancy,
            lighting=self.lighting,
            ventilation=self.ventilation,
            climate=self.climate,
        )

    @property
    def energy_use_by_category(self) -> Dict[ENERGY_USE_CATEGORIES, DataFrame]:
        """Heating energy use in kWh for each hour of the year for each ENERGY_SOURCE for each ENERGY_USE_CATEGORY.
        """
        return {
                ENERGY_USE_CATEGORIES.Others: self._other_energy_use,
                ENERGY_USE_CATEGORIES.Building_standby: self._standby_energy_use,
                ENERGY_USE_CATEGORIES.Lighting: self.lighting.energy_use,
                ENERGY_USE_CATEGORIES.Hot_water: self.hot_water.energy_use,
                ENERGY_USE_CATEGORIES.Ventilation: self.ventilation.energy_use,
                ENERGY_USE_CATEGORIES.Cooling: self.cooling.energy_use,
                ENERGY_USE_CATEGORIES.Heating: self.heating.energy_use,
            }

    @property
    def energy_use(self) -> DataFrame:
        """Total energy use in kWh for each hour of the year for each ENERGY_SOURCE.
        """
        if self._energy_use.isna().any().any():
            self._energy_use.fillna(0, inplace=True)
            for category_use in self.energy_use_by_category.values():
                self._energy_use = self._energy_use.add(category_use, fill_value=0.0)
        return self._energy_use
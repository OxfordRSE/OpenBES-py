import logging
from importlib.resources import files
from typing import Dict

from numpy import logical_and
from pandas import DataFrame, read_csv, Series, MultiIndex
from pydantic import BaseModel, ConfigDict

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

class OpenBESReport(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)
    primary_energy_consumption: DataFrame
    final_energy_consumption_distribution: DataFrame
    space_heating_demand: DataFrame
    space_cooling_demand: DataFrame
    passive_survivability: DataFrame

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

    @property
    def building_name(self) -> str:
        return self.spec.building_name if self.spec.building_name not in ["", None] else "This building"

    @property
    def per_FEC_coefficients(self) -> DataFrame:
        coefficients_df = read_csv(str(files('openbes.simulations.report_data') / "per_FEC_coefficients.csv"))
        coefficients_df = coefficients_df.loc[coefficients_df['Country'] == self.spec.country.value]
        coefficients_df = coefficients_df.set_index(['Energy source'])
        return coefficients_df

    @property
    def primary_energy_consumption(self) -> DataFrame:
        """Primary energy consumption in kWh/m2.

        [BES Report Table N8:Q15]
        """
        energy_use = self.energy_use.sum()
        energy_use.index = [s.value for s in energy_use.index]
        pec_coefficients = self.per_FEC_coefficients['PEC/kWh FEC'].copy()
        pec_gross = pec_coefficients * energy_use
        # Special case for electricity to accommodate generation:
        pec_gross[ENERGY_SOURCES.Electricity.value] = pec_coefficients[ENERGY_SOURCES.Electricity.value] * (
                energy_use[ENERGY_SOURCES.Electricity.value] - self.spec.energy_generated
        ) + self.spec.energy_generated

        pec_nr_coefficients = self.per_FEC_coefficients['PECnr/kWh FEC'].copy()
        pec_nr_gross = pec_nr_coefficients * energy_use
        # Again, electricity is a special case
        pec_nr_gross[ENERGY_SOURCES.Electricity.value] = pec_nr_coefficients[ENERGY_SOURCES.Electricity.value] * (
                energy_use[ENERGY_SOURCES.Electricity.value] - self.spec.energy_generated
        )

        area = self.geometry.conditioned_floor_area
        pec_net = pec_gross / area
        total_pec = sum(pec_net)
        pec_nr = sum(pec_nr_gross / area)
        pec_r = total_pec - pec_nr
        return DataFrame({
            "Non-renewable": [pec_nr, 40, 15, 0, 0],
            "Renewable": [pec_r, 45, 45, 45, 30],
            "Total PEC": [total_pec, 85, 60, 45, 30]
        }, index=Series([
            self.building_name,
            "Recommended nZEB",
            "Passivhaus -Classic",
            "Passivhaus -Plus",
            "Passivhaus -Premium"
        ], name="Building"))

    @property
    def final_energy_consumption_distribution(self) -> DataFrame:
        """Final energy consumption in kWh (gross) and kWh/m2 (by area).

        [BES Report Table N21:P30]
        """
        gross = Series({
            "Heating": self.heating.energy_use.sum().sum(),
            "Cooling": self.cooling.energy_use.sum().sum(),
            "Ventilation": self.ventilation.energy_use.sum().sum(),
            "Hot water": self.hot_water.energy_use.sum().sum(),
            "Lighting": self.lighting.energy_use.sum().sum(),
            "Building background": self._standby_energy_use.sum().sum(),
            "Others": self._other_energy_use.sum().sum(),
        })
        df = DataFrame()
        df['kWh'] = gross
        df['kWh/m2'] = gross/self.geometry.conditioned_floor_area
        return df

    @property
    def space_hvac_demand(self) -> DataFrame:
        """Energy required to heat and cool the building to required temperatures.

        [BES Report Tables N36:Q45]

        These values are not guaranteed to match up with total Heating/Cooling demand,
        because they're scaled by the usage for each zone.

        :returns MultiIndexed DataFrame by Heating/Cooling and case/Passivehaus standard
            with columns for Demand (kWh/m2), Peak (kW), and Peak ratio (W/m2)
        """
        out = DataFrame(
            columns=["Demand (kWh/m2)", "Peak (kW)", "Peak ratio (W/m2)"],
            index=MultiIndex.from_arrays(
                [
                    ["Heating", "Cooling", "Heating", "Cooling"],
                    [self.building_name, self.building_name, "Passivehaus standard", "Passivehaus standard"]
                ],
                names=["Dimension", "Building"]
            )
        )
        out.loc[('Heating', 'Passivehaus standard')] = ["<15", None, "<10"]
        out.loc[('Cooling', 'Passivehaus standard')] = ["<15", None, "<10"]
        zonal_occupancy = self.occupancy.occupancy[['is_occupied']].copy()
        heating_demand = 0
        cooling_demand = 0
        areas = self.geometry.conditioned_floor_areas.copy()
        areas = areas.reset_index()
        for zz in self.geometry.conditioned_floor_areas.index.get_level_values('zone'):
            z = zz.value
            if z == "common_areas":
                z = "common"
            area = areas.loc[areas['zone'] == zz, 'conditioned_floor_area'].sum()
            try:
                opens = getattr(self.spec, f"occupancy_open_{z}") or 24
                closes = getattr(self.spec, f"occupancy_close_{z}") or 0
            except AttributeError:
                opens = getattr(self.spec.parameters, f"occupancy_open_{z}") or 24
                closes = getattr(self.spec.parameters, f"occupancy_close_{z}") or 0
            z_open = [x for x in map(
                lambda x: opens <= x <= closes,
                zonal_occupancy.index.get_level_values("hour")
            )]
            zonal_occupancy[z] = logical_and(zonal_occupancy['is_occupied'], z_open)
            zonal_demand = (
                self.climate.heating_cooling_demand * self.geometry.conditioned_floor_area / 1000  # W/m2 -> kW
                / area  # kW -> kW/m2 for zone
                * zonal_occupancy[z]  # only when zone is occupied
            )
            h = zonal_demand.clip(0).sum()
            c = (zonal_demand * -1).clip(0).sum()
            heating_demand += h
            cooling_demand += c

        peak_heating_demand = max(self.climate.heating_demand * self.geometry.conditioned_floor_area / 1000)
        peak_cooling_demand = max(self.climate.cooling_demand * self.geometry.conditioned_floor_area / 1000)

        out.loc[('Heating', self.building_name)] = [
            heating_demand,
            peak_heating_demand,
            peak_heating_demand / self.geometry.conditioned_floor_area
        ]
        out.loc[('Cooling', self.building_name)] = [
            cooling_demand,
            peak_cooling_demand,
            peak_cooling_demand / self.geometry.conditioned_floor_area
        ]
        return out


    @property
    def passive_survivability(self) -> DataFrame:
        """The proportion of the time the building is in an acceptable comfort range if HVAC is not running."""
        return DataFrame()


    @property
    def report(self) -> OpenBESReport:
        """The BES report for this simulation.
        """
        return OpenBESReport(
            primary_energy_consumption=self.primary_energy_consumption,
            final_energy_consumption_distribution=self.final_energy_consumption_distribution,
            space_heating_demand=self.space_hvac_demand.loc['Heating'],
            space_cooling_demand=self.space_hvac_demand.loc['Cooling'],
            passive_survivability=self.passive_survivability,
        )
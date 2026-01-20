from .. import logging
from copy import deepcopy
from datetime import datetime, UTC
from importlib.metadata import metadata
from importlib.resources import files
from typing import Dict, Optional

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
from ..logging import LogPrefix
from ..schemas import OpenBESCase, OpenBESOutput, OpenBESMetaData
from ..types import (
    OpenBESSpecification,
    ENERGY_USE_CATEGORIES,
    ENERGY_SOURCES,
    get_zone_number,
    LIGHTING_CONTROL,
    HEATING_SYSTEM_TYPES,
)

logger = logging.getLogger(__name__)


class OpenBESReport(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)
    primary_energy_consumption: DataFrame
    final_energy_consumption_distribution: DataFrame
    space_heating_demand: DataFrame
    space_cooling_demand: DataFrame
    passive_survivability: Series


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
        log_prefix: str = "",
        parent_log: Optional[list[str]] = None,
    ):
        super().__init__(spec)

        self.log_prefix = log_prefix
        self.log: list[str] = parent_log or []
        if parent_log is None:
            logging.bind(self.log, base_prefix=log_prefix)

        self._retrofit_report: Optional[DataFrame] = None
        self._full_case_report: Optional[OpenBESCase] = None
        self._timestamp: Optional[str] = None
        self._standby_energy_use = self._energy_use.copy()
        self._standby_energy_use[ENERGY_SOURCES.Electricity] = (
            spec.building_standby_load * 12
        ) / len(self._energy_use)
        self._other_energy_use = self._energy_use.copy()
        self._other_energy_use[ENERGY_SOURCES.Electricity] = (
            spec.other_electricity_usage * 12
        ) / len(self._energy_use)
        self._other_energy_use[ENERGY_SOURCES.Natural_gas] = (
            spec.other_gas_usage * 12
        ) / len(self._energy_use)
        self.hot_water = hot_water or HotWaterSimulation(self.spec)
        self.geometry = geometry or BuildingGeometry(self.spec)
        self.occupancy = occupancy or OccupationSimulation(
            self.spec, geometry=self.geometry
        )
        self.lighting = lighting or LightingSimulation(
            self.spec, occupancy=self.occupancy
        )
        self.ventilation = ventilation or VentilationSimulation(
            self.spec, occupancy=self.occupancy, geometry=self.geometry
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
        logger.info("Building energy simulation initialized.")

    @property
    def energy_use_by_category(self) -> Dict[ENERGY_USE_CATEGORIES, DataFrame]:
        """Heating energy use in kWh for each hour of the year for each ENERGY_SOURCE for each ENERGY_USE_CATEGORY."""
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
        """Total energy use in kWh for each hour of the year for each ENERGY_SOURCE."""
        if self._energy_use.isna().any().any():
            self._energy_use.fillna(0, inplace=True)
            for category_use in self.energy_use_by_category.values():
                self._energy_use = self._energy_use.add(category_use, fill_value=0.0)
        return self._energy_use

    @property
    def building_name(self) -> str:
        return (
            self.spec.building_name
            if self.spec.building_name not in ["", None]
            else "This building"
        )

    @property
    def per_FEC_coefficients(self) -> DataFrame:
        coefficients_df = read_csv(
            str(files("openbes.simulations.report_data") / "per_FEC_coefficients.csv")
        )
        coefficients_df = coefficients_df.loc[
            coefficients_df["Country"] == self.spec.country.value
        ]
        coefficients_df = coefficients_df.set_index(["Energy source"])
        return coefficients_df

    @property
    def primary_energy_consumption(self) -> DataFrame:
        """Primary energy consumption in kWh/m2.

        [BES Report Table N8:Q15]
        """
        energy_use = self.energy_use.sum()
        energy_use.index = [s.value for s in energy_use.index]
        pec_coefficients = self.per_FEC_coefficients["PEC/kWh FEC"].copy()
        pec_gross = pec_coefficients * energy_use
        # Special case for electricity to accommodate generation:
        pec_gross[ENERGY_SOURCES.Electricity.value] = (
            pec_coefficients[ENERGY_SOURCES.Electricity.value]
            * (
                energy_use[ENERGY_SOURCES.Electricity.value]
                - self.spec.energy_generated
            )
            + self.spec.energy_generated
        )

        pec_nr_coefficients = self.per_FEC_coefficients["PECnr/kWh FEC"].copy()
        pec_nr_gross = pec_nr_coefficients * energy_use
        # Again, electricity is a special case
        pec_nr_gross[ENERGY_SOURCES.Electricity.value] = pec_nr_coefficients[
            ENERGY_SOURCES.Electricity.value
        ] * (energy_use[ENERGY_SOURCES.Electricity.value] - self.spec.energy_generated)

        area = self.geometry.conditioned_floor_area
        pec_net = pec_gross / area
        total_pec = sum(pec_net)
        pec_nr = sum(pec_nr_gross / area)
        pec_r = total_pec - pec_nr
        return DataFrame(
            {
                "Non-renewable": [pec_nr, 40, 15, 0, 0],
                "Renewable": [pec_r, 45, 45, 45, 30],
                "Total PEC": [total_pec, 85, 60, 45, 30],
            },
            index=Series(
                [
                    self.building_name,
                    "Recommended nZEB",
                    "Passivhaus -Classic",
                    "Passivhaus -Plus",
                    "Passivhaus -Premium",
                ],
                name="Building",
            ),
        )

    @property
    def final_energy_consumption_distribution(self) -> DataFrame:
        """Final energy consumption in kWh (gross) and kWh/m2 (by area).

        [BES Report Table N21:P30]
        """
        gross = Series(
            {
                "Heating": self.heating.energy_use.sum().sum(),
                "Cooling": self.cooling.energy_use.sum().sum(),
                "Ventilation": self.ventilation.energy_use.sum().sum(),
                "Hot water": self.hot_water.energy_use.sum().sum(),
                "Lighting": self.lighting.energy_use.sum().sum(),
                "Building background": self._standby_energy_use.sum().sum(),
                "Others": self._other_energy_use.sum().sum(),
            }
        )
        df = DataFrame()
        df["kWh"] = gross
        df["kWh/m2"] = gross / self.geometry.conditioned_floor_area
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
                    [
                        self.building_name,
                        self.building_name,
                        "Passivehaus standard",
                        "Passivehaus standard",
                    ],
                ],
                names=["Dimension", "Building"],
            ),
        )
        out.loc[("Heating", "Passivehaus standard")] = ["<15", None, "<10"]
        out.loc[("Cooling", "Passivehaus standard")] = ["<15", None, "<10"]
        zonal_occupancy = self.occupancy.occupancy[["is_occupied"]].copy()
        heating_demand = Series(name="Heating")
        cooling_demand = Series(name="Cooling")
        areas = self.geometry.conditioned_floor_areas.copy()
        areas = areas.reset_index()
        for zz in self.geometry.conditioned_floor_areas.index.get_level_values("zone"):
            z = zz.value
            if not getattr(self.spec, f"condition_z{get_zone_number(zz)}"):
                continue

            area = areas.loc[areas["zone"] == zz, "conditioned_floor_area"].sum()

            if z not in ["common_areas", "other"]:
                # common and other inherit from office; see below
                opens = getattr(self.spec, f"occupancy_open_{z}") or 24
                closes = getattr(self.spec, f"occupancy_close_{z}") or 0
                z_open = [
                    x
                    for x in map(
                        lambda x: opens <= x <= closes,
                        zonal_occupancy.index.get_level_values("hour"),
                    )
                ]
                zonal_occupancy[z] = logical_and(zonal_occupancy["is_occupied"], z_open)
                occupancy = zonal_occupancy[z]
            else:
                # Excel uses the Office occupancy for calculating common conditioning
                # [DX/DY inherit from DC/DD]
                occupancy = zonal_occupancy["office"]

            raw_demand = (
                self.climate.heating_cooling_demand * occupancy
            )  # need HVAC when zone is occupied; W/m2
            zonal_demand = (
                raw_demand
                / 1000  # W/m2 -> kW/m2
                * area  # kW/m2 -> kW for zone
            )
            heating_demand[zz] = zonal_demand.clip(0).sum()
            cooling_demand[zz] = (zonal_demand * -1).clip(0).sum()

        peak_heating_demand = max(
            self.climate.heating_demand * self.geometry.conditioned_floor_area / 1000
        )
        peak_cooling_demand = max(
            self.climate.cooling_demand * self.geometry.conditioned_floor_area / 1000
        )

        out.loc[("Heating", self.building_name)] = [
            heating_demand.sum() / self.geometry.conditioned_floor_area,
            peak_heating_demand,
            peak_heating_demand / self.geometry.conditioned_floor_area * 1000,
        ]
        out.loc[("Cooling", self.building_name)] = [
            cooling_demand.sum() / self.geometry.conditioned_floor_area,
            peak_cooling_demand,
            peak_cooling_demand / self.geometry.conditioned_floor_area * 1000,
        ]
        return out

    @property
    def passive_survivability(self) -> Series:
        """The proportion of the time the building is in an acceptable comfort range if HVAC is not running.

        Acceptable comfort range means the temperature is < 26C. [Hardcoded in Inputs cell J212]

        The proportion is discomfort hours / occupied hours.
        """
        mask = self.climate.air_free_temp.index.get_level_values("month").isin(
            [6, 7, 8]
        )
        occupation = self.occupancy.occupancy.loc[mask, "is_occupied"]
        temp = self.climate.air_free_temp.loc[mask]
        temp_gt_26 = (temp * occupation) >= 26.0
        return Series(
            {
                self.building_name: temp_gt_26.sum() / occupation.sum(),
                "Passivehaus > 26C": "<0.10",
            },
            name="Passive survivability",
        )

    @property
    def report(self) -> OpenBESReport:
        """The BES report for this simulation."""
        return OpenBESReport(
            primary_energy_consumption=self.primary_energy_consumption,
            final_energy_consumption_distribution=self.final_energy_consumption_distribution,
            space_heating_demand=self.space_hvac_demand.loc["Heating"],
            space_cooling_demand=self.space_hvac_demand.loc["Cooling"],
            passive_survivability=self.passive_survivability,
        )

    @property
    def kg_co2_eq(self) -> Series:
        """Kilograms C02 equivalent emissions."""
        energy_use = self.energy_use.sum()
        energy_use.index = [s.value for s in energy_use.index]
        pec_coefficients = self.per_FEC_coefficients["kgCO2/kWh FEC"].copy()
        return pec_coefficients * energy_use

    def sim_to_retrofit_report(self, name: str) -> Series:
        """Output a simulation as a retrofit report row."""
        return Series(
            {
                "Summer discomfort hours (%)": self.passive_survivability[
                    self.building_name
                ]
                * 100,
                "Peak heating load (kW)": (
                    self.climate.heating_demand
                    * self.geometry.conditioned_floor_area
                    / 1000
                ).quantile(0.996),
                "Peak cooling load (kW)": (
                    self.climate.cooling_demand
                    * self.geometry.conditioned_floor_area
                    / 1000
                ).quantile(0.996),
                "Annual heating demand (kWh/m2)": self.report.space_heating_demand.loc[
                    self.building_name, "Demand (kWh/m2)"
                ],
                "Annual cooling demand (kWh/m2)": self.report.space_cooling_demand.loc[
                    self.building_name, "Demand (kWh/m2)"
                ],
                "Final energy consumption (kWh/m2)": self.report.final_energy_consumption_distribution[
                    "kWh/m2"
                ].sum(),
                "Non-renewable primary energy consumption (kWh/m2)": self.report.primary_energy_consumption.loc[
                    self.building_name, "Non-renewable"
                ].sum(),
                "CO2 equivalent emissions kg CO2 eq/m2": self.kg_co2_eq.sum()
                / self.geometry.conditioned_floor_area,
            },
            name=name,
        )

    @property
    def retrofit_report(self) -> DataFrame:
        """Retrofit suggestions and their simulated impact."""
        if self._retrofit_report is None:
            simulations = [self.sim_to_retrofit_report("baseline")]
            combined_spec = deepcopy(self.spec)
            prefix = (self.log_prefix if hasattr(self, "log_prefix") else "") + "  "
            if self.spec.setpoint_winter_day >= 19.0:
                new_spec = deepcopy(self.spec)
                new_spec.setpoint_winter_day = self.spec.setpoint_winter_day - 1.0
                combined_spec.setpoint_winter_day = new_spec.setpoint_winter_day
                logger.info("SUBSIMULATION: Reducing winter setpoint by 1C")
                with LogPrefix("[-1C]"):
                    simulations.append(
                        BuildingEnergySimulation(
                            spec=new_spec, parent_log=self.log, log_prefix=prefix
                        ).sim_to_retrofit_report(
                            f"Reduce winter setpoint from {self.spec.setpoint_winter_day} to {new_spec.setpoint_winter_day}"
                        )
                    )
            if self.spec.lighting_control != LIGHTING_CONTROL.Automatic:
                new_spec = deepcopy(self.spec)
                new_spec.lighting_control = LIGHTING_CONTROL.Automatic
                combined_spec.lighting_control = new_spec.lighting_control
                logger.info("SUBSIMULATION: Smart lighting controls")
                with LogPrefix("[Light]"):
                    simulations.append(
                        BuildingEnergySimulation(
                            spec=new_spec, parent_log=self.log, log_prefix=prefix
                        ).sim_to_retrofit_report("Smart lighting controls")
                    )
            if self.spec.uvalue_window > 1:
                new_spec = deepcopy(self.spec)
                new_spec.uvalue_window = 0.9
                combined_spec.uvalue_window = new_spec.uvalue_window
                logger.info("SUBSIMULATION: Triple-glazed windows with PVC frames")
                with LogPrefix("[3galze]"):
                    simulations.append(
                        BuildingEnergySimulation(
                            spec=new_spec, parent_log=self.log, log_prefix=prefix
                        ).sim_to_retrofit_report(
                            "Triple-galzed windows with PVC frames"
                        )
                    )
            if self.spec.uvalue_roof > 0.5:
                new_spec = deepcopy(self.spec)
                new_spec.uvalue_roof = 0.5
                combined_spec.uvalue_roof = new_spec.uvalue_roof
                logger.info("SUBSIMULATION: Insulate roof to 0.5W/m2 K")
                with LogPrefix("[Roof]"):
                    simulations.append(
                        BuildingEnergySimulation(
                            spec=new_spec, parent_log=self.log, log_prefix=prefix
                        ).sim_to_retrofit_report("Insulate roof to 0.5W/m2 K")
                    )
            if self.spec.heating_system1_type != HEATING_SYSTEM_TYPES.Heat_pump:
                new_spec = deepcopy(self.spec)
                new_spec.heating_system1_type = HEATING_SYSTEM_TYPES.Heat_pump
                new_spec.heating_system1_energy_source = ENERGY_SOURCES.Electricity
                new_spec.heating_system1_efficiency_cop = 3.0
                combined_spec.heating_system1_type = new_spec.heating_system1_type
                combined_spec.heating_system1_energy_source = (
                    new_spec.heating_system1_energy_source
                )
                combined_spec.heating_system1_efficiency_cop = (
                    new_spec.heating_system1_efficiency_cop
                )
                logger.info("SUBSIMULATION: Replace heating with Heat pump")
                with LogPrefix("[Heatpump"):
                    simulations.append(
                        BuildingEnergySimulation(
                            spec=new_spec, parent_log=self.log, log_prefix=prefix
                        ).sim_to_retrofit_report(
                            f"Replace {self.spec.heating_system1_type} heating with Heat pump"
                        )
                    )

            if len(simulations) > 2:
                logger.info("SUBSIMULATION: All suggestions combined")
                with LogPrefix("[All]"):
                    simulations.append(
                        BuildingEnergySimulation(
                            spec=combined_spec, parent_log=self.log, log_prefix=prefix
                        ).sim_to_retrofit_report("Implement all suggestions")
                    )

            out = DataFrame(simulations)
            baseline_fec = out.loc["baseline", "Final energy consumption (kWh/m2)"]
            out["Energy savings (%)"] = (
                (baseline_fec - out["Final energy consumption (kWh/m2)"])
                / baseline_fec
                * 100
            )
            self._retrofit_report = out
        return self._retrofit_report

    def get_outputs(self, include_subsimulations: bool = True) -> OpenBESOutput:
        return OpenBESOutput()

    @property
    def timestamp(self) -> str:
        """Timestamp of the simulation in ISO 8601 format."""
        if self._timestamp is None:
            self._timestamp = datetime.now(UTC).isoformat()
            logger.info(f"Simulation timestamp: {self._timestamp}")
        return self._timestamp

    def generate_case_report(self, include_subsimulations: bool = True) -> OpenBESCase:
        """Generate a case report for this simulation, optionally including subsimulations.

        :param include_subsimulations: Whether to include subsimulations in the report.
        :returns: A OpenBESCase report.
        """
        if self._full_case_report is None:
            self._full_case_report = OpenBESCase(
                inputs=self.spec,
                outputs=self.get_outputs(include_subsimulations=include_subsimulations),
                meta=OpenBESMetaData(
                    version=metadata("openbes")["Version"], timestamp=self.timestamp
                ),
                log=self.log,
            )
        return self._full_case_report

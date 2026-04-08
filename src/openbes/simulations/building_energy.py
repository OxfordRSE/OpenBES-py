import numpy as np

from .. import logging
from copy import deepcopy
from datetime import datetime, UTC
from importlib.metadata import metadata
from importlib.resources import files
from typing import Dict, Optional, List, Any, TypeVar, Type

from pandas import DataFrame, read_csv, Series, MultiIndex, concat, Index
from pydantic import BaseModel, ConfigDict

from .base import EnergyUseSimulation, HOURS_DF, SimulationError
from .thermal import ThermalSimulation, specs_require_thermal_rerun, reset_thermal_cache
from .location import LocationSimulation
from .cooling import CoolingSimulation, CoolingSystemSimulation
from .geometry import BuildingGeometry
from .heating import HeatingSimulation, HeatingSystemSimulation
from .hot_water import HotWaterSimulation
from .lighting import LightingSimulation
from .occupancy import OccupationSimulation
from .reporting import output_precision, to_output_csv
from .ventilation import VentilationSimulation
from ..logging import LogPrefix
from ..schemas import (
    BuildingEnergySimulationOutput,
    ThermalSimulationOutput,
    CoolingSimulationOutput,
    CustomFECCoefficients,
    FECCoefficients,
    GeometrySimulationOutput,
    HeatingSimulationOutput,
    HotWaterSimulationOutput,
    LightingSimulationOutput,
    LocationSimulationOutput,
    OpenBESCase,
    OpenBESOutput,
    OpenBESMetaData,
    HourPeak,
    SpaceThermalDemandResult,
    ThermalSystemResult,
    VentilationSimulationOutput,
    ModelValidation,
)
from ..types import (
    OpenBESSpecification,
    ENERGY_USE_CATEGORIES,
    ENERGY_SOURCES,
    LIGHTING_CONTROL,
    HEATING_SYSTEM_TYPES,
    COMPASS_POINTS,
)

logger = logging.getLogger(__name__)


def day_of_the_month(d: int, m: int) -> int:
    first_day_of_the_month = HOURS_DF.index.get_locs([m, slice(None), 1])[0]
    return (d - HOURS_DF.index.get_level_values("day")[first_day_of_the_month]) + 1


class OpenBESReport(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)
    primary_energy_consumption: Optional[DataFrame]
    final_energy_consumption_distribution: Optional[DataFrame]
    space_heating_demand: Optional[DataFrame]
    space_cooling_demand: Optional[DataFrame]
    passive_survivability: Optional[Series]


class BuildingEnergySimulationError(SimulationError):
    """Raised when building-level output generation fails."""


class BuildingEnergySimulation(EnergyUseSimulation):
    """
    A building energy simulation takes a building specification and model parameters and produces a report
    on the energy use of the building.

    The simulation is composed of several sub-simulations for different aspects of the building's energy use:
    - Geometry
    - Occupancy
    - Solar Radiation
    - Ventilation
    - Lighting
    - Hot Water
    - Thermal
    - Heating
    - Cooling

    Some simulations depend up on others, meaing they can be executed in the following order:
    0: Geometry, Occupancy, Solar Radiation
    1: Ventilation, Lighting, Hot Water
    2: Thermal
    3: Heating, Cooling

    For a full relationship diagram, see `./simulation_dag_full.png` in the repository.

    The Thermal Simulation takes almost all of the computational time, and is run immediately upon instantiation
    of the class.

    Because of the aggressive caching of results, simulations should be considered immutable.
    Do not try to update a simulation with a new specification, instead create a new simulation with the updated spec.

    Example usage:
    ```python
    from openbes import BuildingEnergySimulation, OpenBESSpecification
    spec = OpenBESSpecification.from_toml("path_to_my_spec.toml")
    sim = BuildingEnergySimulation(spec)  # run the simulation (takes a second or so)
    report = sim.report()  # generate the report (instantaneous after the initial simulation)

    # We can also inspect various Pandas Series/DataFrames for more detailed analysis:
    sim.thermal.air_free_temp  # hourly internal temperature without HVAC

    # If necessary, we can dig in to the internals of a simulation:
    sim.thermal._hours  # the full hourly DataFrame used for thermal calculations
    ```
    """

    _required_inputs = ()
    _required_inputs_error_cls = BuildingEnergySimulationError

    # TypeVar for factory return type
    _T = TypeVar("_T")

    @staticmethod
    def _build_simulation(
        name: str, simulation_cls: Type[_T], *args: Any, **kwargs: Any
    ) -> Optional[_T]:
        """Build a simulation instance, returning None if dependencies are unavailable or instantiation fails.

        Args:
            name: Human-readable name of the simulation for logging
            simulation_cls: The simulation class to instantiate
            *args: Positional arguments to pass to the simulation class
            **kwargs: Keyword arguments to pass to the simulation class

        Returns:
            An instance of simulation_cls, or None if initialization failed
        """
        # kwargs are other simulations; if they're None then skip initialization
        for key, value in kwargs.items():
            if value is None:
                logger.warning(
                    f"{name} simulation skipped because {key} simulation failed to initialize."
                )
                return None
        try:
            return simulation_cls(*args, **kwargs)
        except Exception as exc:
            logger.warning(f"{name} simulation failed: {exc}")
            return None

    def _initialize_simuations(self, include_thermal=True):
        """Initialize all simulations, with the option to skip thermal (and therefore heating/cooling) for faster execution during testing."""
        self.hot_water = self.hot_water or self._build_simulation(
            "hot water", HotWaterSimulation, self.spec
        )
        self.geometry = self.geometry or self._build_simulation(
            "geometry", BuildingGeometry, self.spec
        )
        self.occupancy = self.occupancy or self._build_simulation(
            "occupancy", OccupationSimulation, self.spec, geometry=self.geometry
        )
        self.lighting = self.lighting or self._build_simulation(
            "lighting", LightingSimulation, self.spec, occupancy=self.occupancy
        )
        self.ventilation = self.ventilation or self._build_simulation(
            "ventilation",
            VentilationSimulation,
            self.spec,
            occupancy=self.occupancy,
            geometry=self.geometry,
        )
        self.location = self.location or self._build_simulation(
            "location", LocationSimulation, self.spec
        )
        if include_thermal:
            self.thermal = self.thermal or self._build_simulation(
                "thermal",
                ThermalSimulation,
                self.spec,
                geometry=self.geometry,
                occupancy=self.occupancy,
                lighting=self.lighting,
                ventilation=self.ventilation,
                location=self.location,
            )
        self.cooling = self.cooling or self._build_simulation(
            "cooling",
            CoolingSimulation,
            self.spec,
            geometry=self.geometry,
            occupancy=self.occupancy,
            lighting=self.lighting,
            ventilation=self.ventilation,
            thermal=self.thermal,
        )
        self.heating = self.heating or self._build_simulation(
            "heating",
            HeatingSimulation,
            self.spec,
            geometry=self.geometry,
            occupancy=self.occupancy,
            lighting=self.lighting,
            ventilation=self.ventilation,
            thermal=self.thermal,
        )

    def __init__(
        self,
        spec: OpenBESSpecification | dict[str, Any] | None = None,
        hot_water: HotWaterSimulation = None,
        geometry: BuildingGeometry = None,
        occupancy: OccupationSimulation = None,
        lighting: LightingSimulation = None,
        ventilation: VentilationSimulation = None,
        location: LocationSimulation = None,
        thermal: ThermalSimulation = None,
        cooling: CoolingSimulation = None,
        heating: HeatingSimulation = None,
        log_prefix: str = "",
        parent_log: Optional[list[str]] = None,
    ):
        if spec is None:
            spec = OpenBESSpecification()
        elif isinstance(spec, dict):
            spec = OpenBESSpecification.from_toml(spec)
        super().__init__(spec)
        self.log_prefix = log_prefix
        self.log: list[str] = parent_log or []
        if parent_log is None:
            logging.bind(self.log, base_prefix=log_prefix)

        self._mdh_index_: Optional[MultiIndex] = None
        self._outputs: Optional[OpenBESOutput] = None
        self._retrofit_report: Optional[DataFrame] = None
        self._full_case_report: Optional[OpenBESCase] = None
        self._timestamp: Optional[str] = None
        self._standby_energy_use = self._energy_use.copy()
        self._standby_energy_use[ENERGY_SOURCES.Electricity] = (
            self.spec.building_standby_load * 12 / len(self._energy_use)
        )
        self._other_energy_use = self._energy_use.copy()
        self._other_energy_use[ENERGY_SOURCES.Electricity] = (
            self.spec.other_electricity_usage * 12 / len(self._energy_use)
        )
        self._other_energy_use[ENERGY_SOURCES.Natural_gas] = (
            self.spec.other_gas_usage * 12 / len(self._energy_use)
        )

        self.hot_water = hot_water
        self.geometry = geometry
        self.occupancy = occupancy
        self.lighting = lighting
        self.ventilation = ventilation
        self.location = location
        self.thermal = thermal
        self.cooling = cooling
        self.heating = heating
        self._initialize_simuations()
        logger.info("Building energy simulation initialized.")

    def _extract_energy_use(self, key: str) -> DataFrame:
        """Extract energy use for a given category, returning a DataFrame with columns for each ENERGY_SOURCE."""
        if getattr(self, key) is None:
            return self._energy_use.copy().fillna(0)
        return getattr(self, key).energy_use

    @property
    def energy_use_by_category(self) -> Dict[ENERGY_USE_CATEGORIES, DataFrame]:
        """Heating energy use in kWh for each hour of the year for each ENERGY_SOURCE for each ENERGY_USE_CATEGORY."""
        return {
            ENERGY_USE_CATEGORIES.Others: self._other_energy_use,
            ENERGY_USE_CATEGORIES.Building_standby: self._standby_energy_use,
            ENERGY_USE_CATEGORIES.Lighting: self._extract_energy_use("lighting"),
            ENERGY_USE_CATEGORIES.Hot_water: self._extract_energy_use("hot_water"),
            ENERGY_USE_CATEGORIES.Ventilation: self._extract_energy_use("ventilation"),
            ENERGY_USE_CATEGORIES.Cooling: self._extract_energy_use("cooling"),
            ENERGY_USE_CATEGORIES.Heating: self._extract_energy_use("heating"),
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
    def epw_file_checksum(self) -> str:
        return self.location.epw_file_checksum

    @property
    def per_FEC_coefficients(self) -> DataFrame:
        coefficients_df = read_csv(
            str(files("openbes.simulations.report_data") / "per_FEC_coefficients.csv")
        )

        fec_spec = getattr(self.spec, "fec_coefficients", None)

        # Unwrap RootModel wrapper produced by oneOf codegen
        if isinstance(fec_spec, FECCoefficients):
            fec_spec = fec_spec.root

        if isinstance(fec_spec, CustomFECCoefficients):
            # Start from "Other" defaults then overlay any explicitly provided values
            base_df = coefficients_df.loc[
                coefficients_df["Country"] == "Other"
            ].set_index("Energy source")
            # Map Python attribute names back to the energy-source strings used as the index
            field_to_source = {
                "Electricity": "Electricity",
                "Diesel": "Diesel",
                "LPG": "LPG",
                "Natural_gas": "Natural gas",
                "Biomass": "Biomass",
                "Pellets": "Pellets",
            }
            col_map = {
                "PEC_per_kWh_FEC": "PEC/kWh FEC",
                "PECnr_per_kWh_FEC": "PECnr/kWh FEC",
                "kgCO2_per_kWh_FEC": "kgCO2/kWh FEC",
            }
            for attr, source in field_to_source.items():
                row_override: Optional[object] = getattr(fec_spec, attr, None)
                if row_override is not None:
                    for model_col, csv_col in col_map.items():
                        value = getattr(row_override, model_col, None)
                        if value is not None:
                            base_df.at[source, csv_col] = value
            return base_df
        else:
            # fec_spec is either a SUPPORTED_COUNTRIES string/enum, a legacy plain
            # string from spec.country, or None (fall back to "Other").
            if fec_spec is not None:
                country = getattr(fec_spec, "value", fec_spec)
            else:
                # Backward-compat: fall back to legacy `country` field
                legacy_country = getattr(self.spec, "country", None)
                country = (
                    getattr(legacy_country, "value", legacy_country)
                    if legacy_country is not None
                    else "Other"
                )
            coefficients_df = coefficients_df.loc[coefficients_df["Country"] == country]
            coefficients_df = coefficients_df.set_index(["Energy source"])
            return coefficients_df

    @property
    def primary_energy_consumption(self) -> Optional[DataFrame]:
        """Primary energy consumption in kWh/m2.

        [BES Report Table N8:Q15]
        """
        try:
            area = self.geometry.conditioned_floor_area
        except AttributeError:
            return None

        energy_use = self.energy_use.sum()
        energy_use.index = [s.value for s in energy_use.index]
        pec_coefficients = self.per_FEC_coefficients["PEC/kWh FEC"].copy()
        pec_gross = pec_coefficients * energy_use
        # Special case for electricity to accommodate generation:
        energy_generated = (
            self.spec.energy_generated
            if self.spec.energy_generated is not None
            else 0.0
        )
        pec_gross[ENERGY_SOURCES.Electricity.value] = (
            pec_coefficients[ENERGY_SOURCES.Electricity.value]
            * (energy_use[ENERGY_SOURCES.Electricity.value] - energy_generated)
            + energy_generated
        )

        pec_nr_coefficients = self.per_FEC_coefficients["PECnr/kWh FEC"].copy()
        pec_nr_gross = pec_nr_coefficients * energy_use
        # Again, electricity is a special case
        pec_nr_gross[ENERGY_SOURCES.Electricity.value] = pec_nr_coefficients[
            ENERGY_SOURCES.Electricity.value
        ] * (energy_use[ENERGY_SOURCES.Electricity.value] - energy_generated)

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
        """Final energy consumption in kWh broken down by system and energy source.

        Returns a DataFrame with one row per energy-use system and one column per
        ENERGY_SOURCE (Electricity, Diesel, LPG, Natural gas, Biomass, Pellets).
        The index is named 'System'. Summing all energy-source columns for a row
        recovers the total kWh for that system.

        [BES Report Table N21:P30]
        """
        rows = {
            "Heating": self._extract_energy_use("heating").sum(),
            "Cooling": self._extract_energy_use("cooling").sum(),
            "Ventilation": self._extract_energy_use("ventilation").sum(),
            "Hot water": self._extract_energy_use("hot_water").sum(),
            "Lighting": self._extract_energy_use("lighting").sum(),
            "Building background": self._standby_energy_use.sum(),
            "Others": self._other_energy_use.sum(),
        }
        df = DataFrame(rows).T
        df.index.name = "System"
        return df

    @property
    def space_hvac_demand(self) -> Optional[DataFrame]:
        """Energy required to heat and cool the building to required temperatures.

        [BES Report Tables N36:Q45]

        These values are not guaranteed to match up with total Heating/Cooling demand,
        because they're scaled by the usage for each zone.

        :returns MultiIndexed DataFrame by Heating/Cooling and case/Passivehaus standard
            with columns for Demand (kWh/m2), Peak (kW), and Peak ratio (W/m2)
        """
        if self.thermal is None:
            return None

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

        heating_demand = self.thermal.zonal_heating_demand.sum() / 1000
        cooling_demand = self.thermal.zonal_cooling_demand.sum() / 1000 * -1

        peak_heating_demand = max(
            self.thermal.heating_demand * self.geometry.conditioned_floor_area / 1000
        )
        peak_cooling_demand = max(
            self.thermal.cooling_demand * self.geometry.conditioned_floor_area / 1000
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
    def passive_survivability(self) -> Optional[Series]:
        """The proportion of the time the building is in an acceptable comfort range if HVAC is not running.

        Acceptable comfort range means the temperature is < 26C. [Hardcoded in Inputs cell J212]

        The proportion is discomfort hours / occupied hours.
        """
        if not self.thermal:
            return None
        mask = self.thermal.air_free_temp.index.get_level_values("month").isin(
            [6, 7, 8]
        )
        occupation = self.occupancy.is_occupied.loc[mask]
        temp = self.thermal.air_free_temp.loc[mask]
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
            space_heating_demand=self.space_hvac_demand.loc["Heating"]
            if self.space_hvac_demand is not None
            else None,
            space_cooling_demand=self.space_hvac_demand.loc["Cooling"]
            if self.space_hvac_demand is not None
            else None,
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
                    self.thermal.heating_demand
                    * self.geometry.conditioned_floor_area
                    / 1000
                ).quantile(0.996),
                "Peak cooling load (kW)": (
                    self.thermal.cooling_demand
                    * self.geometry.conditioned_floor_area
                    / 1000
                ).quantile(0.996),
                "Annual heating demand (kWh/m2)": self.report.space_heating_demand.loc[
                    self.building_name, "Demand (kWh/m2)"
                ],
                "Annual cooling demand (kWh/m2)": self.report.space_cooling_demand.loc[
                    self.building_name, "Demand (kWh/m2)"
                ],
                "Final energy consumption (kWh/m2)": (
                    self.report.final_energy_consumption_distribution.sum().sum()
                    / self.geometry.conditioned_floor_area
                ),
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

    @property
    def _solstice_csv(self) -> str:
        solstice_mask = (self._hours.index.get_level_values("month").isin([6, 12])) & (
            self._hours.index.get_level_values("day").isin([172, 355])
        )
        ghi = self.thermal.solar_irradiation.ghi.loc[solstice_mask]
        ghi = ghi.reset_index()
        ghi["month"] = np.where(ghi["month"] == 6, "June 21", "December 21")
        ghi = ghi.drop(columns="day")
        ghi = ghi.pivot(
            index="hour", columns="month", values="global_horizontal_irradiance"
        )
        return ghi.round(self.spec.parameters.output_csv_precision).to_csv(header=True)

    @property
    def _mdh_index(self) -> MultiIndex:
        """MultiIndex of month, day (of the month), hour for each hour of the year."""
        if self._mdh_index_ is None:
            idx = self._hours.index.to_frame().reset_index(drop=True)
            idx["day"] = idx["day"] - idx.groupby("month")["day"].transform("min") + 1
            self._mdh_index_ = MultiIndex.from_frame(idx)
        return self._mdh_index_

    @property
    def _temperature_csv(self) -> str:
        """CSV of internal and external temperatures for each hour of the year."""
        temp_df = DataFrame(index=self._hours.index)
        temp_df["external_temperature_C"] = self.thermal.dry_bulb_temp
        temp_df["internal_temperature_C"] = self.thermal.air_free_temp
        temp_df.set_index(self._mdh_index, inplace=True)
        return temp_df.round(self.spec.parameters.output_csv_precision).to_csv(
            header=True
        )

    def _find_peak(self, series: Series, fn: callable) -> HourPeak:
        """Find the peak value in a series using the provided function (e.g. max or min)."""
        months = [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ]
        peak_value = fn(series)
        peak_time = series[series == peak_value].index[0]
        return HourPeak(
            month=months[peak_time[0] - 1],
            day=day_of_the_month(peak_time[1], peak_time[0]),
            hour=peak_time[2],
            value=round(peak_value, self.spec.parameters.output_csv_precision),
        )

    @property
    def quantiles(self):
        return [
            0,
            0.004,
            0.01,
            0.02,
            0.1,
            0.2,
            0.3,
            0.4,
            0.5,
            0.6,
            0.7,
            0.8,
            0.9,
            0.95,
            0.99,
            0.996,
            1,
        ]

    def _model_validation(
        self, simulated: Series, specified: Series
    ) -> ModelValidation:
        """Compare simulated and specified values for model validation."""
        df = concat(
            [simulated.rename("Simulated (kWh)"), specified.rename("Measured (kWh)")],
            axis=1,
        ).dropna(how="any")

        n = len(df)
        if n == 0:
            logger.warning("No overlapping data for model validation.")
            return ModelValidation()

        s = df["Simulated (kWh)"].to_numpy(dtype=float)
        m = df["Measured (kWh)"].to_numpy(dtype=float)

        mean_m = m.mean()
        if mean_m == 0:
            logger.warning(
                "Mean of measured values is zero -> normalization/division by zero."
            )
            return ModelValidation()

        # Residuals
        res = m - s
        mean_bias_error = res.mean()

        dof = max(n, 1)  # degrees of freedom for RMSE and r2; avoid division by zero

        # NMBE: normalized mean bias error
        nmbe = (1 / mean_m) * mean_bias_error

        # CV(RMSE)
        cv_rmse = (1 / mean_m) * np.sqrt(
            np.sum(res**2) / (dof - 1)
        )  # ASHRAE uses ddof of n - 1

        # R^2
        r_numerator = (dof * np.sum(m * s)) - (np.sum(m) * np.sum(s))
        r_denominator = np.sqrt(
            ((dof * np.sum(m**2)) - (np.sum(m) ** 2))
            * ((dof * np.sum(s**2)) - (np.sum(s) ** 2))
        )
        r = r_numerator / r_denominator
        r2 = r**2

        return ModelValidation(
            energy_use_csv=df.round(self.spec.parameters.output_csv_precision)
            .set_index(self.months_index)
            .to_csv(header=True),
            nmbe=nmbe,
            cv_rmse=cv_rmse,
            r2=r2,
        )

    @property
    def degree_days(self):
        base_temperature = 18.0  # Hardcoded in AA109
        hourly_temperatures = self.thermal.dry_bulb_temp
        max_daily_t = hourly_temperatures.groupby(["month", "day"]).max()
        min_daily_t = hourly_temperatures.groupby(["month", "day"]).min()
        avg_daily_t = (max_daily_t + min_daily_t) / 2
        heating_dd = base_temperature - avg_daily_t
        return DataFrame(
            {
                "Heating Degree Days": heating_dd.clip(lower=0),
                "Cooling Degree Days": (-heating_dd).clip(lower=0),
            },
            index=avg_daily_t.index,
        )

    @property
    def overheating_running_average(self) -> Series:
        """Calculate overheating metrics for the building.
        Adaptive thermal comfort model EN 16798-1:2019.

        The week's running mean outdoor temperature is copied from the last day of that week,
        which is the first day on which the running mean can be calculated.

        Returns: DataFrame with hourly overheating flags for each category.
        """
        day_means = self.thermal.dry_bulb_temp.groupby(["month", "day"]).mean()

        weights = np.array([1, 0.8, 0.6, 0.5, 0.4, 0.3, 0.2])
        W = weights.sum()

        trm_daily = (
            concat(
                [day_means.shift(i) * w for i, w in enumerate(weights)],
                axis=1,
            ).sum(axis=1)
            / W
        ).clip(upper=30)

        # Excel-style bootstrap: copy first week value backwards
        trm_daily.iloc[:5] = trm_daily.iloc[6]

        # Expand to hourly
        trm_hourly = trm_daily.reindex(
            self.thermal.dry_bulb_temp.groupby(["month", "day"]).mean().index
        )
        trm_hourly = trm_hourly.repeat(24)
        trm_hourly.index = self.thermal.dry_bulb_temp.index[: len(trm_hourly)]
        trm_hourly.name = "Running mean outdoor temperature (C)"
        return trm_hourly

    @property
    def overheating_limits(self):
        outdoor_running_mean_temp = Series([10.0, 20.0, 30.0])
        limits = DataFrame()
        limits["Outdoor running mean temp (C)"] = outdoor_running_mean_temp
        limits["Category I min (C)"] = outdoor_running_mean_temp * 0.33 + 18.8 - 3
        limits["Category I max (C)"] = outdoor_running_mean_temp * 0.33 + 18.8 + 2
        limits["Category II min (C)"] = outdoor_running_mean_temp * 0.33 + 18.8 - 4
        limits["Category II max (C)"] = outdoor_running_mean_temp * 0.33 + 18.8 + 3
        limits["Category III min (C)"] = outdoor_running_mean_temp * 0.33 + 18.8 - 5
        limits["Category III max (C)"] = outdoor_running_mean_temp * 0.33 + 18.8 + 4
        return limits

    @property
    def building_geometry(self):
        window_area = self.geometry.window_areas.groupby("floor").sum()
        opaque_facade_area = (
            self.geometry.conditioned_facade_areas.groupby("floor").sum() - window_area
        )
        wwr = window_area / (window_area + opaque_facade_area)
        return DataFrame(
            {
                "Opaque facade (m2)": opaque_facade_area,
                "Roof (m2)": self.geometry.roof_projections,
                "Floor (m2)": self.geometry.conditioned_floor_areas.groupby(
                    "floor"
                ).sum(),
                "Windows (m2)": window_area,
                "Window-to-Wall Ratio": wwr,
            }
        )

    @property
    def building_geometry_orientation(self) -> DataFrame:
        window_area = self.geometry.window_areas.groupby("compass_point").sum()
        opaque_facade_area = (
            self.geometry.conditioned_facade_areas.groupby("compass_point").sum()
            - window_area
        )
        opaque_facade_area["Horizontal"] = self.geometry.roof_projections.sum()
        window_area["Horizontal"] = 0.0
        return DataFrame(
            {"Opaque facade (m2)": opaque_facade_area, "Windows (m2)": window_area}
        )

    @property
    def solar_heat_gains(self) -> DataFrame:
        opaque_gains_by_orientation = (
            (
                self.geometry.opaque_areas.to_frame("opaque_area")
                .groupby("compass_point")
                .sum()
                .apply(self.thermal.get_solar_heat_opaque, axis=1)
            )
            .transpose()
            .sum()
        )
        opaque_gains_by_orientation["Horizontal"] = self.thermal.solar_heat_roof.sum()
        # Determine winter/summer
        ref_temp = 22.0
        prev_air_free_temp = self.thermal.air_free_temp.shift(1).fillna(17.4)
        winter = prev_air_free_temp < ref_temp
        window_gains_by_orientation = self.thermal._solar_heat_windows["winter"].where(
            winter, self.thermal._solar_heat_windows["summer"]
        )
        # Add in missing orientations with zero gains
        window_gains_by_orientation = window_gains_by_orientation.reindex(
            columns=list(COMPASS_POINTS), fill_value=0
        )
        window_gains_by_orientation["Horizontal"] = 0.0
        return (
            DataFrame(
                {
                    "Opaque gains (kWh)": opaque_gains_by_orientation,
                    "Window gains (kWh)": window_gains_by_orientation.sum(),
                }
            )
            / 1000
        )  # Wh to kWh

    @property
    def months_index(self) -> Index:
        return Index(
            name="month",
            data=[
                "January",
                "February",
                "March",
                "April",
                "May",
                "June",
                "July",
                "August",
                "September",
                "October",
                "November",
                "December",
            ],
        )

    @property
    def _monthly_electricity_for_validation(self) -> Series:
        """Electricity use for model validation, aggregated by month."""
        df = DataFrame(
            {
                k: v[ENERGY_SOURCES.Electricity]
                for k, v in {
                    k: v.groupby("month").sum()
                    for k, v in self.energy_use_by_category.items()
                }.items()
            }
        )
        df[ENERGY_USE_CATEGORIES.Others] = self.spec.other_electricity_usage
        df[ENERGY_USE_CATEGORIES.Building_standby] = self.spec.building_standby_load
        # Need to use self.lighting.get_kwh_per_month values because self.lighting.energy_use gives different numbers??
        df[ENERGY_USE_CATEGORIES.Lighting] = self.lighting.get_kwh_per_month().values
        return df.sum(axis="columns")

    def _or_none(self, key: str, fn: callable):
        try:
            return fn()
        except Exception as e:
            logger.info(f"Could not calculate {key}: {e}")
            return None

    def _report_or_empty(self, simulation: str, fn: callable, empty_cls: type):
        try:
            return fn()
        except SimulationError as exc:
            logger.info(f"{simulation} report failed: {exc}")
        except Exception as exc:
            logger.warning(f"{simulation} report failed unexpectedly: {exc}")
        return empty_cls()

    def _building_energy_output(self) -> BuildingEnergySimulationOutput:
        try:
            precision = output_precision(self.spec)
            return BuildingEnergySimulationOutput(
                other_energy_use_electricity=self._or_none(
                    "other_energy_use_electricity",
                    lambda: (
                        (
                            self._other_energy_use[ENERGY_SOURCES.Electricity].sum()
                            + self._standby_energy_use[ENERGY_SOURCES.Electricity].sum()
                        )
                        / self.geometry.conditioned_floor_area
                    ),
                ),
                other_energy_use_gas=self._or_none(
                    "other_energy_use_gas",
                    lambda: (
                        self._other_energy_use[ENERGY_SOURCES.Natural_gas].sum()
                        / self.geometry.conditioned_floor_area
                    ),
                ),
                on_site_electricity_generated=self._or_none(
                    "on_site_electricity_generated",
                    lambda: (
                        self.spec.energy_generated
                        / self.geometry.conditioned_floor_area
                    ),
                ),
                on_site_electricity_used=self._or_none(
                    "on_site_electricity_used",
                    lambda: (
                        self.spec.energy_used / self.geometry.conditioned_floor_area
                    ),
                ),
                on_site_electricity_fraction=self._or_none(
                    "on_site_electricity_fraction",
                    lambda: (
                        (self.spec.energy_used / self.geometry.conditioned_floor_area)
                        / (
                            self.final_energy_consumption_distribution.sum().sum()
                            / self.geometry.conditioned_floor_area
                        )
                    ),
                ),
                all_renewable_fraction=self._or_none(
                    "all_renewable_fraction",
                    lambda: (
                        self.primary_energy_consumption.loc[
                            self.building_name, "Renewable"
                        ]
                        / self.primary_energy_consumption.loc[
                            self.building_name, "Total PEC"
                        ]
                    ),
                ),
                final_energy_consumption=self._or_none(
                    "final_energy_consumption",
                    lambda: (
                        self.final_energy_consumption_distribution.sum().sum()
                        / self.geometry.conditioned_floor_area
                    ),
                ),
                primary_energy_consumption=self._or_none(
                    "primary_energy_consumption",
                    lambda: self.primary_energy_consumption.loc[
                        self.building_name, "Total PEC"
                    ],
                ),
                non_renewable_primary_energy_consumption=self._or_none(
                    "non_renewable_primary_energy_consumption",
                    lambda: self.primary_energy_consumption.loc[
                        self.building_name, "Non-renewable"
                    ],
                ),
                co2_equivalent_emissions=self._or_none(
                    "co2_equivalent_emissions",
                    lambda: self.kg_co2_eq.sum() / self.geometry.conditioned_floor_area,
                ),
                final_energy_consumption_csv=self._or_none(
                    "final_energy_consumption_csv",
                    lambda: to_output_csv(
                        self.final_energy_consumption_distribution.rename(
                            columns=lambda c: c.value
                        ).reset_index(),
                        precision,
                        index=False,
                    ),
                ),
                electricity_validation=self._or_none(
                    "electricity_validation",
                    lambda: self._model_validation(
                        self._monthly_electricity_for_validation,
                        Series(
                            [
                                self.spec.electricity_january,
                                self.spec.electricity_february,
                                self.spec.electricity_march,
                                self.spec.electricity_april,
                                self.spec.electricity_may,
                                self.spec.electricity_june,
                                self.spec.electricity_july,
                                self.spec.electricity_august,
                                self.spec.electricity_september,
                                self.spec.electricity_october,
                                self.spec.electricity_november,
                                self.spec.electricity_december,
                            ],
                            index=range(1, 13),
                        ),
                    ),
                ),
                gas_validation=self._or_none(
                    "gas_validation",
                    lambda: self._model_validation(
                        self.energy_use[ENERGY_SOURCES.Natural_gas]
                        .groupby("month")
                        .sum(),
                        Series(
                            [
                                self.spec.gas_january,
                                self.spec.gas_february,
                                self.spec.gas_march,
                                self.spec.gas_april,
                                self.spec.gas_may,
                                self.spec.gas_june,
                                self.spec.gas_july,
                                self.spec.gas_august,
                                self.spec.gas_september,
                                self.spec.gas_october,
                                self.spec.gas_november,
                                self.spec.gas_december,
                            ],
                            index=range(1, 13),
                        ),
                    ),
                ),
            )
        except Exception as exc:
            raise BuildingEnergySimulationError(
                "Failed to generate building energy report output"
            ) from exc

    @property
    def outputs(self) -> OpenBESOutput:
        if self._outputs is None:
            self._outputs = OpenBESOutput(
                location_simulation_output=self._report_or_empty(
                    "LocationSimulation",
                    lambda: self.location.report,
                    LocationSimulationOutput,
                ),
                geometry_simulation_output=self._report_or_empty(
                    "GeometrySimulation",
                    lambda: self.geometry.report,
                    GeometrySimulationOutput,
                ),
                thermal_simulation_output=self._report_or_empty(
                    "ThermalSimulation",
                    lambda: self.thermal.report,
                    ThermalSimulationOutput,
                ),
                ventilation_simulation_output=self._report_or_empty(
                    "VentilationSimulation",
                    lambda: self.ventilation.report,
                    VentilationSimulationOutput,
                ),
                heating_simulation_output=self._report_or_empty(
                    "HeatingSimulation",
                    lambda: self.heating.report,
                    HeatingSimulationOutput,
                ),
                cooling_simulation_output=self._report_or_empty(
                    "CoolingSimulation",
                    lambda: self.cooling.report,
                    CoolingSimulationOutput,
                ),
                lighting_simulation_output=self._report_or_empty(
                    "LightingSimulation",
                    lambda: self.lighting.report,
                    LightingSimulationOutput,
                ),
                hot_water_simulation_output=self._report_or_empty(
                    "HotWaterSimulation",
                    lambda: self.hot_water.report,
                    HotWaterSimulationOutput,
                ),
                building_energy_simulation_output=self._report_or_empty(
                    "BuildingEnergySimulation",
                    self._building_energy_output,
                    BuildingEnergySimulationOutput,
                ),
            )

        return self._outputs

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
            raise NotImplementedError(
                "This will only work once we move self.spec to be OpenBESSpecificationV2"
            )
            self._full_case_report = OpenBESCase(
                inputs=self.spec,
                outputs=self.outputs,
                meta=OpenBESMetaData(
                    version=metadata("openbes")["Version"],
                    timestamp=self.timestamp,
                    EPW_file_checksum=(
                        self.location.epw_file_checksum
                        if self.location is not None
                        else None
                    ),
                ),
                log=self.log,
            )
        return self._full_case_report

    def update_spec(
        self, new_spec: OpenBESSpecification, preserve_log: bool = True
    ) -> "BuildingEnergySimulation":
        """
        Update the building energy simulation with a new specification.

        This method intelligently updates the simulation based on which specs have changed:
        - If thermal-affecting specs changed, resets the thermal cache and rebuilds dependent simulations
        - If only non-thermal specs changed, rebuilds only the affected simulations
        - Preserves the expensive hour-by-hour thermal calculations when the thermal spec hasn't changed

        The thermal simulation is expensive (hour-by-hour iterative calculations), so we only
        rerun it if absolutely necessary (i.e., if specs affecting thermal have changed).
        Other simulations (heating, cooling, ventilation, lighting, etc.) are always recreated
        to reflect the new specification.

        Args:
            new_spec: The new OpenBESSpecification to apply
        """
        # Check if thermal needs to be rerun
        thermal_needs_rerun = self.thermal is None or specs_require_thermal_rerun(
            self.spec, new_spec
        )

        # Update the spec reference
        self.spec = new_spec

        if thermal_needs_rerun:
            # Thermal needs to be completely recalculated
            if self.thermal is None:
                logger.info("Updating with new specification.")
            else:
                logger.info(
                    "Thermal-affecting specs changed. Recalculating thermal simulation..."
                )

            # Recreate from scratch
            out = type(self)(spec=new_spec, log_prefix=self.log_prefix)
        else:
            # Thermal is unchanged - preserve the expensive calculations
            logger.info(
                "Thermal specs unchanged. Reusing cached thermal calculations..."
            )

            # Reset thermal cache to clear intermediate computations but preserve hour-by-hour results
            thermal_sim = deepcopy(self.thermal)
            reset_thermal_cache(thermal_sim)

            out = type(self)(
                spec=new_spec, log_prefix=self.log_prefix, thermal=thermal_sim
            )

            # Retroactively bind new simulations to the existing thermal simulations
            out.thermal.spec = new_spec
            out.thermal.occupancy = out.occupancy
            out.thermal.geometry = out.geometry
            out.thermal.ventilation = out.ventilation
            out.thermal.lighting = out.lighting
            out.thermal.location = out.location

            logger.info("Building energy simulation updated with new specification.")

        if preserve_log:
            out.log = [*self.log, *out.log]
        return out

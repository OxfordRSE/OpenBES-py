import numpy as np

from .. import logging
from copy import deepcopy
from datetime import datetime, UTC
from importlib.metadata import metadata
from importlib.resources import files
from typing import Dict, Optional, List

from pandas import DataFrame, read_csv, Series, MultiIndex, concat, Index
from pydantic import BaseModel, ConfigDict

from .base import EnergyUseSimulation, HOURS_DF
from .climate import ClimateSimulation
from .cooling import CoolingSimulation, CoolingSystemSimulation
from .geometry import BuildingGeometry
from .heating import HeatingSimulation, HeatingSystemSimulation
from .hot_water import HotWaterSimulation
from .lighting import LightingSimulation
from .occupancy import OccupationSimulation
from .ventilation import VentilationSimulation
from ..logging import LogPrefix
from ..schemas import (
    OpenBESCase,
    OpenBESOutput,
    OpenBESMetaData,
    HourPeak,
    SpaceThermalDemandResult,
    VentilationSystemResult,
    ThermalSystemResult,
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

        self._mdh_index_: Optional[MultiIndex] = None
        self._outputs: Optional[OpenBESOutput] = None
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

        heating_demand = self.climate.zonal_heating_demand.sum() / 1000
        cooling_demand = self.climate.zonal_cooling_demand.sum() / 1000 * -1

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
        occupation = self.occupancy.is_occupied.loc[mask]
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

    @property
    def _solstice_csv(self) -> str:
        solstice_mask = (self._hours.index.get_level_values("month").isin([6, 12])) & (
            self._hours.index.get_level_values("day").isin([172, 355])
        )
        ghi = self.climate.solar_irradiation.ghi.loc[solstice_mask]
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
        temp_df["external_temperature_C"] = self.climate.dry_bulb_temp
        temp_df["internal_temperature_C"] = self.climate.air_free_temp
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

    def _space_thermal_demand_result(self, series: Series) -> SpaceThermalDemandResult:
        """Convert a series of thermal demand into a SpaceThermalDemandResult."""
        return SpaceThermalDemandResult(
            demand_total=series.sum(),
            demand_scaled=series.sum() / self.geometry.conditioned_floor_area,
            load_csv=series.groupby("month")
            .sum()
            .round(self.spec.parameters.output_csv_precision)
            .set_axis(self.months_index)
            .rename("Demand (kWh)")
            .to_csv(header=True),
            load_duraction_csv=series.quantile(self.quantiles)
            .rename_axis("Quantile")
            .to_frame(name="kW")
            .round(self.spec.parameters.output_csv_precision)
            .to_csv(header=True),
        )

    def _thermal_system_result(
        self, systems: List[HeatingSystemSimulation | CoolingSystemSimulation]
    ) -> List[ThermalSystemResult]:
        out = []
        for sys in systems:
            energy_use = sys.energy_use.sum().sum()
            peak_load = self._find_peak(sys.energy_use.sum(axis="columns"), max)
            peak_capacity = (
                sys.nominal_capacity * 1
                if isinstance(sys, CoolingSystemSimulation)
                else sys.number
            )
            if isinstance(sys, HeatingSystemSimulation):
                all_year_demand = sys.phi_h_nd_ac
            else:
                all_year_demand = sys.phi_c_nd_ac

            out.append(
                ThermalSystemResult(
                    conditioned_area=sys.area,
                    energy_demand=energy_use / sys.area,
                    energy_demand_on_all_year=all_year_demand.sum(),
                    system_usage=energy_use / self.geometry.conditioned_floor_area,
                    peak_load=peak_load,
                    peak_capacity=peak_capacity,
                    peak_ratio=(
                        peak_capacity
                        / sys.energy_use.sum(axis="columns").quantile(0.996)
                    ),
                )
            )
        return out

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
        res = s - m
        sum_res = res.sum()
        ss_res = np.sum(res**2)

        # RMSE with chosen denominator
        denom = max(n - 1, 1)  # avoid division by zero; ASHRAE uses ddof of n - 1
        rmse = np.sqrt(ss_res / denom)

        # NMBE: normalized mean bias error (percent)
        nmbe_pct = (sum_res / (denom * mean_m)) * 100

        # CV(RMSE) percent
        cv_rmse_pct = (rmse / mean_m) * 100

        # R^2
        ss_tot = np.sum((m - mean_m) ** 2)
        # If ss_tot is zero (constant measured series), define r2 sensibly:
        if ss_tot == 0:
            r2 = float("nan")
        else:
            r2 = 1 - (ss_res / ss_tot)

        return ModelValidation(
            energy_use_csv=df.round(self.spec.parameters.output_csv_precision)
            .set_index(self.months_index)
            .to_csv(header=True),
            nmbe=float(nmbe_pct),
            cv_rmse=float(cv_rmse_pct),
            r2=float(r2),
        )

    @property
    def degree_days(self):
        base_temperature = 18.0  # Hardcoded in AA109
        hourly_temperatures = self.climate.dry_bulb_temp
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
        day_means = self.climate.dry_bulb_temp.groupby(["month", "day"]).mean()

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
            self.climate.dry_bulb_temp.groupby(["month", "day"]).mean().index
        )
        trm_hourly = trm_hourly.repeat(24)
        trm_hourly.index = self.climate.dry_bulb_temp.index[: len(trm_hourly)]
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
                .apply(self.climate.get_solar_heat_opaque, axis=1)
            )
            .transpose()
            .sum()
        )
        opaque_gains_by_orientation["Horizontal"] = self.climate.solar_heat_roof.sum()
        # Determine winter/summer
        ref_temp = 22.0
        prev_air_free_temp = self.climate.air_free_temp.shift(1).fillna(17.4)
        winter = prev_air_free_temp < ref_temp
        window_gains_by_orientation = self.climate._solar_heat_windows["winter"].where(
            winter, self.climate._solar_heat_windows["summer"]
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
    def outputs(self) -> OpenBESOutput:
        if self._outputs is None:
            lighting_peak_load = 0
            for z in range(1, 7):
                try:
                    lighting_peak_load += (
                        self.lighting.get_w_per_luminaire(zone=z)
                        * getattr(self.spec, f"lighting_system_luminary_number_z{z}")
                    ) / 1000  # W to kW
                except (AttributeError, TypeError):
                    continue

            self._outputs = OpenBESOutput(
                **{
                    "altitude": self.climate.epw_metadata["altitude"],
                    "gross_building_area": self.geometry.gross_floor_area,
                    "conditioned_floor_area": self.geometry.conditioned_floor_area,
                    "indoor_air_volume": self.spec.floor_to_ceiling_height
                    * self.geometry.conditioned_floor_area,
                    "indoor_air_heat_capacity": (
                        self.spec.parameters.density_of_air
                        * self.spec.parameters.specific_heat_of_air
                        * self.spec.floor_to_ceiling_height
                        * self.geometry.conditioned_floor_area
                    ),
                    "solstice_ghr_csv": self._solstice_csv,
                    "external_internal_temperature_csv": self._temperature_csv,
                    "max_outdoor_temperature": self._find_peak(
                        self.climate.dry_bulb_temp, max
                    ),
                    "min_outdoor_temperature": self._find_peak(
                        self.climate.dry_bulb_temp, min
                    ),
                    "max_indoor_temperature": self._find_peak(
                        self.climate.air_free_temp, max
                    ),
                    "min_indoor_temperature": self._find_peak(
                        self.climate.air_free_temp, min
                    ),
                    "mean_indoor_temperature": self.climate.air_free_temp.mean(),
                    "discomfort_hours_percent": (
                        (
                            self.occupancy.is_occupied.sum()
                            - (self.occupancy.is_occupied * self.climate.air_free_temp)
                            .between(18, 26, inclusive="neither")
                            .sum()
                        )
                        / self.occupancy.is_occupied.sum()
                        * 100
                    ),
                    "discomfort_hours_percent_summer": self.sim_to_retrofit_report("")[
                        "Summer discomfort hours (%)"
                    ],
                    "heat_exchange_breakdown_csv": (
                        DataFrame(
                            {
                                "Heat transfer (infiltration)": (
                                    self.climate.heat_infiltration_window
                                    + (
                                        self.geometry.heat_infiltration_opaque
                                        / self.geometry.conditioned_floor_area
                                    )
                                )
                                * (
                                    self.climate.air_set_temp
                                    - self.climate.dry_bulb_temp
                                )
                                * -1,
                                "Heat transfer (ventilation)": self.climate.heat_transmission_by_ventilation
                                * (
                                    self.climate.air_set_temp
                                    - self.climate.dry_bulb_temp
                                )
                                * -1,
                                "Solar gains (opaque)": self.climate.solar_heat_opaque
                                / self.geometry.conditioned_floor_area,
                                "Solar gains (glazing)": self.climate.solar_heat_windows
                                / self.geometry.conditioned_floor_area,
                                "Heat from occupants": self.climate.internal_heat_from_occupants,
                                "Heat from appliances": self.climate.internal_heat_from_appliances,
                                "Heat from lighting": self.climate.internal_heat_from_lighting,
                            }
                        )
                        .groupby("month")
                        .sum()
                        .set_index(self.months_index)
                        / 1000  # Wh/m2 to kWh/m2
                    )
                    .round(self.spec.parameters.output_csv_precision)
                    .to_csv(header=True),
                    "space_thermal_demand_csv": (
                        DataFrame(
                            {
                                "Heating demand (kWh/m2)": self.climate.zonal_heating_demand.sum(
                                    axis="columns"
                                )
                                / 1000,
                                "Cooling demand (kWh/m2)": self.climate.zonal_cooling_demand.sum(
                                    axis="columns"
                                )
                                * -1
                                / 1000,
                            }
                        )
                        .groupby("month")
                        .sum()
                        .set_index(self.months_index)
                        / self.geometry.conditioned_floor_area  # kWh to Wh/m2
                    )
                    .round(self.spec.parameters.output_csv_precision)
                    .to_csv(header=True),
                    "infiltration_ach": (
                        (
                            self.climate.air_flow_dependent
                            + self.spec.leakage_air_flow_independent
                        )
                        / self.spec.floor_to_ceiling_height
                    ).mean(),
                    "natural_ach": (
                        self.climate.night_ventilation_enabled
                        * self.spec.natural_ventilation_night
                        / self.spec.floor_to_ceiling_height
                    ).mean(),
                    "heating_demand": self._space_thermal_demand_result(
                        self.climate.zonal_heating_demand.sum(axis="columns") / 1000
                    ),
                    "cooling_demand": self._space_thermal_demand_result(
                        self.climate.zonal_cooling_demand.sum(axis="columns")
                        / 1000
                        * -1
                    ),
                    "ventilation_systems": [
                        VentilationSystemResult(
                            energy_demand=vs.energy_use.sum().sum(),
                            peak_load=max(vs.energy_use.sum(axis="columns")),
                            sfp=max(vs.energy_use.sum(axis="columns"))
                            / (vs.airflow / 3600),
                        )
                        for vs in (
                            self.ventilation.ventilation_simulations
                            if self.ventilation
                            else []
                        )
                    ],
                    "heating_systems": self._thermal_system_result(
                        self.heating.heating_simulations if self.heating else []
                    ),
                    "cooling_systems": self._thermal_system_result(
                        self.cooling.cooling_simulations if self.cooling else []
                    ),
                    "lighting_demand": self.lighting.energy_use.sum().sum()
                    / self.geometry.conditioned_floor_area,
                    "lighting_peak_load": lighting_peak_load,
                    "lighting_load_ratio": lighting_peak_load
                    * 1000  # kW to W
                    / self.geometry.conditioned_floor_area,
                    "hot_water_demand": self.hot_water.energy_use.sum().sum()
                    / self.geometry.conditioned_floor_area,
                    "other_energy_use_electricity": (
                        self._other_energy_use[ENERGY_SOURCES.Electricity].sum()
                        + self._standby_energy_use[ENERGY_SOURCES.Electricity].sum()
                    )
                    / self.geometry.conditioned_floor_area,
                    "other_energy_use_gas": self._other_energy_use[
                        ENERGY_SOURCES.Natural_gas
                    ].sum()
                    / self.geometry.conditioned_floor_area,
                    "on_site_electricity_generated": self.spec.energy_generated
                    / self.geometry.conditioned_floor_area,
                    "on_site_electricity_used": self.spec.energy_used
                    / self.geometry.conditioned_floor_area,
                    "on_site_electricity_fraction": (
                        self.spec.energy_used / self.geometry.conditioned_floor_area
                    )
                    / self.final_energy_consumption_distribution["kWh/m2"].sum(),
                    "all_renewable_fraction": (
                        self.primary_energy_consumption.loc[
                            self.building_name, "Renewable"
                        ]
                        / self.primary_energy_consumption.loc[
                            self.building_name, "Total PEC"
                        ]
                    ),
                    "final_energy_consumption": self.final_energy_consumption_distribution[
                        "kWh/m2"
                    ].sum(),
                    "primary_energy_consumption": self.primary_energy_consumption.loc[
                        self.building_name, "Total PEC"
                    ],
                    "non_renewable_primary_energy_consumption": self.primary_energy_consumption.loc[
                        self.building_name, "Non-renewable"
                    ],
                    "co2_equivalent_emissions": self.kg_co2_eq.sum()
                    / self.geometry.conditioned_floor_area,
                    "final_energy_consumption_csv": self.final_energy_consumption_distribution[
                        "kWh"
                    ]
                    .rename_axis("System")
                    .round(self.spec.parameters.output_csv_precision)
                    .to_csv(header=True),
                    "electricity_validation": self._model_validation(
                        self.energy_use[ENERGY_SOURCES.Electricity]
                        .groupby("month")
                        .sum(),
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
                    "gas_validation": self._model_validation(
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
                    "climate_quantiles_csv": self.climate.dry_bulb_temp.quantile(
                        self.quantiles
                    )
                    .rename_axis("Quantile")
                    .to_frame(name="Temperature (C)")
                    .round(self.spec.parameters.output_csv_precision)
                    .to_csv(header=True),
                    "degree_days_csv": self.degree_days.round(
                        self.spec.parameters.output_csv_precision
                    ).to_csv(header=True),
                    "annual_incident_solar_radiation_csv": (
                        self.climate.solar_irradiation.solar_irradiation.sum(
                            axis="rows"
                        )
                        / 1000
                    )
                    .rename(index=lambda x: x.value)
                    .rename_axis("Compass point")
                    .to_frame(name="Annual incident solar radiation (kWh/m2)")
                    .round(self.spec.parameters.output_csv_precision)
                    .to_csv(header=True),
                    "running_average_outside_temp_csv": self.overheating_running_average.round(
                        self.spec.parameters.output_csv_precision
                    ).to_csv(header=True),
                    "overheating_limits_csv": self.overheating_limits.round(
                        self.spec.parameters.output_csv_precision
                    ).to_csv(header=True, index=False),
                    "building_geometry_csv": self.building_geometry.round(
                        self.spec.parameters.output_csv_precision
                    )
                    .rename(index=lambda x: x.value)
                    .rename_axis("Floor")
                    .to_csv(header=True),
                    "building_geometry_orientation_csv": self.building_geometry_orientation.round(
                        self.spec.parameters.output_csv_precision
                    )
                    .rename(
                        index=lambda x: x.value if isinstance(x, COMPASS_POINTS) else x
                    )
                    .rename_axis("Compass point")
                    .to_csv(header=True),
                    "solar_heat_gains_csv": (
                        self.solar_heat_gains.round(
                            self.spec.parameters.output_csv_precision
                        )
                    )
                    .rename(
                        index=lambda x: x.value if isinstance(x, COMPASS_POINTS) else x
                    )
                    .rename_axis("Compass point")
                    .to_csv(header=True),
                    "window_transmissivity_coefficient_csv": (
                        (
                            self.solar_heat_gains["Window gains (kWh)"]
                            / self.building_geometry_orientation["Windows (m2)"]
                        )
                        / self.climate.solar_irradiation.solar_irradiation.sum(
                            axis="rows"
                        )
                        * 1000
                    )
                    .drop(index="Horizontal")
                    .rename(
                        index=lambda x: x.value if isinstance(x, COMPASS_POINTS) else x
                    )
                    .rename_axis("Compass point")
                    .to_frame(name="Window transmissivity coefficient")
                    .fillna(0)
                    .round(self.spec.parameters.output_csv_precision)
                    .to_csv(header=True),
                }
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
            self._full_case_report = OpenBESCase(
                inputs=self.spec,
                outputs=self.get_outputs(include_subsimulations=include_subsimulations),
                meta=OpenBESMetaData(
                    version=metadata("openbes")["Version"], timestamp=self.timestamp
                ),
                log=self.log,
            )
        return self._full_case_report

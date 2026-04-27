from __future__ import annotations

from hashlib import md5
from importlib.resources import files
from tempfile import NamedTemporaryFile
from urllib.parse import urlparse
from urllib.request import urlopen

from pandas import DataFrame, Series
from pvlib.iotools import read_epw

from .base import HOURS_DF, SimulationError, missing_required_inputs
from .reporting import find_hour_peak, output_precision, to_output_csv, find_day_peak
from .solar_irradiation import SolarIrradiationSimulation
from ..schemas import LocationSimulationOutput
from ..types import OpenBESSpecification


def get_available_epw_files() -> list[str]:
    epw_data_dir = files("openbes.simulations.epw_data")
    return [f"openbes://{f.name}" for f in epw_data_dir.iterdir() if f.name.endswith(".epw")]


class LocationSimulationError(SimulationError):
    """Raised when location report generation fails."""


class LocationSimulation:
    """Loads EPW data and owns EPW-derived weather/solar properties."""
    _required_inputs = ("meteorological_file_path",)

    def __init__(self, spec: OpenBESSpecification):
        self.spec = spec
        missing = missing_required_inputs(self.spec, self._required_inputs)
        if missing:
            raise LocationSimulationError(
                f"LocationSimulation missing required inputs: {', '.join(missing)}"
            )
        self._source_path: str | None = None
        self._epw_data: DataFrame | None = None
        self._epw_metadata: dict | None = None
        self._epw_file_checksum: str | None = None
        self._solar_irradiation: SolarIrradiationSimulation | None = None

    @property
    def meteorological_file_path(self) -> str:
        return self.spec.meteorological_file_path

    def _ensure_loaded(self) -> None:
        source = self.meteorological_file_path
        if self._source_path == source and self._epw_data is not None:
            return

        self._source_path = source
        self._epw_data = None
        self._epw_metadata = None
        self._epw_file_checksum = None
        self._solar_irradiation = None

        parsed = urlparse(source)
        if parsed.scheme in ("http", "https", "ftp"):
            # Try to load pyodide.http packages to check if we're in a Pyodide environment.
            try:
                with urlopen(source) as response:
                    content = response.read()
            except Exception as exc:
                raise type(exc)(
                    f"{exc}. If remote EPW access issues persist, download the file locally "
                    "and supply a local file path instead."
                ) from exc
            with NamedTemporaryFile(suffix=".epw") as tmp:
                tmp.write(content)
                tmp.flush()
                self._epw_data, self._epw_metadata = read_epw(tmp.name)
            self._epw_file_checksum = md5(content).hexdigest()
            return

        if source.startswith("openbes://"):
            package_path = source[len("openbes://"):]
            epw_path = files("openbes.simulations.epw_data") / package_path
            content = epw_path.read_bytes()
            self._epw_data, self._epw_metadata = read_epw(str(epw_path))
            self._epw_file_checksum = md5(content).hexdigest()
            return

        # Local file access is allowed
        try:
            self._epw_data, self._epw_metadata = read_epw(source)
            with open(source, "rb") as f:
                content = f.read()
                self._epw_file_checksum = md5(content).hexdigest()
        except Exception as exc:
            raise type(exc)(
                f"Could not load {source} as a local EPW file. Ensure the path is correct and accessible."
            ) from exc

    @property
    def epw_data(self) -> DataFrame:
        self._ensure_loaded()
        return self._epw_data

    @property
    def epw_metadata(self) -> dict:
        self._ensure_loaded()
        return self._epw_metadata

    @property
    def elevation(self) -> float:
        return self.spec.parameters.altitude or self.epw_metadata.get("altitude", 0.0)

    @property
    def epw_file_checksum(self) -> str:
        self._ensure_loaded()
        return self._epw_file_checksum

    @property
    def dry_bulb_temp(self) -> Series:
        return self.epw_data["temp_air"]

    @property
    def wind_speed(self) -> Series:
        return self.epw_data["wind_speed"]

    @property
    def supply_air_temp(self) -> Series:
        return self.epw_data["temp_air"]

    @property
    def relative_humidity(self) -> Series:
        return self.epw_data["relative_humidity"]

    @property
    def solar_irradiation(self) -> SolarIrradiationSimulation:
        if self._solar_irradiation is None:
            self._solar_irradiation = SolarIrradiationSimulation(
                epw_data=self.epw_data,
                epw_metadata=self.epw_metadata,
                elevation=self.elevation
            )
        return self._solar_irradiation

    @property
    def _hourly_dry_bulb_temp(self) -> Series:
        return Series(self.dry_bulb_temp.values, index=HOURS_DF.index)

    @property
    def _hourly_ghi(self) -> Series:
        return Series(
            self.solar_irradiation.ghi.values,
            index=HOURS_DF.index,
            name="global_horizontal_irradiance",
        )

    @property
    def report(self) -> LocationSimulationOutput:
        try:
            precision = output_precision(self.spec)
            quantiles = [
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
            base_temperature = 18.0
            max_daily_t = self._hourly_dry_bulb_temp.groupby(["month", "day"]).max()
            min_daily_t = self._hourly_dry_bulb_temp.groupby(["month", "day"]).min()
            avg_daily_t = (max_daily_t + min_daily_t) / 2
            heating_dd = base_temperature - avg_daily_t
            degree_days = DataFrame(
                {
                    "Heating Degree Days": heating_dd.clip(lower=0),
                    "Cooling Degree Days": (-heating_dd).clip(lower=0),
                },
                index=avg_daily_t.index,
            )
            solstice_mask = (
                self._hourly_ghi.index.get_level_values("month").isin([6, 12])
            ) & (self._hourly_ghi.index.get_level_values("day").isin([172, 355]))
            ghi = self._hourly_ghi.loc[solstice_mask].reset_index()
            ghi["month"] = ghi["month"].map({6: "June 21", 12: "December 21"})
            ghi = ghi.drop(columns="day").pivot(
                index="hour", columns="month", values="global_horizontal_irradiance"
            )
            annual_radiation = (
                (self.solar_irradiation.solar_irradiation.sum(axis="rows") / 1000)
                .rename(index=lambda x: x.value)
                .rename_axis("Compass point")
                .to_frame(name="Annual incident solar radiation (kWh/m2)")
            )
            quantiles_df = (
                self._hourly_dry_bulb_temp.quantile(quantiles)
                .rename_axis("Quantile")
                .to_frame(name="Temperature (C)")
            )
            return LocationSimulationOutput(
                elevation=self.elevation,
                latitude=self.epw_metadata["latitude"],
                longitude=self.epw_metadata["longitude"],
                city=self.epw_metadata["city"],
                country=self.epw_metadata["country"],
                state_province=self.epw_metadata["state-prov"],
                solstice_ghr_csv=to_output_csv(ghi, precision),
                max_outdoor_temperature=find_hour_peak(
                    self._hourly_dry_bulb_temp, max, precision
                ),
                min_outdoor_temperature=find_hour_peak(
                    self._hourly_dry_bulb_temp, min, precision
                ),
                mean_outdoor_temperature=round(self._hourly_dry_bulb_temp.mean(), precision),
                max_outdoor_day_temperature=find_day_peak(
                    avg_daily_t, max, precision
                ),
                min_outdoor_day_temperature=find_day_peak(
                    avg_daily_t, min, precision
                ),
                mean_outdoor_day_temperature=round(
                    avg_daily_t.groupby(["month", "day"]).mean().mean(), precision
                ),
                temperature_quantiles_csv=to_output_csv(quantiles_df, precision),
                degree_days_csv=to_output_csv(degree_days, precision),
                annual_incident_solar_radiation_csv=to_output_csv(
                    annual_radiation, precision
                ),
            )
        except Exception as exc:
            raise LocationSimulationError("Failed to generate location report") from exc

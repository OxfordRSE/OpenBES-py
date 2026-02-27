from __future__ import annotations

from hashlib import md5
from importlib.resources import files
from tempfile import NamedTemporaryFile
from urllib.parse import urlparse
from urllib.request import urlopen

from pandas import DataFrame, Series
from pvlib.iotools import read_epw

from .solar_irradiation import SolarIrradiationSimulation
from ..types import OpenBESSpecification


def get_available_epw_files() -> list[str]:
    climate_data_dir = files("openbes.simulations.climate_data")
    return [f"openbes://{f.name}" for f in climate_data_dir.iterdir() if f.name.endswith(".epw")]


class LocationSimulation:
    """Loads EPW data and owns EPW-derived weather/solar properties."""

    def __init__(self, spec: OpenBESSpecification):
        self.spec = spec
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
            epw_path = files("openbes.simulations.climate_data") / package_path
            content = epw_path.read_bytes()
            self._epw_data, self._epw_metadata = read_epw(str(epw_path))
            self._epw_file_checksum = md5(content).hexdigest()
            return

        raise ValueError(
            "meteorological_file_path must be a remote URL (http/https/ftp) or openbes:// path. "
            f"Got: {source}"
        )

    @property
    def epw_data(self) -> DataFrame:
        self._ensure_loaded()
        return self._epw_data

    @property
    def epw_metadata(self) -> dict:
        self._ensure_loaded()
        return self._epw_metadata

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
            )
        return self._solar_irradiation

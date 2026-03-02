from .. import logging
from pandas import DataFrame

from .base import EnergyUseSimulation, SimulationError
from .occupancy import OccupationSimulation
from ..schemas import HotWaterSimulationOutput
from ..types import OpenBESSpecification

logger = logging.getLogger(__name__)


class HotWaterSimulationError(SimulationError):
    """Raised when hot water report generation fails."""


class HotWaterSimulation(EnergyUseSimulation):
    """Simulate hot water energy use based on building specifications and occupancy patterns."""
    _required_inputs = ("water_system_energy_source",)
    _required_inputs_error_cls = HotWaterSimulationError

    def __init__(
        self, spec: OpenBESSpecification, occupancy: OccupationSimulation = None
    ):
        super().__init__(spec=spec)
        try:
            self.occupancy = occupancy or OccupationSimulation(spec=spec)
        except SimulationError as exc:
            raise HotWaterSimulationError(
                f"Failed to initialize HotWaterSimulation due to error in dependent simulation: {exc}"
            ) from exc

    def get_daily_hot_water_nominal(self) -> float:
        """Calculate nominal (pre-efficiency scaling) daily hot water energy consumption.
        Args:
            spec (OpenBESSpecification): The building specifications spec data class.
        Returns:
            float: Nominal daily hot water energy consumption in kWh.
        """
        demand = self.spec.water_demand  # l/day
        specific_heat_capacity_water = 4.18  # J/g°C
        output_temp = self.spec.water_reference_temperature  # °C
        input_temp = self.spec.water_supply_temperature  # °C
        per_hour = 1 / 3_600  # Convert seconds to hours

        if demand is None or output_temp is None or input_temp is None:
            logger.warning(
                "Insufficient data to calculate hot water energy consumption."
            )
            return 0.0

        temperature_rise = output_temp - input_temp  # °C (from cold to hot water)

        return specific_heat_capacity_water * temperature_rise * demand * per_hour

    def get_daily_hot_water(self) -> float:
        """
        Adjust nominal hot water energy consumption by heater efficiency.
        Args:
            spec (OpenBESSpecification): The building specifications spec data class.
        Returns:
            float: Daily hot water energy consumption in kWh.
        """
        if self.spec.water_system_efficiency_cop is None:
            logger.warning(
                "Insufficient data to calculate hot water energy consumption."
            )
            return 0.0

        return (
            self.get_daily_hot_water_nominal() * self.spec.water_system_efficiency_cop
        )

    def get_hot_water_per_month(self) -> DataFrame:
        """Return the amount of energy used heating water for each month of the year.
        Args:
            spec (OpenBESSpecification): The building specifications spec data class.
        Returns:
            DataFrame: Hot water energy consumption in kWh for each month.
        """
        kWh_per_day = self.get_daily_hot_water()
        result = self.occupancy.occupied_days_per_month * kWh_per_day
        result.name = "kWh"
        return result

    @property
    def energy_use(self) -> DataFrame:
        """Hot water energy use in kWh for each hour of the year."""
        if self._energy_use[self.spec.water_system_energy_source].hasnans:
            daily_kWh = self.get_daily_hot_water()
            hourly_kWh = (
                daily_kWh * self.occupancy.occupied_days_per_month.sum()
            ) / self.occupancy.is_occupied.sum()
            self._energy_use[self.spec.water_system_energy_source] = [
                hourly_kWh
            ] * self.occupancy.is_occupied
        return self._energy_use

    @property
    def report(self) -> HotWaterSimulationOutput:
        try:
            area = self.occupancy.geometry.conditioned_floor_area
            return HotWaterSimulationOutput(
                hot_water_demand=self.energy_use.sum().sum() / area if area else None
            )
        except Exception as exc:
            raise HotWaterSimulationError(
                "Failed to generate hot water report"
            ) from exc

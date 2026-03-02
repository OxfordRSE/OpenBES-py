from pandas import DataFrame

from ..types import OpenBESSpecification, ENERGY_SOURCES


def month_for_day(day_number_in_year: int) -> int:
    """Calculate the month for a given day number in the year.
    Args:
        day_number_in_year (int): The day number in the year (1-365).
    Returns:
        int: The corresponding month (1-12).
    """
    if day_number_in_year <= 31:
        return 1
    elif day_number_in_year <= 59:
        return 2
    elif day_number_in_year <= 90:
        return 3
    elif day_number_in_year <= 120:
        return 4
    elif day_number_in_year <= 151:
        return 5
    elif day_number_in_year <= 181:
        return 6
    elif day_number_in_year <= 212:
        return 7
    elif day_number_in_year <= 243:
        return 8
    elif day_number_in_year <= 273:
        return 9
    elif day_number_in_year <= 304:
        return 10
    elif day_number_in_year <= 334:
        return 11
    else:
        return 12


# Blank DataFrame of each hour with month info, indexed by day of the year
HOURS_DF = DataFrame(
    [
        {"month": month_for_day(d), "day": d, "hour": h, "is_daytime": 8 <= h <= 22}
        for d in range(1, 366)
        for h in range(1, 25)
    ]
).set_index(["month", "day", "hour"])


class SimulationError(RuntimeError):
    """Base exception for simulation-level failures."""


class SimulationRequiredInputsError(SimulationError, ValueError):
    """Raised when required specification inputs are missing for a simulation."""


class EnergyUseSimulationInitError(SimulationError, ValueError):
    pass


def _resolve_required_input(spec: OpenBESSpecification, key: str):
    value = spec
    for part in key.split("."):
        value = getattr(value, part)
    return value


def missing_required_inputs(
    spec: OpenBESSpecification,
    required_inputs: list[str] | tuple[str, ...],
    getter=None,
) -> list[str]:
    if not required_inputs:
        return []
    resolver = getter or (lambda k: _resolve_required_input(spec, k))
    missing = []
    for key in required_inputs:
        try:
            value = resolver(key)
        except (AttributeError, KeyError, TypeError):
            missing.append(key)
            continue
        if value is None or value == "":
            missing.append(key)
    return missing


class HourlySimulation:
    """
    Base class for hourly simulations.

    Each instance is initialized with an OpenBESSpecification and contains an `_hours` property
    that holds a DataFrame representing each hour of the year.

    These simulations usually make heavy use of the `@property` decorator to define various calculated properties
    based on the specification and the hourly data.
    Properties will typically add columns to the `_hours` DataFrame as needed for various calculations,
    and usually return that DataFrame or specific columns from it.
    """

    spec: OpenBESSpecification
    _hours: DataFrame
    _required_inputs: tuple[str, ...] = ()
    _required_inputs_error_cls = SimulationRequiredInputsError

    def __init__(self, spec: OpenBESSpecification):
        self.spec = spec
        self.validate_required_inputs()
        self._hours = HOURS_DF.copy()

    def validate_required_inputs(
        self,
        required_inputs: list[str] | tuple[str, ...] | None = None,
        *,
        getter=None,
        context: str | None = None,
        error_cls=None,
    ) -> None:
        required = self._required_inputs if required_inputs is None else required_inputs
        missing = missing_required_inputs(self.spec, required, getter=getter)
        if not missing:
            return
        label = context or self.__class__.__name__
        exc_cls = error_cls or self._required_inputs_error_cls
        raise exc_cls(f"{label} missing required inputs: {', '.join(missing)}")


class EnergyUseSimulation(HourlySimulation):
    """
    Base class for hourly energy use simulations.

    Child classes should override the energy_use property to return a DataFrame representing
    the energy use in kW for each hour of the year, with a column for each of the ENERGY_SOURCES.

    The _energy_use property is initialized as a DataFrame of NaNs with the same index as _hours
    and columns for each ENERGY_SOURCES. self.energy_use should populate this DataFrame appropriately.
    """
    _required_inputs_error_cls = EnergyUseSimulationInitError

    def __init__(self, spec: OpenBESSpecification):
        super().__init__(spec)
        self._energy_use = DataFrame(
            index=self._hours.index, columns=list(ENERGY_SOURCES)
        ).astype(float)

    def get_param_or_spec(self, key: str):
        try:
            return getattr(self.spec.parameters, key)
        except AttributeError:
            return getattr(self.spec, key)

    @property
    def energy_use(self) -> DataFrame:
        """DataFrame of energy use in kW for each hour of the year, with a column for each ENERGY_SOURCES."""
        raise NotImplementedError(
            "Child classes must implement the energy_use property."
        )

    @property
    def annual_energy_use(self) -> DataFrame:
        return self.energy_use.sum().sum()

    @property
    def report(self) -> dict:
        raise NotImplementedError("Child classes must implement the report property.")

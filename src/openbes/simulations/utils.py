from pandas import DataFrame
from src.openbes.types import OPERATIONAL_DAYS_PER_MONTH

OPERATIONAL_DAYS_DF = DataFrame({m.value: d for m, d in OPERATIONAL_DAYS_PER_MONTH.items()}, index=["days"])

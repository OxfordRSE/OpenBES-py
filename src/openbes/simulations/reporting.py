from __future__ import annotations

from pandas import DataFrame, Series


def to_output_csv(
    value: DataFrame | Series,
    precision: int,
    *,
    header: bool = True,
    index: bool = True,
) -> str:
    """Serialize a tabular output to CSV using OpenBES output conventions."""
    return value.round(precision).to_csv(header=header, index=index)

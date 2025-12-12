from typing import Optional

from pydantic import field_validator, Field

from .generated.models import OpenBESSpecificationV2 as OpenBESSpecificationV2_raw

class OpenBESSpecificationV2(OpenBESSpecificationV2_raw):
    def __init__(self, **kwargs):
        self._init_kwargs = kwargs
        super().__init__(**kwargs)

    heat_capacity: Optional[float] = Field(
        default=None, description="Heat capacity Am rating."
    )

    @field_validator("heat_capacity", mode="before")
    def validate_heat_capacity(cls, v):
        if v in ["Very light", "Light", "Medium"]:
            return 2.5
        elif v == "Heavy":
            return 3.0
        elif v == "Very heavy":
            return 3.5
        elif isinstance(v, float):
            return v
        else:
            raise ValueError(f"Unknown heat capacity class: {v}")

    


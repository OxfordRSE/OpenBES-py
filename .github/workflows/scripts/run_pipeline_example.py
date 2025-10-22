from src.openbes.pipeline import pipeline
from src.openbes.types.dataclasses import OpenBESSpecification, OpenBESParameters

spec = OpenBESSpecification()
params = OpenBESParameters()
result = pipeline(spec, params)
print('Pipeline result:', result)

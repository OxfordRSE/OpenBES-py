from openbes.pipeline import pipeline
from openbes.types.dataclasses import OpenBESSpecification, OpenBESParameters

spec = OpenBESSpecification()
params = OpenBESParameters()
result = pipeline(spec, params)
print('Pipeline result:', result)

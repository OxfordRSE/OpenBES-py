from openbes import BuildingEnergySimulation
from openbes.examples import HOLYWELL_HOUSE_SPEC

simulation = BuildingEnergySimulation(spec=HOLYWELL_HOUSE_SPEC)
print("Overall annual energy use:", simulation.energy_use.sum().sum())

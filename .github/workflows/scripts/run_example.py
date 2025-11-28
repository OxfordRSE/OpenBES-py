from openbes import BuildingEnergySimulation
from openbes.examples import HOLYWELL_HOUSE_SPECIFICATION

simulation = BuildingEnergySimulation(spec=HOLYWELL_HOUSE_SPECIFICATION)
print('Overall annual energy use:', simulation.energy_use.sum().sum())

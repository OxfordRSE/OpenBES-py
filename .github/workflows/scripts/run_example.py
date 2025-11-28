from openbes import BuildingEnergySimulation, OpenBESSpecification

spec = OpenBESSpecification.from_toml('tests/test_cases/cases/600.toml')
simulation = BuildingEnergySimulation(spec=spec)
print('Overall annual energy use:', simulation.energy_use.sum().sum())

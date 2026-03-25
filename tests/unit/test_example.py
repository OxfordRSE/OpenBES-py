import unittest
from tests.unit.utils import (
    OpenBESTestCase,
)


class Example(OpenBESTestCase):
    def test_example(self):
        from openbes import BuildingEnergySimulation
        from openbes.examples import HOLYWELL_HOUSE_SPEC

        simulation = BuildingEnergySimulation(spec=HOLYWELL_HOUSE_SPEC)
        assert simulation.energy_use.sum().sum() is not None

    def test_load_example(self):
        from openbes.examples import load_example

        spec = load_example("Holywell House")
        assert spec is not None

if __name__ == "__main__":
    unittest.main()

import unittest

from openbes.examples import list_examples, load_example, HOLYWELL_HOUSE_SPEC
from tests.unit.utils import (
    OpenBESTestCase,
)
from openbes import BuildingEnergySimulation


class Example(OpenBESTestCase):
    def test_example(self):
        simulation = BuildingEnergySimulation(spec=HOLYWELL_HOUSE_SPEC)
        assert simulation.energy_use.sum().sum() is not None

    def test_load_example(self):
        from openbes.examples import load_example

        spec = load_example("Holywell House")
        assert spec is not None

    def test_examples(self):
        for example in list_examples():
            with self.subTest(example=example["name"]):
                load_example(example["name"])

if __name__ == "__main__":
    unittest.main()

import unittest

from openbes import OpenBESSpecification, BuildingEnergySimulation
from openbes.schemas import OpenBESOutput, json_to_toml
from openbes.simulations.thermal import ThermalSimulationError, ThermalSimulation
from openbes.simulations.geometry import GeometrySimulationError, BuildingGeometry
from openbes.types import OpenBESParameters, MONTHS, ENERGY_SOURCES
from openbes.simulations.building_energy import BuildingEnergySimulationError, OpenBESReport


class MiscellaneousUtilities(unittest.TestCase):
    def test_listable_enum_list(self):
        self.assertEqual(MONTHS.list_values()[0], "Jan")

    def test_listable_enum_by_index(self):
        self.assertEqual(MONTHS.get_by_index(0), MONTHS.Jan)

    def test_listable_enum_from_str(self):
        spec = OpenBESSpecification(cooling_system1_energy_source="Natural gas",
                                    building_length=1.0,
                                    building_width=1.0, meteorological_file_path="None.epw")
        self.assertEqual(spec.cooling_system1_energy_source, ENERGY_SOURCES.Natural_gas)
        self.assertTrue(isinstance(spec.cooling_system1_energy_source, ENERGY_SOURCES))

    def test_spec_with_param_dict(self):
        params = {"cooling_system2_number": 10}
        spec = OpenBESSpecification(building_width=1.0, building_length=1.0, meteorological_file_path="None.epw",
                                    parameters=params)
        self.assertTrue(isinstance(spec.parameters, OpenBESParameters))
        self.assertEqual(spec.parameters.cooling_system2_number, 10)

    def test_building_simulation_empty_spec_dict_fails_gracefully(self):
        spec = OpenBESSpecification()
        with self.assertRaises(GeometrySimulationError) as exc:
            BuildingGeometry(spec)
        self.assertIn("missing required inputs", str(exc.exception))
        with self.assertRaises(ThermalSimulationError) as exc:
            ThermalSimulation(spec)
        self.assertIn("missing required inputs", str(exc.exception))

    def test_javascript_call(self):
        obj = {
            "building": {
                "name": "Concept Building",
                "height": 12,
                "width": 20,
                "length": 30
            },
            "meteorological_file_path": "openbes://UK_Oxford_GBR_ENG_RAF.Benson.036580_TMYx.2007-2021.epw",
            "zones": [
                {
                    "name": "Office",
                    "areas": [
                        1200,
                        0,
                        0,
                        0,
                        0
                    ],
                    "conditioned": True,
                    "active_hours": {
                        "start": 8,
                        "end": 17
                    }
                },
                {
                    "name": "Teaching",
                    "areas": [
                        0,
                        1200,
                        0,
                        0,
                        0
                    ],
                    "conditioned": True,
                    "active_hours": {
                        "start": 8,
                        "end": 17
                    }
                }
            ]
        }
        json_spec = json_to_toml(obj)
        spec = OpenBESSpecification.from_toml(json_spec)
        sim = BuildingEnergySimulation(spec)
        self.assertEqual(sim.energy_use.sum().sum(), 0)

    def test_blank_spec_update(self):
        sim = BuildingEnergySimulation()
        sim.update_spec(
            OpenBESSpecification(building_length=1.0, building_width=1.0))
        self.assertEqual(sim.spec.building_length, 1.0)
        self.assertEqual(sim.spec.building_width, 1.0)

if __name__ == "__main__":
    unittest.main()
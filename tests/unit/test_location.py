import unittest
from unittest.mock import patch

from openbes.simulations.location import LocationSimulation, get_available_epw_files
from openbes.types import OpenBESSpecification


class TestLocationSimulation(unittest.TestCase):
    def _spec(self, path: str) -> OpenBESSpecification:
        return OpenBESSpecification(
            building_length=10.0,
            building_width=10.0,
            meteorological_file_path=path,
        )

    def test_available_files_use_openbes_prefix(self):
        files = get_available_epw_files()
        self.assertTrue(all(f.startswith("openbes://") for f in files))

    def test_openbes_path_loads_and_has_checksum(self):
        sim = LocationSimulation(self._spec("openbes://USA_Denver_725650TYCST.epw"))
        self.assertIn("latitude", sim.epw_metadata)
        self.assertEqual(len(sim.epw_file_checksum), 32)

    def test_local_path_accepted(self):
        sim = LocationSimulation(self._spec("no/file/here.epw"))
        with self.assertRaises(FileNotFoundError):
            _ = sim.epw_data

    @patch("openbes.simulations.location.urlopen")
    def test_remote_error_message_contains_guidance(self, mock_urlopen):
        mock_urlopen.side_effect = ConnectionError("boom")
        sim = LocationSimulation(self._spec("https://example.com/file.epw"))
        with self.assertRaises(Exception) as ctx:
            _ = sim.epw_data
        self.assertIn("download the file locally", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()

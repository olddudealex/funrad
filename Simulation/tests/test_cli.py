import sys
import unittest
from pathlib import Path


SIMULATION_DIR = Path(__file__).resolve().parents[1]
if str(SIMULATION_DIR) not in sys.path:
    sys.path.insert(0, str(SIMULATION_DIR))

import main


class CliTests(unittest.TestCase):
    def test_default_report_folder_is_simulation_generated(self):
        source = Path("somewhere") / "Example.RevA.toyradar"

        self.assertEqual(
            main.default_report_path(source, ".results.json"),
            SIMULATION_DIR / "generated" / "Example.RevA.results.json",
        )
        self.assertEqual(
            main.default_report_path(source, ".results.md"),
            SIMULATION_DIR / "generated" / "Example.RevA.results.md",
        )


if __name__ == "__main__":
    unittest.main()

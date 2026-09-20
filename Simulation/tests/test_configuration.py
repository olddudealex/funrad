from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


SIMULATION_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIMULATION_DIR))

from config import ConfigurationError, load_configuration, validate_configuration
from graph.node_graph import NodeGraph


class ConfigurationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config_path = SIMULATION_DIR / "configs" / "FunRad.RevA.toyradar"

    def test_reva_configuration_is_strictly_valid(self) -> None:
        document, warnings = load_configuration(self.config_path)
        self.assertEqual([], warnings)
        self.assertEqual(1, document["schema_version"])
        self.assertEqual(16, len(document["blocks"]))
        self.assertEqual(21, len(document["connections"]))
        self.assertEqual(4, len(document["scenarios"]))

    def test_portable_json_schema_is_valid_json(self) -> None:
        schema_path = SIMULATION_DIR / "configs" / "toyradar.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertEqual("ToyRadar executable design configuration", schema["title"])
        self.assertEqual(1, schema["properties"]["schema_version"]["const"])

    def test_unknown_parameter_is_rejected(self) -> None:
        document, _ = load_configuration(self.config_path)
        broken = copy.deepcopy(document)
        broken["blocks"][0]["params"]["magic_number"] = 42
        with self.assertRaises(ConfigurationError) as context:
            validate_configuration(broken)
        self.assertIn("unknown keys: magic_number", str(context.exception))

    def test_graph_round_trip_preserves_specification_metadata(self) -> None:
        document, _ = load_configuration(self.config_path)
        graph = NodeGraph()
        graph.from_dict(document)
        round_trip = graph.to_dict()
        self.assertEqual(document["design"], round_trip["design"])
        self.assertEqual(document["scenarios"], round_trip["scenarios"])
        self.assertEqual("TX PA", round_trip["blocks"][3]["name"])
        self.assertEqual("QPA9127", round_trip["blocks"][3]["part_number"])

    def test_legacy_preset_migrates_with_explicit_warnings(self) -> None:
        legacy_path = SIMULATION_DIR / "PLL_Option.toyradar"
        document, warnings = load_configuration(legacy_path)
        self.assertEqual(1, document["schema_version"])
        self.assertTrue(any("legacy unversioned" in warning for warning in warnings))
        self.assertTrue(any("conversion_loss_db" in warning for warning in warnings))
        self.assertTrue(any("full_scale_dbm" in warning for warning in warnings))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import sys
import unittest
from dataclasses import asdict
from pathlib import Path


SIMULATION_DIR = Path(__file__).resolve().parents[1]
if str(SIMULATION_DIR) not in sys.path:
    sys.path.insert(0, str(SIMULATION_DIR))

from config import load_configuration
from graph.node_graph import NodeGraph
from reporting import calculate_document
from scenario import ConfigurationSession, effective_configuration


class ScenarioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document, _ = load_configuration(
            SIMULATION_DIR / "configs" / "FunRad.RevA.toyradar"
        )

    def test_effective_configuration_applies_same_overrides_as_report(self):
        effective = effective_configuration(self.document, "far_plus10dbsm")
        target = next(block for block in effective["blocks"] if block["id"] == "target")
        base_target = next(block for block in self.document["blocks"] if block["id"] == "target")
        self.assertEqual(10.0, target["params"]["rcs_dbsm"])
        self.assertEqual(0.0, base_target["params"]["rcs_dbsm"])

    def test_scenario_edit_does_not_change_base(self):
        session = ConfigurationSession(self.document)
        session.select("far_plus10dbsm")
        session.set_parameter("target", "distance_m", 60.0)
        self.assertEqual(45.0, session.base_params("target")["distance_m"])
        effective = session.effective_document()
        target = next(block for block in effective["blocks"] if block["id"] == "target")
        self.assertEqual(60.0, target["params"]["distance_m"])

    def test_reset_and_promote_are_explicit(self):
        session = ConfigurationSession(self.document)
        session.select("far_plus10dbsm")
        session.reset_override("target", "distance_m")
        target = next(
            block for block in session.effective_document()["blocks"]
            if block["id"] == "target"
        )
        self.assertEqual(45.0, target["params"]["distance_m"])

        session.promote_block_overrides("target")
        self.assertEqual(10.0, session.base_params("target")["rcs_dbsm"])
        self.assertEqual(set(), session.override_keys("target"))

    def test_structure_sync_does_not_copy_effective_params_into_base(self):
        session = ConfigurationSession(self.document)
        session.select("far_plus10dbsm")
        graph_document = session.effective_document()
        graph_target = next(
            block for block in graph_document["blocks"] if block["id"] == "target"
        )
        graph_target["pos"] = [321, 654]
        self.assertEqual(10.0, graph_target["params"]["rcs_dbsm"])

        session.sync_graph_structure(graph_document)
        base_target = next(
            block for block in session.document["blocks"] if block["id"] == "target"
        )
        self.assertEqual([321, 654], base_target["pos"])
        self.assertEqual(0.0, base_target["params"]["rcs_dbsm"])

    def test_add_copy_and_delete_scenario(self):
        session = ConfigurationSession(self.document)
        session.select("far_plus10dbsm")
        first_id = session.add_scenario("Far target, +20 dBsm")
        self.assertEqual("far_target_20_dbsm", first_id)
        self.assertEqual(
            {"distance_m", "rcs_dbsm"},
            session.override_keys("target"),
        )

        second_id = session.add_scenario("Far target, +20 dBsm", copy_active=False)
        self.assertEqual("far_target_20_dbsm_2", second_id)
        self.assertEqual(set(), session.override_keys("target"))
        self.assertEqual(second_id, session.delete_active_scenario())
        self.assertIsNone(session.active_scenario_id)

    def test_gui_effective_graph_and_report_produce_same_metrics(self):
        scenario_id = "far_plus10dbsm"
        graph = NodeGraph()
        graph.from_dict(effective_configuration(self.document, scenario_id))
        graph.run(strict=True)
        gui_metrics = asdict(graph.compute_metrics())

        report = calculate_document(self.document)
        report_metrics = next(
            case["metrics"] for case in report["scenarios"]
            if case["id"] == scenario_id
        )
        self.assertEqual(report_metrics, gui_metrics)


if __name__ == "__main__":
    unittest.main()

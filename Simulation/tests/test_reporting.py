from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path


SIMULATION_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIMULATION_DIR))

from config import configuration_hash, load_configuration
from physics.radar_equation import max_range_m
from reporting import calculate_document


class ReportingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document, cls.warnings = load_configuration(
            SIMULATION_DIR / "configs" / "FunRad.RevA.toyradar"
        )

    def test_report_is_deterministic_and_complete(self) -> None:
        first = calculate_document(self.document, self.warnings)
        second = calculate_document(self.document, self.warnings)
        self.assertEqual(first, second)
        self.assertEqual(configuration_hash(self.document), first["source_configuration_sha256"])
        self.assertEqual(4, len(first["scenarios"]))
        self.assertTrue(all(len(case["budget"]) == 16 for case in first["scenarios"]))
        for case in first["scenarios"]:
            has_adc_warning = any(
                "ADC half-LSB" in warning for warning in case["warnings"]
            )
            self.assertEqual(case["metrics"]["snr_db"] <= -200.0, has_adc_warning)

    def test_ten_db_rcs_change_has_expected_power_and_range_scaling(self) -> None:
        report = calculate_document(self.document, self.warnings)
        by_distance: dict[float, list[dict]] = {}
        for case in report["scenarios"]:
            distance = case["overrides"]["target"]["distance_m"]
            by_distance.setdefault(distance, []).append(case)

        for same_range_cases in by_distance.values():
            self.assertEqual(2, len(same_range_cases))
            low, high = sorted(
                same_range_cases,
                key=lambda case: case["overrides"]["target"]["rcs_dbsm"],
            )
            rcs_delta = (
                high["overrides"]["target"]["rcs_dbsm"]
                - low["overrides"]["target"]["rcs_dbsm"]
            )
            high_target = next(
                row for row in high["budget"] if row["block_id"] == "target"
            )
            low_target = next(
                row for row in low["budget"] if row["block_id"] == "target"
            )
            self.assertTrue(
                math.isclose(
                    rcs_delta,
                    high_target["signal_level"] - low_target["signal_level"],
                    abs_tol=1e-9,
                )
            )

        expected = 10.0 ** (10.0 / 40.0)
        common = dict(
            ptx_dbm=2.0,
            gt_dbi=12.0,
            gr_dbi=12.0,
            nf_db=0.66,
            snr_min_db=10.0,
            bw_hz=1e6,
            freq_hz=5.8e9,
        )
        range_ratio = (
            max_range_m(rcs_dbsm=0.0, **common)
            / max_range_m(rcs_dbsm=-10.0, **common)
        )
        self.assertTrue(math.isclose(expected, range_ratio, rel_tol=1e-12))


if __name__ == "__main__":
    unittest.main()

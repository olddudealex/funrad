from __future__ import annotations

import copy
import json
import math
from dataclasses import asdict
from pathlib import Path
from typing import Any

from config import ENGINE_VERSION, configuration_hash
from graph.node_graph import NodeGraph
from graph.registry import _BLOCK_REGISTRY
from scenario import apply_overrides


def calculate_document(document: dict[str, Any], load_warnings: list[str] | None = None) -> dict:
    scenarios = document.get("scenarios") or [
        {"id": "base", "label": "Base configuration", "overrides": {}}
    ]
    snr_min_db = float(document.get("analyses", {}).get("snr_min_db", 10.0))
    results = []
    for scenario in scenarios:
        scenario_document = copy.deepcopy(document)
        apply_overrides(scenario_document, scenario.get("overrides", {}))
        graph = NodeGraph()
        graph.from_dict(scenario_document)
        graph.run(strict=True)
        metrics = asdict(graph.compute_metrics(snr_min_db=snr_min_db))
        scenario_warnings: list[str] = []
        if metrics["snr_db"] <= -200.0:
            scenario_warnings.append(
                "Target signal is below the current ADC half-LSB dead zone; "
                "reported SNR is a sentinel and maximum range is zero."
            )
        results.append({
            "id": scenario["id"],
            "label": scenario.get("label", scenario["id"]),
            "overrides": copy.deepcopy(scenario.get("overrides", {})),
            "metrics": metrics,
            "budget": graph.get_power_budget(),
            "warnings": scenario_warnings,
        })

    return _finite_values({
        "report_schema_version": 1,
        "engine_version": ENGINE_VERSION,
        "source_configuration_sha256": configuration_hash(document),
        "design": copy.deepcopy(document.get("design", {})),
        "environment": copy.deepcopy(document.get("environment", {})),
        "analysis_settings": copy.deepcopy(document.get("analyses", {})),
        "configuration_warnings": list(load_warnings or []),
        "open_definitions": _open_definitions(document),
        "scenarios": results,
    })


def write_results_json(results: dict, path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")


def write_markdown_report(document: dict, results: dict, path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    design = results.get("design", {})
    lines = [
        f"# {design.get('name', 'ToyRadar')} {design.get('revision', '')} — Generated Results".strip(),
        "",
        "> [!warning] Generated file",
        "> Do not edit this page manually. Regenerate it from the executable `.toyradar` configuration.",
        "",
        f"- Engine version: `{results['engine_version']}`",
        f"- Configuration SHA-256: `{results['source_configuration_sha256']}`",
        f"- Minimum SNR used for range estimate: {results['analysis_settings'].get('snr_min_db', 10.0):g} dB",
        "",
        "## Configuration",
        "",
        "| Block | Part | Parameter | Value | Status |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for block_data in document.get("blocks", []):
        cls = _BLOCK_REGISTRY[block_data["type"]]
        template = cls()
        metadata = block_data.get("parameter_metadata", {})
        first = True
        for key, value in block_data["params"].items():
            spec = template.param_specs[key]
            unit = f" {spec.unit}" if spec.unit else ""
            status = metadata.get(key, {}).get("status", "—")
            lines.append(
                "| "
                + " | ".join([
                    _md(block_data["name"] if first else ""),
                    _md(block_data.get("part_number", "") if first else ""),
                    _md(spec.label),
                    _md(f"{_format_value(value)}{unit}"),
                    _md(status),
                ])
                + " |"
            )
            first = False

    lines.extend(["", "## Scenario summary", ""])
    lines.extend([
        "| Scenario | Range (m) | RCS (dBsm) | TX attenuation (dB) | SNR (dB) | Maximum range (m) | Range resolution (m) | Beat frequency (kHz) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    for scenario in results["scenarios"]:
        overrides = scenario["overrides"]
        target = overrides.get("target", {})
        tx_att = overrides.get("tx_attenuator", {})
        metrics = scenario["metrics"]
        lines.append(
            "| "
            + " | ".join([
                _md(scenario["label"]),
                _format_number(target.get("distance_m")),
                _format_number(target.get("rcs_dbsm")),
                _format_number(tx_att.get("attenuation_db")),
                _format_number(metrics.get("snr_db")),
                _format_number(metrics.get("max_range_m")),
                _format_number(metrics.get("range_resolution_m")),
                _format_number(_divide(metrics.get("beat_freq_hz"), 1000.0)),
            ])
            + " |"
        )

    scenario_warnings = [
        (scenario["label"], warning)
        for scenario in results["scenarios"]
        for warning in scenario.get("warnings", [])
    ]
    if scenario_warnings:
        lines.extend(["", "### Scenario warnings", ""])
        for label, warning in scenario_warnings:
            lines.append(f"- **{_md(label)}:** {_md(warning)}")

    if results["open_definitions"]:
        lines.extend(["", "## Open definitions", ""])
        for item in results["open_definitions"]:
            note = f" — {item['note']}" if item.get("note") else ""
            lines.append(f"- **{_md(item['location'])}**{note}")

    for scenario in results["scenarios"]:
        lines.extend([
            "",
            f"## Link budget — {_md(scenario['label'])}",
            "",
            "| Stage | Part | Domain | Signal | Noise | SNR (dB) |",
            "| --- | --- | --- | ---: | ---: | ---: |",
        ])
        for row in scenario["budget"]:
            unit = row["unit"]
            lines.append(
                "| "
                + " | ".join([
                    _md(row["label"]),
                    _md(row.get("part_number", "")),
                    row["domain"],
                    f"{_format_number(row['signal_level'])} {unit}",
                    f"{_format_number(row['noise_level'])} {unit}",
                    _format_number(row["snr_db"]),
                ])
                + " |"
            )

    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _open_definitions(document: dict) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for key, value in document.get("analyses", {}).items():
        if key.endswith("_status") and value == "open":
            items.append({"location": f"analyses.{key[:-7]}"})
    for block in document.get("blocks", []):
        for key, metadata in block.get("parameter_metadata", {}).items():
            if metadata.get("status") == "open":
                item = {"location": f"{block['id']}.{key}"}
                if metadata.get("note"):
                    item["note"] = str(metadata["note"])
                items.append(item)
    return items


def _finite_values(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _finite_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_finite_values(item) for item in value]
    return value


def _format_value(value: Any) -> str:
    return (
        f"{value:g}"
        if isinstance(value, (int, float)) and not isinstance(value, bool)
        else str(value)
    )


def _format_number(value: Any) -> str:
    if value is None:
        return "—"
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _divide(value: Any, divisor: float) -> float | None:
    return None if value is None else value / divisor


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")

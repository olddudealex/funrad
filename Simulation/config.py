from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import blocks  # noqa: F401 - imports register all block classes
from graph.registry import _BLOCK_REGISTRY


CURRENT_SCHEMA_VERSION = 1
ENGINE_VERSION = "1.0"


class ConfigurationError(ValueError):
    def __init__(self, issues: list[str]):
        self.issues = issues
        super().__init__("Invalid ToyRadar configuration:\n- " + "\n- ".join(issues))


def configuration_hash(document: dict[str, Any]) -> str:
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_configuration(path: str | Path, *, require_connected: bool = True) -> tuple[dict, list[str]]:
    source = Path(path)
    with source.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    document, warnings = migrate_configuration(raw, source.name)
    validate_configuration(document, require_connected=require_connected)
    return document, warnings


def save_configuration(
    document: dict[str, Any], path: str | Path, *, require_connected: bool = False
) -> None:
    validate_configuration(document, require_connected=require_connected)
    destination = Path(path)
    with destination.open("w", encoding="utf-8") as handle:
        json.dump(document, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def migrate_configuration(raw: dict[str, Any], source_name: str = "legacy.toyradar") -> tuple[dict, list[str]]:
    if not isinstance(raw, dict):
        raise ConfigurationError(["Document root must be an object."])

    document = copy.deepcopy(raw)
    warnings: list[str] = []
    version = document.get("schema_version", 0)
    if version == CURRENT_SCHEMA_VERSION:
        return document, warnings
    if version != 0:
        raise ConfigurationError([
            f"Unsupported schema_version {version!r}; this engine supports {CURRENT_SCHEMA_VERSION}."
        ])

    warnings.append(
        f"{source_name}: legacy unversioned document migrated to schema version 1."
    )
    document["schema_version"] = CURRENT_SCHEMA_VERSION
    document.setdefault("design", {
        "name": Path(source_name).stem,
        "revision": "legacy",
        "description": "Migrated legacy ToyRadar configuration",
    })
    document.setdefault("environment", {
        "reference_temperature_k": 290.0,
        "rf_impedance_ohm": 50.0,
    })
    document.setdefault("analyses", {"snr_min_db": 10.0})
    document.setdefault("scenarios", [])

    for block_data in document.get("blocks", []):
        block_type = block_data.get("type", "")
        cls = _BLOCK_REGISTRY.get(block_type)
        if cls is None:
            continue
        template = cls()
        params = block_data.setdefault("params", {})
        block_data.setdefault("name", template.display_name)

        if block_type == "TargetBlock":
            for legacy_key in ("tx_antenna_gain_dbi", "rx_antenna_gain_dbi"):
                if legacy_key in params:
                    params.pop(legacy_key)
                    warnings.append(
                        f"{block_data.get('id', block_type)}: removed legacy {legacy_key}; "
                        "antenna blocks own antenna gain."
                    )
        if block_type == "MixerBlock" and "conversion_loss_db" in params:
            loss = float(params.pop("conversion_loss_db"))
            params["voltage_gain_db"] = -loss
            warnings.append(
                f"{block_data.get('id', block_type)}: converted conversion_loss_db={loss:g} "
                f"to voltage_gain_db={-loss:g}."
            )
        if block_type == "ADCBlock" and "full_scale_dbm" in params:
            dbm = float(params.pop("full_scale_dbm"))
            power_w = 10.0 ** ((dbm - 30.0) / 10.0)
            peak_v = math.sqrt(power_w * 50.0) * math.sqrt(2.0)
            params["full_scale_pm_v"] = peak_v
            warnings.append(
                f"{block_data.get('id', block_type)}: converted legacy full_scale_dbm={dbm:g} "
                f"at 50 ohm to full_scale_pm_v={peak_v:.6g}."
            )

        for key, default in template.params.items():
            if key not in params:
                params[key] = default
                warnings.append(
                    f"{block_data.get('id', block_type)}: filled missing parameter {key!r} "
                    f"with default {default!r}."
                )

    return document, warnings


def validate_configuration(document: dict[str, Any], *, require_connected: bool = True) -> None:
    issues: list[str] = []
    if document.get("schema_version") != CURRENT_SCHEMA_VERSION:
        issues.append(f"schema_version must be {CURRENT_SCHEMA_VERSION}.")

    design = document.get("design")
    if not isinstance(design, dict) or not isinstance(design.get("name"), str):
        issues.append("design.name must be a string.")

    environment = document.get("environment", {})
    if not isinstance(environment, dict):
        issues.append("environment must be an object.")
    else:
        for key in ("reference_temperature_k", "rf_impedance_ohm"):
            value = environment.get(key)
            if not _is_number(value) or value <= 0:
                issues.append(f"environment.{key} must be a positive number.")
        if _is_number(environment.get("reference_temperature_k")) and environment["reference_temperature_k"] != 290.0:
            issues.append("environment.reference_temperature_k must remain 290 K until the engine accepts it as runtime input.")
        if _is_number(environment.get("rf_impedance_ohm")) and environment["rf_impedance_ohm"] != 50.0:
            issues.append("environment.rf_impedance_ohm must remain 50 ohm until the engine accepts it as runtime input.")

    blocks_data = document.get("blocks")
    if not isinstance(blocks_data, list) or not blocks_data:
        issues.append("blocks must be a non-empty array.")
        blocks_data = []

    block_objects: dict[str, Any] = {}
    block_data_by_id: dict[str, dict] = {}
    for index, block_data in enumerate(blocks_data):
        where = f"blocks[{index}]"
        if not isinstance(block_data, dict):
            issues.append(f"{where} must be an object.")
            continue
        block_id = block_data.get("id")
        block_type = block_data.get("type")
        if not isinstance(block_id, str) or not block_id:
            issues.append(f"{where}.id must be a non-empty string.")
            continue
        if block_id in block_objects:
            issues.append(f"Duplicate block id {block_id!r}.")
            continue
        cls = _BLOCK_REGISTRY.get(block_type)
        if cls is None:
            issues.append(f"{where}.type {block_type!r} is not registered.")
            continue
        block = cls(block_id=block_id)
        block_objects[block_id] = block
        block_data_by_id[block_id] = block_data
        if not isinstance(block_data.get("name"), str) or not block_data.get("name"):
            issues.append(f"{where}.name must be a non-empty string.")

        params = block_data.get("params")
        if not isinstance(params, dict):
            issues.append(f"{where}.params must be an object.")
            continue
        unknown = sorted(set(params) - set(block.params))
        missing = sorted(set(block.params) - set(params))
        if unknown:
            issues.append(f"{where}.params has unknown keys: {', '.join(unknown)}.")
        if missing:
            issues.append(f"{where}.params is missing: {', '.join(missing)}.")
        for key in set(params) & set(block.params):
            _validate_parameter(issues, f"{where}.params.{key}", params[key], block.param_specs[key])

        metadata = block_data.get("parameter_metadata", {})
        if not isinstance(metadata, dict):
            issues.append(f"{where}.parameter_metadata must be an object.")
        else:
            for key, item in metadata.items():
                if key not in block.params:
                    issues.append(f"{where}.parameter_metadata refers to unknown parameter {key!r}.")
                if not isinstance(item, dict):
                    issues.append(f"{where}.parameter_metadata.{key} must be an object.")
                    continue
                status = item.get("status")
                if status not in {None, "chosen", "working", "provisional", "open", "measured"}:
                    issues.append(f"{where}.parameter_metadata.{key}.status is invalid.")

    connections = document.get("connections")
    if not isinstance(connections, list):
        issues.append("connections must be an array.")
        connections = []
    destination_ports: set[tuple[str, str]] = set()
    adjacency: dict[str, list[str]] = {block_id: [] for block_id in block_objects}
    connected_inputs: set[tuple[str, str]] = set()
    for index, connection in enumerate(connections):
        where = f"connections[{index}]"
        if not isinstance(connection, dict):
            issues.append(f"{where} must be an object.")
            continue
        src_id = connection.get("src_block")
        dst_id = connection.get("dst_block")
        src_name = connection.get("src_port")
        dst_name = connection.get("dst_port")
        src = block_objects.get(src_id)
        dst = block_objects.get(dst_id)
        if src is None:
            issues.append(f"{where}.src_block {src_id!r} does not exist.")
        if dst is None:
            issues.append(f"{where}.dst_block {dst_id!r} does not exist.")
        if src is None or dst is None:
            continue
        src_port = src.get_port(src_name)
        dst_port = dst.get_port(dst_name)
        if src_port is None or src_port.direction != "output":
            issues.append(f"{where}.src_port {src_name!r} is not an output of {src_id!r}.")
            continue
        if dst_port is None or dst_port.direction != "input":
            issues.append(f"{where}.dst_port {dst_name!r} is not an input of {dst_id!r}.")
            continue
        if not _ports_compatible(src_port.port_type, dst_port.port_type):
            issues.append(
                f"{where} connects incompatible domains {src_port.port_type!r} -> "
                f"{dst_port.port_type!r}."
            )
        destination = (dst_id, dst_name)
        if destination in destination_ports:
            issues.append(f"{where} duplicates destination {dst_id}.{dst_name}.")
        destination_ports.add(destination)
        connected_inputs.add(destination)
        adjacency[src_id].append(dst_id)

    if require_connected:
        for block_id, block in block_objects.items():
            for port in block.input_ports():
                if port.required and (block_id, port.name) not in connected_inputs:
                    issues.append(f"Required input {block_id}.{port.name} is not connected.")

    if _has_cycle(adjacency):
        issues.append("Connection graph contains a cycle.")

    scenarios = document.get("scenarios", [])
    if not isinstance(scenarios, list):
        issues.append("scenarios must be an array.")
    else:
        seen_scenarios: set[str] = set()
        for index, scenario in enumerate(scenarios):
            where = f"scenarios[{index}]"
            if not isinstance(scenario, dict):
                issues.append(f"{where} must be an object.")
                continue
            scenario_id = scenario.get("id")
            if not isinstance(scenario_id, str) or not scenario_id:
                issues.append(f"{where}.id must be a non-empty string.")
            elif scenario_id in seen_scenarios:
                issues.append(f"Duplicate scenario id {scenario_id!r}.")
            else:
                seen_scenarios.add(scenario_id)
            overrides = scenario.get("overrides", {})
            if not isinstance(overrides, dict):
                issues.append(f"{where}.overrides must be an object.")
                continue
            for block_id, params in overrides.items():
                block = block_objects.get(block_id)
                if block is None:
                    issues.append(f"{where}.overrides refers to unknown block {block_id!r}.")
                    continue
                if not isinstance(params, dict):
                    issues.append(f"{where}.overrides.{block_id} must be an object.")
                    continue
                for key, value in params.items():
                    spec = block.param_specs.get(key)
                    if spec is None:
                        issues.append(f"{where}.overrides.{block_id} has unknown parameter {key!r}.")
                    else:
                        _validate_parameter(issues, f"{where}.overrides.{block_id}.{key}", value, spec)

    analyses = document.get("analyses", {})
    if not isinstance(analyses, dict):
        issues.append("analyses must be an object.")
    elif not _is_number(analyses.get("snr_min_db", 10.0)):
        issues.append("analyses.snr_min_db must be numeric.")

    if issues:
        raise ConfigurationError(issues)


def _validate_parameter(issues: list[str], where: str, value: Any, spec: Any) -> None:
    expected = spec.value_type
    if expected is float:
        valid_type = _is_number(value)
    elif expected is int:
        valid_type = isinstance(value, int) and not isinstance(value, bool)
    else:
        valid_type = isinstance(value, expected)
    if not valid_type:
        issues.append(f"{where} must be {expected.__name__}.")
        return
    if spec.choices and value not in spec.choices:
        issues.append(f"{where} must be one of {', '.join(spec.choices)}.")
    if _is_number(value):
        if spec.minimum is not None and value < spec.minimum:
            issues.append(f"{where} must be >= {spec.minimum}.")
        if spec.maximum is not None and value > spec.maximum:
            issues.append(f"{where} must be <= {spec.maximum}.")
        if where.rsplit(".", 1)[-1] in {
            "distance_m", "center_freq_ghz", "bandwidth_mhz", "chirp_duration_ms",
            "simulation_time_ms", "sample_rate_mhz", "cutoff_hz", "full_scale_pm_v",
        } and value <= 0:
            issues.append(f"{where} must be > 0.")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _ports_compatible(source: str, destination: str) -> bool:
    return source == destination or (source, destination) in {
        ("rf", "lo"),
        ("coupled", "lo"),
    }


def _has_cycle(adjacency: dict[str, list[str]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        if any(visit(neighbour) for neighbour in adjacency.get(node, [])):
            return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in adjacency)

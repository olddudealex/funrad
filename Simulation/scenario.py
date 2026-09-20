from __future__ import annotations

from copy import deepcopy
import re
from typing import Any


BASE_SCENARIO_LABEL = "Base configuration"


def apply_overrides(document: dict[str, Any], overrides: dict[str, Any]) -> None:
    """Apply block-parameter overrides to a configuration document in place."""
    blocks = {block["id"]: block for block in document["blocks"]}
    for block_id, params in overrides.items():
        blocks[block_id]["params"].update(deepcopy(params))


def effective_configuration(
    document: dict[str, Any], scenario_id: str | None
) -> dict[str, Any]:
    """Return base configuration merged with one scenario's overrides."""
    effective = deepcopy(document)
    if scenario_id is None:
        return effective
    scenario = next(
        (item for item in effective.get("scenarios", []) if item["id"] == scenario_id),
        None,
    )
    if scenario is None:
        raise KeyError(f"Unknown scenario {scenario_id!r}.")
    apply_overrides(effective, scenario.get("overrides", {}))
    return effective


class ConfigurationSession:
    """Canonical base document plus the scenario currently shown by the GUI."""

    def __init__(self, document: dict[str, Any]):
        self.document = deepcopy(document)
        self.active_scenario_id: str | None = None

    def load(self, document: dict[str, Any]) -> None:
        self.document = deepcopy(document)
        self.active_scenario_id = None

    def scenarios(self) -> list[tuple[str | None, str]]:
        return [(None, BASE_SCENARIO_LABEL)] + [
            (item["id"], item.get("label", item["id"]))
            for item in self.document.get("scenarios", [])
        ]

    def select(self, scenario_id: str | None) -> None:
        if scenario_id is not None and not any(
            item["id"] == scenario_id for item in self.document.get("scenarios", [])
        ):
            raise KeyError(f"Unknown scenario {scenario_id!r}.")
        self.active_scenario_id = scenario_id

    def add_scenario(self, label: str, *, copy_active: bool = True) -> str:
        label = label.strip()
        if not label:
            raise ValueError("Scenario name cannot be empty.")
        used_ids = {item["id"] for item in self.document.get("scenarios", [])}
        stem = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_") or "scenario"
        scenario_id = stem
        number = 2
        while scenario_id in used_ids:
            scenario_id = f"{stem}_{number}"
            number += 1

        overrides: dict[str, Any] = {}
        active = self._active_scenario()
        if copy_active and active is not None:
            overrides = deepcopy(active.get("overrides", {}))
        self.document.setdefault("scenarios", []).append({
            "id": scenario_id,
            "label": label,
            "overrides": overrides,
        })
        self.active_scenario_id = scenario_id
        return scenario_id

    def delete_active_scenario(self) -> str:
        if self.active_scenario_id is None:
            raise ValueError("The base configuration cannot be deleted.")
        deleted_id = self.active_scenario_id
        self.document["scenarios"] = [
            item for item in self.document.get("scenarios", [])
            if item["id"] != deleted_id
        ]
        self.active_scenario_id = None
        return deleted_id

    def effective_document(self) -> dict[str, Any]:
        return effective_configuration(self.document, self.active_scenario_id)

    def base_params(self, block_id: str) -> dict[str, Any]:
        return deepcopy(self._block(block_id)["params"])

    def override_keys(self, block_id: str) -> set[str]:
        scenario = self._active_scenario()
        if scenario is None:
            return set()
        return set(scenario.get("overrides", {}).get(block_id, {}))

    def set_parameter(self, block_id: str, key: str, value: Any) -> None:
        if self.active_scenario_id is None:
            self._block(block_id)["params"][key] = deepcopy(value)
            return
        scenario = self._active_scenario()
        assert scenario is not None
        scenario.setdefault("overrides", {}).setdefault(block_id, {})[key] = deepcopy(value)

    def reset_override(self, block_id: str, key: str) -> None:
        scenario = self._active_scenario()
        if scenario is None:
            return
        block_overrides = scenario.get("overrides", {}).get(block_id)
        if not block_overrides:
            return
        block_overrides.pop(key, None)
        if not block_overrides:
            scenario["overrides"].pop(block_id, None)

    def promote_block_overrides(self, block_id: str) -> None:
        """Move all active overrides for one block into its base parameters."""
        scenario = self._active_scenario()
        if scenario is None:
            return
        block_overrides = scenario.get("overrides", {}).get(block_id)
        if not block_overrides:
            return
        self._block(block_id)["params"].update(deepcopy(block_overrides))
        scenario["overrides"].pop(block_id, None)

    def sync_graph_structure(self, graph_document: dict[str, Any]) -> None:
        """Copy topology/layout from the effective graph without leaking overrides to base."""
        existing = {block["id"]: block for block in self.document.get("blocks", [])}
        merged_blocks: list[dict[str, Any]] = []
        structural_keys = (
            "type", "id", "name", "pos", "mirrored", "part_number", "role",
            "parameter_metadata",
        )
        for graph_block in graph_document.get("blocks", []):
            source_block = existing.get(graph_block["id"])
            if source_block is None:
                merged_blocks.append(deepcopy(graph_block))
                continue
            merged = deepcopy(source_block)
            for key in structural_keys:
                if key in graph_block:
                    merged[key] = deepcopy(graph_block[key])
                elif key in {"part_number", "role", "parameter_metadata"}:
                    merged.pop(key, None)
            if self.active_scenario_id is None:
                merged["params"] = deepcopy(graph_block["params"])
            merged_blocks.append(merged)

        live_ids = {block["id"] for block in merged_blocks}
        self.document["blocks"] = merged_blocks
        self.document["connections"] = deepcopy(graph_document.get("connections", []))
        for scenario in self.document.get("scenarios", []):
            overrides = scenario.get("overrides", {})
            for block_id in list(overrides):
                if block_id not in live_ids:
                    overrides.pop(block_id)

    def _block(self, block_id: str) -> dict[str, Any]:
        block = next(
            (item for item in self.document.get("blocks", []) if item["id"] == block_id),
            None,
        )
        if block is None:
            raise KeyError(f"Unknown block {block_id!r}.")
        return block

    def _active_scenario(self) -> dict[str, Any] | None:
        if self.active_scenario_id is None:
            return None
        return next(
            item for item in self.document.get("scenarios", [])
            if item["id"] == self.active_scenario_id
        )

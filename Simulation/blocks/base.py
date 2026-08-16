from __future__ import annotations
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, NamedTuple

import numpy as np

from physics.signal import SignalState


class PlotData(NamedTuple):
    title: str
    x_label: str
    y_label: str
    x: np.ndarray
    y: np.ndarray
    extra_series: list = []          # list of (label, x, y) for additional lines
    x_view: tuple | None = None      # (x_min, x_max) in x-axis units; None = fit


@dataclass
class Port:
    name: str
    direction: str    # "input" | "output"
    port_type: str    # "rf" | "lo" | "if" | "coupled"
    dpg_attr_id: int = 0


class Block(ABC):
    """Base class for all radar signal chain blocks."""

    display_name: str = "Block"
    category: str = "Generic"
    model_help: str = ""       # shown in property panel "Model description" section

    def __init__(self, block_id: str | None = None):
        self.block_id: str = block_id or str(uuid.uuid4())
        self.params: dict[str, Any] = {}
        self.param_options: dict[str, list[str]] = {}  # key → allowed values → renders as combo
        self.param_labels: dict[str, str] = {}         # key → override display label in property panel
        self.ports: list[Port] = []
        self.node_id: int = 0          # DPG node widget ID, set on draw
        self._dpg_pos: tuple[int, int] = (50, 50)
        self.mirrored: bool = False    # flip input/output pin sides on canvas
        self._setup_ports()
        self._setup_params()

    @abstractmethod
    def _setup_ports(self):
        """Define self.ports."""

    @abstractmethod
    def _setup_params(self):
        """Populate self.params with default values."""

    @abstractmethod
    def process(self, inputs: dict[str, SignalState]) -> dict[str, SignalState]:
        """Pure function. inputs/outputs are keyed by port name."""

    def get_plot_data(self, output_signal: SignalState) -> PlotData:
        """Single fallback plot. Prefer overriding get_plots()."""
        x = np.array([output_signal.center_freq_hz / 1e9])
        y = np.array([output_signal.power_dbm])
        return PlotData(
            title=f"{self.display_name} — output power",
            x_label="Frequency (GHz)",
            y_label="Power (dBm)",
            x=x, y=y,
        )

    def get_plots(self, output_signal: SignalState) -> dict[str, PlotData]:
        """Return all available plots keyed by tab label. Override for multiple."""
        return {"Signal": self.get_plot_data(output_signal)}

    def input_ports(self) -> list[Port]:
        return [p for p in self.ports if p.direction == "input"]

    def output_ports(self) -> list[Port]:
        return [p for p in self.ports if p.direction == "output"]

    def get_port(self, name: str) -> Port | None:
        return next((p for p in self.ports if p.name == name), None)

    def to_dict(self) -> dict:
        return {
            "type": type(self).__name__,
            "id": self.block_id,
            "pos": list(self._dpg_pos),
            "mirrored": self.mirrored,
            "params": self.params.copy(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> Block:
        obj = cls(block_id=d["id"])
        obj._dpg_pos = tuple(d.get("pos", [50, 50]))
        obj.mirrored = bool(d.get("mirrored", False))
        for k, v in d.get("params", {}).items():
            if k in obj.params:
                obj.params[k] = v
        return obj


class SingleIOBlock(Block):
    """Convenience mixin: one 'rf_in' input, one 'rf_out' output."""

    def _setup_ports(self):
        self.ports = [
            Port("rf_in", "input", "rf"),
            Port("rf_out", "output", "rf"),
        ]

    def process(self, inputs: dict[str, SignalState]) -> dict[str, SignalState]:
        sig = inputs.get("rf_in", SignalState())
        out = self.transform(sig)
        return {"rf_out": out}

    @abstractmethod
    def transform(self, sig: SignalState) -> SignalState:
        """Apply this block's transformation to a single SignalState."""

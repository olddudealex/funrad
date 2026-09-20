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
    required: bool = True


@dataclass(frozen=True)
class ParameterSpec:
    """Machine-readable definition shared by the GUI and file validator."""

    key: str
    label: str
    value_type: type
    unit: str = ""
    minimum: float | int | None = None
    maximum: float | int | None = None
    choices: tuple[str, ...] = ()
    description: str = ""


_UNIT_SUFFIXES = (
    ("_dbc_hz", "dBc/Hz"),
    ("_ghz", "GHz"),
    ("_mhz", "MHz"),
    ("_khz", "kHz"),
    ("_hz", "Hz"),
    ("_dbsm", "dBsm"),
    ("_dbm", "dBm"),
    ("_dbv", "dBV"),
    ("_dbi", "dBi"),
    ("_db", "dB"),
    ("_ms", "ms"),
    ("_pm_v", "V peak"),
    ("_v", "V"),
    ("_m", "m"),
    ("_k", "K"),
)


def _infer_parameter_spec(block: "Block", key: str, value: Any) -> ParameterSpec:
    unit = ""
    label_key = key
    for suffix, candidate in _UNIT_SUFFIXES:
        if key.endswith(suffix):
            unit = candidate
            label_key = key[:-len(suffix)]
            break

    minimum: float | int | None = None
    maximum: float | int | None = None
    if key in {"bits", "dac_bits"}:
        minimum, maximum, unit = 1, 32, "bit"
    elif key in {"order"}:
        minimum, maximum = 1, 20
    elif key in {"nfft"}:
        minimum, maximum = 1, 16_777_216
    elif key in {"distance_m", "center_freq_ghz", "bandwidth_mhz",
                 "chirp_duration_ms", "simulation_time_ms", "sample_rate_mhz",
                 "cutoff_hz", "full_scale_pm_v"}:
        minimum = 0.0
    elif key in {"nf_db", "insertion_loss_db", "through_loss_db", "coupling_db"}:
        minimum = 0.0

    choices = tuple(block.param_options.get(key, ()))
    if key in block.param_labels:
        label = block.param_labels[key]
    else:
        words = label_key.split("_")
        replacements = {
            "freq": "Frequency",
            "nf": "Noise Figure",
            "rcs": "RCS",
            "lo": "LO",
            "iq": "I/Q",
            "dac": "DAC",
            "nfft": "FFT Length",
        }
        label = " ".join(replacements.get(word, word.title()) for word in words)
    if unit and unit.lower() not in label.lower():
        label = f"{label} ({unit})"
    return ParameterSpec(
        key=key,
        label=label,
        value_type=type(value),
        unit=unit,
        minimum=minimum,
        maximum=maximum,
        choices=choices,
    )


class Block(ABC):
    """Base class for all radar signal chain blocks."""

    display_name: str = "Block"
    category: str = "Generic"
    model_help: str = ""       # shown in property panel "Model description" section

    def __init__(self, block_id: str | None = None):
        self.block_id: str = block_id or str(uuid.uuid4())
        self.instance_name: str = self.display_name
        self.part_number: str = ""
        self.role: str = ""
        self.params: dict[str, Any] = {}
        self.param_options: dict[str, list[str]] = {}  # key → allowed values → renders as combo
        self.param_labels: dict[str, str] = {}         # key → override display label in property panel
        self.parameter_metadata: dict[str, dict[str, Any]] = {}
        self.param_specs: dict[str, ParameterSpec] = {}
        self.ports: list[Port] = []
        self.node_id: int = 0          # DPG node widget ID, set on draw
        self._dpg_pos: tuple[int, int] = (50, 50)
        self.mirrored: bool = False    # flip input/output pin sides on canvas
        self._setup_ports()
        self._setup_params()
        self.param_specs = {
            key: _infer_parameter_spec(self, key, value)
            for key, value in self.params.items()
        }

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
        result = {
            "type": type(self).__name__,
            "id": self.block_id,
            "name": self.instance_name,
            "pos": list(self._dpg_pos),
            "mirrored": self.mirrored,
            "params": self.params.copy(),
        }
        if self.part_number:
            result["part_number"] = self.part_number
        if self.role:
            result["role"] = self.role
        if self.parameter_metadata:
            result["parameter_metadata"] = self.parameter_metadata.copy()
        return result

    @classmethod
    def from_dict(cls, d: dict) -> Block:
        obj = cls(block_id=d["id"])
        obj.instance_name = str(d.get("name", obj.display_name))
        obj.part_number = str(d.get("part_number", ""))
        obj.role = str(d.get("role", ""))
        obj._dpg_pos = tuple(d.get("pos", [50, 50]))
        obj.mirrored = bool(d.get("mirrored", False))
        obj.parameter_metadata = dict(d.get("parameter_metadata", {}))
        for k, v in d.get("params", {}).items():
            if k in obj.params:
                expected = obj.param_specs[k].value_type
                obj.params[k] = float(v) if expected is float else v
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

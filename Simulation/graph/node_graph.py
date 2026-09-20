from __future__ import annotations
import math
from copy import deepcopy
from collections import defaultdict, deque
from dataclasses import dataclass

from physics.signal import SignalState
from physics.radar_equation import (
    range_resolution_m, max_unambiguous_velocity_ms,
)
from blocks.base import Block
from .connection import Connection
from .registry import _BLOCK_REGISTRY


@dataclass
class RadarMetrics:
    range_resolution_m: float = 0.0
    max_range_m: float = 0.0
    max_doppler_velocity_ms: float = 0.0
    beat_freq_hz: float = 0.0
    snr_db: float = 0.0
    bandwidth_hz: float = 0.0
    center_freq_hz: float = 0.0
    chirp_duration_s: float = 0.0


class NodeGraph:
    """Manages all blocks and their connections; runs the simulation."""

    def __init__(self):
        self.blocks: dict[str, Block] = {}
        self.connections: list[Connection] = []
        self._last_signals: dict[str, dict[str, SignalState]] = {}
        self.document_metadata: dict = {
            "schema_version": 1,
            "design": {"name": "Untitled", "revision": "working"},
            "environment": {
                "reference_temperature_k": 290.0,
                "rf_impedance_ohm": 50.0,
            },
            "scenarios": [],
            "analyses": {"snr_min_db": 10.0},
        }
        self.load_warnings: list[str] = []

    # ------------------------------------------------------------------
    # Block management
    # ------------------------------------------------------------------

    def add_block(self, block: Block):
        self.blocks[block.block_id] = block

    def remove_block(self, block_id: str):
        self.blocks.pop(block_id, None)
        self.connections = [
            c for c in self.connections
            if c.src_block_id != block_id and c.dst_block_id != block_id
        ]
        self._last_signals.pop(block_id, None)
        for scenario in self.document_metadata.get("scenarios", []):
            overrides = scenario.get("overrides", {})
            if isinstance(overrides, dict):
                overrides.pop(block_id, None)

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(self, src_block_id: str, src_port: str,
                dst_block_id: str, dst_port: str,
                dpg_link_id: int = 0) -> Connection:
        # Remove any existing connection to the same destination port
        self.connections = [
            c for c in self.connections
            if not (c.dst_block_id == dst_block_id and c.dst_port_name == dst_port)
        ]
        conn = Connection(src_block_id, src_port, dst_block_id, dst_port, dpg_link_id)
        self.connections.append(conn)
        return conn

    def disconnect_by_dpg_link(self, dpg_link_id: int):
        self.connections = [c for c in self.connections if c.dpg_link_id != dpg_link_id]

    def disconnect(self, src_block_id: str, src_port: str,
                   dst_block_id: str, dst_port: str):
        self.connections = [
            c for c in self.connections
            if not (c.src_block_id == src_block_id and c.src_port_name == src_port
                    and c.dst_block_id == dst_block_id and c.dst_port_name == dst_port)
        ]

    def get_connection_to(self, dst_block_id: str,
                          dst_port: str) -> Connection | None:
        return next(
            (c for c in self.connections
             if c.dst_block_id == dst_block_id and c.dst_port_name == dst_port),
            None,
        )

    # ------------------------------------------------------------------
    # Topological sort (Kahn's algorithm)
    # ------------------------------------------------------------------

    def topological_sort(self) -> list[Block]:
        in_degree: dict[str, int] = {bid: 0 for bid in self.blocks}
        adj: dict[str, list[str]] = defaultdict(list)

        for c in self.connections:
            if c.src_block_id in self.blocks and c.dst_block_id in self.blocks:
                adj[c.src_block_id].append(c.dst_block_id)
                in_degree[c.dst_block_id] += 1

        queue = deque(bid for bid, deg in in_degree.items() if deg == 0)
        order = []
        while queue:
            bid = queue.popleft()
            order.append(bid)
            for neighbour in adj[bid]:
                in_degree[neighbour] -= 1
                if in_degree[neighbour] == 0:
                    queue.append(neighbour)

        if len(order) != len(self.blocks):
            raise ValueError("Cycle detected in node graph — cannot run simulation.")

        return [self.blocks[bid] for bid in order]

    # ------------------------------------------------------------------
    # Simulation
    # ------------------------------------------------------------------

    def run(self, *, strict: bool = False) -> dict[str, dict[str, SignalState]]:
        """Run all blocks in topological order. Returns {block_id: {port: signal}}."""
        sorted_blocks = self.topological_sort()
        signals: dict[str, dict[str, SignalState]] = {}

        for block in sorted_blocks:
            # Gather inputs from connected upstream ports
            inputs: dict[str, SignalState] = {}
            for port in block.input_ports():
                conn = self.get_connection_to(block.block_id, port.name)
                if conn and conn.src_block_id in signals:
                    src_outputs = signals[conn.src_block_id]
                    if conn.src_port_name in src_outputs:
                        inputs[port.name] = src_outputs[conn.src_port_name]

            try:
                outputs = block.process(inputs)
            except Exception as e:
                if strict:
                    raise RuntimeError(
                        f"Block {block.instance_name!r} ({block.block_id}) failed: {e}"
                    ) from e
                outputs = {}
                print(f"[NodeGraph] Error in block {block.instance_name}: {e}")

            signals[block.block_id] = outputs

        self._last_signals = signals
        return signals

    def run_to(self, block_id: str) -> dict[str, SignalState] | None:
        """Run only up to and including the specified block."""
        try:
            sorted_blocks = self.topological_sort()
        except ValueError:
            return None

        signals: dict[str, dict[str, SignalState]] = {}
        for block in sorted_blocks:
            inputs: dict[str, SignalState] = {}
            for port in block.input_ports():
                conn = self.get_connection_to(block.block_id, port.name)
                if conn and conn.src_block_id in signals:
                    src_outputs = signals[conn.src_block_id]
                    if conn.src_port_name in src_outputs:
                        inputs[port.name] = src_outputs[conn.src_port_name]
            try:
                outputs = block.process(inputs)
            except Exception as e:
                outputs = {}
                print(f"[NodeGraph] Error in block {block.instance_name}: {e}")
            signals[block.block_id] = outputs
            if block.block_id == block_id:
                break

        return signals.get(block_id)

    def get_last_signal(self, block_id: str) -> dict[str, SignalState] | None:
        return self._last_signals.get(block_id)

    _BUDGET_PORT_PREF = ("rf_out", "range_out", "I_out", "through")

    def get_power_budget(self) -> list[dict]:
        """Signal power and noise floor at each stage in topological order."""
        if not self._last_signals:
            return []
        try:
            sorted_blocks = self.topological_sort()
        except ValueError:
            return []
        budget = []
        seen: dict[str, int] = {}
        for block in sorted_blocks:
            outputs = self._last_signals.get(block.block_id, {})
            if not outputs:
                continue
            sig = None
            for p in self._BUDGET_PORT_PREF:
                if p in outputs:
                    sig = outputs[p]
                    break
            if sig is None:
                sig = next(iter(outputs.values()))
            name = block.instance_name
            n = seen.get(name, 0) + 1
            seen[name] = n
            label = f"{name} {n}" if n > 1 else name
            snr = sig.power_dbm - sig.noise_floor_dbm
            is_if = math.isfinite(sig.voltage_dbv)
            budget.append({
                "block_id":     block.block_id,
                "block_type":   type(block).__name__,
                "label":        label,
                "part_number":  block.part_number,
                "signal_level": sig.voltage_dbv if is_if else sig.power_dbm,
                "noise_level":  (sig.voltage_dbv - snr) if is_if else sig.noise_floor_dbm,
                "snr_db":       snr,
                "unit":         "dBV" if is_if else "dBm",
                "domain":       "IF" if is_if else "RF",
            })
        return budget

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def compute_metrics(self, snr_min_db: float | None = None) -> RadarMetrics:
        """Derive radar performance metrics from the last simulation run."""
        if not self._last_signals:
            self.run()

        # Prefer RangeFFT output (post-FFT SNR), fall back to ADC, then last block.
        from blocks.dsp import RangeFFTBlock
        from blocks.rx_path import ADCBlock
        adc_signal: SignalState | None = None

        for bid, block in self.blocks.items():
            if isinstance(block, RangeFFTBlock) and bid in self._last_signals:
                outputs = self._last_signals[bid]
                sig = outputs.get("range_out") or next(iter(outputs.values()), None)
                if sig is not None:
                    adc_signal = sig
                    break

        if adc_signal is None:
            for bid, block in self.blocks.items():
                if isinstance(block, ADCBlock) and bid in self._last_signals:
                    outputs = self._last_signals[bid]
                    adc_signal = next(iter(outputs.values()), None)
                    break

        if adc_signal is None:
            # Fall back to last non-empty output
            for bid in reversed(list(self._last_signals.keys())):
                outputs = self._last_signals[bid]
                if outputs:
                    adc_signal = next(iter(outputs.values()))
                    break

        if adc_signal is None:
            return RadarMetrics()

        rr = range_resolution_m(adc_signal.chirp_bandwidth_hz)
        # Triangular chirp: T_rep = 2 × T_chirp (up-ramp to next up-ramp)
        T_rep = 2.0 * adc_signal.chirp_duration_s
        v_max = max_unambiguous_velocity_ms(T_rep, adc_signal.carrier_freq_hz)

        from blocks.target import TargetBlock
        target_block = next(
            (b for b in self.blocks.values() if isinstance(b, TargetBlock)), None
        )
        if target_block is not None and adc_signal.snr_db > -200:
            if snr_min_db is None:
                snr_min_db = float(
                    self.document_metadata.get("analyses", {}).get("snr_min_db", 10.0)
                )
            r = float(target_block.params["distance_m"])
            mr = r * 10.0 ** ((adc_signal.snr_db - snr_min_db) / 40.0)
        else:
            mr = 0.0

        # ADC dead-zone constraint: signal voltage must exceed ½ LSB.
        # Use the ADC block's own per-channel output voltage — NOT adc_signal
        # (which may be IQ-combined by RangeFFT and carry a spurious +3 dB).
        adc_block = next((b for b in self.blocks.values() if isinstance(b, ADCBlock)), None)
        if adc_block is not None and target_block is not None:
            adc_outs = self._last_signals.get(adc_block.block_id, {})
            adc_ch = adc_outs.get("I_out") or next(iter(adc_outs.values()), None)
            if adc_ch is not None and math.isfinite(adc_ch.voltage_dbv):
                bits = int(adc_block.params["bits"])
                fs_v = float(adc_block.params["full_scale_pm_v"])
                lsb_half_dbv = 20.0 * math.log10(fs_v / (2 ** bits))
                r_adc = float(target_block.params["distance_m"]) * 10.0 ** (
                    (adc_ch.voltage_dbv - lsb_half_dbv) / 40.0)
                mr = min(mr, r_adc)

        return RadarMetrics(
            range_resolution_m=rr,
            max_range_m=mr,
            max_doppler_velocity_ms=v_max,
            beat_freq_hz=adc_signal.beat_freq_hz,
            snr_db=adc_signal.snr_db,
            bandwidth_hz=adc_signal.chirp_bandwidth_hz,
            center_freq_hz=adc_signal.carrier_freq_hz,
            chirp_duration_s=adc_signal.chirp_duration_s,
        )

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        result = deepcopy(self.document_metadata)
        result.update({
            "blocks": [b.to_dict() for b in self.blocks.values()],
            "connections": [c.to_dict() for c in self.connections],
        })
        return result

    def from_dict(self, d: dict):
        self.blocks.clear()
        self.connections.clear()
        self._last_signals.clear()
        self.document_metadata = {
            key: deepcopy(value)
            for key, value in d.items()
            if key not in {"blocks", "connections"}
        }

        for bd in d.get("blocks", []):
            cls_name = bd.get("type", "")
            cls = _BLOCK_REGISTRY.get(cls_name)
            if cls is None:
                raise ValueError(f"Unknown block type '{cls_name}'.")
            block = cls.from_dict(bd)
            self.blocks[block.block_id] = block

        for cd in d.get("connections", []):
            conn = Connection.from_dict(cd)
            self.connections.append(conn)

    def save_to_file(self, path: str):
        from config import save_configuration

        save_configuration(self.to_dict(), path, require_connected=False)

    def load_from_file(self, path: str):
        from config import load_configuration

        document, warnings = load_configuration(path, require_connected=False)
        self.from_dict(document)
        self.load_warnings = warnings
        return warnings

    def clear(self):
        self.blocks.clear()
        self.connections.clear()
        self._last_signals.clear()
        self.load_warnings.clear()

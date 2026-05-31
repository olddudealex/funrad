from __future__ import annotations
import dearpygui.dearpygui as dpg
from graph.node_graph import RadarMetrics


class MetricsPanel:
    """Top bar displaying radar performance metrics."""

    _INFO_WIN = "metric_info_win"

    _THEORY: dict[str, tuple[str, str]] = {
        "range_res": (
            "Range Resolution",
            "dR = c / (2 * B)\n\n"
            "The minimum distance between two distinguishable targets.\n"
            "A chirp of bandwidth B defines a time-frequency cell of width 1/B.\n"
            "The factor 2 accounts for the round-trip propagation.\n\n"
            "Variables:\n"
            "  c  = 299 792 458 m/s   (speed of light)\n"
            "  B  = chirp bandwidth (Hz)",
        ),
        "max_range": (
            "Maximum Detection Range",
            "R_max = R * 10^( (SNR - SNR_min) / 40 )\n\n"
            "Derived from the radar range equation: SNR ~ 1/R^4.\n"
            "If the simulated chain detects the target at range R with SNR (dB),\n"
            "the maximum detectable range scales with the fourth root of SNR margin.\n\n"
            "Variables:\n"
            "  R        = actual target range in the simulation (m)\n"
            "  SNR      = signal-to-noise ratio at ADC output (dB)\n"
            "  SNR_min  = 10 dB  (minimum SNR required for detection)",
        ),
        "doppler_res": (
            "Maximum Unambiguous Velocity",
            "v_max = c / (4 * fc * T_rep)\n\n"
            "Phase between consecutive chirps encodes target velocity:\n"
            "  dphi = 4*pi * v * T_rep / lambda\n"
            "Nyquist limit: |dphi| < pi  ->  |v| < lambda / (4 * T_rep).\n"
            "Faster targets alias to a lower apparent velocity.\n\n"
            "Variables:\n"
            "  c      = speed of light (m/s)\n"
            "  fc     = carrier frequency (Hz)\n"
            "  T_rep  = chirp repetition interval\n"
            "         = 2 * T_chirp  for a triangular waveform",
        ),
        "snr": (
            "Signal-to-Noise Ratio",
            "SNR = P_signal - P_noise   (dB)\n\n"
            "Difference between signal power and noise floor at the ADC.\n"
            "Both are tracked through the full processing chain:\n"
            "  * amplifiers increase signal and noise equally\n"
            "  * noise figure adds excess noise at each stage\n"
            "  * ADC quantisation adds quantisation noise\n\n"
            "Variables:\n"
            "  P_signal  = signal power at ADC input (dBm)\n"
            "  P_noise   = kTB + cumulative noise figure (dBm)",
        ),
        "beat_freq": (
            "Beat Frequency",
            "f_beat = 2*R * (B / T) / c\n\n"
            "The reflected chirp arrives with round-trip delay tau = 2R/c.\n"
            "Mixing the transmitted and received chirps produces a constant\n"
            "difference frequency equal to the sweep rate * delay.\n\n"
            "Variables:\n"
            "  R  = target distance (m)\n"
            "  B  = chirp bandwidth (Hz)\n"
            "  T  = chirp ramp duration (s)\n"
            "  c  = speed of light (m/s)",
        ),
    }

    def __init__(self):
        self._tags: dict[str, int | str] = {}

    def build(self, parent: int | str):
        with dpg.group(horizontal=True, parent=parent):
            dpg.add_text("Metrics:", color=(200, 200, 200))
            dpg.add_spacer(width=8)

            for key, label in [
                ("range_res", "Range res:"),
                ("max_range", "Max range:"),
                ("doppler_res", "Max v:"),
                ("snr", "SNR:"),
                ("beat_freq", "Beat freq:"),
            ]:
                dpg.add_text(label, color=(160, 200, 255))
                tag = dpg.add_text("—", color=(255, 255, 255))
                self._tags[key] = tag
                dpg.add_button(label="?", width=18, height=18,
                               callback=lambda s, a, u: self._show_info(u),
                               user_data=key)
                dpg.add_spacer(width=10)

    def _show_info(self, key: str):
        if dpg.does_item_exist(self._INFO_WIN):
            dpg.delete_item(self._INFO_WIN)
        title, body = self._THEORY[key]
        with dpg.window(label=f"Theory — {title}", tag=self._INFO_WIN,
                        width=460, height=260, no_scrollbar=False,
                        on_close=lambda: dpg.delete_item(self._INFO_WIN)):
            dpg.add_text(body, wrap=440)

    def update(self, m: RadarMetrics):
        def _set(key: str, val: str):
            if key in self._tags:
                dpg.set_value(self._tags[key], val)

        _set("range_res", f"{m.range_resolution_m:.2f} m")
        _set("max_range", f"{m.max_range_m:.0f} m")
        _set("doppler_res", f"{m.max_doppler_velocity_ms:.2f} m/s")
        _set("snr", f"{m.snr_db:.1f} dB")
        _set("beat_freq", f"{m.beat_freq_hz/1e3:.1f} kHz")

from __future__ import annotations
import numpy as np

from physics.signal import SignalState
from physics.radar_equation import received_power_dbm, beat_freq_hz
from physics.noise import thermal_noise_dbm

from .base import Block, Port, PlotData


class TargetBlock(Block):
    """Models a radar target: applies radar range equation and generates reflected signal."""

    display_name = "Target"
    category = "Scene"

    def _setup_ports(self):
        self.ports = [
            Port("tx_in", "input", "rf"),
            Port("rx_out", "output", "rf"),
        ]

    def _setup_params(self):
        self.params = {
            "distance_m": 50.0,
            "rcs_dbsm": 0.0,       # 0 dBsm ≈ 1 m² (car-like)
            "tx_antenna_gain_dbi": 12.0,
            "rx_antenna_gain_dbi": 12.0,
        }

    def process(self, inputs: dict[str, SignalState]) -> dict[str, SignalState]:
        sig = inputs.get("tx_in", SignalState())
        d = self.params["distance_m"]
        rcs = self.params["rcs_dbsm"]
        gt = self.params["tx_antenna_gain_dbi"]
        gr = self.params["rx_antenna_gain_dbi"]

        pr_dbm = received_power_dbm(
            ptx_dbm=sig.power_dbm,
            gt_dbi=gt,
            gr_dbi=gr,
            rcs_dbsm=rcs,
            distance_m=d,
            freq_hz=sig.center_freq_hz,
        )

        f_beat = beat_freq_hz(d, sig.sweep_rate_hz_per_s)
        noise_floor = thermal_noise_dbm(sig.bandwidth_hz)  # ambient kTB at RX port

        # Delay (τ = 2R/c) and attenuate the sample array
        if len(sig.samples):
            fs = sig.sample_rate_hz if sig.sample_rate_hz > 0 else sig.bandwidth_hz
            n = len(sig.samples)
            n_delay = min(int(round(2.0 * d / 3e8 * fs)), n)
            delayed = np.zeros(n, dtype=np.complex64)
            if n_delay < n:
                delayed[n_delay:] = sig.samples[: n - n_delay]
            amp_scale = 10.0 ** ((pr_dbm - sig.power_dbm) / 20.0)
            out_samples = (delayed * amp_scale).astype(np.complex64)
        else:
            out_samples = sig.samples

        return {"rx_out": sig.copy(
            power_dbm=pr_dbm,
            noise_floor_dbm=noise_floor,
            noise_figure_db=0.0,
            beat_freq_hz=f_beat,
            samples=out_samples,
        )}

    def get_plot_data(self, output_signal: SignalState) -> PlotData:
        distances = np.linspace(1, 500, 300)
        powers = []
        for d in distances:
            pr = received_power_dbm(
                ptx_dbm=output_signal.power_dbm,
                gt_dbi=self.params["tx_antenna_gain_dbi"],
                gr_dbi=self.params["rx_antenna_gain_dbi"],
                rcs_dbsm=self.params["rcs_dbsm"],
                distance_m=d,
                freq_hz=output_signal.center_freq_hz,
            )
            powers.append(pr)
        noise = np.full_like(distances, output_signal.noise_floor_dbm)
        return PlotData(
            title=f"Target — Rx power vs distance (RCS={self.params['rcs_dbsm']} dBsm)",
            x_label="Distance (m)", y_label="Rx Power (dBm)",
            x=distances, y=np.array(powers),
            extra_series=[("Noise floor", distances, noise)],
        )

    def get_plots(self, sig: SignalState) -> dict[str, PlotData]:
        distances = np.linspace(1, 500, 300)
        slope = sig.sweep_rate_hz_per_s
        if slope <= 0:
            slope = (sig.bandwidth_hz / sig.chirp_duration_s
                     if sig.chirp_duration_s > 0 else 200e6 / 1e-3)
        f_beats_khz = np.array([beat_freq_hz(d, slope) for d in distances]) / 1e3
        beat_plot = PlotData(
            title=f"Beat freq vs range  slope={slope/1e12:.2f} THz/s",
            x_label="Distance (m)", y_label="Beat frequency (kHz)",
            x=distances, y=f_beats_khz,
            extra_series=[("Target",
                           np.array([float(self.params["distance_m"])]),
                           np.array([beat_freq_hz(self.params["distance_m"], slope) / 1e3]))],
        )
        return {"Rx power vs range": self.get_plot_data(sig), "Beat freq vs range": beat_plot}

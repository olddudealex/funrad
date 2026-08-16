from __future__ import annotations
import numpy as np

from physics.signal import SignalState
from physics.radar_equation import received_power_dbm, beat_freq_hz

from .base import Block, Port, PlotData


class TargetBlock(Block):
    """Models a radar target: applies radar range equation and generates reflected signal."""

    display_name = "Target"
    category = "Scene"
    model_help = (
        "Radar target: round-trip radar range equation.\n"
        "\n"
        "Received power (before RX antenna):\n"
        "  P_rx = P_tx + RCS_dBsm\n"
        "         + 20·log10(λ) − 30·log10(4π)\n"
        "         − 40·log10(R)                [dBm]\n"
        "\n"
        "Antenna gains: gt = gr = 0 dBi here.\n"
        "  TX gain applied by the TX Antenna block.\n"
        "  RX gain applied by the RX Antenna block.\n"
        "  (Avoids double-counting.)\n"
        "\n"
        "Noise: SNR is preserved through propagation.\n"
        "  N_rx = N_tx − path_loss_db\n"
        "  Dominant RX noise = kT0B from RX antenna.\n"
        "\n"
        "Time delay: τ = 2R/c applied to samples.\n"
        "Beat freq:  f_b = 2R·(B/T_chirp)/c\n"
        "\n"
        "RCS guide: 0 dBsm ≈ person, 10 ≈ car, 20 ≈ truck."
    )

    def _setup_ports(self):
        self.ports = [
            Port("tx_in", "input", "rf"),
            Port("rx_out", "output", "rf"),
        ]

    def _setup_params(self):
        self.params = {
            "distance_m": 50.0,
            "rcs_dbsm": 0.0,       # 0 dBsm ~ 1 m^2 (car-like)
        }
        # Antenna gains are applied by the TX/RX Antenna blocks in the chain;
        # the radar equation here uses gt=0, gr=0 to avoid double-counting.

    def process(self, inputs: dict[str, SignalState]) -> dict[str, SignalState]:
        sig = inputs.get("tx_in", SignalState())
        d = self.params["distance_m"]
        rcs = self.params["rcs_dbsm"]

        pr_dbm = received_power_dbm(
            ptx_dbm=sig.power_dbm,
            gt_dbi=0.0,
            gr_dbi=0.0,
            rcs_dbsm=rcs,
            distance_m=d,
            freq_hz=sig.center_freq_hz,
        )

        f_beat = beat_freq_hz(d, sig.sweep_rate_hz_per_s)
        path_loss_db = sig.power_dbm - pr_dbm
        noise_floor  = sig.noise_floor_dbm - path_loss_db

        # Delay (tau = 2R/c) and attenuate the sample array
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
                gt_dbi=0.0,
                gr_dbi=0.0,
                rcs_dbsm=self.params["rcs_dbsm"],
                distance_m=d,
                freq_hz=output_signal.center_freq_hz,
            )
            powers.append(pr)
        noise = np.full_like(distances, output_signal.noise_floor_dbm)
        return PlotData(
            title=f"Target  -  Rx power vs distance (RCS={self.params['rcs_dbsm']} dBsm)",
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

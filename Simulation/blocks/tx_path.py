from __future__ import annotations
import math
import numpy as np

from physics.signal import SignalState
from physics.chirp import pll_chirp_signal, dac_iq_signal

from .base import Block, SingleIOBlock, Port, PlotData



def _chirp_plot(sig: SignalState) -> PlotData:
    """Instantaneous frequency vs time — triangular sweep, multiple periods."""
    T = sig.chirp_duration_s
    sim_t = (len(sig.samples) / sig.sample_rate_hz
             if len(sig.samples) and sig.sample_rate_hz > 0 else T * 4)
    n_pts = min(int(sim_t / T * 200), 4000)   # ~200 pts per ramp, cap at 4 k
    t_s = np.linspace(0.0, sim_t, n_pts)
    period = 2.0 * T
    t_mod = t_s % period
    sweep_rate = sig.bandwidth_hz / T
    f_inst_hz = np.where(t_mod < T,
                         sweep_rate * t_mod,
                         sig.bandwidth_hz - sweep_rate * (t_mod - T))
    freq_ghz = (sig.center_freq_hz - sig.bandwidth_hz / 2 + f_inst_hz) / 1e9
    return PlotData(
        title=(f"Chirp sweep  BW={sig.bandwidth_hz/1e6:.0f} MHz  "
               f"T={T*1e3:.1f} ms  sim={sim_t*1e3:.0f} ms"),
        x_label="Time (ms)", y_label="Frequency (GHz)",
        x=t_s * 1e3, y=freq_ghz,
    )


class PLLChirpBlock(Block):
    display_name = "PLL Chirp"
    category = "TX"

    def _setup_ports(self):
        self.ports = [Port("rf_out", "output", "rf")]

    def _setup_params(self):
        self.params = {
            "waveform": "Sawtooth",
            "center_freq_ghz": 5.8,
            "bandwidth_mhz": 150.0,
            "chirp_duration_ms": 1.0,
            "simulation_time_ms": 5.0,
            "power_dbm": 10.0,
            "phase_noise_dbc_hz": -90.0,
        }
        self.param_options = {"waveform": ["Sawtooth", "Triangular"]}

    def process(self, inputs):
        sig = pll_chirp_signal(
            center_freq_hz=self.params["center_freq_ghz"] * 1e9,
            bandwidth_hz=self.params["bandwidth_mhz"] * 1e6,
            chirp_duration_s=self.params["chirp_duration_ms"] * 1e-3,
            power_dbm=self.params["power_dbm"],
            simulation_time_s=self.params["simulation_time_ms"] * 1e-3,
            waveform=self.params["waveform"],
        )
        return {"rf_out": sig}

    def get_plots(self, sig: SignalState) -> dict[str, PlotData]:
        pn0 = self.params["phase_noise_dbc_hz"]   # dBc/Hz at 100 kHz offset
        f_ref = 1e5                                 # reference offset: 100 kHz
        offsets = np.logspace(3, 8, 400)            # 1 kHz … 100 MHz

        # L(f) = pn0 + 20·log10(f_ref / f)   [−20 dB/dec slope]
        pn_psd = pn0 + 20 * np.log10(f_ref / offsets)
        pn_psd = np.clip(pn_psd, -180, 0)

        pn_plot = PlotData(
            title=f"Phase noise PSD  L(f) = {pn0} + 20·log10({f_ref/1e3:.0f} kHz / f)",
            x_label="Offset (Hz)", y_label="Phase noise (dBc/Hz)",
            x=offsets, y=pn_psd,
        )

        return {"Chirp sweep": _chirp_plot(sig), "Phase noise PSD": pn_plot}


class DACIQBlock(Block):
    display_name = "DAC/IQ Mod"
    category = "TX"

    def _setup_ports(self):
        self.ports = [Port("rf_out", "output", "rf")]

    def _setup_params(self):
        self.params = {
            "center_freq_ghz": 5.8,
            "bandwidth_mhz": 150.0,
            "chirp_duration_ms": 1.0,
            "simulation_time_ms": 5.0,
            "power_dbm": 10.0,
            "dac_bits": 12,
            "lo_feedthrough_dbm": -30.0,
            "image_rejection_db": 40.0,
        }

    def process(self, inputs):
        sig = dac_iq_signal(
            center_freq_hz=self.params["center_freq_ghz"] * 1e9,
            bandwidth_hz=self.params["bandwidth_mhz"] * 1e6,
            chirp_duration_s=self.params["chirp_duration_ms"] * 1e-3,
            power_dbm=self.params["power_dbm"],
            dac_bits=self.params["dac_bits"],
            simulation_time_s=self.params["simulation_time_ms"] * 1e-3,
        )
        return {"rf_out": sig}

    def get_plots(self, sig: SignalState) -> dict[str, PlotData]:
        bw = sig.bandwidth_hz / 1e9
        fc = sig.center_freq_hz / 1e9
        lo_ft = self.params["lo_feedthrough_dbm"]
        image_db = self.params["image_rejection_db"]
        freqs = np.linspace(fc - bw, fc + bw, 200)
        imp_plot = PlotData(
            title="Spectrum with IQ impairments",
            x_label="Frequency (GHz)", y_label="Power (dBm)",
            x=freqs,
            y=np.full(200, sig.power_dbm),
            extra_series=[
                ("LO feedthrough", np.array([fc]), np.array([lo_ft])),
                ("Image", np.array([fc - bw]), np.array([sig.power_dbm - image_db])),
                ("Noise floor", freqs, np.full(200, sig.noise_floor_dbm)),
            ],
        )
        return {"Chirp sweep": _chirp_plot(sig), "IQ impairments": imp_plot}


class AmplifierBlock(SingleIOBlock):
    display_name = "Amplifier"
    category = "TX"

    def _setup_params(self):
        self.params = {"gain_db": 20.0, "nf_db": 0.0}

    def transform(self, sig: SignalState) -> SignalState:
        g, nf = self.params["gain_db"], self.params["nf_db"]
        amp_scale = 10.0 ** (g / 20.0)
        new_samples = (sig.samples * amp_scale).astype(np.complex64) if len(sig.samples) else sig.samples
        return sig.copy(
            power_dbm=sig.power_dbm + g,
            noise_floor_dbm=sig.noise_floor_dbm + g + nf,
            noise_figure_db=sig.noise_figure_db + nf,
            samples=new_samples,
        )

    def get_plots(self, _: SignalState) -> dict[str, PlotData]:
        return {}


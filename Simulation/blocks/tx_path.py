from __future__ import annotations
import math
import numpy as np

from physics.signal import SignalState
from physics.chirp import pll_chirp_signal, dac_iq_signal
from physics.noise import thermal_noise_dbm

from .base import Block, SingleIOBlock, Port, PlotData



def _chirp_plot(sig: SignalState) -> PlotData:
    """Instantaneous frequency vs time  -  triangular sweep, multiple periods."""
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
    model_help = (
        "PLL-based linear FMCW chirp source.\n"
        "\n"
        "Waveform:\n"
        "  Sawtooth:   f(t) = f_c−B/2 + (B/T)·t  [0≤t<T]\n"
        "  Triangular: up-ramp then down-ramp, 2T.\n"
        "\n"
        "Power: constant at power_dbm (dBm).\n"
        "Noise floor: kT0B  [T0=290 K, B=bandwidth].\n"
        "Phase noise: L(f) ≈ L0 + 20·log10(f_ref/f)\n"
        "  (1/f² PSD model, −20 dB/decade slope).\n"
        "\n"
        "Samples at fs = 10×B for smooth waveform plots.\n"
        "Signal exits as complex-baseband chirp."
    )

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
        offsets = np.logspace(3, 8, 400)            # 1 kHz ... 100 MHz

        # L(f) = pn0 + 20*log10(f_ref / f)   [-20 dB/dec slope]
        pn_psd = pn0 + 20 * np.log10(f_ref / offsets)
        pn_psd = np.clip(pn_psd, -180, 0)

        pn_plot = PlotData(
            title=f"Phase noise PSD  L(f) = {pn0} + 20*log10({f_ref/1e3:.0f} kHz / f)",
            x_label="Offset (Hz)", y_label="Phase noise (dBc/Hz)",
            x=offsets, y=pn_psd,
        )

        return {"Chirp sweep": _chirp_plot(sig), "Phase noise PSD": pn_plot}


class DACIQBlock(Block):
    display_name = "DAC/IQ Mod"
    category = "TX"
    model_help = (
        "DAC + IQ modulator chirp source.\n"
        "\n"
        "Same chirp as PLLChirp with IQ impairments:\n"
        "  LO feedthrough: power spike at the carrier.\n"
        "  Image sideband: at f_c−B (SSB upconversion).\n"
        "\n"
        "SQNR_DAC = 6.02·dac_bits + 1.76          [dB]\n"
        "  (full-scale sinusoid model; limits dynamic\n"
        "  range of the TX signal).\n"
        "\n"
        "Noise = kT0B + DAC quantisation noise.\n"
        "\n"
        "lo_feedthrough_dbm: LO leakage to output.\n"
        "image_rejection_db: SSB image suppression."
    )

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
    model_help = (
        "Single-port RF amplifier (PA, driver, buffer).\n"
        "\n"
        "Signal:  P_out = P_in + gain_db            [dBm]\n"
        "Noise:   N_out = (N_in + kT0B·(F−1)) · G  [mW]\n"
        "  where  F = 10^(nf_db/10)   (noise factor)\n"
        "         G = 10^(gain_db/10) (power gain)\n"
        "         k = 1.38e-23 J/K,  T0 = 290 K\n"
        "\n"
        "The device adds only kT0B·(F−1) — excess noise\n"
        "referred to the input.  Input kT0B must come\n"
        "from an upstream source (PLLChirp noise floor).\n"
        "\n"
        "Note: TX chain NF has negligible effect on\n"
        "radar sensitivity; dominant noise is in RX."
    )

    def _setup_params(self):
        self.params = {"gain_db": 20.0, "nf_db": 0.0}

    def transform(self, sig: SignalState) -> SignalState:
        g, nf = self.params["gain_db"], self.params["nf_db"]
        amp_scale = 10.0 ** (g / 20.0)
        new_samples = (sig.samples * amp_scale).astype(np.complex64) if len(sig.samples) else sig.samples
        # N_out = (N_in + kT0B*(F-1)) * G   -  device adds only excess noise
        kTB_mw   = 10.0 ** (thermal_noise_dbm(sig.bandwidth_hz) / 10.0)
        f_linear = 10.0 ** (nf / 10.0)
        g_linear = 10.0 ** (g  / 10.0)
        n_in_mw  = 10.0 ** (sig.noise_floor_dbm / 10.0)
        n_out_mw = (n_in_mw + kTB_mw * (f_linear - 1.0)) * g_linear
        new_noise = 10.0 * math.log10(max(n_out_mw, 1e-30))
        return sig.copy(
            power_dbm=sig.power_dbm + g,
            noise_floor_dbm=new_noise,
            noise_figure_db=sig.noise_figure_db + nf,
            samples=new_samples,
        )

    def get_plots(self, _: SignalState) -> dict[str, PlotData]:
        return {}


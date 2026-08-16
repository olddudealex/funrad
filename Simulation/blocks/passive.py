from __future__ import annotations
import math
import numpy as np

from physics.signal import SignalState, SignalKind
from physics.noise import thermal_noise_dbm
from .base import Block, SingleIOBlock, Port, PlotData


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def _passive_noise_mw(noise_floor_dbm: float, loss_db: float, bw_hz: float) -> float:
    """Output noise [mW] of a passive element at T0 = 290 K.

    N_out = N_in/L + kT0B·(1 − 1/L)   where L = 10^(loss_db/10).
    Correctly accounts for thermal noise added by any lossy passive device.
    Valid for loss_db > 0 (L > 1).  For loss_db ≤ 0 use simple scaling.
    """
    L = 10.0 ** (loss_db / 10.0)
    kTB_mw = 10.0 ** (thermal_noise_dbm(bw_hz) / 10.0)
    N_in_mw = 10.0 ** (noise_floor_dbm / 10.0)
    return N_in_mw / L + kTB_mw * (1.0 - 1.0 / L)


# ---------------------------------------------------------------------------
# Blocks
# ---------------------------------------------------------------------------

class AntennaBlock(SingleIOBlock):
    """Antenna block: applies gain and computes EIRP (TX) or effective gain (RX)."""

    display_name = "Antenna"
    category = "Passive"
    model_help = (
        "Antenna: directional gain element.\n"
        "\n"
        "TX mode:\n"
        "  P_out = P_in + gain_dbi          [dBm]\n"
        "  N_out = N_in·G  (no thermal injection)\n"
        "\n"
        "RX mode — injects thermal noise at port:\n"
        "  P_out = P_in + gain_dbi\n"
        "  kT0B = thermal_noise_dbm(BW, T0=290 K)\n"
        "  N_out = 10·log10(10^((N_in+G)/10)\n"
        "                  + 10^(kT0B/10))  [dBm]\n"
        "\n"
        "The RX antenna is the explicit source of the\n"
        "kT0B thermal noise floor seen by the LNA.\n"
        "Noise temperature fixed at T0 = 290 K.\n"
        "\n"
        "gain_dbi: gain relative to isotropic radiator."
    )

    def _setup_params(self):
        self.params = {
            "gain_dbi": 12.0,
            "direction": "TX",
        }
        self.param_options = {"direction": ["TX", "RX"]}

    def transform(self, sig: SignalState) -> SignalState:
        g = self.params["gain_dbi"]
        amp_scale = 10.0 ** (g / 20.0)
        new_samples = (sig.samples * amp_scale).astype(np.complex64) if len(sig.samples) else sig.samples

        new_noise_dbm = sig.noise_floor_dbm + g

        if self.params["direction"] == "RX":
            # Explicitly inject thermal noise at T0 = 290 K at the antenna port.
            # This is the kT0B source that feeds the LNA — the LNA then adds kT0B·(F−1),
            # giving the correct total of kT0B·F at the LNA output (kT0B·F·G).
            kTB_mw  = 10.0 ** (thermal_noise_dbm(sig.bandwidth_hz) / 10.0)
            N_in_mw = 10.0 ** (new_noise_dbm / 10.0)   # incoming noise after antenna gain
            new_noise_dbm = 10.0 * math.log10(max(N_in_mw + kTB_mw, 1e-30))

        return sig.copy(
            power_dbm=sig.power_dbm + g,
            noise_floor_dbm=new_noise_dbm,
            samples=new_samples,
        )

    def get_plots(self, _: SignalState) -> dict[str, PlotData]:
        return {}


class CouplerBlock(Block):
    """Directional coupler: 1 input → 2 outputs (through + coupled)."""

    display_name = "Dir. Coupler"
    category = "Passive"
    model_help = (
        "Directional coupler: 1 input → through + coupled.\n"
        "\n"
        "Through port:\n"
        "  P_th = P_in − through_loss_db\n"
        "  N_th = N_in/L_il + kT0B·(1−1/L_il)  [mW]\n"
        "  L_il = 10^(through_loss_db/10)\n"
        "\n"
        "Coupled port (tagged LO for mixer input):\n"
        "  P_cp = P_in − coupling_db\n"
        "  N_cp = N_in/L_c + kT0B·(1−1/L_c)    [mW]\n"
        "  L_c  = 10^(coupling_db/10)\n"
        "\n"
        "Both ports inject passive thermal noise at\n"
        "T0 = 290 K.\n"
        "Isolation and directivity are not modelled."
    )

    def _setup_ports(self):
        self.ports = [
            Port("rf_in", "input", "rf"),
            Port("through", "output", "rf"),
            Port("coupled", "output", "coupled"),
        ]

    def _setup_params(self):
        self.params = {
            "coupling_db": 20.0,      # isolation from input to coupled port
            "through_loss_db": 0.5,   # insertion loss on through path
        }

    def process(self, inputs: dict[str, SignalState]) -> dict[str, SignalState]:
        sig = inputs.get("rf_in", SignalState())
        c  = self.params["coupling_db"]
        il = self.params["through_loss_db"]

        through_scale = 10.0 ** (-il / 20.0)
        coupled_scale = 10.0 ** (-c  / 20.0)
        if len(sig.samples):
            through_samples = (sig.samples * through_scale).astype(np.complex64)
            coupled_samples = (sig.samples * coupled_scale).astype(np.complex64)
        else:
            through_samples = sig.samples
            coupled_samples = sig.samples.copy()

        # Passive thermal noise injection at T0 = 290 K for both ports
        through_noise_mw  = _passive_noise_mw(sig.noise_floor_dbm, il, sig.bandwidth_hz)
        coupled_noise_mw  = _passive_noise_mw(sig.noise_floor_dbm, c,  sig.bandwidth_hz)
        through_noise_dbm = 10.0 * math.log10(max(through_noise_mw, 1e-30))
        coupled_noise_dbm = 10.0 * math.log10(max(coupled_noise_mw, 1e-30))

        through = sig.copy(
            power_dbm=sig.power_dbm - il,
            noise_floor_dbm=through_noise_dbm,
            samples=through_samples,
        )
        coupled = sig.copy(
            power_dbm=sig.power_dbm - c,
            noise_floor_dbm=coupled_noise_dbm,
            samples=coupled_samples,
            kind=SignalKind.LO,
        )
        return {"through": through, "coupled": coupled}

    def get_plots(self, _: SignalState) -> dict[str, PlotData]:
        return {}


class AttenuatorBlock(SingleIOBlock):
    """Fixed passive attenuator."""

    display_name = "Attenuator"
    category = "Passive"
    model_help = (
        "Passive RF attenuator at T0 = 290 K.\n"
        "\n"
        "Signal:  P_out = P_in − att_db         [dBm]\n"
        "\n"
        "Noise — passive mode (att_db > 0):\n"
        "  L = 10^(att_db/10)   (power loss, > 1)\n"
        "  N_out = N_in/L + kT0B·(1−1/L)      [mW]\n"
        "  → For L >> 1, N_out → kT0B.\n"
        "  → SNR degrades by exactly att_db.\n"
        "\n"
        "Gain mode (att_db ≤ 0):\n"
        "  Noise scales with signal; no NF model.\n"
        "  Use AmplifierBlock for a realistic active\n"
        "  element with a noise figure."
    )

    def _setup_params(self):
        self.params = {"attenuation_db": 10.0}

    def transform(self, sig: SignalState) -> SignalState:
        att = self.params["attenuation_db"]
        amp_scale = 10.0 ** (-att / 20.0)
        new_samples = (sig.samples * amp_scale).astype(np.complex64) if len(sig.samples) else sig.samples

        if att > 0.0:
            # Passive attenuation: inject thermal noise at T0 = 290 K
            new_noise_mw  = _passive_noise_mw(sig.noise_floor_dbm, att, sig.bandwidth_hz)
            new_noise_floor = 10.0 * math.log10(max(new_noise_mw, 1e-30))
        else:
            # Gain or unity: scale noise proportionally (no NF model)
            new_noise_floor = sig.noise_floor_dbm - att

        return sig.copy(
            power_dbm=sig.power_dbm - att,
            noise_floor_dbm=new_noise_floor,
            samples=new_samples,
        )

    def get_plots(self, _: SignalState) -> dict[str, PlotData]:
        return {}


class WilkinsonDividerBlock(Block):
    """Wilkinson power divider: splits input equally to two outputs (−3 dB + excess loss each)."""

    display_name = "Wilkinson Div."
    category = "Passive"
    model_help = (
        "Wilkinson power divider: 1 → 2 equal outputs.\n"
        "\n"
        "Each output:\n"
        "  loss = 3 + insertion_loss_db         [dB]\n"
        "  P_out = P_in − loss\n"
        "  (3 dB: ideal equal split; IL: excess loss)\n"
        "\n"
        "Noise (passive, T0 = 290 K):\n"
        "  L = 10^(loss/10)\n"
        "  N_out = N_in/L + kT0B·(1−1/L)      [mW]\n"
        "\n"
        "out2 is tagged SignalKind.LO for mixer\n"
        "compatibility (LO reference path).\n"
        "Port-to-port isolation is not modelled."
    )

    def _setup_ports(self):
        self.ports = [
            Port("rf_in", "input",  "rf"),
            Port("out1",  "output", "rf"),
            Port("out2",  "output", "rf"),
        ]

    def _setup_params(self):
        self.params = {"insertion_loss_db": 0.3}

    def process(self, inputs: dict[str, SignalState]) -> dict[str, SignalState]:
        sig = inputs.get("rf_in", SignalState())
        il  = self.params["insertion_loss_db"]
        total_loss = 3.0 + il   # ideal 3 dB split + excess loss

        scale = 10.0 ** (-total_loss / 20.0)
        samples_out = (sig.samples * scale).astype(np.complex64) if len(sig.samples) else sig.samples

        # Passive thermal noise injection at T0 = 290 K
        new_noise_mw  = _passive_noise_mw(sig.noise_floor_dbm, total_loss, sig.bandwidth_hz)
        new_noise_dbm = 10.0 * math.log10(max(new_noise_mw, 1e-30))

        out = sig.copy(
            power_dbm=sig.power_dbm - total_loss,
            noise_floor_dbm=new_noise_dbm,
            samples=samples_out,
        )
        return {"out1": out, "out2": out.copy(kind=SignalKind.LO)}

    def get_plots(self, _: SignalState) -> dict[str, PlotData]:
        return {}


class FilterBlock(SingleIOBlock):
    """Simple filter: models insertion loss only in MVP."""

    display_name = "Filter"
    category = "Passive"
    model_help = (
        "RF filter: models insertion loss only.\n"
        "\n"
        "Signal:  P_out = P_in − insertion_loss_db\n"
        "\n"
        "Noise (passive, T0 = 290 K, IL > 0):\n"
        "  L = 10^(IL/10)\n"
        "  N_out = N_in/L + kT0B·(1−1/L)      [mW]\n"
        "\n"
        "Frequency selectivity (LP/HP/BP) is recorded\n"
        "but NOT applied to the sample array here.\n"
        "Use IFFilterBlock for a Butterworth response\n"
        "in the IF chain.\n"
        "\n"
        "order: filter roll-off order (display only).\n"
        "cutoff_hz: −3 dB frequency (display only)."
    )

    def _setup_params(self):
        self.params = {
            "filter_type": "LP",
            "cutoff_hz": 5e6,
            "insertion_loss_db": 1.0,
            "order": 4,
        }
        self.param_options = {"filter_type": ["LP", "HP", "BP"]}

    def transform(self, sig: SignalState) -> SignalState:
        il = self.params["insertion_loss_db"]
        amp_scale = 10.0 ** (-il / 20.0)
        new_samples = (sig.samples * amp_scale).astype(np.complex64) if len(sig.samples) else sig.samples

        if il > 0.0:
            new_noise_mw  = _passive_noise_mw(sig.noise_floor_dbm, il, sig.bandwidth_hz)
            new_noise_floor = 10.0 * math.log10(max(new_noise_mw, 1e-30))
        else:
            new_noise_floor = sig.noise_floor_dbm - il

        return sig.copy(
            power_dbm=sig.power_dbm - il,
            noise_floor_dbm=new_noise_floor,
            samples=new_samples,
        )

    def get_plot_data(self, output_signal: SignalState) -> PlotData:
        from scipy.signal import butter, freqs
        order = self.params["order"]
        cutoff = self.params["cutoff_hz"]
        f = np.logspace(3, 8, 500)
        omega = 2 * math.pi * f
        omega_c = 2 * math.pi * cutoff
        b, a = butter(order, omega_c, btype="low", analog=True)
        _, h = freqs(b, a, worN=omega)
        mag_db = 20 * np.log10(np.abs(h) + 1e-12) - self.params["insertion_loss_db"]
        return PlotData(
            title=f"Filter response — {self.params['filter_type']}, fc={cutoff/1e6:.2f} MHz, N={order}",
            x_label="Frequency (Hz)", y_label="Magnitude (dB)",
            x=f, y=mag_db,
        )

    def get_plots(self, sig: SignalState) -> dict[str, PlotData]:
        fc = sig.center_freq_hz / 1e9
        bw = sig.bandwidth_hz / 1e9
        freqs_arr = np.linspace(fc - bw / 2, fc + bw / 2, 200)
        budget = PlotData(
            title=f"Filter output  IL={self.params['insertion_loss_db']} dB",
            x_label="Frequency (GHz)", y_label="Power (dBm)",
            x=freqs_arr, y=np.full_like(freqs_arr, sig.power_dbm),
            extra_series=[("Noise floor", freqs_arr, np.full_like(freqs_arr, sig.noise_floor_dbm))],
        )
        return {"Filter response": self.get_plot_data(sig), "Power budget": budget}

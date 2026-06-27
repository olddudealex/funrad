from __future__ import annotations
import math
import numpy as np

from physics.signal import SignalState, SignalKind
from .base import Block, SingleIOBlock, Port, PlotData


class AntennaBlock(SingleIOBlock):
    """Antenna block: applies gain and computes EIRP (TX) or effective gain (RX)."""

    display_name = "Antenna"
    category = "Passive"

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
        return sig.copy(
            power_dbm=sig.power_dbm + g,
            noise_floor_dbm=sig.noise_floor_dbm + g,
            samples=new_samples,
        )

    def get_plots(self, _: SignalState) -> dict[str, PlotData]:
        return {}


class CouplerBlock(Block):
    """Directional coupler: 1 input → 2 outputs (through + coupled)."""

    display_name = "Dir. Coupler"
    category = "Passive"

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
        c = self.params["coupling_db"]
        il = self.params["through_loss_db"]
        through_scale = 10.0 ** (-il / 20.0)
        coupled_scale = 10.0 ** (-c / 20.0)
        if len(sig.samples):
            through_samples = (sig.samples * through_scale).astype(np.complex64)
            coupled_samples = (sig.samples * coupled_scale).astype(np.complex64)
        else:
            through_samples = sig.samples
            coupled_samples = sig.samples.copy()
        through = sig.copy(
            power_dbm=sig.power_dbm - il,
            noise_floor_dbm=sig.noise_floor_dbm - il,
            samples=through_samples,
        )
        coupled = sig.copy(
            power_dbm=sig.power_dbm - c,
            noise_floor_dbm=sig.noise_floor_dbm - c,
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

    def _setup_params(self):
        self.params = {"attenuation_db": 10.0}

    def transform(self, sig: SignalState) -> SignalState:
        att = self.params["attenuation_db"]
        amp_scale = 10.0 ** (-att / 20.0)
        new_samples = (sig.samples * amp_scale).astype(np.complex64) if len(sig.samples) else sig.samples
        return sig.copy(
            power_dbm=sig.power_dbm - att,
            noise_floor_dbm=sig.noise_floor_dbm - att,
            samples=new_samples,
        )

    def get_plots(self, _: SignalState) -> dict[str, PlotData]:
        return {}


class FilterBlock(SingleIOBlock):
    """Simple filter: models insertion loss only in MVP."""

    display_name = "Filter"
    category = "Passive"

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
        return sig.copy(
            power_dbm=sig.power_dbm - il,
            noise_floor_dbm=sig.noise_floor_dbm - il,
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
        freqs = np.linspace(fc - bw / 2, fc + bw / 2, 200)
        budget = PlotData(
            title=f"Filter output  IL={self.params['insertion_loss_db']} dB",
            x_label="Frequency (GHz)", y_label="Power (dBm)",
            x=freqs, y=np.full_like(freqs, sig.power_dbm),
            extra_series=[("Noise floor", freqs, np.full_like(freqs, sig.noise_floor_dbm))],
        )
        return {"Filter response": self.get_plot_data(sig), "Power budget": budget}

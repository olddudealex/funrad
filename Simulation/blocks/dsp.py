from __future__ import annotations
import math
import numpy as np

from physics.signal import SignalState
from .base import Block, Port, PlotData


class RangeFFTBlock(Block):
    """Range FFT: computes the N-point FFT of the beat signal.

    Passes time-domain samples through unchanged so the rest of the chain is
    unaffected.  Updates noise_floor_dbm to the per-bin level, which makes
    compute_metrics() report the correct post-FFT SNR automatically.

    The FFT result is computed on demand for the plot only.
    """

    display_name = "Range FFT"
    category = "DSP"

    def _setup_ports(self):
        self.ports = [
            Port("if_in",    "input",  "if"),
            Port("range_out","output", "if"),
        ]

    def _setup_params(self):
        self.params = {
            "window": "Hanning",   # "Hanning" | "Rectangular"
            "nfft": 1024,          # FFT size; input truncated or zero-padded to this
        }

    def process(self, inputs: dict[str, SignalState]) -> dict[str, SignalState]:
        sig = inputs.get("if_in", SignalState())
        if not len(sig.samples):
            return {"range_out": sig}

        nfft = max(1, int(self.params["nfft"]))
        # Processing gain comes only from the real (non-zero) samples used.
        # Zero-padding beyond the input length interpolates bins but adds no gain.
        n_used = min(nfft, len(sig.samples))
        fft_gain_db = 10.0 * math.log10(n_used)
        per_bin_noise = sig.noise_floor_dbm - fft_gain_db

        return {"range_out": sig.copy(noise_floor_dbm=per_bin_noise)}

    # ------------------------------------------------------------------
    # Plots
    # ------------------------------------------------------------------

    def get_plots(self, sig: SignalState) -> dict[str, PlotData]:
        if not len(sig.samples):
            return {}

        nfft = max(1, int(self.params["nfft"]))
        n_in = len(sig.samples)
        n_used = min(nfft, n_in)
        use_hanning = self.params["window"] == "Hanning"

        # Build the windowed, nfft-point input array
        s = sig.samples[:n_used].astype(np.complex128)
        win = np.hanning(n_used) if use_hanning else np.ones(n_used)
        s_win = s * win
        if nfft > n_used:
            # Zero-pad to nfft
            padded = np.zeros(nfft, dtype=np.complex128)
            padded[:n_used] = s_win
            s_win = padded

        spec = np.fft.fft(s_win)           # nfft-point FFT
        # sig.noise_floor_dbm is already the per-bin level — process() applied
        # the FFT gain once.  Do NOT subtract again here.
        fft_gain_db = 10.0 * math.log10(n_used)   # for title display only
        per_bin_noise = sig.noise_floor_dbm

        # Positive frequencies only (single-sided)
        half = nfft // 2
        mag = np.abs(spec[:half])
        power_db = 20.0 * np.log10(mag / nfft + 1e-12)
        power_norm = power_db - power_db.max() + sig.power_dbm

        fs = sig.sample_rate_hz if sig.sample_rate_hz > 0 else sig.bandwidth_hz
        freqs_khz = np.arange(half) * (fs / nfft) / 1e3

        snr_fft = sig.power_dbm - per_bin_noise
        pad_note = f"+{nfft - n_used}z" if nfft > n_used else ""
        title = (f"Range FFT  f_beat={sig.beat_freq_hz/1e3:.1f} kHz"
                 f"  N={n_used}{pad_note}/{nfft}"
                 f"  gain={fft_gain_db:.0f} dB  SNR={snr_fft:.1f} dB")

        noise = np.full_like(freqs_khz, per_bin_noise)
        plot = PlotData(
            title=title,
            x_label="Frequency (kHz)",
            y_label="Power (dBm)",
            x=freqs_khz,
            y=power_norm,
            extra_series=[("Noise floor (per bin)", freqs_khz, noise)],
        )
        return {"Range FFT": plot}

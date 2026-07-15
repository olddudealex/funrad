from __future__ import annotations
import math
import numpy as np

from physics.signal import SignalState, SignalKind
from .base import Block, Port, PlotData
from .signal_plots import _compute_fft


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
            Port("I_in",     "input",  "if"),
            Port("Q_in",     "input",  "if"),
            Port("range_out","output", "if"),
        ]

    def _setup_params(self):
        self.params = {
            "window": "Hanning",
            "nfft": 1024,
        }
        self.param_options = {"window": ["Hanning", "Rectangular"]}

    def process(self, inputs: dict[str, SignalState]) -> dict[str, SignalState]:
        I_sig = inputs.get("I_in", SignalState())
        Q_sig = inputs.get("Q_in")

        if Q_sig is not None and len(Q_sig.samples):
            # Combine I+Q into complex; restore combined power/noise (+3 dB each)
            combined = (I_sig.samples.real + 1j * Q_sig.samples.real).astype(np.complex64)
            iq_vdbv = (I_sig.voltage_dbv + 10 * math.log10(2.0)
                       if math.isfinite(I_sig.voltage_dbv) else float('nan'))
            sig = I_sig.copy(
                samples=combined,
                power_dbm=I_sig.power_dbm + 10 * math.log10(2.0),
                noise_floor_dbm=I_sig.noise_floor_dbm + 10 * math.log10(2.0),
                kind=SignalKind.IF_IQ,
                voltage_dbv=iq_vdbv,
            )
        else:
            sig = I_sig

        if not len(sig.samples):
            return {"range_out": sig}

        nfft = max(1, int(self.params["nfft"]))
        n_used = min(nfft, len(sig.samples))
        # Hanning window reduces coherent SNR gain by 10·log10(3/2) ≈ 1.76 dB
        # vs the rectangular-window formula 10·log10(n_used).
        window_loss_db = 10.0 * math.log10(1.5) if self.params["window"] == "Hanning" else 0.0
        fft_gain_db = 10.0 * math.log10(n_used) - window_loss_db
        per_bin_noise = sig.noise_floor_dbm - fft_gain_db

        return {"range_out": sig.copy(noise_floor_dbm=per_bin_noise)}

    # ------------------------------------------------------------------
    # Plots
    # ------------------------------------------------------------------

    def get_plots(self, sig: SignalState) -> dict[str, PlotData]:
        if not len(sig.samples):
            return {}

        nfft   = max(1, int(self.params["nfft"]))
        window = self.params["window"]
        fs     = sig.sample_rate_hz if sig.sample_rate_hz > 0 else sig.bandwidth_hz

        freqs_khz, mag, n_used = _compute_fft(sig.samples, nfft, window, fs)
        power_db   = 20.0 * np.log10(mag + 1e-12)

        fft_gain_db   = 10.0 * math.log10(n_used)
        per_bin_noise = sig.noise_floor_dbm
        snr_fft       = sig.power_dbm - per_bin_noise

        is_if     = math.isfinite(sig.voltage_dbv)
        ref       = sig.voltage_dbv if is_if else sig.power_dbm
        noise_val = (sig.voltage_dbv - snr_fft) if is_if else per_bin_noise
        y_lbl     = "Voltage (dBV)" if is_if else "Power (dBm)"

        pad    = nfft - n_used
        n_note = f"{n_used}+{pad}z/{nfft}" if pad > 0 else f"{n_used}/{nfft}"
        title  = (f"Range FFT  f_beat={sig.beat_freq_hz/1e3:.1f} kHz"
                  f"  N={n_note}  win={window}"
                  f"  gain={fft_gain_db:.0f} dB  SNR={snr_fft:.1f} dB")

        power_norm = power_db - power_db.max() + ref
        noise = np.full_like(freqs_khz, noise_val)
        plot  = PlotData(
            title=title,
            x_label="Frequency (kHz)",
            y_label=y_lbl,
            x=freqs_khz,
            y=power_norm,
            extra_series=[("Noise floor (per bin)", freqs_khz, noise)],
        )
        return {"Range FFT": plot}

from __future__ import annotations
import math
import numpy as np

from physics.signal import SignalState
from .base import PlotData


def _peak_v(power_dbm: float) -> float:
    """Peak voltage into 50 Ω from a dBm power level."""
    return math.sqrt(2.0 * 10.0 ** (power_dbm / 10.0) * 1e-3 * 50.0)


def _chirp_slope(sig: SignalState) -> float:
    if sig.sweep_rate_hz_per_s > 0:
        return sig.sweep_rate_hz_per_s
    if sig.chirp_duration_s > 0:
        return sig.bandwidth_hz / sig.chirp_duration_s
    return 200e6 / 1e-3


# ---------------------------------------------------------------------------
# Time-domain
# ---------------------------------------------------------------------------

def signal_time_plot(sig: SignalState) -> PlotData:
    if len(sig.samples):
        fs = sig.sample_rate_hz if sig.sample_rate_hz > 0 else sig.bandwidth_hz
        span_ms = len(sig.samples) / fs * 1e3
        s = sig.samples
        t_us = np.arange(len(s)) / fs * 1e6

        if sig.center_freq_hz < 1e6:
            # IF signal after downconvert mixer — plot I channel only
            return PlotData(
                title=(f"IF signal (real)  f_beat={sig.beat_freq_hz/1e3:.1f} kHz  "
                       f"P={sig.power_dbm:.1f} dBm  span={span_ms:.2f} ms"),
                x_label="Time (µs)", y_label="Voltage (V)",
                x=t_us, y=s.real.astype(np.float64),
            )
        else:
            # RF chirp — I channel + envelope
            return PlotData(
                title=(f"Chirp signal  P={sig.power_dbm:.1f} dBm  "
                       f"fs={fs/1e6:.0f} MHz  span={span_ms:.2f} ms"),
                x_label="Time (µs)", y_label="Amplitude (V)",
                x=t_us, y=s.real.astype(np.float64),
                extra_series=[("Envelope", t_us, np.abs(s).astype(np.float64))],
            )

    # Fallback: analytic synthesis
    amplitude = _peak_v(sig.power_dbm)

    if sig.center_freq_hz < 1e6:
        f_beat = max(sig.beat_freq_hz, 1e3)
        t_s = np.linspace(0.0, 8.0 / f_beat, 1000)
        return PlotData(
            title=f"Beat signal  f={f_beat/1e3:.1f} kHz  P={sig.power_dbm:.1f} dBm",
            x_label="Time (µs)", y_label="Amplitude (V)",
            x=t_s * 1e6,
            y=amplitude * np.sin(2.0 * np.pi * f_beat * t_s),
        )

    slope = _chirp_slope(sig)
    t_window = min(math.sqrt(20.0 / slope), sig.chirp_duration_s)
    t_s = np.linspace(0.0, t_window, 2000)
    return PlotData(
        title=f"Baseband chirp  B={sig.bandwidth_hz/1e6:.0f} MHz  P={sig.power_dbm:.1f} dBm",
        x_label="Time (µs)", y_label="Amplitude (V)",
        x=t_s * 1e6,
        y=amplitude * np.cos(np.pi * slope * t_s ** 2),
    )


# ---------------------------------------------------------------------------
# Frequency-domain
# ---------------------------------------------------------------------------

def signal_freq_plot(sig: SignalState, use_hanning: bool = True) -> PlotData:
    """Single FFT of actual samples. Axis units and trim range depend on center_freq_hz:
    near-zero (IF after mixer) → kHz; RF → GHz."""
    s = sig.samples.astype(np.complex128)
    fs = sig.sample_rate_hz if sig.sample_rate_hz > 0 else sig.bandwidth_hz
    n = len(s)
    win = np.hanning(n) if use_hanning else np.ones(n)
    spec = np.fft.fftshift(np.fft.fft(s * win))
    freqs_hz = np.fft.fftshift(np.fft.fftfreq(n, d=1.0 / fs))
    power_db = 20.0 * np.log10(np.abs(spec) / n + 1e-12)
    power_norm = power_db - power_db.max() + sig.power_dbm

    if sig.center_freq_hz < 1e6:
        # IF / baseband — show 0…1 MHz in kHz
        mask = (freqs_hz >= 0) & (freqs_hz <= 1e6)
        f_axis = freqs_hz[mask] / 1e3
        title = f"IF spectrum  f_beat={sig.beat_freq_hz/1e3:.1f} kHz"
        x_label = "Frequency (kHz)"
    else:
        # RF chirp — shift by carrier, show ±B/2 in GHz
        mask = np.abs(freqs_hz) <= sig.bandwidth_hz / 2 * 1.2
        f_axis = (sig.center_freq_hz + freqs_hz[mask]) / 1e9
        snr = sig.power_dbm - sig.noise_floor_dbm
        title = (f"RF spectrum  fc={sig.center_freq_hz/1e9:.2f} GHz"
                 f"  B={sig.bandwidth_hz/1e6:.0f} MHz  SNR={snr:.1f} dB")
        x_label = "Frequency (GHz)"

    noise = np.full_like(f_axis, sig.noise_floor_dbm)
    return PlotData(
        title=title, x_label=x_label, y_label="Power (dBm)",
        x=f_axis, y=power_norm[mask],
        extra_series=[("Noise floor", f_axis, noise)],
    )

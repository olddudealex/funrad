from __future__ import annotations
import math
import numpy as np

from physics.signal import SignalState, SignalKind
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
# Shared FFT helper — single implementation used by all callers
# ---------------------------------------------------------------------------

def _compute_fft(
    samples: np.ndarray,
    nfft: int,
    window: str,
    fs: float,
) -> tuple[np.ndarray, np.ndarray, int]:
    """Windowed FFT, centred at 0 (fftshift applied).

    Parameters
    ----------
    samples : input array (complex64 or similar)
    nfft    : FFT size; input is truncated or zero-padded to this length
    window  : "Hanning" | "Rectangular"
    fs      : sample rate in Hz (used only for frequency axis)

    Returns
    -------
    freqs_khz   : centred frequency axis in kHz, length = nfft
    mag_per_bin : |FFT[k]| / nfft  (linear amplitude, caller converts to dB)
    n_used      : number of input samples consumed (≤ nfft)
    """
    n_in   = len(samples)
    n_used = min(nfft, n_in)
    win    = np.hanning(n_used) if window == "Hanning" else np.ones(n_used)
    s      = samples[:n_used].astype(np.complex128) * win
    if nfft > n_used:
        padded          = np.zeros(nfft, dtype=np.complex128)
        padded[:n_used] = s
        s               = padded
    spec      = np.fft.fftshift(np.fft.fft(s))
    freqs_khz = (np.arange(nfft) - nfft // 2) * (fs / nfft) / 1e3
    return freqs_khz, np.abs(spec) / nfft, n_used


# ---------------------------------------------------------------------------
# Time-domain helpers
# ---------------------------------------------------------------------------

def _if_time_plot(sig: SignalState) -> PlotData:
    if len(sig.samples):
        fs      = sig.sample_rate_hz if sig.sample_rate_hz > 0 else sig.bandwidth_hz
        span_ms = len(sig.samples) / fs * 1e3
        t_us    = np.arange(len(sig.samples)) / fs * 1e6
        return PlotData(
            title=(f"IF signal (real)  f_beat={sig.beat_freq_hz/1e3:.1f} kHz  "
                   f"P={sig.power_dbm:.1f} dBm  span={span_ms:.2f} ms"),
            x_label="Time (µs)", y_label="Voltage (V)",
            x=t_us, y=sig.samples.real.astype(np.float64),
        )
    f_beat = max(sig.beat_freq_hz, 1e3)
    t_s    = np.linspace(0.0, 8.0 / f_beat, 1000)
    return PlotData(
        title=f"Beat signal  f={f_beat/1e3:.1f} kHz  P={sig.power_dbm:.1f} dBm",
        x_label="Time (µs)", y_label="Amplitude (V)",
        x=t_s * 1e6, y=_peak_v(sig.power_dbm) * np.sin(2.0 * np.pi * f_beat * t_s),
    )


def _rf_time_plot(sig: SignalState) -> PlotData:
    if len(sig.samples):
        fs      = sig.sample_rate_hz if sig.sample_rate_hz > 0 else sig.bandwidth_hz
        span_ms = len(sig.samples) / fs * 1e3
        t_us    = np.arange(len(sig.samples)) / fs * 1e6
        s       = sig.samples
        return PlotData(
            title=(f"Chirp signal  P={sig.power_dbm:.1f} dBm  "
                   f"fs={fs/1e6:.0f} MHz  span={span_ms:.2f} ms"),
            x_label="Time (µs)", y_label="Amplitude (V)",
            x=t_us, y=s.real.astype(np.float64),
            extra_series=[("Envelope", t_us, np.abs(s).astype(np.float64))],
        )
    slope    = _chirp_slope(sig)
    t_window = min(math.sqrt(20.0 / slope), sig.chirp_duration_s)
    t_s      = np.linspace(0.0, t_window, 2000)
    return PlotData(
        title=f"Baseband chirp  B={sig.bandwidth_hz/1e6:.0f} MHz  P={sig.power_dbm:.1f} dBm",
        x_label="Time (µs)", y_label="Amplitude (V)",
        x=t_s * 1e6, y=_peak_v(sig.power_dbm) * np.cos(np.pi * slope * t_s ** 2),
    )


_TIME_PLOT_FN = {
    SignalKind.RF:    _rf_time_plot,
    SignalKind.LO:    _rf_time_plot,
    SignalKind.IF_I:  _if_time_plot,
    SignalKind.IF_IQ: _if_time_plot,
}


def signal_time_plot(sig: SignalState) -> PlotData:
    return _TIME_PLOT_FN[sig.kind](sig)


# ---------------------------------------------------------------------------
# Frequency-domain helpers
# ---------------------------------------------------------------------------

def _if_freq_plot(sig: SignalState, use_hanning: bool,
                  x_clip_hz: float | None = None) -> PlotData:
    is_if     = math.isfinite(sig.voltage_dbv)
    ref       = sig.voltage_dbv if is_if else sig.power_dbm
    noise_val = (sig.voltage_dbv - sig.snr_db) if is_if else sig.noise_floor_dbm
    y_lbl     = "Voltage (dBV)" if is_if else "Power (dBm)"
    x_view    = (-x_clip_hz / 1e3, x_clip_hz / 1e3) if x_clip_hz else None

    fs = sig.sample_rate_hz if sig.sample_rate_hz > 0 else sig.bandwidth_hz
    if not len(sig.samples):
        freqs = np.linspace(-fs / 2e3, fs / 2e3, 256)
        sig_line   = np.full_like(freqs, ref)
        noise_line = np.full_like(freqs, noise_val)
        return PlotData(
            f"IF spectrum  (no samples)  f_beat={sig.beat_freq_hz/1e3:.1f} kHz",
            "Frequency (kHz)", y_lbl, freqs, sig_line,
            [("Noise floor", freqs, noise_line)], x_view,
        )
    n        = len(sig.samples)
    win_name = "Hanning" if use_hanning else "Rectangular"
    freqs_khz, mag, n_used = _compute_fft(sig.samples, n, win_name, fs)
    power_db   = 20.0 * np.log10(mag + 1e-12)
    power_norm = power_db - power_db.max() + ref
    noise      = np.full_like(freqs_khz, noise_val)
    title = (f"IF spectrum  f_beat={sig.beat_freq_hz/1e3:.1f} kHz"
             f"  N={n_used}  fs={fs/1e6:.3g} MHz  SNR={sig.snr_db:.1f} dB")
    return PlotData(title, "Frequency (kHz)", y_lbl,
                    freqs_khz, power_norm, [("Noise floor", freqs_khz, noise)], x_view)


def _rf_freq_plot(sig: SignalState, use_hanning: bool) -> PlotData:
    fs = sig.sample_rate_hz if sig.sample_rate_hz > 0 else sig.bandwidth_hz
    if not len(sig.samples):
        f_start = (sig.center_freq_hz - sig.bandwidth_hz / 2) / 1e9
        f_stop  = (sig.center_freq_hz + sig.bandwidth_hz / 2) / 1e9
        freqs   = np.linspace(f_start, f_stop, 256)
        floor   = np.full_like(freqs, sig.noise_floor_dbm)
        return PlotData(
            f"RF spectrum  fc={sig.center_freq_hz/1e9:.2f} GHz  B={sig.bandwidth_hz/1e6:.0f} MHz",
            "Frequency (GHz)", "Power (dBm)", freqs,
            np.full_like(freqs, sig.power_dbm), [("Noise floor", freqs, floor)],
        )
    n        = len(sig.samples)
    win_name = "Hanning" if use_hanning else "Rectangular"
    freqs_khz, mag, _ = _compute_fft(sig.samples, n, win_name, fs)
    freqs_hz   = freqs_khz * 1e3
    mask       = np.abs(freqs_hz) <= sig.bandwidth_hz / 2 * 1.2
    f_axis_ghz = (sig.center_freq_hz + freqs_hz[mask]) / 1e9
    power_db   = 20.0 * np.log10(mag + 1e-12)
    power_norm = power_db - power_db.max() + sig.power_dbm
    noise      = np.full_like(f_axis_ghz, sig.noise_floor_dbm)
    title = (f"RF spectrum  fc={sig.center_freq_hz/1e9:.2f} GHz"
             f"  B={sig.bandwidth_hz/1e6:.0f} MHz  SNR={sig.snr_db:.1f} dB")
    return PlotData(title, "Frequency (GHz)", "Power (dBm)",
                    f_axis_ghz, power_norm[mask], [("Noise floor", f_axis_ghz, noise)])


_FREQ_PLOT_FN = {
    SignalKind.RF:    _rf_freq_plot,
    SignalKind.LO:    _rf_freq_plot,
    SignalKind.IF_I:  _if_freq_plot,
    SignalKind.IF_IQ: _if_freq_plot,
}


def signal_freq_plot(sig: SignalState, use_hanning: bool = True,
                     x_clip_hz: float | None = None) -> PlotData:
    if sig.kind in (SignalKind.IF_I, SignalKind.IF_IQ):
        return _if_freq_plot(sig, use_hanning, x_clip_hz=x_clip_hz)
    return _FREQ_PLOT_FN[sig.kind](sig, use_hanning)

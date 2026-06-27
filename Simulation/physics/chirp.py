from __future__ import annotations
import numpy as np

from .signal import SignalState, power_to_amplitude
from .noise import thermal_noise_dbm

_MAX_SAMPLES = 10_000_000   # 2 M complex64 = 16 MB; covers 10 ms at 200 MHz


def _triangular_chirp_samples(bandwidth_hz: float, chirp_duration_s: float,
                               simulation_time_s: float,
                               power_dbm: float) -> tuple[np.ndarray, float]:
    """
    Generate complex baseband samples for a triangular FMCW chirp.

    Frequency sweeps -B/2 → +B/2 (up ramp) then +B/2 → -B/2 (down ramp),
    periodically.  With fs = B, all frequencies stay within ±fs/2 (no aliasing).
    Phase is continuous at every ramp transition; the net phase change per full
    period is exactly 0, so no per-period offset is needed.

    Returns (samples, fs) where fs = bandwidth_hz.
    """
    T = chirp_duration_s
    B = bandwidth_hz
    sweep_rate = B / T
    fs = 2.0 * B  # the B would be enough to avoid aliasing, but use 2B to see the full shape of the spectrum
    n = min(int(fs * simulation_time_s), _MAX_SAMPLES)
    t = np.arange(n, dtype=np.float64) / fs

    period = 2.0 * T
    t_mod = t % period

    up_mask = t_mod < T
    tau_up = np.where(up_mask, t_mod, 0.0)
    tau_dn = np.where(~up_mask, t_mod - T, 0.0)

    # Integrate 2π·f_inst analytically:
    #   up:   f(τ)  = -B/2 + sweep_rate·τ   → φ = -π·B·τ + π·slope·τ²
    #   down: f(τ') = +B/2 - sweep_rate·τ'  → φ = +π·B·τ' - π·slope·τ'²
    phase_up = np.pi * sweep_rate * tau_up ** 2 - np.pi * B * tau_up
    phase_dn = np.pi * B * tau_dn - np.pi * sweep_rate * tau_dn ** 2

    phase = np.where(up_mask, phase_up, phase_dn)

    amplitude = power_to_amplitude(power_dbm)
    samples = (amplitude * np.exp(1j * phase)).astype(np.complex64)
    return samples, fs


def _sawtooth_chirp_samples(bandwidth_hz: float, chirp_duration_s: float,
                             simulation_time_s: float,
                             power_dbm: float) -> tuple[np.ndarray, float]:
    """
    Generate complex baseband samples for a sawtooth FMCW chirp.

    Frequency sweeps -B/2 → +B/2 (up ramp only), then instantly resets.
    Beat frequency is always +f_beat (single-sided spectrum).
    """
    T          = chirp_duration_s
    B          = bandwidth_hz
    sweep_rate = B / T
    fs         = 2.0 * B
    n          = min(int(fs * simulation_time_s), _MAX_SAMPLES)
    t          = np.arange(n, dtype=np.float64) / fs
    tau        = t % T                                   # position within current ramp
    phase      = np.pi * sweep_rate * tau ** 2 - np.pi * B * tau
    amplitude  = power_to_amplitude(power_dbm)
    samples    = (amplitude * np.exp(1j * phase)).astype(np.complex64)
    return samples, fs


def pll_chirp_signal(center_freq_hz: float = 58e8,
                     bandwidth_hz: float = 150e6,
                     chirp_duration_s: float = 1e-3,
                     power_dbm: float = 10.0,
                     simulation_time_s: float | None = None,
                     waveform: str = "Sawtooth") -> SignalState:
    """Create the initial SignalState for a PLL-based triangular chirp generator."""
    sweep_rate  = bandwidth_hz / chirp_duration_s
    sim_t       = simulation_time_s if simulation_time_s is not None else chirp_duration_s * 2
    noise_floor = thermal_noise_dbm(bandwidth_hz)

    _gen = _sawtooth_chirp_samples if waveform == "Sawtooth" else _triangular_chirp_samples
    samples, fs = _gen(bandwidth_hz, chirp_duration_s, sim_t, power_dbm)

    return SignalState(
        center_freq_hz=center_freq_hz,
        carrier_freq_hz=center_freq_hz,
        bandwidth_hz=bandwidth_hz,
        chirp_duration_s=chirp_duration_s,
        sweep_rate_hz_per_s=sweep_rate,
        power_dbm=power_dbm,
        noise_floor_dbm=noise_floor,
        noise_figure_db=0.0,
        sample_rate_hz=fs,
        samples=samples,
    )


def dac_iq_signal(center_freq_hz: float = 58e8,
                  bandwidth_hz: float = 150e6,
                  chirp_duration_s: float = 1e-3,
                  power_dbm: float = 10.0,
                  dac_bits: int = 12,
                  simulation_time_s: float | None = None) -> SignalState:
    """Create the initial SignalState for a DAC/IQ modulator triangular chirp path."""
    sweep_rate = bandwidth_hz / chirp_duration_s
    dac_snr_db = 6.02 * dac_bits + 1.76
    noise_floor = power_dbm - dac_snr_db
    sim_t = simulation_time_s if simulation_time_s is not None else chirp_duration_s * 2

    samples, fs = _triangular_chirp_samples(bandwidth_hz, chirp_duration_s,
                                             sim_t, power_dbm)

    return SignalState(
        center_freq_hz=center_freq_hz,
        carrier_freq_hz=center_freq_hz,
        bandwidth_hz=bandwidth_hz,
        chirp_duration_s=chirp_duration_s,
        sweep_rate_hz_per_s=sweep_rate,
        power_dbm=power_dbm,
        noise_floor_dbm=noise_floor,
        noise_figure_db=0.0,
        sample_rate_hz=fs,
        samples=samples,
    )

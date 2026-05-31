import math

C_LIGHT = 299_792_458.0  # m/s


def wavelength_m(freq_hz: float) -> float:
    return C_LIGHT / freq_hz


def free_space_path_loss_db(distance_m: float, freq_hz: float) -> float:
    """One-way free-space path loss (dB)."""
    lam = wavelength_m(freq_hz)
    return 20 * math.log10(4 * math.pi * distance_m / lam)


def two_way_path_loss_db(distance_m: float, freq_hz: float) -> float:
    """Round-trip free-space path loss including both legs."""
    return 2 * free_space_path_loss_db(distance_m, freq_hz)


def received_power_dbm(ptx_dbm: float, gt_dbi: float, gr_dbi: float,
                        rcs_dbsm: float, distance_m: float, freq_hz: float) -> float:
    """Radar range equation: received signal power (dBm)."""
    lam = wavelength_m(freq_hz)
    # Pr = Pt * Gt * Gr * lambda^2 * sigma / ((4*pi)^3 * R^4)
    pr_dbm = (ptx_dbm + gt_dbi + gr_dbi + rcs_dbsm
              + 20 * math.log10(lam)
              - 30 * math.log10(4 * math.pi)
              - 40 * math.log10(distance_m))
    return pr_dbm


def max_range_m(ptx_dbm: float, gt_dbi: float, gr_dbi: float, rcs_dbsm: float,
                nf_db: float, snr_min_db: float, bw_hz: float, freq_hz: float,
                temp_k: float = 290.0) -> float:
    """Maximum detection range for a given minimum SNR (m)."""
    from .noise import thermal_noise_dbm
    noise_dbm = thermal_noise_dbm(bw_hz, temp_k) + nf_db
    lam = wavelength_m(freq_hz)
    # Rmax^4 = Pt*Gt*Gr*lam^2*sigma / ((4pi)^3 * kTB*NF * SNRmin)
    numerator = (ptx_dbm + gt_dbi + gr_dbi + rcs_dbsm
                 + 20 * math.log10(lam) - 30 * math.log10(4 * math.pi))
    denominator = noise_dbm + snr_min_db
    r4_db = numerator - denominator
    r4_linear = 10 ** (r4_db / 10)
    return r4_linear ** 0.25


def range_resolution_m(bandwidth_hz: float) -> float:
    """Range resolution: c / (2*B)."""
    return C_LIGHT / (2 * bandwidth_hz)


def beat_freq_hz(distance_m: float, sweep_rate_hz_per_s: float) -> float:
    """Beat frequency for a target at given distance: 2*R*slope/c."""
    return 2 * distance_m * sweep_rate_hz_per_s / C_LIGHT


def doppler_resolution_hz(chirp_duration_s: float, n_chirps: int = 1) -> float:
    """Doppler resolution: 1 / (N_chirps * T_chirp)."""
    return 1.0 / (n_chirps * chirp_duration_s)


def doppler_to_velocity_ms(doppler_hz: float, freq_hz: float) -> float:
    """Convert Doppler frequency to radial velocity (m/s)."""
    return doppler_hz * C_LIGHT / (2 * freq_hz)


def max_unambiguous_velocity_ms(chirp_rep_interval_s: float, freq_hz: float) -> float:
    """Maximum unambiguous radial velocity (m/s) for chirp-to-chirp phase Doppler.

    v_max = λ / (4 × T_rep) = c / (4 × fc × T_rep)

    For a triangular waveform pass T_rep = 2 × T_chirp (up-ramp to next up-ramp).
    For a sawtooth waveform pass T_rep = T_chirp.
    """
    return C_LIGHT / (4.0 * freq_hz * chirp_rep_interval_s)

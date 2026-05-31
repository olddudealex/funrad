import math

BOLTZMANN_K = 1.380649e-23
T_DEFAULT_K = 290.0


def thermal_noise_dbm(bw_hz: float, temp_k: float = T_DEFAULT_K) -> float:
    """Thermal noise power in dBm for a given bandwidth."""
    noise_w = BOLTZMANN_K * temp_k * bw_hz
    return 10 * math.log10(noise_w / 1e-3)


def friis_nf(nf_stages_db: list[float], gain_stages_db: list[float]) -> float:
    """Friis formula: total noise figure (dB) for a cascade of stages."""
    if not nf_stages_db:
        return 0.0
    nf_linear = [10 ** (nf / 10) for nf in nf_stages_db]
    gain_linear = [10 ** (g / 10) for g in gain_stages_db]
    total_nf = nf_linear[0]
    cumulative_gain = gain_linear[0]
    for nf, g in zip(nf_linear[1:], gain_linear[1:]):
        total_nf += (nf - 1) / cumulative_gain
        cumulative_gain *= g
    return 10 * math.log10(total_nf)


def integrate_phase_noise(pn_dbc_hz: float, offset_hz: float, bw_hz: float) -> float:
    """
    Approximate integrated phase noise power (dBc) over a flat region.
    pn_dbc_hz: SSB phase noise density (dBc/Hz) assumed flat over [offset_hz, offset_hz+bw_hz].
    Returns integrated phase noise in dBc.
    """
    integrated_w = 10 ** (pn_dbc_hz / 10) * bw_hz
    return 10 * math.log10(integrated_w)


def noise_figure_to_noise_floor_dbm(nf_db: float, bw_hz: float,
                                     temp_k: float = T_DEFAULT_K) -> float:
    """Input-referred noise floor given a noise figure and bandwidth."""
    return thermal_noise_dbm(bw_hz, temp_k) + nf_db

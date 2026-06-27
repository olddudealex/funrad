from __future__ import annotations
import math
from dataclasses import dataclass, field, replace
from enum import Enum

import numpy as np


class SignalKind(str, Enum):
    RF    = "rf"     # high-frequency chirp (GHz range)
    LO    = "lo"     # local oscillator (same freq range as RF)
    IF_I  = "if_i"  # single real channel; samples.imag == 0
    IF_IQ = "if_iq" # complex baseband; real=I, imag=Q


def power_to_amplitude(power_dbm: float) -> float:
    """RMS amplitude (V) of a unit complex phasor into 50 Ω at *power_dbm*."""
    return math.sqrt(10.0 ** (power_dbm / 10.0) * 1e-3 * 50.0)


@dataclass
class SignalState:
    """Represents the signal at a single point in the radar processing chain."""
    center_freq_hz: float = 58e8        # current signal center; 0.0 after downconvert mixer
    carrier_freq_hz: float = 58e8       # RF carrier — set by source, never modified downstream
    bandwidth_hz: float = 150e6         # instantaneous signal bandwidth at this node
    chirp_bandwidth_hz: float = 0.0     # original chirp bandwidth B — set by source, never modified downstream
    chirp_duration_s: float = 1e-3      # T_chirp (one ramp, half the triangular period)
    sweep_rate_hz_per_s: float = 0.0    # = B / T_chirp (derived, 0 = auto)
    power_dbm: float = 10.0             # signal power at this node
    noise_floor_dbm: float = float('nan')  # noise power in bandwidth; auto-computed if nan
    noise_figure_db: float = 0.0        # cumulative noise figure from source
    beat_freq_hz: float = 0.0           # set by TargetBlock; used for range calculation
    voltage_dbv: float = float('nan')   # IF-domain signal level in dBV; NaN = RF domain

    # Signal kind — used for plot dispatch; propagates through copy()
    kind: SignalKind = field(default=SignalKind.RF, compare=False)

    # Complex baseband samples flowing through the chain
    sample_rate_hz: float = field(default=0.0, compare=False, repr=False)
    samples: np.ndarray = field(
        default_factory=lambda: np.array([], dtype=np.complex64),
        compare=False, repr=False,
    )

    def __post_init__(self):
        if self.chirp_bandwidth_hz == 0.0:
            object.__setattr__(self, "chirp_bandwidth_hz", self.bandwidth_hz)
        if self.sweep_rate_hz_per_s == 0.0 and self.chirp_duration_s > 0:
            object.__setattr__(self, "sweep_rate_hz_per_s",
                               self.chirp_bandwidth_hz / self.chirp_duration_s)
        if math.isnan(self.noise_floor_dbm):
            object.__setattr__(self, "noise_floor_dbm",
                               -174.0 + 10.0 * math.log10(max(self.bandwidth_hz, 1.0)))

    def copy(self, **overrides) -> SignalState:
        return replace(self, **overrides)

    @property
    def snr_db(self) -> float:
        return self.power_dbm - self.noise_floor_dbm

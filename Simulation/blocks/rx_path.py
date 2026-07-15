from __future__ import annotations
import math
import numpy as np

from physics.signal import SignalState, SignalKind, power_to_amplitude
from physics.noise import thermal_noise_dbm, noise_figure_to_noise_floor_dbm
from .base import Block, SingleIOBlock, Port, PlotData


class LNABlock(SingleIOBlock):
    """Low-Noise Amplifier."""

    display_name = "LNA"
    category = "RX"

    def _setup_params(self):
        self.params = {
            "gain_db": 20.0,
            "nf_db": 3.0,
        }

    def transform(self, sig: SignalState) -> SignalState:
        g = self.params["gain_db"]
        nf = self.params["nf_db"]
        added_noise = noise_figure_to_noise_floor_dbm(nf, sig.bandwidth_hz)
        noise_combined_w = (10 ** (sig.noise_floor_dbm / 10) +
                            10 ** (added_noise / 10)) * 10 ** (g / 10)
        new_noise_floor = 10 * math.log10(noise_combined_w)
        new_nf = sig.noise_figure_db + nf
        amp_scale = 10.0 ** (g / 20.0)
        new_samples = (sig.samples * amp_scale).astype(np.complex64) if len(sig.samples) else sig.samples
        return sig.copy(
            power_dbm=sig.power_dbm + g,
            noise_floor_dbm=new_noise_floor,
            noise_figure_db=new_nf,
            samples=new_samples,
        )

    def get_plots(self, _: SignalState) -> dict[str, PlotData]:
        return {}


class MixerBlock(Block):
    """Mixer: combines RF and LO to produce IF (beat frequency)."""

    display_name = "Mixer"
    category = "RX"

    def _setup_ports(self):
        self.ports = [
            Port("lo_in", "input", "lo"),
            Port("rf_in", "input", "rf"),
            Port("I_out", "output", "if"),
            Port("Q_out", "output", "if"),
        ]

    def _setup_params(self):
        self.params = {
            "voltage_gain_db": 5.8,
            "nf_db": 8.0,
            "mode": "downconvert",
        }
        self.param_options = {"mode": ["downconvert", "upconvert"]}

    def process(self, inputs: dict[str, SignalState]) -> dict[str, SignalState]:
        rf = inputs.get("rf_in", SignalState())
        lo = inputs.get("lo_in", rf.copy())

        gv_db = self.params["voltage_gain_db"]
        nf = self.params["nf_db"]
        downconvert = self.params["mode"] == "downconvert"

        if_bw = rf.bandwidth_hz
        n_thermal_w = 10 ** (thermal_noise_dbm(if_bw) / 10)
        n_in_w      = 10 ** (rf.noise_floor_dbm / 10)
        f_linear    = 10 ** (nf / 10)
        gv_linear   = 10.0 ** (gv_db / 20.0)        # voltage amplitude ratio
        n_out_w     = (n_in_w + n_thermal_w * (f_linear - 1)) * gv_linear ** 2
        noise_floor = 10 * math.log10(n_out_w)
        if_power = rf.power_dbm + gv_db

        out_center = 0.0 if downconvert else lo.center_freq_hz + rf.center_freq_hz

        if len(rf.samples) and len(lo.samples):
            n = min(len(rf.samples), len(lo.samples))
            rf_amp = power_to_amplitude(rf.power_dbm)
            lo_amp = power_to_amplitude(lo.power_dbm)
            if rf_amp > 0 and lo_amp > 0:
                rf_norm = rf.samples[:n] / rf_amp
                lo_norm = lo.samples[:n] / lo_amp
                mixed = lo_norm * (np.conj(rf_norm) if downconvert else rf_norm)
                out_samples = (mixed * power_to_amplitude(if_power)).astype(np.complex64)
            else:
                out_samples = np.zeros(n, dtype=np.complex64)
        else:
            out_samples = rf.samples

        ch_power = if_power
        ch_noise = noise_floor
        # Voltage conversion: RF input power (50 Ω) scaled by per-channel voltage gain
        v_rf_rms = math.sqrt(max(10.0 ** (rf.power_dbm / 10.0) * 1e-3 * 50.0, 0.0))
        g_v      = gv_linear
        v_ch_rms = v_rf_rms * g_v
        voltage_dbv = (20.0 * math.log10(v_ch_rms)
                       if v_ch_rms > 1e-15 else -300.0)

        sig_base = rf.copy(
            center_freq_hz=out_center,
            power_dbm=ch_power,
            noise_floor_dbm=ch_noise,
            noise_figure_db=rf.noise_figure_db + nf,
            kind=SignalKind.IF_I,
            voltage_dbv=voltage_dbv,
        )
        I_samples = out_samples.real.astype(np.complex64)
        Q_samples = out_samples.imag.astype(np.complex64)
        return {
            "I_out": sig_base.copy(samples=I_samples),
            "Q_out": sig_base.copy(samples=Q_samples),
        }

    def get_plots(self, _: SignalState) -> dict[str, PlotData]:
        return {}


class ADCBlock(SingleIOBlock):
    """Analog-to-Digital Converter: models quantization noise."""

    display_name = "ADC"
    category = "RX"

    def _setup_ports(self):
        self.ports = [
            Port("I_in",  "input",  "if"),
            Port("Q_in",  "input",  "if"),
            Port("I_out", "output", "if"),
            Port("Q_out", "output", "if"),
        ]

    def process(self, inputs: dict[str, SignalState]) -> dict[str, SignalState]:
        outputs = {"I_out": self.transform(inputs.get("I_in", SignalState()))}
        if "Q_in" in inputs:
            outputs["Q_out"] = self.transform(inputs["Q_in"])
        return outputs

    def _setup_params(self):
        self.params = {
            "bits": 12,
            "sample_rate_mhz": 10.0,
            "full_scale_pm_v": 4.096,     # peak amplitude (V), ±V_fs
        }
        self.param_labels = {"full_scale_pm_v": "Full Scale ±V"}

    def transform(self, sig: SignalState) -> SignalState:
        bits = self.params["bits"]
        fs_hz = self.params["sample_rate_mhz"] * 1e6
        fs_v  = self.params["full_scale_pm_v"]       # peak amplitude (V)
        sqnr_db = 6.02 * bits + 1.76
        # Work in the voltage domain — no impedance assumption.
        # Noise floor in dBV is derived from the tracked SNR (dimensionless dB).
        quant_noise_dbv  = 20.0 * math.log10(fs_v) - sqnr_db
        noise_floor_dbv  = sig.voltage_dbv - sig.snr_db
        total_noise_dbv  = 10.0 * math.log10(
            10.0 ** (noise_floor_dbv / 10.0) + 10.0 ** (quant_noise_dbv / 10.0)
        )
        # Convert back to dBm (noise_floor_dbm field) via the same SNR relationship.
        new_snr_db  = sig.voltage_dbv - total_noise_dbv
        total_noise = sig.power_dbm - new_snr_db

        new_samples = sig.samples
        new_fs = fs_hz
        if len(sig.samples):
            fs_in = sig.sample_rate_hz if sig.sample_rate_hz > 0 else sig.bandwidth_hz
            M = max(1, int(round(fs_in / fs_hz)))
            # Plain downsampling — no implicit filtering.
            # Add an explicit FilterBlock (LP, cutoff = fs_adc/2) before the
            # ADC if anti-aliasing is needed.
            decimated = sig.samples[::M].astype(np.complex64)

            # Uniform scalar quantization on I and Q
            levels = 2 ** bits
            half = levels / 2
            real_q = np.round(decimated.real / fs_v * half) / half * fs_v
            imag_q = np.round(decimated.imag / fs_v * half) / half * fs_v
            new_samples = (real_q + 1j * imag_q).astype(np.complex64)

            # Dead-zone: signal rounds to 0 when per-channel amplitude < ½ LSB.
            lsb_half  = fs_v / (2 ** bits)
            sig_amp_v = (10.0 ** (sig.voltage_dbv / 20.0)
                         if math.isfinite(sig.voltage_dbv)
                         else power_to_amplitude(sig.power_dbm))
            out_power_dbm = -300.0 if sig_amp_v < lsb_half else sig.power_dbm
        else:
            out_power_dbm = sig.power_dbm

        return sig.copy(
            power_dbm=out_power_dbm,
            noise_floor_dbm=total_noise,
            sample_rate_hz=new_fs,
            samples=new_samples,
            voltage_dbv=sig.voltage_dbv,
        )

    def get_plot_data(self, output_signal: SignalState) -> PlotData:
        bits = self.params["bits"]
        fs = self.params["sample_rate_mhz"] * 1e6
        f_beat = output_signal.beat_freq_hz if output_signal.beat_freq_hz > 0 else 1e5
        n_samples = 256
        t_us = np.arange(n_samples) / fs * 1e6
        # Simulate a sinusoidal beat signal at beat_freq plus quantization
        amplitude = 10 ** ((output_signal.power_dbm - 10) / 20)
        raw = amplitude * np.sin(2 * math.pi * f_beat * t_us * 1e-6)
        full_scale = self.params["full_scale_pm_v"]
        levels = 2 ** bits
        quantized = np.round(raw / full_scale * levels / 2) / (levels / 2) * full_scale
        return PlotData(
            title=f"ADC output — {bits}-bit, fs={fs/1e6:.0f} MHz",
            x_label="Time (µs)", y_label="Amplitude",
            x=t_us, y=quantized,
            extra_series=[("Continuous", t_us, raw)],
        )

    def get_plots(self, sig: SignalState) -> dict[str, PlotData]:
        return {"Time domain": self.get_plot_data(sig)}


class IQAmplifierBlock(Block):
    """IF I/Q amplifier — applies gain and noise figure to each channel independently."""

    display_name = "IF Amp"
    category = "RX"

    def _setup_ports(self):
        self.ports = [
            Port("I_in",  "input",  "if"),
            Port("Q_in",  "input",  "if"),
            Port("I_out", "output", "if"),
            Port("Q_out", "output", "if"),
        ]

    def _setup_params(self):
        self.params = {"gain_db": 20.0, "nf_db": 5.0}

    def process(self, inputs: dict[str, SignalState]) -> dict[str, SignalState]:
        outputs = {"I_out": self._transform_channel(inputs.get("I_in", SignalState()))}
        if "Q_in" in inputs:
            outputs["Q_out"] = self._transform_channel(inputs["Q_in"])
        return outputs

    def _transform_channel(self, sig: SignalState) -> SignalState:
        g   = self.params["gain_db"]
        nf  = self.params["nf_db"]
        added_noise = noise_figure_to_noise_floor_dbm(nf, sig.bandwidth_hz)
        noise_w = (10 ** (sig.noise_floor_dbm / 10) + 10 ** (added_noise / 10)) * 10 ** (g / 10)
        amp_scale   = 10.0 ** (g / 20.0)
        new_samples = (sig.samples * amp_scale).astype(np.complex64) if len(sig.samples) else sig.samples
        new_vdbv = sig.voltage_dbv + g if math.isfinite(sig.voltage_dbv) else float('nan')
        return sig.copy(
            power_dbm=sig.power_dbm + g,
            noise_floor_dbm=10 * math.log10(noise_w),
            noise_figure_db=sig.noise_figure_db + nf,
            samples=new_samples,
            voltage_dbv=new_vdbv,
        )

    def get_plots(self, _: SignalState) -> dict[str, PlotData]:
        return {}


class IFFilterBlock(Block):
    """IF low-pass anti-aliasing filter using a Butterworth response."""

    display_name = "IF Filter"
    category = "RX"

    def _setup_ports(self):
        self.ports = [
            Port("I_in",  "input",  "if"),
            Port("Q_in",  "input",  "if"),
            Port("I_out", "output", "if"),
            Port("Q_out", "output", "if"),
        ]

    def _setup_params(self):
        self.params = {
            "cutoff_hz": 5e6,
            "order": 4,
            "insertion_loss_db": 1.0,
        }

    def process(self, inputs: dict[str, SignalState]) -> dict[str, SignalState]:
        outputs = {"I_out": self._transform_channel(inputs.get("I_in", SignalState()))}
        if "Q_in" in inputs:
            outputs["Q_out"] = self._transform_channel(inputs["Q_in"])
        return outputs

    def _transform_channel(self, sig: SignalState) -> SignalState:
        from scipy.signal import butter, lfilter
        cutoff = float(self.params["cutoff_hz"])
        order  = int(self.params["order"])
        il     = self.params["insertion_loss_db"]

        new_samples = sig.samples
        if len(sig.samples):
            fs  = sig.sample_rate_hz if sig.sample_rate_hz > 0 else sig.bandwidth_hz * 2
            wn  = min(cutoff / (fs / 2.0), 0.999)
            b, a = butter(order, wn, btype="low")
            new_samples = lfilter(b, a, sig.samples.astype(np.complex128)).astype(np.complex64)

        old_bw = sig.bandwidth_hz
        new_bw = min(cutoff, old_bw)
        bw_db  = 10.0 * math.log10(new_bw / old_bw) if new_bw < old_bw else 0.0

        new_vdbv = sig.voltage_dbv - il if math.isfinite(sig.voltage_dbv) else float('nan')
        return sig.copy(
            power_dbm=sig.power_dbm - il,
            noise_floor_dbm=sig.noise_floor_dbm + bw_db - il,
            bandwidth_hz=new_bw,
            samples=new_samples,
            voltage_dbv=new_vdbv,
        )

    def get_plots(self, sig: SignalState) -> dict[str, PlotData]:
        from scipy.signal import butter, freqz
        cutoff = float(self.params["cutoff_hz"])
        order  = int(self.params["order"])
        il     = self.params["insertion_loss_db"]
        fs     = sig.sample_rate_hz if sig.sample_rate_hz > 0 else sig.bandwidth_hz * 2
        wn     = min(cutoff / (fs / 2.0), 0.999)
        b, a   = butter(order, wn, btype="low")
        w, h   = freqz(b, a, worN=2000, fs=fs)
        mag_db = 20.0 * np.log10(np.abs(h) + 1e-12) - il
        plot   = PlotData(
            title=f"IF Filter  LP  fc={cutoff/1e6:.2f} MHz  N={order}  IL={il:.1f} dB",
            x_label="Frequency (kHz)", y_label="Magnitude (dB)",
            x=w / 1e3, y=mag_db,
        )
        return {"Filter response": plot}

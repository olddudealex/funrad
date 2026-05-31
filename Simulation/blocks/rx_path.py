from __future__ import annotations
import math
import numpy as np

from physics.signal import SignalState, power_to_amplitude
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

    def get_plot_data(self, output_signal: SignalState) -> PlotData:
        freqs = np.array([
            (output_signal.center_freq_hz - output_signal.bandwidth_hz / 2) / 1e9,
            output_signal.center_freq_hz / 1e9,
            (output_signal.center_freq_hz + output_signal.bandwidth_hz / 2) / 1e9,
        ])
        powers = np.full_like(freqs, output_signal.power_dbm)
        noise = np.full_like(freqs, output_signal.noise_floor_dbm)
        return PlotData(
            title=f"LNA — G={self.params['gain_db']} dB, NF={self.params['nf_db']} dB",
            x_label="Frequency (GHz)", y_label="Power (dBm)",
            x=freqs, y=powers,
            extra_series=[("Noise floor", freqs, noise)],
        )

    def get_plots(self, sig: SignalState) -> dict[str, PlotData]:
        fc = sig.center_freq_hz / 1e9
        bw = sig.bandwidth_hz / 1e9
        freqs = np.linspace(fc - bw / 2, fc + bw / 2, 200)
        spectrum = PlotData(
            title=f"LNA output  G={self.params['gain_db']} dB  NF={self.params['nf_db']} dB",
            x_label="Frequency (GHz)", y_label="Power (dBm)",
            x=freqs, y=np.full_like(freqs, sig.power_dbm),
            extra_series=[("Noise floor", freqs, np.full_like(freqs, sig.noise_floor_dbm))],
        )
        nf_range = np.linspace(0, 20, 200)
        snr_in = sig.snr_db + self.params["nf_db"]
        nf_plot = PlotData(
            title="Output SNR vs NF",
            x_label="NF (dB)", y_label="SNR (dB)",
            x=nf_range, y=snr_in - nf_range,
            extra_series=[("Operating point",
                           np.array([float(self.params["nf_db"])]),
                           np.array([sig.snr_db]))],
        )
        return {"Output spectrum": spectrum, "NF tradeoff": nf_plot}


class MixerBlock(Block):
    """Mixer: combines RF and LO to produce IF (beat frequency)."""

    display_name = "Mixer"
    category = "RX"

    def _setup_ports(self):
        self.ports = [
            Port("lo_in", "input", "lo"),
            Port("rf_in", "input", "rf"),
            Port("if_out", "output", "if"),
        ]

    def _setup_params(self):
        self.params = {
            "conversion_loss_db": 6.0,
            "nf_db": 8.0,
            "mode": "downconvert",   # "downconvert" | "upconvert"
        }

    def process(self, inputs: dict[str, SignalState]) -> dict[str, SignalState]:
        rf = inputs.get("rf_in", SignalState())
        lo = inputs.get("lo_in", rf.copy())

        cl = self.params["conversion_loss_db"]
        nf = self.params["nf_db"]
        downconvert = self.params["mode"] == "downconvert"

        if_bw = rf.bandwidth_hz
        n_thermal_w = 10 ** (thermal_noise_dbm(if_bw) / 10)
        n_in_w      = 10 ** (rf.noise_floor_dbm / 10)
        f_linear    = 10 ** (nf / 10)
        cl_linear   = 10 ** (cl / 10)
        n_out_w     = (n_in_w + n_thermal_w * (f_linear - 1)) / cl_linear
        noise_floor = 10 * math.log10(n_out_w)
        if_power = rf.power_dbm - cl

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

        return {"if_out": rf.copy(
            center_freq_hz=out_center,
            power_dbm=if_power,
            noise_floor_dbm=noise_floor,
            noise_figure_db=rf.noise_figure_db + nf,
            samples=out_samples,
        )}

    def get_plot_data(self, output_signal: SignalState) -> PlotData:
        f_beat = output_signal.beat_freq_hz
        f_max = 1e6
        freqs_khz = np.linspace(0, f_max / 1e3, 500)
        sigma = (f_max / 1e3) * 0.02
        spectrum = output_signal.power_dbm - 20 * ((freqs_khz - f_beat / 1e3) / sigma) ** 2
        spectrum = np.clip(spectrum, output_signal.noise_floor_dbm - 10, None)
        noise = np.full_like(freqs_khz, output_signal.noise_floor_dbm)
        return PlotData(
            title=f"Mixer IF spectrum — f_beat={f_beat/1e3:.1f} kHz",
            x_label="Frequency (kHz)", y_label="Power (dBm)",
            x=freqs_khz, y=spectrum,
            extra_series=[("Noise floor", freqs_khz, noise)],
        )

    def get_plots(self, sig: SignalState) -> dict[str, PlotData]:
        f_beat = max(sig.beat_freq_hz, 1e3)
        n = 500
        t_us = np.linspace(0, 10 / f_beat * 1e6, n)
        amplitude = 10 ** ((sig.power_dbm - 10) / 20)
        beat_plot = PlotData(
            title=f"Beat signal  f={f_beat/1e3:.1f} kHz",
            x_label="Time (µs)", y_label="Amplitude (V)",
            x=t_us, y=amplitude * np.sin(2 * np.pi * f_beat * t_us * 1e-6),
        )
        return {"IF spectrum": self.get_plot_data(sig), "Beat signal": beat_plot}


class ADCBlock(SingleIOBlock):
    """Analog-to-Digital Converter: models quantization noise."""

    display_name = "ADC"
    category = "RX"

    def _setup_params(self):
        self.params = {
            "bits": 12,
            "sample_rate_mhz": 10.0,
            "full_scale_dbm": 10.0,
        }

    def transform(self, sig: SignalState) -> SignalState:
        bits = self.params["bits"]
        fs_hz = self.params["sample_rate_mhz"] * 1e6
        full_scale_dbm = self.params["full_scale_dbm"]
        sqnr_db = 6.02 * bits + 1.76
        quant_noise_dbm = full_scale_dbm - sqnr_db
        total_noise = 10 * math.log10(
            10 ** (sig.noise_floor_dbm / 10) + 10 ** (quant_noise_dbm / 10)
        )

        new_samples = sig.samples
        new_fs = fs_hz
        if len(sig.samples):
            fs_in = sig.sample_rate_hz if sig.sample_rate_hz > 0 else sig.bandwidth_hz
            M = max(1, int(round(fs_in / fs_hz)))
            if M > 1:
                try:
                    from scipy.signal import decimate as _decimate
                    r = sig.samples.astype(np.complex128)
                    dec = (_decimate(r.real, M, zero_phase=True) +
                           1j * _decimate(r.imag, M, zero_phase=True))
                    decimated = dec.astype(np.complex64)
                except Exception:
                    decimated = sig.samples[::M].astype(np.complex64)
            else:
                decimated = sig.samples.copy()

            # Uniform scalar quantization on I and Q
            fs_amp = power_to_amplitude(full_scale_dbm)
            levels = 2 ** bits
            half = levels / 2
            real_q = np.round(decimated.real / fs_amp * half) / half * fs_amp
            imag_q = np.round(decimated.imag / fs_amp * half) / half * fs_amp
            new_samples = (real_q + 1j * imag_q).astype(np.complex64)

        # Update power_dbm from the actual quantised samples.
        # If the signal was below the quantisation threshold (< ½ LSB) it
        # rounds to zero on both I and Q channels, so the total sample power
        # equals the quantisation noise alone.  Subtracting the known
        # quantisation noise gives the residual signal power; when that is
        # ≤ 0 the signal was completely lost and we flag it as −300 dBm so
        # that downstream SNR calculations correctly show an undetectable target.
        out_power_dbm = sig.power_dbm
        if len(new_samples) > 0:
            total_mw  = float(np.mean(np.abs(new_samples) ** 2)) / 50.0 * 1000.0
            quant_mw  = 10.0 ** (quant_noise_dbm / 10.0)
            sig_mw    = total_mw - quant_mw
            out_power_dbm = (10.0 * math.log10(sig_mw)
                             if sig_mw > 0 else -300.0)

        return sig.copy(
            power_dbm=out_power_dbm,
            noise_floor_dbm=total_noise,
            sample_rate_hz=new_fs,
            samples=new_samples,
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
        full_scale = 10 ** ((self.params["full_scale_dbm"] - 10) / 20)
        levels = 2 ** bits
        quantized = np.round(raw / full_scale * levels / 2) / (levels / 2) * full_scale
        return PlotData(
            title=f"ADC output — {bits}-bit, fs={fs/1e6:.0f} MHz",
            x_label="Time (µs)", y_label="Amplitude",
            x=t_us, y=quantized,
            extra_series=[("Continuous", t_us, raw)],
        )

    def get_plots(self, sig: SignalState) -> dict[str, PlotData]:
        bits = self.params["bits"]
        fs = self.params["sample_rate_mhz"] * 1e6
        f_beat = sig.beat_freq_hz if sig.beat_freq_hz > 0 else 1e5

        n = 512
        t = np.arange(n) / fs
        amplitude = 10 ** ((sig.power_dbm - 10) / 20)
        raw = amplitude * np.sin(2 * math.pi * f_beat * t)
        full_scale = 10 ** ((self.params["full_scale_dbm"] - 10) / 20)
        levels = 2 ** bits
        quantized = np.round(raw / full_scale * levels / 2) / (levels / 2) * full_scale
        fft_freqs = np.fft.rfftfreq(n, d=1 / fs) / 1e3   # kHz
        fft_mag = 20 * np.log10(np.abs(np.fft.rfft(quantized)) / n + 1e-12)
        fft_plot = PlotData(
            title=f"ADC FFT  {bits}-bit  fs={fs/1e6:.0f} MHz",
            x_label="Frequency (kHz)", y_label="Power (dBm)",
            x=fft_freqs, y=fft_mag,
            extra_series=[("Noise floor", fft_freqs,
                           np.full_like(fft_freqs, sig.noise_floor_dbm))],
        )
        return {"Time domain": self.get_plot_data(sig), "FFT spectrum": fft_plot}

# FunRad Rev.A — Generated Results

> [!warning] Generated file
> Do not edit this page manually. Regenerate it from the executable `.toyradar` configuration.

- Engine version: `1.4`
- Configuration SHA-256: `ea1c13ea484442c6fa8863758c42c2344a0de80087ed64e3809868a3b0103851`
[Open interactive HTML report](FunRad%20Rev.A%20Results.html)

![Tolerance overview](FunRad%20Rev.A%20Results.png)

- Detection threshold is configured on each Range FFT block.

## Configuration

| Block | Part | Parameter | Value |
| --- | --- | --- | ---: |
| PLL/VCO | LMX2491 + HMC431 | Waveform | Sawtooth |
|  |  | Center Frequency (GHz) | 5.8 GHz |
|  |  | Bandwidth (MHz) | 150 MHz |
|  |  | Chirp Duration (ms) | 1 ms |
|  |  | Inter-chirp idle (ms) | 0 ms |
|  |  | Simulation Time (ms) | 5 ms |
|  |  | Power (dBm) | 2 dBm |
|  |  | Phase Noise (dBc/Hz) | -90 dBc/Hz |
| TX/LO Split | Planar Wilkinson | Insertion Loss (dB) | 0.3 dB |
| TX Atten. | PE43711B-Z | Attenuation (dB) | 16 dB |
| TX PA | QPA9127 | Gain (dB) | 19 dB |
|  |  | Noise Figure (dB) | 1.4 dB |
| TX Coupler |  | Coupling (dB) | 20 dB |
|  |  | Through Loss (dB) | 0.5 dB |
| TX Ant. | Custom Rev.A | Gain (dBi) | 12 dBi |
|  |  | Direction | TX |
| Target |  | Distance (m) | 45 m |
|  |  | RCS (dBsm) | 0 dBsm |
| LO Amplifier | GALI-84+ | Gain (dB) | 12 dB |
|  |  | Noise Figure (dB) | 3 dB |
| RX Ant. | Custom Rev.A | Gain (dBi) | 12 dBi |
|  |  | Direction | RX |
| RX LNA | QPL9504 | Gain (dB) | 17.9 dB |
|  |  | Noise Figure (dB) | 0.66 dB |
| I/Q Demod. | ADL5380 | Voltage Gain (dB) | 5.8 dB |
|  |  | Noise Figure (dB) | 15.5 dB |
|  |  | Mode | downconvert |
| IF Filter | TBD | Cutoff (Hz) | 1e+06 Hz |
|  |  | Order | 4 |
|  |  | Insertion Loss (dB) | 1 dB |
| IF FDA | THS4551 | Gain (dB) | 20 dB |
|  |  | Added Output Noise (dBV) | -87.74 dBV |
| AA Filter | TBD | Cutoff (Hz) | 1e+06 Hz |
|  |  | Order | 4 |
|  |  | Insertion Loss (dB) | 1 dB |
| ADC | TBD | Minimum signal (LSB RMS; 0=off) | 0.5 |
|  |  | Bits | 14 bit |
|  |  | Sample Rate (MHz) | 3.5 MHz |
|  |  | Full Scale ±V (V peak) | 4.096 V peak |
| Range FFT |  | Detection SNR threshold (dB) | 10 dB |
|  |  | Window | Hanning |
|  |  | FFT Length | 1024 |
|  |  | Acquisition Start (µs) | 0 µs |
|  |  | Acquisition Duration (µs) | 0 µs |
| LO split 1:2 | Planar Wilkinson | Insertion Loss (dB) | 0.3 dB |
| LO outputs 1/2 | Planar Wilkinson | Insertion Loss (dB) | 0.3 dB |
| LO outputs 3/4 | Planar Wilkinson | Insertion Loss (dB) | 0.3 dB |
| TX-RX Leakage |  | Attenuation (dB) | 25 dB |
| RX Sum |  | Include added signal | True |

## Scenario summary

| Scenario | Range (m) | RCS (dBsm) | TX attenuation (dB) | SNR (dB) | Maximum range (m) | Range resolution (m) | Beat frequency (kHz) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Close target, 0 dBsm | 1 | 0 | 33 | 71.687 | 18.012 | 3.416 | 1.001 |
| Far target, +10 dBsm | 75 | 10 | 16 | 23.686 | 85.224 | 3.416 | 75.052 |

### Scenario warnings

- **Close target, 0 dBsm:** IF FDA I_out: above maximum (configured).
- **Close target, 0 dBsm:** IF FDA Q_out: above maximum (configured).
- **Close target, 0 dBsm:** ADC I_in: above maximum (ADC full scale).
- **Close target, 0 dBsm:** ADC Q_in: above maximum (ADC full scale).
- **Close target, 0 dBsm:** ADC: target-only ADC overload at a tolerance corner (-8.65 dB headroom); linear results are invalid there.
- **Far target, +10 dBsm:** RX LNA rf_out: above maximum (configured).
- **Far target, +10 dBsm:** I/Q Demod. rf_in: above maximum (configured).
- **Far target, +10 dBsm:** I/Q Demod. I_out: above maximum (configured).
- **Far target, +10 dBsm:** I/Q Demod. Q_out: above maximum (configured).
- **Far target, +10 dBsm:** IF FDA I_out: above maximum (configured).
- **Far target, +10 dBsm:** IF FDA Q_out: above maximum (configured).
- **Far target, +10 dBsm:** ADC I_in: above maximum (ADC full scale).
- **Far target, +10 dBsm:** ADC Q_in: above maximum (ADC full scale).
- **Far target, +10 dBsm:** ADC: target-only ADC overload at a tolerance corner (-25.65 dB headroom); linear results are invalid there.

## Open definitions

- **Hardware qualification** — Gain/loss tolerances and typical operating screens require validation at actual supply, temperature and loading.
- **RF summation / leakage** — Budget levels include the combined signal; detection SNR tracks the wanted rf_in input. Waveforms add coherently and the ADC clips. Analytical levels use phase-averaged powers and independent noise, without predicting leakage sidelobes, coherent cancellation, or analog compression distortion.
- **ADC model** — Ideal quantization; engineering RMS signal threshold. Leakage, DC offset, jitter and measured ENOB are not modeled.
- **FFT model** — White uncorrelated noise and one-ramp acquisition; detection uses the selected FFT block threshold.
- **Analog model** — Linear signal propagation; compression limits flag violations without modeling distortion. LO drive checks are static; phase noise and settling are not propagated into detection.

## Link budget — Close target, 0 dBsm

| Stage | Part | Domain | Signal | Noise | SNR (dB) |
| --- | --- | --- | ---: | ---: | ---: |
| PLL/VCO | LMX2491 + HMC431 | RF | 2.00 dBm | -92.214 dBm | 94.214 |
| TX/LO Split | Planar Wilkinson | RF | -1.30 dBm | -92.214 dBm | 90.914 |
| TX Atten. | PE43711B-Z | RF | -34.30 dBm | -92.214 dBm | 57.914 |
| LO Amplifier | GALI-84+ | RF | 10.70 dBm | -77.214 dBm | 87.914 |
| TX PA | QPA9127 | RF | -15.30 dBm | -71.814 dBm | 56.514 |
| LO split 1:2 | Planar Wilkinson | RF | 7.40 dBm | -80.361 dBm | 87.761 |
| TX Coupler |  | RF | -15.80 dBm | -72.309 dBm | 56.509 |
| LO outputs 1/2 | Planar Wilkinson | RF | 4.10 dBm | -83.35 dBm | 87.45 |
| LO outputs 3/4 | Planar Wilkinson | RF | 4.10 dBm | -83.35 dBm | 87.45 |
| TX Ant. | Custom Rev.A | RF | -3.80 dBm | -60.309 dBm | 56.509 |
| Target |  | RF | -62.51 dBm | -119.018 dBm | 56.509 |
| TX-RX Leakage |  | RF | -28.80 dBm | -84.506 dBm | 55.706 |
| RX Sum |  | RF | -28.80 dBm | -84.504 dBm | 55.706 |
| RX Ant. | Custom Rev.A | RF | -16.80 dBm | -72.458 dBm | 55.66 |
| RX LNA | QPL9504 | RF | 1.10 dBm | -54.55 dBm | 55.652 |
| I/Q Demod. | ADL5380 | IF | -6.11 dBV | -61.735 dBV | 55.627 |
| IF Filter | TBD | IF | -7.11 dBV | -84.496 dBV | 77.388 |
| IF FDA | THS4551 | IF | 12.89 dBV | -64.476 dBV | 77.367 |
| AA Filter | TBD | IF | 11.89 dBV | -65.476 dBV | 77.367 |
| ADC | TBD | IF | 11.89 dBV | -65.168 dBV | 77.059 |
| Range FFT |  | IF | 14.90 dBV | -90.495 dBV | 105.397 |

## Link budget — Far target, +10 dBsm

| Stage | Part | Domain | Signal | Noise | SNR (dB) |
| --- | --- | --- | ---: | ---: | ---: |
| PLL/VCO | LMX2491 + HMC431 | RF | 2.00 dBm | -92.214 dBm | 94.214 |
| TX/LO Split | Planar Wilkinson | RF | -1.30 dBm | -92.214 dBm | 90.914 |
| TX Atten. | PE43711B-Z | RF | -17.30 dBm | -92.214 dBm | 74.914 |
| LO Amplifier | GALI-84+ | RF | 10.70 dBm | -77.214 dBm | 87.914 |
| TX PA | QPA9127 | RF | 1.70 dBm | -71.814 dBm | 73.514 |
| LO split 1:2 | Planar Wilkinson | RF | 7.40 dBm | -80.361 dBm | 87.761 |
| TX Coupler |  | RF | 1.20 dBm | -72.309 dBm | 73.509 |
| LO outputs 1/2 | Planar Wilkinson | RF | 4.10 dBm | -83.35 dBm | 87.45 |
| LO outputs 3/4 | Planar Wilkinson | RF | 4.10 dBm | -83.35 dBm | 87.45 |
| TX Ant. | Custom Rev.A | RF | 13.20 dBm | -60.309 dBm | 73.509 |
| Target |  | RF | -110.51 dBm | -184.02 dBm | 73.509 |
| TX-RX Leakage |  | RF | -11.80 dBm | -84.506 dBm | 72.706 |
| RX Sum |  | RF | -11.80 dBm | -84.506 dBm | 72.706 |
| RX Ant. | Custom Rev.A | RF | 0.20 dBm | -72.46 dBm | 72.66 |
| RX LNA | QPL9504 | RF | 18.10 dBm | -54.552 dBm | 72.652 |
| I/Q Demod. | ADL5380 | IF | 10.89 dBV | -61.737 dBV | 72.626 |
| IF Filter | TBD | IF | 9.89 dBV | -84.498 dBV | 94.387 |
| IF FDA | THS4551 | IF | 29.89 dBV | -64.477 dBV | 94.367 |
| AA Filter | TBD | IF | 28.89 dBV | -65.477 dBV | 94.367 |
| ADC | TBD | IF | 28.89 dBV | -65.169 dBV | 94.059 |
| Range FFT |  | IF | 31.90 dBV | -90.496 dBV | 122.396 |

## Tolerance corridors

Model endpoint envelopes, not statistical confidence intervals. Provisional inputs do not qualify hardware.

| Scenario | Nominal SNR (dB) | Minimum (dB) | Maximum (dB) | Corners |
| --- | ---: | ---: | ---: | ---: |
| Close target, 0 dBsm | 71.687 | 69.941 | 72.854 | 2048 |
| Far target, +10 dBsm | 23.686 | 21.940 | 24.853 | 2048 |

## Detection and operating limits

ADC threshold is in per-channel RMS LSBs (0 disables). SNR remains analytical even below the threshold. Range is bounded by ADC and SNR, conditional on stage validity; configured stage limits are checked at each scenario, not extrapolated to range.

| Scenario | Nominal detectable | Passing corners | ADC/SNR range corridor (m) |
| --- | --- | ---: | --- |
| Close target, 0 dBsm | False | 198/2048 | 12.75 – 25.44 |
| Far target, +10 dBsm | False | 0/2048 | 60.33 – 120.38 |

### Stage limits — Close target, 0 dBsm

- TX Atten. / rf_in: -1.30 dBm; min=None, max=23.0; pass; passing corners 2048/2048.
- TX PA / rf_out: -15.30 dBm; min=None, max=17.0; pass; passing corners 2048/2048.
- LO Amplifier / rf_out: 10.70 dBm; min=None, max=15.5; pass; passing corners 2048/2048.
- RX LNA / rf_out: 1.10 dBm; min=None, max=17.5; pass; passing corners 2048/2048.
- I/Q Demod. / lo_in: 4.10 dBm; min=-6.0, max=6.0; pass; passing corners 2048/2048.
- I/Q Demod. / rf_in: 1.10 dBm; min=None, max=8.2; pass; passing corners 2048/2048.
- I/Q Demod. / I_out: 0.70 V_peak; min=None, max=1.0; pass; passing corners 1896/2048.
- I/Q Demod. / Q_out: 0.70 V_peak; min=None, max=1.0; pass; passing corners 1896/2048.
- IF FDA / I_out: 6.24 V_peak; min=None, max=4.54; above maximum; passing corners 220/2048.
- IF FDA / Q_out: 6.24 V_peak; min=None, max=4.54; above maximum; passing corners 220/2048.
- ADC / I_in: 3.93 V_rms; min=0.00025, max=None; pass; passing corners 2048/2048.
- ADC / I_in: 5.56 V_peak; min=None, max=4.096; above maximum; passing corners 214/2048.
- ADC / Q_in: 3.93 V_rms; min=0.00025, max=None; pass; passing corners 2048/2048.
- ADC / Q_in: 5.56 V_peak; min=None, max=4.096; above maximum; passing corners 214/2048.
- LO outputs 1/2 / out1: 4.10 dBm; min=-6.0, max=6.0; pass; passing corners 2048/2048.
- LO outputs 1/2 / out2: 4.10 dBm; min=-6.0, max=6.0; pass; passing corners 2048/2048.
- LO outputs 3/4 / out1: 4.10 dBm; min=-6.0, max=6.0; pass; passing corners 2048/2048.
- LO outputs 3/4 / out2: 4.10 dBm; min=-6.0, max=6.0; pass; passing corners 2048/2048.

### Stage limits — Far target, +10 dBsm

- TX Atten. / rf_in: -1.30 dBm; min=None, max=23.0; pass; passing corners 2048/2048.
- TX PA / rf_out: 1.70 dBm; min=None, max=17.0; pass; passing corners 2048/2048.
- LO Amplifier / rf_out: 10.70 dBm; min=None, max=15.5; pass; passing corners 2048/2048.
- RX LNA / rf_out: 18.10 dBm; min=None, max=17.5; above maximum; passing corners 736/2048.
- I/Q Demod. / lo_in: 4.10 dBm; min=-6.0, max=6.0; pass; passing corners 2048/2048.
- I/Q Demod. / rf_in: 18.10 dBm; min=None, max=8.2; above maximum; passing corners 0/2048.
- I/Q Demod. / I_out: 4.95 V_peak; min=None, max=1.0; above maximum; passing corners 0/2048.
- I/Q Demod. / Q_out: 4.95 V_peak; min=None, max=1.0; above maximum; passing corners 0/2048.
- IF FDA / I_out: 44.16 V_peak; min=None, max=4.54; above maximum; passing corners 0/2048.
- IF FDA / Q_out: 44.16 V_peak; min=None, max=4.54; above maximum; passing corners 0/2048.
- ADC / I_in: 27.83 V_rms; min=0.00025, max=None; pass; passing corners 2048/2048.
- ADC / I_in: 39.36 V_peak; min=None, max=4.096; above maximum; passing corners 0/2048.
- ADC / Q_in: 27.83 V_rms; min=0.00025, max=None; pass; passing corners 2048/2048.
- ADC / Q_in: 39.36 V_peak; min=None, max=4.096; above maximum; passing corners 0/2048.
- LO outputs 1/2 / out1: 4.10 dBm; min=-6.0, max=6.0; pass; passing corners 2048/2048.
- LO outputs 1/2 / out2: 4.10 dBm; min=-6.0, max=6.0; pass; passing corners 2048/2048.
- LO outputs 3/4 / out1: 4.10 dBm; min=-6.0, max=6.0; pass; passing corners 2048/2048.
- LO outputs 3/4 / out2: 4.10 dBm; min=-6.0, max=6.0; pass; passing corners 2048/2048.

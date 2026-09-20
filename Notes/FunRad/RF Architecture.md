# RF Architecture

FunRad is a small 5.8 GHz FMCW radar. This page describes the signal path and the decisions behind it. It deliberately does not duplicate the full mathematics or every workbook result.

- Current agreed and provisional values: [[FunRad Rev.A Specification]]
- Full link-budget and noise derivations: [[RF Calculations]]
- Numerical workbook: [[FunRad Stages Calculations.ods]]
- Generated simulator configuration and results: [[Generated/FunRad Rev.A Results]]
- TX coupler 3-D EM design and tuning: [[TX Coupler EM Method]]
- Work to close before implementation: [[Simulation Closure Checklist]]

![[FunRadBlockDiagram.excalidraw.svg|697]]

The VCO output is split into TX and LO paths. The TX attenuator sets the transmitted level without changing the PA operating point definition. The LO branch is amplified and divided for the receive channels. Each receiver converts the 5.8 GHz echo directly to differential baseband, limits the noise bandwidth to 1 MHz, drives the ADC with a fully differential amplifier, and then forms a range spectrum digitally.

## TX path

| Stage | Part | Nominal gain/loss (dB) | Nominal output (dBm) | Comment |
| --- | --- | ---: | ---: | --- |
| VCO | HMC431 | — | 2 | Current source level |
| 1:2 divider | Planar Wilkinson | -3 | -1 | Ideal division shown; layout loss must be added later |
| Step attenuator | PE43711B-Z | -16 | -17 | One operating example, not the only setting |
| PA | QPA9127 | +19 | 2 | Nominal output for the example setting |

The directional coupler after the PA provides a measurement or monitoring path. Its coupling, through loss, directivity, detector/interface, and calibration method still need to be selected during schematic work.

## LO distribution

| Stage | Part | Nominal gain/loss (dB) | Nominal output (dBm) | Comment |
| --- | --- | ---: | ---: | --- |
| VCO | HMC431 | — | 2 | Shared with TX path |
| 1:2 divider | Planar Wilkinson | -3 | -1 | LO branch input |
| Fixed attenuator | To be selected | -5 | -6 | Provides matching/isolation and sets drive |
| LO amplifier | GALI-84+ | +12 | 6 | Nominal value |
| 1:4 divider | Planar Wilkinson | -6 | 0 per output | Four-way receive distribution |

<span style="color:red">The required ADL5380 LO-drive range must be checked across divider loss, gain tolerance, temperature, and PCB loss. The simulator LO path must also be kept consistent with this four-output hardware path.</span>

## RX and IF path

| Stage | Part / setting | Value used now | Status |
| --- | --- | ---: | --- |
| LNA | QPL9504 | 17.9 dB gain, 0.66 dB NF | Working value at 5.8 GHz |
| I/Q demodulator | ADL5380 | 5.8 dB voltage gain, 15.5 dB NF | Working value |
| First IF filter | To be designed | 1 MHz noise bandwidth, 1 dB insertion loss | <span style="color:red">Transfer function not defined</span> |
| Differential driver | THS4551 | 20 dB differential gain | Working circuit assumption |
| Anti-alias filter | To be designed | 1 MHz noise bandwidth, 1 dB insertion loss | <span style="color:red">Transfer function not defined</span> |
| ADC | Current model | 14 bit, 3.5 MS/s, 8.192 Vpp differential span | Provisional |

The RF chain is calculated in dBm. Cells I9 and J9 in the RX worksheets mark the explicit change from RF power to RMS voltage in a 50 Ω reference system. From that point the IF signal and noise are propagated in dBV. The complete conversion and noise equations are in [[RF Calculations]].

The THS4551 is treated as a circuit, not as a single unexplained noise-figure value. Its input-voltage noise, input-current noise, feedback resistors, gain resistors, noise gain, and equivalent noise bandwidth are combined to obtain output-referred added noise. That result is then combined with the amplified noise already present at its input.

## Reference cases

The design cases are 1 m and 150 m targets, each evaluated at 0 dBsm and -10 dBsm. They are intended to expose both ADC overload at close range and sensitivity at long range. TX attenuation is part of each case rather than a hidden global assumption.

<span style="color:red">After the antenna-gain correction in the simulator, the received-power values in the workbook, simulator, and reference specification must be compared once more before any SNR or maximum-range number is treated as a design guarantee.</span>

## What is chosen and what remains open

The 5.8 GHz carrier, 150 MHz working sweep bandwidth, 1 MHz IF bandwidth, QPL9504, ADL5380, and THS4551 are the present Rev.A direction. They are not a promise that every surrounding component value or interface is finished.

The items that need joint decisions are kept in [[Simulation Closure Checklist]]. The most important are:

- the exact ADC full-scale, LSB, quantisation-noise, SINAD/ENOB, and clipping conventions;
- the number of acquired samples per ramp, FFT length, window, FFT-bin noise bandwidth, and meaning of processing gain;
- sawtooth timing, reset/settling interval, and the resulting velocity model;
- the exact IF and anti-alias filters;
- TX-to-RX leakage, compression margins, phase noise, chirp nonlinearity, and spurs;
- final number of receive channels and the corresponding LO distribution;
- power tree, reference clock, PCB stack-up, shielding, and mechanical partitioning.

These are intentionally marked as open instead of being filled with convenient assumptions.

## Document rule

[[FunRad Rev.A Specification]] is the short source of truth for configuration. [[FunRad Stages Calculations.ods]] is the numerical model, [[RF Calculations]] explains the equations, and this page explains the architecture. When an agreed parameter changes, all affected sources should be updated in the same pass.

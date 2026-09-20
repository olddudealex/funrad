# Simulation Closure Checklist

This page preserves the work to do before the simulator becomes the verified reference model. We will take it step by step later; no unresolved item here is assumed to be accepted.

The versioned executable configuration and current machine-generated output are available in `Simulation/configs/FunRad.RevA.toyradar` and [[Generated/FunRad Rev.A Results]]. Their presence does not close the unresolved ADC, FFT, waveform, or hardware-validity decisions below.

## Already corrected

- [x] Count TX and RX antenna gain once in the radar equation.
- [x] Introduce the receiver $kT_0B$ noise floor at the RX input.
- [x] Use $kT_0B(F-1)$ for device-added LNA noise when source noise is propagated separately.
- [x] Make passive loss add thermal noise and therefore degrade SNR.
- [x] Align the QPL9504 working NF with the 0.66 dB value at 5.8 GHz.

These corrections should receive regression tests during the reference-model pass.

## Step 1 — Golden reference cases

- [ ] Recalculate the 1 m and 150 m cases at 0 dBsm and -10 dBsm after the model fixes.
- [ ] Choose the TX attenuator setting for each case.
- [ ] Compare the workbook and simulator at the RX antenna, LNA, mixer, FDA, ADC, and FFT-bin checkpoints.
- [ ] Store tolerances, not only nominal values.

Done when the four cases in [[FunRad Rev.A Specification]] have agreed expected values and automated comparisons.

## Step 2 — ADC meaning

This step needs a deliberate decision rather than an automatic edit.

- [ ] Confirm whether 8.192 V means differential peak-to-peak span and define the allowed common-mode range.
- [ ] Define one LSB from the selected span and code convention.
- [ ] Choose whether analytical quantisation noise uses $\Delta/\sqrt{12}$, ideal full-scale-sine SQNR, datasheet SINAD/ENOB, or more than one clearly labelled result.
- [ ] Set overload margin for target, leakage, DC offset, noise, and tolerances.
- [ ] Check THS4551 linear output swing and ADC input-network settling.

Done when voltage, code, clipping, and noise plots all use the same stated conventions.

## Step 3 — Sampling and FFT meaning

- [ ] Choose the usable acquisition interval inside one ramp.
- [ ] Derive samples per ramp from $f_s$ and that interval.
- [ ] Choose FFT length separately from the number of real samples; label zero padding correctly.
- [ ] Choose the window and calculate its coherent gain and equivalent noise bandwidth.
- [ ] Keep total analog noise, noise per FFT bin, and displayed spectrum scaling as separate quantities.
- [ ] Derive range-bin spacing and physical range resolution from the actual observed sweep bandwidth.

Done when a synthetic tone and white-noise test reproduce the predicted amplitude, bin noise, and range.

## Step 4 — Waveform timing and velocity

- [ ] Freeze sawtooth or triangular operation for Rev.A.
- [ ] Define ramp, reset, settling, idle, and repetition timing.
- [ ] Make maximum unambiguous velocity depend on the selected waveform and repetition interval.
- [ ] Exclude invalid reset/settling samples from processing.

Done when the UI, simulator equations, and specification use the same timing diagram.

## Step 5 — Large-signal validity

- [ ] Add or verify compression checks for the PA, LNA, demodulator, THS4551, and ADC.
- [ ] Include gain, attenuator, splitter, and filter tolerances in close-target limits.
- [ ] Validate ADL5380 operation against LO drive across all four LO outputs.
- [ ] Show minimum usable range as well as maximum range.

Done when every stage reports headroom and invalid operating points are visibly rejected or flagged.

## Step 6 — Effects outside the thermal-noise budget

- [ ] Add a TX-to-RX leakage scenario including antenna coupling and PCB/enclosure coupling.
- [ ] Define whether PLL phase noise, chirp nonlinearity, spurs, DC offset, I/Q imbalance, and image rejection affect detection or are illustration-only.
- [ ] Add clock jitter using the selected ADC input-frequency assumptions.
- [ ] Add amplitude flatness and group-delay variation after the IF filters are designed.

Done when each plot is labelled either performance-affecting or illustrative, with no ambiguous middle state.

## Step 7 — Configuration and regression safety

- [ ] Replace or migrate the stale 77 GHz `PLL_Option.toyradar` preset and old parameter names.
- [ ] Reconcile the simulator LO chain with the GALI-84+ and 1:4 hardware architecture.
- [ ] Add unit tests for radar equation, $kT_0B$, cascaded noise, passive loss, ADC scaling, FFT-bin noise, and range resolution.
- [ ] Add the four golden end-to-end cases.
- [ ] Mark calculated estimates separately from datasheet-qualified or measured values.

Done when changes that disturb a reference value fail a test instead of silently changing a plot.

## Later implementation gate

KiCad floorplanning can start before this checklist is complete. Detailed schematic decisions need the reference waveform, channel count, ADC interface, major parts, and power/clock direction. PCB layout release should wait for the power tree, PLL/VCO, LO distribution, IF/ADC interface, compression/leakage checks, mechanical stack-up, shielding, and bring-up strategy.

# Before starting the hardware implementation

The immediate direction remains sensible: close the model definitions that affect architecture, make the documentation readable, and start a rough KiCad floorplan early enough for mechanical constraints to influence the circuit.

The detailed simulator review is now kept in [[Simulation Closure Checklist]]. The antenna-gain ownership, receiver $kT_0B$ source, passive-device thermal noise, LNA $F-1$ treatment, and 0.66 dB QPL9504 noise figure have been corrected in the app. They remain listed there as completed items so regression tests can preserve them.

## Recommended sequence

1. Work through [[Simulation Closure Checklist]] together, one decision at a time. ADC quantisation and FFT meaning require explicit choices and are intentionally not resolved by the documentation rewrite.
2. Use [[FunRad Rev.A Specification]] as the shared working configuration for the workbook, simulator, schematic, firmware, and notes.
3. Keep derivations in [[RF Calculations]] and the architectural explanation in [[RF Architecture]].
4. Start a rough KiCad floorplan with real footprints, connectors, shield areas, mounting holes, and the existing antenna-board dimensions.
5. Let the floorplan expose the board partition, layer stack, LO distribution, power, clock, shielding, and test-access decisions before detailed routing.

## KiCad floorplan questions

The first pass should compare at least two arrangements: electronics behind the approximately 40 mm × 180 mm antenna aperture, and separate antenna/RF/digital boards.

Place realistic areas for:

- PLL, VCO, loop filter, and reference clock;
- TX attenuator, PA, coupler, and detector/test path;
- RX LNA and I/Q demodulators;
- LO amplifier and 1:4 distribution;
- IF filters, THS4551 stages, and ADC;
- processor/interface, memory, regulators, programming, and external I/O;
- controlled-impedance transitions, via fences, shield cans, mounting holes, and keepouts.

The floorplan should answer board partitioning, channel count, connector locations, enclosure depth, stack-up, RF material, shield boundaries, and whether the intended receive architecture fits the cost and area.

## Details expected during schematic capture

- PLL loop filter, ramp control, VCO tuning margin, reset/settling, and reference phase noise;
- ADC clock source and jitter budget;
- RF biasing, stability, compression, harmonics, mixer LO drive, isolation, and leakage;
- Wilkinson and coupler impedances, balance, directivity, resistor rating, and calibration;
- THS4551 common mode, load, stability, swing, and ADC kickback network;
- exact IF/anti-alias response, ENBW, Nyquist attenuation, and settling;
- rails, current budget, regulator noise/efficiency, sequencing, thermal behaviour, and test points;
- processor throughput, memory, calibration storage, and bring-up interface.

KiCad floorplanning can begin now. Detailed schematic capture should follow once the reference waveform, channel count, ADC interface, and major component/package choices are sufficiently stable. PCB layout release should wait for the power tree, clocks, PLL/VCO, LO distribution, IF/ADC interfaces, compression/leakage analysis, stack-up, shielding, and bring-up plan.

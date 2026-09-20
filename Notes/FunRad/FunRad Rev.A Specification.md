# FunRad Rev.A Specification

This is the working configuration of the first FunRad implementation. It is a small system specification: one place where the workbook, simulator, schematic, firmware, and documentation can see the same values. A value can be **chosen**, **provisional**, or **open**. Provisional values are usable for calculations but are not frozen.

The executable block configuration is maintained in `Simulation/configs/FunRad.RevA.toyradar`. Its current generated calculation report is [[Generated/FunRad Rev.A Results]]. The generated page is quantitative output, not a replacement for the design decisions recorded here.

## Intended use

FunRad is a compact 5.8 GHz FMCW radar intended to detect and range simple targets. The current reference cases are chosen to exercise both ends of the dynamic range; they are not yet formal detection guarantees.

| Requirement | Current definition | Status |
| --- | --- | --- |
| Minimum reference range | 1 m | Provisional |
| Maximum reference range | 150 m | Provisional |
| Reference target RCS | 0 dBsm and -10 dBsm | Chosen for analysis |
| Detection criterion | Not yet defined as probability of detection / false alarm | <span style="color:red">Open</span> |
| Number of simultaneous RX channels | Hardware concept shows four | <span style="color:red">Open</span> |

## Waveform and RF

| Parameter | Current value | Status |
| --- | ---: | --- |
| Carrier frequency, $f_c$ | 5.8 GHz | Chosen |
| Usable sweep bandwidth, $B$ | 150 MHz | Provisional |
| Ramp duration, $T_{ramp}$ | 1 ms | Provisional |
| Waveform | Sawtooth in the current simulator configuration | Provisional |
| Ramp reset / settling time | — | <span style="color:red">Open</span> |
| VCO output | 2 dBm nominal | Provisional |
| TX antenna gain | 12 dBi | Provisional |
| RX antenna gain | 12 dBi | Provisional |
| PCB, connector, radome, and polarization losses | — | <span style="color:red">Open</span> |

The nominal free-space range resolution for a complete linear sweep is

$$
\Delta R=\frac{c}{2B}.
$$

For $B=150\ \mathrm{MHz}$ this is about $1.00\ \mathrm{m}$. This number applies only when the acquired observation covers the intended sweep bandwidth; the ADC/FFT sampling plan is still open.

## RF and IF chain

| Function | Part / implementation | Working value | Status |
| --- | --- | ---: | --- |
| VCO | HMC431 | 5.8 GHz, 2 dBm nominal | Provisional |
| TX step attenuator | PE43711B-Z | Example setting: 16 dB | Part chosen; operating cases provisional |
| TX amplifier | QPA9127 | 19 dB gain | Provisional |
| LO amplifier | GALI-84+ | 12 dB gain | Provisional |
| LO distribution | 1:4 Wilkinson | 6.02 dB ideal split | Provisional |
| RX LNA | QPL9504 | 17.9 dB gain, 0.66 dB NF | Working values at 5.8 GHz |
| I/Q demodulator | ADL5380 | 5.8 dB voltage gain, 15.5 dB NF | Working values |
| First IF filter | To be designed | 1 MHz ENBW assumption, 1 dB loss | <span style="color:red">Open implementation</span> |
| Differential ADC driver | THS4551 | 20 dB signal gain; calculated added noise -87.74 dBV | Provisional circuit |
| Anti-alias filter | To be designed | 1 MHz ENBW assumption, 1 dB loss | <span style="color:red">Open implementation</span> |

## ADC and digital processing

| Parameter | Current value | Status |
| --- | ---: | --- |
| ADC resolution | 14 bit | Provisional |
| Differential input span | 8.192 Vpp | Provisional; confirm datasheet convention |
| Sample rate, $f_s$ | 3.5 MS/s | Provisional |
| Samples used per ramp | — | <span style="color:red">Open</span> |
| FFT length | 1024 in the present simulator | <span style="color:red">Open as Rev.A choice</span> |
| Window | Hann in the present simulator | <span style="color:red">Open as Rev.A choice</span> |
| ADC quantisation-noise convention | — | <span style="color:red">Open; do not use as a signed-off limit yet</span> |
| ADC SINAD / ENOB at the operating point | — | <span style="color:red">Open</span> |
| FFT-bin noise / processing-gain convention | — | <span style="color:red">Open</span> |
| ADC clock-jitter budget | — | <span style="color:red">Open</span> |

## Reference calculation cases

The following four cases should become golden cross-checks shared by the workbook and simulator:

| Case | Range | RCS | TX attenuation | Expected checkpoints |
| --- | ---: | ---: | ---: | --- |
| Close / large | 1 m | 0 dBsm | To be selected | RX antenna, LNA, mixer, FDA, ADC, FFT bin |
| Close / small | 1 m | -10 dBsm | To be selected | Same checkpoints |
| Far / large | 150 m | 0 dBsm | To be selected | Same checkpoints |
| Far / small | 150 m | -10 dBsm | To be selected | Same checkpoints |

<span style="color:red">The expected numerical checkpoint values are not frozen yet. First reconcile the recently corrected antenna/noise model with the workbook, then store the agreed values here.</span>

## Mechanical and implementation constraints

| Item | Current state |
| --- | --- |
| Existing antenna Rev.A outline | Approximately 40 mm × 180 mm |
| One board or separate antenna/RF/digital boards | <span style="color:red">Open</span> |
| Frontend PCB layer count and stack-up | JLCPCB JLC04161H-7628: 4 layers, 1.6 mm nominal, 1 oz outer copper, 0.5 oz inner copper; L1–L2 and L3–L4 use 7628 prepreg. Use 0.2104 mm as the L1–L2 dielectric height in Qucs and impedance models. | Chosen |
| Frontend PCB material | Standard FR-4 with 7628 prepreg; use $D_k=4.4$ and $\tan\delta=0.020$ as provisional Qucs values at 5.8 GHz; sweep $\tan\delta=0.015$ to $0.025$ for sensitivity | Chosen stack-up; electrical model provisional |
| Shield partitions and enclosure | <span style="color:red">Open</span> |
| Power rails and sequencing | <span style="color:red">Open</span> |
| Reference and ADC clock architecture | <span style="color:red">Open</span> |

## Change rule

An agreed configuration change should update, as applicable:

1. this specification;
2. [[FunRad Stages Calculations.ods]];
3. the simulator default or saved reference configuration;
4. [[RF Architecture]] and [[RF Calculations]];
5. the schematic and firmware once they exist.

This page should state decisions and status. Derivations belong in [[RF Calculations]], and deferred validation work belongs in [[Simulation Closure Checklist]].

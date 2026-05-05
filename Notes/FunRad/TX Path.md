# Introduction
The transmit path could be done using two main different approaches:
1. Using synthesizer IC. I didn't find separate VCO that covers the range 5.7GHz...5.9GHz confidently, so I considered the option of using synthesizer LMX2572RHAT with embedded VCO:
   ![[TxPathWithPLL.excalidraw|100%]]
2. Using DAC for generation of I/Q baseband signals with shifting them to RF frequency via the modulator:
   ![[TxPathWithDAC.excalidraw|100%]]
# TX Chain Quality Parameters

## TX Path Comparison Result Comparison Table

| Parameter              | Unit   | Synth LMX2572 | DAC5672+ | Method                               |
| ---------------------- | ------ | ------------- | -------- | ------------------------------------ |
| Chirp linearity error  | Hz RMS | TBD           | TBD      | see [[#Chirp Linearity]]             |
| Sweep slope error      | %      | TBD           | TBD      | see [[#Sweep Slope Error]]           |
| Bandwidth              | MHz    | 150           | 150      | datasheet/spec                       |
| Phase noise @100kHz    | dBc/Hz | TBD           | TBD      | datasheet see [[#Phase Noise]]       |
| Integrated phase noise | dBc    | TBD           | TBD      | see [[#Phase Noise]]                 |
| SFDR                   | dBc    | TBD           | TBD      | datasheet                            |
| SNR                    | dB     | TBD           | TBD      | calc see [[#SNR]]                    |
| Clock jitter SNR       | dB     | N/A           | TBD      | see [[#Clock jitter SNR]]            |
| Image rejection (IRR)  | dB     | N/A           | TBD      | est/meas [[#Image Rejection Ration]] |
| LO leakage             | dBc    | N/A           | TBD      | est/meas                             |
| Amplitude flatness     | dB     | TBD           | TBD      | see [[#Amplitude Flatness]]          |
| Group delay variation  | ns     | TBD           | TBD      | see [[#Group Delay Variation]]       |
## Chirp Linearity

## Sweep Slope Error

## Phase Noise

## SFDR

## SNR

## Clock jitter SNR

## Image Rejection Ration

## Amplitude Flatness

## Group Delay Variation


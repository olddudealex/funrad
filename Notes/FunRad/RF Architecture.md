# General
Here is the latest version of RF architecture of FunRad project:
![[FunRadBlockDiagram.excalidraw.svg|697]]

# TX Channel Calculation

| Stage             | Part#            | Gain/Loss (db) | Gain/Loss Tolerance (dB) | Typ Out (dBm) | Abs Min Out (dBm) | Abs Max Out (dBm) | P1dB (dBm) | Max RF Input (dBm) |
| ----------------- | ---------------- | -------------- | ------------------------ | ------------- | ----------------- | ----------------- | ---------- | ------------------ |
| VCO               | HMC431           | -              |                          | 2             | -1                | 3                 |            |                    |
| Wilkinson Divider | Planar Component | -3             |                          | -1            | -4                | 0                 |            |                    |
| Step Attennuator  | PE43711B-Z       | -16            | 0,71                     | -17           | -20,71            | -15,29            |            | 23                 |
| Amplifier         | Qorvo QPA9127    | 19             | 1                        | 2             | -2,71             | 4,71              | 17         |                    |
# LO Path Calculation
| Stage                 | Part#            | Gain/Loss (db) | Gain/Loss Tolerance (dB) | Typ Out (dBm) | Abs Min Out (dBm) | Abs Max Out (dBm) | P1dB (dBm) |
|-----------------------|------------------|----------------|--------------------------|---------------|-------------------|-------------------|------------|
| VCO                   | HMC431           | -              |                          | 2             | -1                | 3                 |            |
| Wilkinson Divider 1:2 | Planar Component | -3             |                          | -1            | -4                | 0                 |            |
| Attennuator           | Fixed            | -5             | 0,5                      | -6            | -9,5              | -4,5              |            |
| Amplifier             | GALI-84+         | 12             | 1                        | 6             | 1,5               | 8,5               | 15,5       |
| Wilkinson Divider 1:4 | Planar Component | -6             | 0,5                      | 0             | -5                | 3                 |

# RX Channel Calculation
## Far Target Case

### Sweep Slope Error

### Phase Noise

### SFDR

### SNR

### Clock jitter SNR

### Image Rejection Ration

### Amplitude Flatness

### Group Delay Variation


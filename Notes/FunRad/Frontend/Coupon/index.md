# PCB coupon: launches, measurements and EM studies

**Status: revision B ordered.** The selected BWSMA launch uses two symmetric 2.8 × 4.8 mm L2 clearances, original tapers and intact L3 / Bottom.

## Design decision

| Check | Result |
|---|---|
| Nominal, finer mesh, 5.3–6.3 GHz | Worst loss 0.578 dB; S21 span 0.030 dB; worst S11 −16.18 dB |
| Dielectric sensitivity, εr=4.2 / 4.5 / 4.8 | Worst loss 0.632 dB; worst S11 −14.49 dB across sampled cases |
| L3 clearances | Worsen performance; retain L3 |
| Next physical check | Measure the revised launches on revision B |

These are connector-inclusive model results. The revised coupon will test the simulated improvement against the real connector and solder joints.

## Reports in chronological order

| Order | Report | Question / purpose |
|---|---|---|
| 01 | [PCB-only model](01_PCB_ONLY_RESULTS.md) | Compare the two initial meshes and measurements; identify the launch problem. |
| 02 | [PCB modal-port control](02_MODAL_PORT_CHECK.md) | Add L3 and test the alternative excitation on unchanged launches. |
| 03 | [Simplified connector geometry](03_CONNECTOR_GEOMETRY.md) | Define the BWSMA connector and coaxial excitation model. |
| 04 | [Connector-inclusive control](04_COAX_RESULTS.md) | Compare intact-L2 simulation with measurements before changing the launches. |
| 05 | [Initial L2 cutouts](05_L2_CUTOUT_RESULTS.md) | Test ground relief, wider openings and the abrupt-step alternative. |
| 06 | [Cutout geometry search](06_L2_CUTOUT_FLATNESS_SWEEP.md) | Optimize width and length over 5.3–6.3 GHz; extend beneath the taper, including 5.0 mm. |
| 07 | [Broadband verification](07_BROADBAND_CHECK.md) | Check the selected 2.8 × 4.8 mm cutout over 0.5–6.5 GHz. |
| 08 | [Mesh refinement](08_MESH_REFINEMENT.md) | Check the selected geometry with three meshes over 5.3–6.3 GHz. |
| 09 | [L3 cutout experiment](09_L3_CUTOUT_RESULTS.md) | Test matching L3 windows beneath the selected L2 openings; retain Bottom. |
| 10 | [Dielectric sensitivity](10_DIELECTRIC_SENSITIVITY.md) | Test εr=4.2 / 4.5 / 4.8 with fixed geometry, loss tangent and mesh. |

## Original measurements

| File | Measurement |
|---|---|
| [Through connection](measurements/through_connection.s2p) | VNA/cable through reference |
| [90 mm vertical](measurements/coupon_7628_vertical_90mm.s2p) | Original long coupon |
| [90 mm rotated](measurements/coupon_7628_vertical_90mm_rotated.s2p) | Port reversal check |
| [10 mm horizontal](measurements/coupon_7628_horizontal_10mm.s2p) | Original BWSMA launches |
| [10 mm, Amphenol](measurements/coupon_7628_horizontal_10mm_amphenol.s2p) | Connector substitution trial |

### Measurement plots

- [90 mm coupon](assets/measurements/coupon_7628_vertical_90mm.png)
- [Port reversal comparison](assets/measurements/coupon_7628_vertical_90mm_rotation_comparison.png)
- [VNA through reference](assets/measurements/coupon_7628_through_comparison.png)
- [10 mm versus 90 mm](assets/measurements/coupon_7628_10mm_90mm_comparison.png)
- [BWSMA versus Amphenol](assets/measurements/coupon_7628_amphenol_comparison.png)

## Code, data and fabrication

- Simulation geometry, mesh settings, runners, compact NPZ/S2P results and metadata: `Frontend/emerge/coupon_10mm/`.
- Numbered reports and figure assets: this folder. Report scripts regenerate the pages here through `report_paths.py`.
- Revision B footprint: `Frontend:SMA_BWSMA-KE-P001_EdgeMount_L2Cutout_2.8x4.8mm`.
- Ordered production archive: `Frontend/kicad/FrontendPCBCoupon/production/FunRad_Frontend_PCB_Coupon_B.zip`.

[Simulation code and commands](https://github.com/olddudealex/funrad/tree/main/Frontend/emerge/coupon_10mm) · [Footprint library](https://github.com/olddudealex/funrad/tree/main/Frontend/kicad/library).

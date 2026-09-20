# Coupler results audit — 2026-09-17

The compensation concept works in the saved simulations, but the current notes do not establish a fabrication-ready winner. The main correction is that the preferred geometry changes when the saved networks are evaluated in the intended 50 ohm system. Keep both the compact asymmetric and the valid 90-degree symmetric variants in contention.

This review read [[TX Coupler EM Method]], [[Comb Study]], [[Symmetry Study]], [[Quasi-static 2-D Solver]], the EMerge README and Python sources, and reprocessed 46 saved full-matrix NPZ datasets. No new EM solve or hardware measurement was performed. Historical notes and simulation defaults remain unchanged.

**Reproducible results**

`Frontend/emerge/audit_results.py` writes `Frontend/emerge/results/audit_summary.csv`: 92 rows, one solver-reference and one 50-ohm evaluation per dataset. Five older files without the required full matrices are excluded. Directivity is min(S31_dB - S41_dB) over 5.7–5.9 GHz. Other centre values are at 5.8 GHz. These are fitted saved curves, not 601 independently solved frequencies.

| Variant | D min, solver reference | D min, 50 ohm | S31 at 5.8, 50 ohm | S31 range in band, 50 ohm | S21 at 5.8, 50 ohm | Return loss min in band, 50 ohm |
|---|---:|---:|---:|---:|---:|---:|
| Original full-feed, no comb | 7.41 | 6.90 | -11.82 | -11.86 to -11.79 | -0.829 | 21.28 |
| Default `opt` comb | 20.35 | 17.96 | -15.01 | -15.38 to -14.66 | -0.588 | 25.18 |
| Compact asymmetric, W=0.37 | 25.22 | 20.94 | -14.79 | -15.14 to -14.47 | -0.560 | 36.41 |
| Compact asymmetric, W=0.38 | 28.90 | 23.12 | -15.23 | -15.60 to -14.88 | -0.546 | 34.32 |
| Symmetric 90 degrees, Y=1.40 | 26.37 | **24.43** | -14.92 | -15.24 to -14.63 | -0.580 | 26.87 |

All table entries except geometry are dB. Both compact asymmetric variants have Y_COMB=1.00, JOG=0.90, gap=0.11 mm. The symmetric variant has W_C=0.38, Y_COMB=1.40, JOG=0.90, gap=0.11 mm. All use L_C=7.39, W_50=0.37 and explicit overlap=0.27 mm, with three fingers per side, finger width 0.08 and finger gap 0.06 mm.

Exact candidate files:

- `sparams_opt_comb3_w0.38s0.11o0.27y1j0.9.npz`
- `sparams_opt_comb3_sym_w0.38s0.11o0.27y1.4j0.9b90.npz`

The saved 50-ohm conversion was independently reproduced via S → Y → S with real per-port impedances. Maximum complex difference across all audited files is 5.92e-15. The reversal is therefore already present in the saved data and is not a new renormalization implementation discrepancy. Across audited in-band matrices, maximum singular value is 0.98044 or less, and maximum absolute reciprocity residual is 4.08e-4. These checks find no gross passivity violation, but do not prove mesh accuracy or physical validity.

**What is established**

- The default etched compensation substantially improves directivity over the bare full-feed model.
- Moving and shortening the comb, with width/gap retuning, improves the asymmetric design at both reference impedances. Its 50-ohm improvement over the default is about 5.2 dB, rather than the quoted 8.6 dB at the solver reference.
- The uniform-section even/odd model and the two-dimensional solver are useful synthesis tools; they cannot by themselves optimize transitions plus an extended comb.
- The earlier degenerate symmetric geometry is appropriately withdrawn. The valid symmetric result remains useful and should not be discarded.
- The ideal-cap calculation reproduces 76 fF / 37.57 dB at the truncated model's own reference impedance.

**The most consequential mistakes or unsupported conclusions**

1. **Optimizing at the solver reference and calling the result a system result.** Full-feed results use about 47.97–48.02 ohm, while the truncated baseline uses about 45.95–45.98 ohm. A 50-ohm system requires evaluation at 50 ohm, followed by resolving the port-model uncertainty. Avoiding renormalization does not remove that uncertainty; it evaluates a different termination condition. The compact asymmetric design loses 5.78 dB of quoted directivity on conversion, while the symmetric one loses 1.94 dB. Consequently, “symmetry does not pay” is not supported for the intended system. Reference conversion is standard network handling; see [scikit-rf's renormalization example](https://scikit-rf.readthedocs.io/en/latest/examples/networktheory/Renormalizing%20S-parameters.html). This does not establish either model as converged physical truth.

2. **The 37.6 dB ideal-cap result is not a demonstrated system ceiling.** Sweeping 0–150 fF in 1 fF steps on the same truncated matrix, then evaluating at 50 ohm, gives an optimum of 85 fF and 25.78 dB. Keeping 76 fF gives 22.02 dB. Furthermore, truncating geometry and introducing narrow modal ports is not equivalent to validated de-embedding of the complete layout. The claim that essentially all of a 16–17 dB deficit belongs to comb parasitics is not established by this comparison. Correctly referenced equivalent circuit models should agree regardless of their file representation when actual terminations are held fixed; the blanket advice that the 50-ohm file cannot be used for circuit work is misleading.

3. **Fabrication margin was assessed on the main gap while overlooking the comb.** The model's 0.08 mm fingers / 0.06 mm gaps are below JLCPCB's published standard 1 oz multilayer 0.09 / 0.09 mm capability. Even the stated 3 mil BGA exception would not cover 0.06 mm. A different approved process or redesigned comb is required before calling this manufacturable. The wider 0.11 mm main gap is beneficial, but does not solve this. Source checked 2026-09-17: [JLCPCB rigid PCB capabilities](https://jlcpcb.com/capabilities/Capab).

4. **The coupling requirement changes between documents.** The main target is described over 5.7–5.9 GHz; the Comb Study later treats ±0.3 dB as a centre-frequency requirement. No audited 50-ohm dataset satisfies -15 ±0.3 dB across the full band. The compact candidate reaches -15.60 dB; the symmetric candidate reaches -14.63 dB. Decide explicitly whether calibration permits band slope, and keep nominal centring separate from ripple and production tolerance.

5. **Physical explanations became stronger than the experiments justify.** “Series inductance refuted” and “ground capacitance settles it” are too categorical. A small reactance change can matter greatly to a cancellation null. Holding overlap fixed does not hold the complete capacitance matrix fixed: stem length, tip/root fields, bus separation and routing all change. Summing capacitance of all six fingers to ground and comparing it directly to one bridging capacitor also mixes modal weightings. Ground capacitance is plausible and deserves extraction, not a verdict from correlated return-loss curves. Moving the comb and shortening the board is likewise not an isolated displacement experiment.

6. **Broadband response is not manufacturing robustness.** A flat nominal frequency response says nothing conclusive about correlated etch changes, substrate height, dielectric constant, copper thickness, finish, or mask. A small drawing grid is a convenience, not a physical prohibition on intermediate nominal values. Quantization should not replace tolerance analysis.

**Specific implementation and provenance issues**

- `MESH['normal']['comb']=0.05` is declared but never used. Only `trace=0.30` and `port=0.20` are passed to the mesher. Geometry can still force smaller elements, so this does not prove a bad mesh; it means the claimed dedicated comb refinement is absent. There is no demonstrated fine-to-finer convergence of the reported isolation.
- The script requests 25 frequencies over 4.5–7.5 GHz and vector-fits each S entry onto 601 frequencies using `model_S(..., _warn=False)`. The NPZ omits original solved samples, fit residuals, mesh statistics, complete parameters and solver-version provenance. Smooth curves and a precise worst-case value are insufficient validation of a deep null.
- Output names omit `--fast`, `--cu-loss`, port/layer settings and some other parameters, allowing materially different runs to overwrite the same result. A bend-only override is also absent from the tag unless another geometry override is present.
- The asymmetric path hardcodes 90-degree turns even if `--bend` is supplied. `--at-comb` uses an asymmetric builder even with `--symmetric`. Geometry guards against short intermediate segments are inside the symmetric branch only. Restrict these flag combinations or implement them consistently before using them in future sweeps.
- In `opt`, the preset overlap takes precedence over `ctarget`, so changing `--ctarget` does not tune the comb as its help suggests. In the symmetric builder, preset overlap fallback is skipped unless explicitly passed. Existing candidate commands do pass it explicitly.
- The Comb Study layout plot calls `_build` without its candidate gap, so that drawing uses the default 0.10 mm instead of the stated 0.11 mm. Illustrations should be generated from the same complete configuration as the result.
- The 2-D convergence discussion omits copper snapping: at d=10 um, Python's rounding maps t=35 um to 40 um; d=5 um represents 35 um exactly. Thus the 10-versus-5 comparison is not purely discretization error even though W and gap are aligned. The Transcalc comparison also has inconsistent capacitance numbers across the two notes. Its discrepancies merit investigation, but a single-line impedance agreement does not validate every coupled-mode quantity.
- README describes superseded geometry, API assumptions and unexecuted setup. The main note still promotes series inductance while the Comb Study claims to refute it. “Shipped” and “measured” in these pages mean a default simulated design and simulated values; hardware validation was not established in this review.
- Conductor loss remains missing. Through-loss values are optimistic model results, and adding a scalar loss afterward cannot establish how finite conductivity changes isolation. The claim that the loss option is broken needs a straight-line control and reference-convention investigation.

**Recommended direction**

The valid symmetric 90-degree variant is the provisional leader for directivity in the saved 50-ohm data: 24.43 versus 23.12 dB. Its 1.31 dB advantage is too small to declare a robust winner with the unresolved port and mesh errors. The compact asymmetric layout remains a strong alternative: better input match, slightly lower simulated through loss, and shorter fingers. Do not adopt either unchanged for fabrication.

The next useful work, in order:

1. Freeze the system requirement: 50-ohm terminations, allowable centre coupling and band variation, minimum directivity/return loss, intended forward-monitor or reflected-power function, and actual detector/termination loads.
2. Make the result pipeline reproducible: complete configuration and version metadata, unique run IDs, raw solved points, fitted points, mesh statistics, and consistent 50-ohm metrics.
3. Validate a straight feed line and both candidate port/mesh models, including direct solves near 5.7, 5.8 and 5.9 GHz and refinement of comb edges/gaps and ports. Compare complex isolation, not only dB minima.
4. Redesign the compensation to an agreed manufacturing rule, then retune both shortlisted routings at 50 ohm. Start with a compact etched capacitor over an intact ground plane. A ground relief can be an exploratory branch, but changes return currents and may expose lower layers, so it is not an isolated parasitic-removal experiment.
5. Sweep correlated etch bias, comb gaps and widths, dielectric thickness/permittivity, copper thickness, and actual loads. Choose by worst-case performance or yield, then build a measurement coupon with calibration/de-embedding structures.

The immediate gain is to repair the comparison criteria and fabrication assumptions. Additional nominal optimization of the existing 60 um comb risks refining a result that cannot be transferred to the intended board process.

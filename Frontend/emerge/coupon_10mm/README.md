# 10 mm coupon: EMerge models

## Frozen revision A input and revision B production board

`pcb_geometry.json` is the frozen input used for these studies. It was extracted
from `Frontend/kicad/FrontendPCBCoupon/FrontendPCBCoupon.kicad_pcb` at commit
`a9084aac1679af253d10157d710fbbb8d9ddad6e`, with SHA-256
`3ba350c1c6aad231a5e7823e1dddab60c90445c49e33a89f6d0dd30495e28443`.
That historical board is retained in Git. The live board is now the ordered
revision B, which already includes the L2 relief. Reproduction of the studies
uses the saved JSON; it does not require another PCB extraction.

`extract_pcb.py` refuses to overwrite existing geometry with a different source
board revision. For a new board extraction, provide `--board` and a distinct
`--output` filename. Keep the revision A JSON unchanged for the historical
intact-L2 control and the geometry sweeps.

## Reports in chronological order

Read these in order to follow the model changes, geometry search and numerical checks.

| Order | Report | Question / purpose |
|---|---|---|
| 01 | [PCB-only model](../../../Notes/FunRad/Frontend/Coupon/01_PCB_ONLY_RESULTS.md) | Compare the two initial meshes and measurements; identify the launch problem. |
| 02 | [PCB modal-port control](../../../Notes/FunRad/Frontend/Coupon/02_MODAL_PORT_CHECK.md) | Add L3 and test the alternative excitation on unchanged launches. |
| 03 | [Simplified connector geometry](../../../Notes/FunRad/Frontend/Coupon/03_CONNECTOR_GEOMETRY.md) | Define the BWSMA connector and coaxial excitation model. |
| 04 | [Connector-inclusive control](../../../Notes/FunRad/Frontend/Coupon/04_COAX_RESULTS.md) | Compare intact-L2 simulation with measurements before changing the launches. |
| 05 | [Initial L2 cutouts](../../../Notes/FunRad/Frontend/Coupon/05_L2_CUTOUT_RESULTS.md) | Test ground relief, wider openings and the abrupt-step alternative. |
| 06 | [Cutout geometry search](../../../Notes/FunRad/Frontend/Coupon/06_L2_CUTOUT_FLATNESS_SWEEP.md) | Optimize width and length over 5.3–6.3 GHz; extend beneath the taper, including 5.0 mm. |
| 07 | [Broadband verification](../../../Notes/FunRad/Frontend/Coupon/07_BROADBAND_CHECK.md) | Check the selected 2.8 × 4.8 mm cutout over 0.5–6.5 GHz. |
| 08 | [Mesh refinement](../../../Notes/FunRad/Frontend/Coupon/08_MESH_REFINEMENT.md) | Check the selected geometry with three meshes over 5.3–6.3 GHz. |
| 09 | [L3 cutout experiment](../../../Notes/FunRad/Frontend/Coupon/09_L3_CUTOUT_RESULTS.md) | Test matching L3 windows beneath the selected L2 openings; retain Bottom. |
| 10 | [Dielectric sensitivity](../../../Notes/FunRad/Frontend/Coupon/10_DIELECTRIC_SENSITIVITY.md) | Test εr=4.2 / 4.5 / 4.8 with fixed geometry, loss tangent and mesh. |

The numbered reports and their plots live in `Notes/FunRad/Frontend/Coupon/`.
The report generators publish there through `report_paths.py`. This README
documents the executable modules and reproduction commands.

## Flatness study over 5.3–6.3 GHz

**Initial geometry sweep: 6 geometries / 66 frequency cases on the standard mesh.** The best tested opening is
**2.8 × 4.8 mm**, with the original tapers and L3 intact. Across the 11 points,
worst insertion loss is 0.627 dB, S21 span is 0.035 dB, and worst S11 is −15.65 dB.
At 5.8 GHz: S21=−0.595 dB and S11=−20.01 dB. Reflection flatness is measured
in amplitude; S11 still varies substantially when plotted in dB.

[L2 cutout flatness sweep](../../../Notes/FunRad/Frontend/Coupon/06_L2_CUTOUT_FLATNESS_SWEEP.md) is a separate report
for six width/length combinations: W=2.8, 3.5 or 4.2 mm; L=4.2 or 4.8 mm.
Each case uses 11 direct points (5.3, 5.4, …, 6.3 GHz), original tapers and
intact L3. The fixed score balances worst-case loss/reflection and variation;
its full definition and all component metrics are included in the report.

```powershell
.\.venv\Scripts\python.exe -m coupon_10mm.sweep_flatness
.\.venv\Scripts\python.exe -m coupon_10mm.report_flatness
```

The sequential runner is resumable. Geometry meshes are kept in their existing
variant folders; these new results have a `_5p3to6p3GHz` suffix, so they do not
overwrite broadband data. To run one case directly, use, for example:

```powershell
.\.venv\Scripts\python.exe -m coupon_10mm.connector_model --l2-opening 3.5 4.2 --frequency-grid flatness --solve
```

The under-taper extension study holds width at 2.8 mm and tests lengths
5.0, 5.2, 5.6 and 6.0 mm, adding 0.2–1.2 mm beneath the unchanged tapers.
It appends phase 2 to the same flatness report and reuses the 4.8 mm result
as a reference without solving it again:

**Completed: four extensions, 44 new frequency cases; 10 geometries / 110 cases overall.** Length 4.8 mm
retains the best worst-case loss/matching and S21 flatness. Length 5.6 mm
has the flattest S11 (0.51 dB span), but around −10.3 dB, with 0.976 dB
worst insertion loss. Extending through the full taper to 6.0 mm is worse
than 5.6 mm in all four criteria. The added 5.0 mm case (T04) gives 0.700 dB
worst loss, 0.069 dB S21 span and -13.50 dB worst S11.
It ranks second under the fixed score. See phase 2 of the flatness report.

```powershell
.\.venv\Scripts\python.exe -m coupon_10mm.sweep_taper_cutout
.\.venv\Scripts\python.exe -m coupon_10mm.report_taper_cutout
```

## L2 pad cutouts with the BWSMA connectors

**The first 20-point trial is complete.** See [results and comparison plots](../../../Notes/FunRad/Frontend/Coupon/05_L2_CUTOUT_RESULTS.md).
At 6 GHz the simulated S21 improves from −8.79 to −1.32 dB; S11 improves
from −1.05 to −8.48 dB. This remains an initial size trial on one mesh.

The first trial removes **1.6 × 4.8 mm of L2 copper beneath each signal pad**.
The dielectric is retained. L3, bottom ground, vias, connectors and top copper
are unchanged. The mesh and sweep use the same settings as the connector
control, with separate files under `preview_coax_open_1.6x4.8mm/` and
`result_coax_open_1.6x4.8mm.*`.

```powershell
# Preview this geometry:
.\.venv\Scripts\python.exe -m coupon_10mm.connector_model --l2-opening 1.6 4.8 --view

# Generate a new mesh and solve the 20-point trial:
.\.venv\Scripts\python.exe -m coupon_10mm.connector_model --l2-opening 1.6 4.8 --solve

# After a matching mesh exists, inspect it without remeshing:
.\.venv\Scripts\python.exe -m coupon_10mm.connector_model --l2-opening 1.6 4.8 --reuse-mesh --view-mesh

# Compare the completed sweep with the original-ground connector control:
.\.venv\Scripts\python.exe -m coupon_10mm.compare_cutout
```

Commands run from `C:\Fun\ToyRadar\Frontend\emerge`. The comparison produces
`05_L2_CUTOUT_RESULTS.md`, plots, metrics and a 50 Ω Touchstone file. A measurement
of the modified board is not available; the original-board measurement is
shown only for context.

The second completed width trial uses **4.2 × 4.8 mm** cutouts, reaching the inner edges
of the 0.9 mm ground pins at y=±2.10 mm. It removes no L2 beneath the pins
or ground vias; the PCB pads have a 0.15 mm inner overhang beyond the pins.
Results are stored separately under `preview_coax_open_4.2x4.8mm/` and
`result_coax_open_4.2x4.8mm.*`.
Compared with 1.6 mm width, S21 improves from −1.32 to −0.76 dB at 6 GHz,
but worsens from −0.42 to −1.18 dB at 4 GHz. The report includes both trials.

```powershell
.\.venv\Scripts\python.exe -m coupon_10mm.connector_model --l2-opening 4.2 4.8 --solve
.\.venv\Scripts\python.exe -m coupon_10mm.compare_cutout --compare-widths
```

`--compare-widths` adds the wide trial and three-variant plots to
`05_L2_CUTOUT_RESULTS.md`. Regenerating the first trial's report with the default
comparison command preserves this added width-comparison section.

## Abrupt pad-to-microstrip transitions

`--transition step` replaces the two PCB tapers with abrupt 1.2-to-0.37 mm
steps at the existing pad inner edges. The pads stay 4.8 × 1.2 mm; their
10 mm separation becomes uniform narrow microstrip. The connectors and
4.2 × 4.8 mm ground cutouts are unchanged. Omitting this flag retains the
original KiCad tapers.

```powershell
.\.venv\Scripts\python.exe -m coupon_10mm.connector_model --l2-opening 4.2 4.8 --transition step --view
.\.venv\Scripts\python.exe -m coupon_10mm.connector_model --l2-opening 4.2 4.8 --transition step --solve
.\.venv\Scripts\python.exe -m coupon_10mm.compare_step
```

This keeps the same **20-point 0.5–6 GHz grid**, rather than adding a separate
narrow-band sweep. The target is 5.8 GHz ±75 MHz, but only the 5.8 GHz point
of this grid lies inside that band. `compare_step` appends the geometry and
response comparison to `05_L2_CUTOUT_RESULTS.md`. The step files have a `_step`
suffix; the three earlier connector sweeps remain separate.
The step sweep completed: at 5.8 GHz, S21 worsens from −0.81 to −1.11 dB
and S11 from −12.88 to −9.34 dB. The tapered 4.2 mm-cutout geometry remains
the better reference at this sampled application frequency.

## Original BWSMA connectors with coax modal ports

**First control completed: 20 frequencies, no ground openings.** See
[results and measurement comparison](../../../Notes/FunRad/Frontend/Coupon/04_COAX_RESULTS.md), and
[geometry, dimensions and assumptions](../../../Notes/FunRad/Frontend/Coupon/03_CONNECTOR_GEOMETRY.md).

From PowerShell in `C:\Fun\ToyRadar\Frontend\emerge`:

```powershell
# Open EMerge's native rotatable geometry viewer:
.\.venv\Scripts\python.exe -m coupon_10mm.connector_model --view

# Generate the actual FEM mesh, then keep the native mesh viewer open:
.\.venv\Scripts\python.exe -m coupon_10mm.connector_model --view-mesh

# Inspect the already generated matching mesh without rebuilding it:
.\.venv\Scripts\python.exe -m coupon_10mm.connector_model --reuse-mesh --view-mesh

# Save geometry illustrations only:
.\.venv\Scripts\python.exe -m coupon_10mm.connector_model --images

# Reproduce the approved original-ground connector control:
.\.venv\Scripts\python.exe -m coupon_10mm.connector_model --reuse-mesh --solve
.\.venv\Scripts\python.exe -m coupon_10mm.compare_coax
```

`connector_model.py` separates connector dimensions (`Connector`), PCB and
connector construction (`build`), CAD connectivity checks (`check_geometry`),
FEM mesh settings (`MESH_MM` and `mesh`), illustrations (`images`), and the
explicit sweep (`solve`). Close the interactive window to return to PowerShell.
Viewers never proceed to a frequency sweep after closing. `--solve` is a
separate command and cannot be combined with either viewer.

The light-background assembly, cutaway and port-section illustrations use
`images()` in `connector_model.py`: Gmsh tessellates the actual committed OCC
CAD surfaces, and a custom PyVista plotter sets the camera, colours, transparency
and clipping plane. They are CAD renders, not EMerge internal-viewer screenshots.
`native_mesh.png`, with its dark background and EMerge watermark, is produced
by EMerge's own `model.view(..., plot_mesh=True)`.

`native_view.py` works around EMerge 2.8.9 / emsutil's off-screen screenshot
reset: it recreates the plotter with `pv.OFF_SCREEN=False` before showing the
interactive window. Otherwise a `vtkGenericRenderWindowInteractor` can survive
the reset and the window can return immediately. The corrected plotter uses
`vtkWin32RenderWindowInteractor`. This fix also applies to `model.py --view-mesh`.

The older artificial PCB-feed and lumped-port models below remain reference
experiments; they are separate from the connector proposal.

## Preview the proposed L2 openings first

From PowerShell in `C:\Fun\ToyRadar\Frontend\emerge`:

```powershell
.\.venv\Scripts\python.exe -m coupon_10mm.model --layers 3 --port-type modal --l2-opening 1.6 4.8 --view
```

This opens EMerge's native interactive geometry viewer. The arguments after
`--l2-opening` are **width and length in mm**, for each of two symmetric windows.
This initial trial has 1.6 × 4.8 mm windows under the signal pads. Only L2 is
cut; L3 and the ground beneath the connector ground tabs/vias remain intact.
The openings stop before the pad-to-trace tapers. The modal feed grounds are
cut where they overlap the windows; the distant port planes retain solid ground.

`--view` uses quick preview meshing. To inspect the actual simulation mesh,
replace `--view` with `--view-mesh`; this takes longer. Rotate with left-drag,
zoom with the wheel and pan with Shift + left-drag. Close the viewer to return
to PowerShell. **Neither viewer command runs a frequency sweep.**

The opening variant has its own `preview_3layer_modal_open_1.6x4.8mm/` directory.
Its results, if explicitly solved later, use the matching variant name and do
not replace the intact-L2 reference. Omit `--l2-opening 1.6 4.8` to preview the
intact-L2 control. The opening dimensions are an initial trial, not an optimum.

## L3 and modal-port control

The optional **top/L2/L3 model with modal ports** uses separate files under
`preview_3layer_modal/` and `result_3layer_modal.*`. The original two-layer
results below remain the lumped-port references. The new control keeps both
launch pads, tapers and L2 ground intact; no opening has been added.

```powershell
# Native interactive mesh viewer for the L3/modal-port control:
python -m coupon_10mm.model --layers 3 --port-type modal --reuse-mesh --view-mesh

# Cross-sectional port checks only, at 1 GHz (no 3-D sweep):
python -m coupon_10mm.model --layers 3 --port-type modal --reuse-mesh --check-modes

# One 20-frequency 3-D control sweep:
python -m coupon_10mm.model --layers 3 --port-type modal --reuse-mesh --solve

# Compare the completed control with the lumped reference and measurements:
python -m coupon_10mm.compare_modal
```

L3 top is z=−1.2906 mm and its thickness is 15.2 µm. The port planes are
x=−5 and 25.16 mm, on uniform 1.2 mm-wide access lines. The access-line length
is 5.28 mm per end. Their native modal impedance is approximately 22.8 Ω at
1 GHz. `Smat50_pad` removes the feed propagation in native modal impedance
and then converts to a 50 Ω reference at x=0.28 and 19.88 mm. `Smat50` keeps
the outer feed reference planes. These two arrays must not be confused.
The new preview mesh has 341,191 tetrahedra: 60 µm signal-edge target,
180 µm signal-surface target, 250 µm port-face target and 900 µm substrate
target, using first-order FEM. [Modal-port control report](../../../Notes/FunRad/Frontend/Coupon/02_MODAL_PORT_CHECK.md).

## Original two-layer lumped-port references

**Two completed reference sweeps, using two meshes.** Both use first-order FEM and
the same top/L2 PCB geometry. No simulation was rerun to relabel the plots.

| Mesh name (signal-edge target) | Tetrahedra | Solved frequencies | Where used |
|---|---:|---:|---|
| Mesh 40 µm | 419,408 | 8 | Archived first full-band plot; purple dashed curve in Figure 1 |
| Mesh 60 µm | 218,732 | 20 | Green curve in Figure 1; green curve in the 2.6 GHz detail (Figure 2) |

See [the mesh parameter table, figures and results](../../../Notes/FunRad/Frontend/Coupon/01_PCB_ONLY_RESULTS.md). The names refer
to a **local size target at signal edges**, not a uniform grid. Two earlier
second-order solve attempts were stopped for memory use; neither produced a
completed S-parameter dataset. CAD/mesh/viewer previews are not EM sweeps.

The model contains only **top copper, the top dielectric, and L2**.
The four-layer geometry/mesh preview in `preview/` produced no EM results and
is not used in any comparison plot. `preview_2layer/` contains Mesh 60 µm.

## Native interactive viewer

From `C:\Fun\ToyRadar\Frontend\emerge`, with the virtual environment active:

```powershell
python -m coupon_10mm.model --view-mesh
```

Once the top/L2 mesh exists, open it without remeshing:

```powershell
python -m coupon_10mm.model --view-mesh --reuse-mesh
```

This builds the two-layer tetrahedral mesh and opens **EMerge's own viewer**
with surface-mesh edges visible. It does not run an electromagnetic solve.
Drag with the left mouse button to rotate, scroll to zoom, and use
Shift + left-drag to pan. Close the window to return to the terminal.

For solid geometry instead of mesh edges:

```powershell
python -m coupon_10mm.model --view
```

Viewer commands and `--solve` cannot be combined: closing the viewer never
starts a frequency sweep automatically.

## Model

The source is `Frontend/kicad/FrontendPCBCoupon/FrontendPCBCoupon.kicad_pcb`,
coupon D at original board coordinates x=47.460–67.620, y=112.000–128.000 mm.
KiCad's polygon engine extracts the pads, saved filled copper and teardrops;
the tapers are not replaced by a guessed shape. The board is not modified.

| Item | Value |
|---|---|
| Modelled board portion | 20.16 × 16 mm; 0.2606 mm including top copper and L2 |
| Signal pads | 4.8 × 1.2 mm each |
| Connecting track | 0.37 mm wide; 10 mm between pad inner edges, including the two tapers |
| Top copper to L2 | 0.2104 mm dielectric |
| Copper | F.Cu 35 µm and L2 15.2 µm; conductivity 58 MS/m |
| FR-4 | er=4.5, tanδ=0.02, from the KiCad stack-up |
| Ground connections | 12 plated holes, truncated at the bottom of L2; nominal 0.3 mm bore, assumed 25 µm wall |
| Ports | Ideal 50 Ω vertical faces between signal pads and L2 at x=0.4 and 19.76 mm |
| Air box | x=−5…25.16, y=−13…13, z=−6.5512…5.035 mm |
| Exterior | First-order absorbing boundary; no metal shield |
| Mesh | Current counts in `preview_2layer/geometry.json` |
| Local targets | Substrate 0.9 mm; signal surface 0.18 mm; signal edges 0.06 mm; ports 0.08 mm |

The earlier coupler simulations used er=4.4; this model explicitly follows the
CAD value 4.5. Consecutive polygon vertices closer than 5 µm are coalesced to
avoid microscopic OCC corner segments. Connector bodies, pins, solder fillets,
soldermask and broken panel tabs are omitted. This is a **PCB discontinuity
model**, not a complete model of the measured SMA assembly. Both sweeps completed
successfully. At eight shared frequencies, changing the mesh changed S21 by at
most 0.04 dB and S11 by at most 0.34 dB. The 2.65 GHz notch has not been checked
with Mesh 40 µm, and the effect of increasing the air-box size has not been checked.

## Files

- `extract_pcb.py`: KiCad → `pcb_geometry.json`; source hash and untouched copper contours.
- `model.py`: EMerge geometry, materials, ports and mesh. Solving requires `--solve`.
- `view.py`: render the actual committed CAD using the already generated Gmsh mesh.
- `preview_2layer/geometry.json`: dimensions, assumptions and mesh counts.
- `preview_2layer/coupon.brep`: CAD; `preview_2layer/coupon.msh`: mesh; `preview_2layer/coupon.vtk`: mesh for ParaView/PyVista.
- `preview_2layer/native_geometry.png`: EMerge's native geometry screenshot.
- `preview_2layer/mesh_3d.png`, `preview_2layer/mesh_taper.png`, `preview_2layer/mesh_section.png`: optional views generated by `view.py`.

## Reproduce in PowerShell

From `C:\Fun\ToyRadar\Frontend\emerge`:

```powershell
# Only needed after the PCB source changes; uses KiCad's Python.
& 'C:\Program Files\KiCad\10.0\bin\python.exe' .\coupon_10mm\extract_pcb.py

# CAD and mesh only. This does not run the EM frequency sweep.
.\.venv\Scripts\python.exe -m coupon_10mm.model --mesh

# Save preview images using the existing mesh; does not remesh or solve.
.\.venv\Scripts\python.exe -m coupon_10mm.view
```

The explicit solve command, to use after geometry/mesh review, is
`python -m coupon_10mm.model --solve`. It rebuilds the mesh and solves the
20 directly sampled frequencies listed in `model.py`: broad coverage of
0.5–6 GHz, with 50 MHz steps from 2.4 to 2.7 GHz around the measured S11 dip.
To solve the already reviewed mesh, use
`python -m coupon_10mm.model --solve --reuse-mesh`.
Frequency matrices are assembled and solved one at a time to limit RAM use.
This is a single EMerge `run_sweep()` call containing all frequencies;
`frequency_groups=1` controls matrix batching, not separate simulation scripts.
The default is **first-order FEM** (`--order 1`) on the reviewed mesh. The
second-order trial requested approximately 75 GB during factorization on this
32 GB PC and was stopped without producing results. `--order 2` is available
for a machine with enough memory. Both completed sweeps use first-order elements;
their accuracy at the eight shared frequencies was compared between the two meshes.
Results are written to `result_2layer.npz`; the run status is recorded in
`preview_2layer/geometry.json`.

After completion, generate the measurement comparison and numerical checks:

```powershell
python -m coupon_10mm.compare
```

This produces `preview_2layer/simulation_comparison.png` and `metrics.json`.
It also writes `01_PCB_ONLY_RESULTS.md` and `result_2layer.s2p`. Solve metadata is preserved
in `result_2layer.json` separately from the replaceable preview metadata.
The measured files contain S11/S21 only; their zero S12/S22 columns are not
treated as measurements. The simulated ports have a fixed 50 Ω reference.

Mesh 40 µm's eight-frequency result and first comparison plot are preserved in
`runs/baseline_8pt/` (small data and plots only). Mesh 60 µm's 20-frequency
result is `result_2layer.npz`. `compare.py` generates Figure 1 with both named
meshes, and Figure 2 (`resonance_2p6GHz.png`) with Mesh 60 µm only.

## Broadband verification of the selected cutout

[0.5–6.5 GHz check](../../../Notes/FunRad/Frontend/Coupon/07_BROADBAND_CHECK.md): 31 directly solved points, reusing the
selected 2.8 × 4.8 mm mesh. Worst sampled loss is 0.913 dB (4.5 GHz), and
worst S11 is −12.85 dB (4 GHz). The 5.3–6.3 GHz results repeat within 4e−13
in complex S. See the report for comparison plots and the reproduction command.

## Mesh refinement of the selected cutout

[Mesh refinement report](../../../Notes/FunRad/Frontend/Coupon/08_MESH_REFINEMENT.md): the saved standard mesh (362,870
tetrahedra) is compared with two new first-order meshes (480,870 and 649,089).
Each uses the same 11 frequencies over 5.3–6.3 GHz: 22 new frequency solves.
The last change is at most 0.0157 dB in S21 and 0.00155 in reflection amplitude.
The finest mesh gives 0.578 dB worst insertion loss and −16.18 dB worst S11.
The geometry remains 2.8 × 4.8 mm with original tapers and L3 intact.

Use `--mesh-profile standard`, `refined` or `finer` with `coupon_10mm.connector_model`.
The target-size table, comparison plots and full commands are in the report.

## L3 cutout experiment

[Report 09](../../../Notes/FunRad/Frontend/Coupon/09_L3_CUTOUT_RESULTS.md): one new 11-point sweep using the same
finer mesh targets as the control. Matching 2.8 × 4.8 mm L3 windows worsen
worst loss from 0.578 to 0.644 dB, S21 span from 0.030 to 0.073 dB, and
worst S11 from −16.18 to −14.11 dB. Retain L3 and Bottom intact.

Use `--l3-opening` together with `--l2-opening WIDTH LENGTH` to reproduce this
local L3 relief. The flag removes copper only inside the two matching windows.

## Dielectric sensitivity

[Report 10](../../../Notes/FunRad/Frontend/Coupon/10_DIELECTRIC_SENSITIVITY.md): two new 11-point sweeps at εr=4.2
and 4.8, with the εr=4.5 finer-mesh reference reused. The exploratory range
is ±0.3 around the CAD value, not a supplier tolerance guarantee. Loss tangent
stays 0.02. Across the sampled cases, worst loss is 0.632 dB, S21 span remains
below 0.097 dB, and worst S11 is −14.49 dB. Keep the current geometry for a
revised physical coupon; L3 and Bottom remain intact.

`--pcb-er VALUE` changes the homogeneous PCB dielectric; non-nominal results
receive an `_er...` suffix. `sweep_dielectric.py` runs the two corners sequentially
on the saved finer mesh. The coax mode search now uses the analytical PTFE TEM
index; port Z0 and propagation agree with the saved nominal reference.

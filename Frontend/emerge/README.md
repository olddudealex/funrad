# FunRad coupler simulations

Current geometry: **R052 / final51**. Latest physical-model check: **R058 / final51_copper9**, same copper outline, finite copper conductivity and nine frequencies. It is a prototype candidate: R058 misses the upper-band coupling window by about 0.12 dB. See [design report](../../Notes/FunRad/TX%20Coupler%20EM%20Method.md) and [simulation catalogue](../../Notes/FunRad/Coupler%20Simulation%20Catalogue.md).

## Active files

| File or folder | Purpose |
|---|---|
| `redesign.py`, `redesign_configs/` | Current EM driver and tested configurations; `selection.json` selects report examples |
| `coupler_sim.py` | Shared polygon builder and geometry helpers imported by the current driver; its standalone defaults are historical |
| `results_redesign/` | All 58 attempts: configs, outlines, compact raw matrices, metrics, mesh counts and available driver snapshots |
| `coupler_catalogue.py`, `coupler_decision_tree.py` | Rebuild SQLite, searchable table, gallery, animation and full decision tree |
| `coupler_story_figures.py`, `coupler_box_figure.py` | Current circuit-search, response and enclosure illustrations |
| `redesign_figures.py` | Earlier geometry, sensitivity and ground illustrations still referenced by the consolidated report |
| `coupled_2d.py`, `final_cross_section_check.py`, `figs_2d.py` | Cross-section solver, final diagnostic and historical explanatory figures |
| `redesign_geometry_check.py`, `redesign_summary.py` | Saved-outline clearance check and console results summary |
| `export_coupler_footprint.py`, `validate_coupler_footprint.py` | Exact-outline footprint export and native KiCad validation |
| `results/*.npz` | 51 historical fitted data sets needed for the complete catalogue and lumped-capacitor explanation |
| `legacy/` | Archived helpers and unrun proposals; not part of the current workflow |

## Rebuild reports without solving EM

Use the existing `.venv`, or create one using `setup.ps1`, `setup.bat` or `setup.sh`. The saved runs used EMerge 2.8.9; `environment_versions.json` records installed package versions. `requirements.txt` gives installation ranges, not an exact platform lock.

```powershell
.\.venv\Scripts\python.exe coupler_story_figures.py
.\.venv\Scripts\python.exe coupler_catalogue.py
.\.venv\Scripts\python.exe coupler_box_figure.py
.\.venv\Scripts\python.exe export_coupler_footprint.py
```

The committed cross-section diagnostic is in `catalogue/final_cross_section.json`; recompute with `python final_cross_section_check.py` when needed. `validate_coupler_footprint.py` requires KiCad's Python environment, not the EMerge venv. See [footprint integration and checks](../kicad/README.md).

## Run EM

```powershell
.\.venv\Scripts\python.exe redesign.py redesign_configs/final51_copper9.json
```

Completed runs are reused; new configurations generate their own hashed result directories. Preserve existing raw results. R058 models a PEC enclosure with modal-port apertures; its dimensions are documented in the footprint README. No enclosure-size convergence sweep has been performed.

## What goes into Git

Keep source code, tested configs, all compact redesign records, historical NPZ matrices, report images and the footprint. The historical matrices total about 18 MB and preserve the original catalogue; duplicate historical Touchstone exports stay local. Exclude the regenerable ~78 MB SQLite database, environment, caches, meshes, solver logs and temporary GIF preview frames. The full animation is about 2 MB and is retained because the reports use it.

Run IDs and original configuration timestamps are committed separately, so rebuilding after checkout preserves the search order. Driver snapshots preserve available run-specific driver versions; older runs did not snapshot every dependency and cannot be claimed to be bit-for-bit reproducible.

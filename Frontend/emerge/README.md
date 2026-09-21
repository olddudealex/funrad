# FunRad coupler: current code

## Folder map

```text
emerge/
  simulation/          Main functionality: geometry, materials, box, mesh, solver
  reports/             Figures, animation and catalogue generators (saved data)
  tests/               Geometry/mesh regression, clearance, 2-D and KiCad checks
  exports/             KiCad footprint generation from saved copper outlines
  redesign_configs/    Inputs for the recorded experiments
  results_redesign/    Raw evidence for 58 attempts, including 54 coupler runs
  results/             Historical matrices used by the design explanation
  catalogue/           Generated indexes/database and saved diagnostic results
  setup.*              Environment installation
  requirements.txt     Dependencies
```

Run every Python command below **from this `emerge/` directory**, using `python -m package.module`. The subfolders are Python packages, so imports work without path hacks. Report images are written to `Notes/FunRad/images/`; the footprint is written to `Frontend/kicad/`.

**One EM entry point: [simulation/run.py](simulation/run.py).** This is the refactored implementation of the 54 four-port simulations and four numerical controls. The original code is preserved in commit `6c4012c`; obsolete helpers have been deleted from the working folder.

Current geometry: **R052 / final51**. Latest physical-model check: **R058 / final51_copper9**, same outline with finite copper conductivity and nine frequency samples. It remains a prototype candidate; R058 misses the upper-band coupling window by about 0.12 dB.

## Read the simulation in this order

```text
JSON configuration
  -> domain.create_simulation()    materials and PCB layouter
  -> geometry.build_paths()        routed lines and comb fingers
  -> domain.build_domain()         copper thickness, ground, box and port faces
  -> mesh.generate_mesh()          global and local refinement
  -> ModalPort + run_sweep()       port conditions and frequency solve
  -> raw.npz + metrics.json        modal and 50-ohm S parameters
```

| What you want to understand/change | Where to look |
|---|---|
| Coupled lines, bends and comb placement | [simulation/geometry.py](simulation/geometry.py): `build_coupler()` |
| Finger length and attachment to its conductor | `simulation/geometry.py`: `finger_length()`, `FingerBuilder` |
| Polygon cleanup needed by EMerge | `simulation/geometry.py`: `install_polygon_dedupe()` |
| Dielectric and finite copper conductivity | [simulation/domain.py](simulation/domain.py): `create_simulation()` |
| Substrate, ground, optional L2 opening, enclosure, port faces | `simulation/domain.py`: `build_domain()` |
| Trace, port and edge mesh sizes | [simulation/mesh.py](simulation/mesh.py): `generate_mesh()` |
| Frequency sweep, boundary conditions, saved outputs | [simulation/run.py](simulation/run.py): numbered steps in `run()` |

Geometry now receives configuration values explicitly. It no longer modifies a historical module's globals or replaces its segment method. The asymmetric geometry and lower-stack options remain because the comparison experiments used them. The polygon-deduplication workaround also remains necessary for these models.

## Parameters

Dimensions are **mm**, unless stated otherwise. Original JSON keys remain unchanged to preserve run IDs and directory hashes; geometry code uses descriptive variable names.

| JSON keys | Meaning |
|---|---|
| `length`, `w`, `gap` | Central coupled-section length, conductor width and edge gap |
| `feed_w` | Feed and comb-jog conductor width |
| `y`, `jog`, `bend` | Line-centre spacing at combs, jog length, bend angle in degrees |
| `fingers`, `fw`, `fg`, `overlap` | Fingers per conductor per comb, finger width/gap, opposing-finger overlap |
| `symmetric`, `shift` | Mirrored routing and optional longitudinal comb shift |
| `h`, `t`, `er`, `tand` | Dielectric height above L2, copper thickness, relative permittivity, loss tangent |
| `copper_loss`, `conductivity` | Finite conductivity enabled; conductivity in S/m |
| `resolution` | Global mesh size as a **fraction of wavelength**, not mm |
| `trace_mesh`, `port_mesh`, `edge_mesh` | Local sizes in mm; zero edge size disables only explicit edge refinement |
| `port_width` | Width of each modal-port face |
| `fmin`, `fmax`, `nf` | Frequency limits in GHz and number of directly solved points |
| `lower_stack`, `relief` | Lower-stack control and L2 aperture width |
| `straight`, `legacy_ground` | Numerical-control switches; normally false |
| `tolerance` | Permit the smaller feature limits used by the etch-sensitivity controls |

Fixed settings in `simulation/domain.py`: roof 2.5 mm above substrate, 2 mm lateral margins, no end margin. Unassigned exterior faces default to PEC; the driver applies modal-port conditions to the port faces. `simulation/geometry.py` fixes feed-centre spacing at 2.5 mm and each straight feed at 1.5 mm.

## Run or inspect a configuration

```powershell
.\.venv\Scripts\python.exe -m simulation.run redesign_configs/final51_copper9.json
```

Completed runs are reused. Start from that JSON and give a new experiment a new `name`. Changing Python code alone does not invalidate a cached result. `--preview` builds the geometry without meshing/solving for a new config; saved outlines are already available in each completed run's `layout.png` and `layout.json`.

Use the existing environment, or `setup.ps1`, `setup.bat` or `setup.sh`. The saved runs used EMerge 2.8.9; `environment_versions.json` records versions. `requirements.txt` is an installation range, not an exact platform lock.

## Supporting tools: none is an alternate 3-D driver

| Files | Purpose |
|---|---|
| `reports/catalogue.py`, `reports/decision_tree.py` | SQLite, searchable table, gallery, animation and full tree |
| `reports/story_figures.py`, `reports/box_figure.py` | Current circuit-search, response and enclosure illustrations |
| `reports/supporting_figures.py` | Geometry, sensitivity and ground illustrations still used by the report |
| `simulation/coupled_2d.py`, `tests/cross_section.py`, `reports/cross_section_figures.py` | Separate 2-D diagnostic and its explanatory figures |
| `tests/geometry_clearance.py` | Saved-outline clearance check |
| `exports/footprint.py`, `tests/footprint.py` | Footprint export and native KiCad validation |
| `tests/refactor.py` | Regression against saved geometry and mesh evidence |

```powershell
.\.venv\Scripts\python.exe -m reports.story_figures
.\.venv\Scripts\python.exe -m reports.catalogue
.\.venv\Scripts\python.exe -m reports.box_figure
.\.venv\Scripts\python.exe -m exports.footprint
```

These commands rebuild artifacts without EM solves. `tests/cross_section.py` recomputes the separate 2-D diagnostic. Footprint validation requires KiCad's bundled Python; see [integration instructions](../kicad/README.md).

## Saved results and regression

- `results_redesign/`: 58 attempts with configs, actual outlines, raw matrices, mesh counts and available driver snapshots. Of these, 54 are completed four-port simulations.
- `results/*.npz`: 51 historical matrices still used by the complete catalogue and capacitor-compensation explanation. Duplicate Touchstone/viewer exports are removed.
- `catalogue/`: stable IDs, original timestamps, diagnostics and generated indexes. The ~78 MB SQLite file is local and can be rebuilt; it is excluded from Git.
- `results_redesign/*/driver_snapshot.py`: historical evidence, **not entry points**. Recover their dependencies from commit `6c4012c` when investigating the old implementation. New runs snapshot the complete `simulation/` package under `source/simulation/`, plus a driver snapshot.

```powershell
.\.venv\Scripts\python.exe -m tests.refactor --mesh
```

Checks every saved layout vertex, three representative 3-D domain bounds, and R058 node/tetrahedron counts. Results go to `catalogue/refactor_verification.json`. It does not rerun the frequency solve or establish new S-parameter convergence.

Deleted: `legacy/` (including unrun proposals), old `coupler_sim.py`, redundant `redesign_summary.py`, temporary refactoring code, and duplicate generated exports. Relevant raw measurements and report-generating tools are retained. Environments, meshes, logs and caches stay outside Git.

[Design report](../../Notes/FunRad/TX%20Coupler%20EM%20Method.md) · [Simulation catalogue](../../Notes/FunRad/Coupler%20Simulation%20Catalogue.md)

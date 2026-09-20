# FunRad TX coupler — EMerge 3-D model

## Current design (2026-09-20)

The current symmetric prototype is `redesign_configs/final51.json`, run with
`python redesign.py redesign_configs/final51.json`. The consolidated design note is
[TX Coupler EM Method](../../Notes/FunRad/TX%20Coupler%20EM%20Method.md).
The [catalogue](catalogue/README.md) contains SQLite results, geometry metadata,
readable labels and a searchable HTML table; [KiCad export](../kicad/README.md)
contains the validated footprint. Use `coupler_catalogue.py` and
`coupler_story_figures.py` to rebuild current illustrations.

The material below describes the **historical** `coupler_sim.py` workflow and
defaults, not the selected footprint. The existing environment runs EMerge 2.8.9
with Pardiso; the old setup-status narrative below is not a current status report.

3-D EM model of the 15 dB microstrip directional coupler between the QPA9127
and the antenna, with the etched interdigital compensation capacitors.
Companion to the design note (rev B, bare copper on JLC04161H-7628).

```
files
  setup.ps1 / setup.bat / setup.sh   create .venv and install EMerge
  requirements.txt
  probe_api.py                       print the EMerge API this install exposes
  coupler_sim.py                     the model
  results/                           .npz and .s4p land here
```

## 1. Environment

Windows (PowerShell):

```powershell
cd C:\Fun\ToyRadar\Frontend\emerge
powershell -ExecutionPolicy Bypass -File .\setup.ps1
.\.venv\Scripts\Activate.ps1
```

or `setup.bat` from cmd, or `./setup.sh` on Linux/WSL.

EMerge needs **Python 3.10 – 3.13** (not 3.14). It pulls in gmsh, pyvista,
numba, mkl and scipy, so the first install is a few hundred MB.

On Windows the sparse solve is much faster with UMFPACK — see
`UMFPACK_Install_windows.md` in the EMerge repo, then
`pip install scikit-umfpack` into this venv.

> I could not create the venv for you. The shell I have on your machine is a
> sandboxed Linux VM with your folder mounted and no route to PyPI, so a venv
> made there would be both empty and the wrong platform for a Windows box.
> The scripts above do it in one command.

## 2. Check the API before the first run

```
python probe_api.py
```

`coupler_sim.py` is written against the API in EMerge's published
stepped-impedance-filter example (`em.Material`, `em.Simulation`,
`em.geo.PCB`, `.new().store().straight()`, `modal_port`, `compile_paths`,
`determine_bounds`, `generate_pcb`, `mw.set_resolution`,
`mw.set_frequency_range`, `mesher.set_boundary_size` / `set_face_size`,
`mw.bc.ModalPort` / `PEC`, `mw.run_sweep`, `sol.scalar.grid.model_S`).
I had no way to install EMerge and run it, so treat the first run as a
shakedown. `probe_api.py` prints the real signatures; two things are worth
looking at specifically:

* **`z(i)`** — the script assumes `layers=2` with the traces on `z(1)` and
  ground on `z(0)`. If the indexing is the other way round, pass
  `--layers 3 --trace-layer 2` (the values the vendor example uses) or
  `--trace-layer 0`.
* **a native bend** — line B needs two 45° tapers per end. The published API
  only shows `.straight()`, so the script draws each tapered segment as its
  own path with a diagonal direction vector and lets `compile_paths(merge=True)`
  union them (segments overlap by `OVL = 0.04 mm` at every joint). If your
  build has `.bend()` / `.turn()` / `.arc()`, swapping it into `Layout.seg()`
  is a five-line change and gives proper mitres.

## 3. Run

```
python coupler_sim.py --fast --no-comb     # ~minutes: does the flow work?
python coupler_sim.py --no-comb            # baseline, uncompensated
python coupler_sim.py                      # 3 fingers per side
python coupler_sim.py --sweep-comb         # 0 / 2 / 3 / 4 fingers
python coupler_sim.py --show               # 3-D viewer after solving
```

Each run writes `results/sparams_<tag>.npz` and a Touchstone `.s4p`.

## 4. Geometry

```
port 1 ────────────────────────────────────────────────────────── port 2   line A
          │←──────────── L = 7.394 mm, gap 0.155 mm ────────────→│         (straight)
port 3 ──╲__╱──────────────────────────────────────────────╲__╱── port 4   line B
           ▲ comb                                            ▲ comb
```

Line A is straight, width 0.371 mm at the feeds and 0.346 mm over the coupled
length. Line B comes in at 2.50 mm centre-to-centre, tapers at 45° to a
1.40 mm jog at 1.30 mm centre-to-centre — this is where the comb lives — then
tapers again to the 0.501 mm coupled spacing, runs 7.394 mm, and mirrors out.
Board is 17.192 mm long; all four ports sit on the two end faces.

**Comb.** Three fingers per side, 0.10 mm wide, 0.08 mm gaps, interleaved
along x in a 1.00 mm span, reaching from line A's lower edge down and from
line B's upper edge up so they overlap by 0.395 mm. The 2-D mutual
capacitance for that finger pitch is 22.8 pF/m, so
`C = 5 × 0.395 mm × 22.8 pF/m = 0.045 pF` per end.

That is deliberately **under** the 0.057 pF optimum. The 2-D estimate counts
only the facing edges and ignores the finger tips and the connecting root,
which add 10–25 %; overshooting past ~0.11 pF makes directivity worse than no
compensation at all. Adjust with `C_TARGET_PF`, `FINGER_W`, `FINGER_GAP` and
`--fingers`.

## 5. Copper thickness — read this before trusting the numbers

The released etch (W 0.346 / s 0.155 mm) was solved **with** 35 µm copper.
If EMerge's PCB layouter draws traces as zero-thickness surfaces, simulating
that geometry will under-report coupling by roughly 0.35 dB, because the
35 µm sidewalls facing each other across the gap are what the released numbers
account for. Check `probe_api.py` for a thickness argument on `PCB(...)` or
`generate_pcb(...)`:

* thickness supported → keep `--geom t35` and set it to 35 µm;
* zero-thickness only → use `--geom t0`, which is the equivalent
  zero-thickness synthesis (W 0.382 / s 0.129 / L 7.168 mm, 50 Ω feed
  0.403 mm). Both describe the same electrical coupler.

## 6. What the 2-D model predicts, for comparison

At 5.8 GHz, released geometry, no compensation:

| | 2-D quasi-static |
|---|---|
| coupling S31 | −14.99 dB |
| through S21 | −0.513 dB |
| isolation S41 | −21.69 dB |
| return loss S11 | −36.5 dB |
| directivity | 6.7 dB |

With the comb at its optimum the four-port analysis gives ≥ 30 dB directivity.
Expect 3-D to disagree in two specific ways, and treat them as the *result*
rather than as errors:

1. **Length.** End fringing (~80 µm equivalent per end) makes the real
   structure electrically longer, so peak coupling lands 1–3 % low in
   frequency. If the coupling peak sits below 5.8 GHz, shorten `L_C`.
2. **Comb value.** The 3-D comb will be worth more than the 2-D estimate.
   If directivity peaks below 3 fingers, drop to 2; if it is still climbing at
   4, the fingers are undersized.

Neither the 2-D solver nor Qucs can see either effect — that is exactly why
this run exists.

## 7. Known limitations of this model

* The **shield lid** (2.5 mm above L1) is not imposed; the layouter's air box
  sets the boundary. Worth 0.08 dB at 2.0 mm and less above that, so ignore it
  unless you go low-profile.
* The **coplanar ground pour** (1.0 mm keep-out) is not drawn. It is worth
  0.03 dB at 1.0 mm; add it as a polygon if you tighten the keep-out.
* **Surface roughness** and the ENIG nickel layer are not modelled; both add a
  little loss, not coupling. See §11 of the design note.
* Only L1/L2 are modelled — the 4-layer stack below L2 is irrelevant to a
  microstrip over a solid plane.

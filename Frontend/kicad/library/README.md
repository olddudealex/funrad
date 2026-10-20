# Shared KiCad libraries

Symbols and footprints shared by the KiCad projects in `Frontend/kicad/`
(`Frontend/`, `FrontendPCBCoupon/`). Kept here, outside any one project, so a
part drawn once is usable from all of them.

| Path | Contents |
|---|---|
| `FunRad.kicad_sym` | Component symbols (AD8318, ADL5380, LMX2491, SMA_132289, Wilkinson splitters, ...) |
| `FunRad.pretty/` | Footprints for those parts, the Samtec and SMA connectors, and the EM-derived coupler |

Both are registered under the single nickname **`Frontend`**, so a part is
referenced as `Frontend:<name>` everywhere.

`FunRad_Coupler_5GHz8_Symmetric_15dB` in `FunRad.pretty/` is not an ordinary
footprint — it is etched copper exported from the EM model, with net ties and
stack-up requirements. Read the [coupler workflow and integration notes](../../emerge/README.md) before placing it.

## BWSMA launch for coupon revision B

Use **`Frontend:SMA_BWSMA-KE-P001_EdgeMount_L2Cutout_2.8x4.8mm`**
([footprint](FunRad.pretty/SMA_BWSMA-KE-P001_EdgeMount_L2Cutout_2.8x4.8mm.kicad_mod)).
It copies the original BWSMA pads, six ground stitching holes, fabrication
outline and 3D model, and adds one **In1.Cu (L2) rule area** under signal pad 1.

| Parameter | Footprint coordinates |
|---|---|
| Clearance along the pad | x = −2.4…+2.4 mm (4.8 mm) |
| Clearance across the pad | y = −1.4…+1.4 mm (2.8 mm) |
| Centre | Signal pad 1 / footprint origin |
| Restricted layer | In1.Cu only; L3 and Bottom retained |
| Inside the L2 window | Copper pours, tracks, vias and pads prohibited |

Select this variant for the revision B BWSMA connectors, then **refill zones
with `B`**. The rule area rotates with the footprint. Keep the board's tested
pad-to-0.37 mm trace taper and surrounding ground arrangement; the taper is
board routing, not part of this footprint. The original
`SMA_BWSMA-KE-P001_EdgeMount` remains available for revision A.

The geometry follows the [coupon studies](../../emerge/coupon_10mm/README.md),
including [mesh refinement](../../../Notes/FunRad/Frontend/Coupon/08_MESH_REFINEMENT.md),
the [L3 trial](../../../Notes/FunRad/Frontend/Coupon/09_L3_CUTOUT_RESULTS.md) and
[dielectric sensitivity](../../../Notes/FunRad/Frontend/Coupon/10_DIELECTRIC_SENSITIVITY.md).

KiCad 10.0.5 loaded the footprint and filled a four-layer validation board at
0°, 90°, 180° and 270°. Checks confirm that all 11 pads match the original,
the L2 windows are empty, L2 copper remains 50 µm beyond each edge midpoint,
and L3 / Bottom remain filled beneath the windows. From this library directory:

```powershell
& 'C:\Program Files\KiCad\10.0\bin\python.exe' .\tests\sma_l2_cutout.py
```

The script writes its temporary board and check results under
`Frontend/kicad/validation/sma_l2_cutout/` (ignored by Git).

## How projects reach these

Each project carries its own `sym-lib-table` and `fp-lib-table`, checked into
git, pointing here with a path relative to the project:

```
(lib (name "Frontend")(type "KiCad")(uri "${KIPRJMOD}/../library/FunRad.kicad_sym")(options "")(descr "FunRad shared symbols"))
```

`${KIPRJMOD}` is the project directory, so nothing has to be configured per
machine and a fresh clone works as-is. This does mean the tables assume the
project sits one level below `library/`; a project at a different depth needs
its own relative path.

Caveats:

- KiCad's **Manage Symbol/Footprint Libraries** dialog writes *absolute* paths.
  After adding a library through the GUI, edit the table back to a
  `${KIPRJMOD}/../library/...` form, or the path breaks on another machine.
- The nickname is `Frontend`, not `FunRad`. It is historical: it is what the
  ~100 `Frontend:` references in the existing schematics, `FunRad.kicad_sym`
  and `Frontend.kicad_pcb` already use, so keeping it avoided touching them.
  Renaming it later is a search/replace across those files plus these tables.
- Do not also register these libraries in KiCad's **global** tables. A global
  entry with the same nickname collides with the project one, its absolute path
  is not in git, and a global entry using `${KIPRJMOD}` resolves against
  whatever project happens to be open — which is how the symbol library was
  wired before and why only one project could see it.

## Adding a part

Draw the symbol into `FunRad.kicad_sym` and its footprint into `FunRad.pretty/`,
set the symbol's Footprint field to `Frontend:<footprint name>`, and both
projects see it with no further changes.

3D models are referenced as `${KICAD10_3DMODEL_DIR}/...` or embedded in the
`.kicad_mod` via `kicad-embed://`. Keep it that way: neither form breaks when a
library or project folder moves.

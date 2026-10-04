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

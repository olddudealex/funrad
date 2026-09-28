# Shared KiCad libraries

Symbols and footprints shared by the KiCad projects in `Frontend/kicad/`
(`Frontend/`, `FrontendPCBCoupon/`). Kept here, outside any one project, so a
part drawn once is usable from all of them.

| Path | Nickname | Contents |
|---|---|---|
| `FunRad.kicad_sym` | `Frontend` | Component symbols (AD8318, ADL5380, LMX2491, SMA_132289, Wilkinson splitters, ...) |
| `FunRad.pretty/` | `Frontend` | Footprints for those parts, plus the Samtec and SMA connectors |
| `FunRad_RF.pretty/` | `FunRad_RF` | EM-derived RF structures. See `../README.md` before placing the coupler. |

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
- The nicknames are `Frontend` and `FunRad_RF`, not `FunRad`. `Frontend` is
  historical: it is what the ~100 `Frontend:` references in the existing
  schematics, `FunRad.kicad_sym` and `Frontend.kicad_pcb` already use, so
  keeping it avoided touching them. Renaming it later is a search/replace
  across those files plus these tables.
- Do not also register these libraries in KiCad's **global** tables. A global
  entry with the same nickname collides with the project one, and its absolute
  path is not in git.

## Adding a part

Draw the symbol into `FunRad.kicad_sym` and its footprint into `FunRad.pretty/`,
set the symbol's Footprint field to `Frontend:<footprint name>`, and both
projects see it with no further changes.

3D models are referenced as `${KICAD10_3DMODEL_DIR}/...` or embedded in the
`.kicad_mod` via `kicad-embed://`. Keep it that way: neither form breaks when a
library or project folder moves.

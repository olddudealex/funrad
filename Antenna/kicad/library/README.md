# Shared KiCad libraries

Footprints shared by the KiCad projects in `Antenna/kicad/` (`line_array/`,
`line_array_feed/`, `line_array_feed_h_pol/`).

| Path | Nickname | Contents |
|---|---|---|
| `PatchLineArray.pretty/` | `PatchLineArray` | Etched patch elements and the T-junction feed for the 5.8 GHz line array |

These are EM-derived copper geometries, not packages for purchased parts. The
boards in use reference `PatchLineArray:Patch_er3_100Ohm` and
`PatchLineArray:T-junction_patches_feed` (`line_array_feed`) and
`PatchLineArray:Patch_131_160_ins_30` (`line_array_feed_h_pol`). The
`Patch_121_230` / `_122_230` / `_123_230` / `_126_230` variants are earlier
dimension sweeps kept for reference.

## How projects reach these

Each project carries its own `fp-lib-table`, checked into git, pointing here
with a path relative to the project:

```
(lib (name "PatchLineArray")(type "KiCad")(uri "${KIPRJMOD}/../library/PatchLineArray.pretty")(options "")(descr "..."))
```

`${KIPRJMOD}` is the project directory, so nothing has to be configured per
machine and a fresh clone works as-is. The tables assume the project sits one
level below `library/`.

No symbol table is needed here: these projects use only KiCad's stock symbol
libraries (`Connector:Conn_Coaxial_Small`, `MountingHole:`).

Caveats:

- KiCad's **Manage Footprint Libraries** dialog writes *absolute* paths. After
  adding a library through the GUI, edit the table back to a
  `${KIPRJMOD}/../library/...` form, or the path breaks on another machine.
- Do not register this library in KiCad's **global** table. It was global
  before, with an absolute path that pointed at the `line_array` project folder
  rather than at the footprints — so the nickname resolved to an empty library,
  and the boards only still opened because a `.kicad_pcb` stores a full copy of
  every footprint it places. Updating footprints from the library would have
  failed.

See `../../Frontend/kicad/library/README.md` for the same arrangement on the
frontend side.

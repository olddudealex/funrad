"""Grounded lid (shield can) above the coupled section: how far the even and
odd modes move, and from what height it starts to matter.  Standard Python;
run from Frontend/emerge."""
import json
from pathlib import Path
from simulation.coupled_2d import modes, coupling_db

F = 5.8e9          # band centre
D = 10.0           # grid; the differences between rows are what this measures
W = 370.0          # coupled-conductor width, measured at x = 0 on the exported footprint
S = 130.0          # edge gap between the two conductors
REF = 2500.0       # lid height used by the 54 three-dimensional runs

# open reference first, then the heights of interest
HEIGHTS = (25000.0, 5080.0, 3600.0, 2500.0, 2000.0, 1000.0, 500.0)

rows = []
for lid in HEIGHTS:
    z0e, z0o, eps_e, eps_o = modes(W, S, d_um=D, lid_um=lid)
    c_db, z_match = coupling_db(z0e, z0o)
    rows.append(dict(lid_um=lid, Z0e=z0e, Z0o=z0o, eps_eff_e=eps_e,
                     eps_eff_o=eps_o, coupling_db=c_db, Z_match=z_match))
base = next(r["coupling_db"] for r in rows if r["lid_um"] == REF)
for r in rows:
    r["d_coupling_db_vs_ref"] = r["coupling_db"] - base

print(f"W = {W:.0f} um, S = {S:.0f} um, {D:.0f} um grid, {F/1e9:.1f} GHz")
print(f"{'lid':>9}  {'Z0e':>7}  {'Z0o':>7}  {'eps_e':>8}  {'eps_o':>8}  "
      f"{'C (dB)':>8}  {'vs 2.5 mm':>9}")
for r in rows:
    print(f"{r['lid_um']/1000:>7.2f}mm  {r['Z0e']:>7.3f}  {r['Z0o']:>7.3f}  "
          f"{r['eps_eff_e']:>8.5f}  {r['eps_eff_o']:>8.5f}  {r['coupling_db']:>8.3f}  "
          f"{r['d_coupling_db_vs_ref']:>+9.3f}")

out = Path(__file__).resolve().parents[1] / "catalogue" / "lid_height.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(dict(W_um=W, S_um=S, grid_um=D, f_Hz=F,
                               ref_lid_um=REF, rows=rows), indent=2))
print(f"\nwritten: {out}")

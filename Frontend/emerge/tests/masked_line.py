"""Soldermask loading on the coupon's 50-ohm line: eps_eff shift and the
re-tuned width.  Standard Python; run from Frontend/emerge."""
import json, math
from pathlib import Path
from simulation.coupled_2d import single

C = 299792458.0
F = 5.8e9          # band centre
L = 40.0e-3        # the 40 mm coupon pair
D = 5.0            # grid; width resolution is one cell
W_BARE = 370.0
ER_MASK = 3.8      # LPI soldermask, 3.5-4.2 at GHz
MASK = 20.0        # um over copper

Zb, Eb = single(W_BARE, d_um=D)
rows = []
for mk in (10.0, 20.0, 30.0):
    z, e = single(W_BARE, d_um=D, mask_um=mk, er_mask=ER_MASK)
    rows.append(dict(mask_um=mk, Z0=z, eps_eff=e,
                     dphi_deg_over_40mm=360*F*L*(math.sqrt(e)-math.sqrt(Eb))/C))

lo, hi = 315.0, 355.0
for _ in range(7):
    m = (lo+hi)/2
    if single(m, d_um=D, mask_um=MASK, er_mask=ER_MASK)[0] > Zb: lo = m
    else: hi = m
W50 = round((lo+hi)/2 / D) * D
z50, e50 = single(W50, d_um=D, mask_um=MASK, er_mask=ER_MASK)

out = dict(purpose="Soldermask loading on the coupon 50-ohm line",
           grid_um=D, er_mask=ER_MASK, mask_um=MASK,
           bare=dict(W_um=W_BARE, Z0=Zb, eps_eff=Eb),
           thickness_sweep=rows,
           masked_50ohm=dict(W_um=W50, Z0=z50, eps_eff=e50,
                             delta_W_um=W50-W_BARE))
print(json.dumps(out, indent=2))
Path(__file__).resolve().parents[1].joinpath(
    'catalogue/masked_line.json').write_text(json.dumps(out, indent=2))

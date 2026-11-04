"""Re-use the existing electrostatic solver for the coupon's uniform line.

From Frontend/emerge: python -m coupon_10mm.line_cross_section
This is a 2-D capacitance diagnostic, not a new connector-inclusive 3-D solve.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from simulation.coupled_2d import single
from .report_paths import HERE

RESULT = HERE / 'result_line_cross_section.json'


def main():
    geometry = json.loads((HERE / 'pcb_geometry.json').read_text(encoding='utf-8'))
    parameters = dict(W_um=370.0, t_um=geometry['layers'][0]['thickness_mm']*1000,
                      er=4.5, h_um=geometry['top_to_l2_dielectric_mm']*1000,
                      mask_um=0.0)
    rows = []
    for label, grid, pad, lid in [('coarse', 10., 1500., 2500.),
                                   ('fine', 5., 1500., 2500.),
                                   ('coarse_wider_box', 10., 2500., 4000.),
                                   ('fine_wider_box', 5., 2500., 4000.)]:
        zc, ee = single(**parameters, d_um=grid, xpad_um=pad, lid_um=lid)
        row = dict(label=label, grid_um=grid, side_padding_um=pad,
                   air_height_um=lid, Zc_ohm=float(zc), eps_eff=float(ee),
                   represented_width_um=round(parameters['W_um']/grid)*grid,
                   represented_copper_um=round(parameters['t_um']/grid)*grid,
                   represented_dielectric_um=round(parameters['h_um']/grid)*grid)
        rows.append(row)
        print(label, 'Zc', round(float(zc), 4), 'eps_eff', round(float(ee), 6), flush=True)
    solver = Path(__file__).resolve().parents[1]/'simulation/coupled_2d.py'
    result = dict(purpose='Coupon single-microstrip cross-section; existing solver reused',
                  created_utc=datetime.now(timezone.utc).isoformat(), parameters=parameters,
                  solver='simulation.coupled_2d.single',
                  solver_sha256=hashlib.sha256(solver.read_bytes()).hexdigest(),
                  geometry_source_sha256=hashlib.sha256((HERE/'pcb_geometry.json').read_bytes()).hexdigest(),
                  selected='fine_wider_box', rows=rows,
                  assumptions=['Uniform bare strip over continuous L2; no top ground beside its centre.',
                               'Finite copper thickness, perfect-conductor equipotentials; lossless real epsilon.',
                               'Grounded outer box is a numerical boundary, not a modelled shielding cap.',
                               'Quasi-static: no frequency dispersion; L2 pad cutouts and launches excluded.',
                               'Dielectric er=4.5 matches nominal saved 10 mm connector-inclusive FEM.'])
    RESULT.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()

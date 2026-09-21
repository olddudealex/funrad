"""Independent, reproducible coupler investigation. Units: mm except solver SI.

Run one solve at a time. Each immutable run directory retains configuration,
actual trace outlines, mesh statistics, raw S and port impedances. No fits.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import emerge as em
import gmsh
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from simulation.geometry import build_paths, outline, install_polygon_dedupe
from simulation.domain import create_simulation, build_domain
from simulation.mesh import generate_mesh
from emerge._emerge.physics.microwave.microwave_data import renormalise_s

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results_redesign'


def run(config, preview=False):
    ident = config['name'] + '_' + hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:10]
    dest = OUT / ident
    dest.mkdir(parents=True, exist_ok=True)
    if (dest / 'raw.npz').exists():
        print('Already completed:', dest, flush=True)
        return
    (dest / 'config.json').write_text(json.dumps(config, indent=2), encoding='utf-8')
    # Preserve the whole package for new runs, plus the historical driver entry.
    for source in (ROOT / 'simulation').glob('*.py'):
        snapshot = dest / 'source' / 'simulation' / source.name
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_bytes(source.read_bytes())
    (dest / 'driver_snapshot.py').write_bytes(Path(__file__).read_bytes())
    em.cleanup()
    # 1. Materials and 2-D copper geometry (mm).
    install_polygon_dedupe()
    model, layouter, copper = create_simulation(config, ident)
    info, names = build_paths(layouter, config)
    polygons = [outline(p) for p in layouter.paths]
    (dest / 'layout.json').write_text(json.dumps(dict(polygons=polygons, info=info), indent=2))
    fig, ax = plt.subplots(figsize=(12, 4))
    for poly in polygons:
        xy = np.array(poly)
        ax.fill(xy[:,0], xy[:,1], color='#bd7138', ec='#663718', lw=.6)
    ax.set(aspect='equal', xlabel='x (mm)', ylabel='y (mm)', title=config['name'])
    ax.grid(alpha=.2)
    fig.tight_layout(); fig.savefig(dest / 'layout.png', dpi=170); plt.close(fig)
    # 2. 3-D stack, enclosure and modal-port faces.
    ports, metal, ground = build_domain(layouter, config, copper, polygons, names)
    gmsh.model.occ.synchronize()
    boxes = dict(ground=[gmsh.model.getBoundingBox(*dt) for dt in ground.dimtags],
                 traces=[gmsh.model.getBoundingBox(*dt) for dt in metal.dimtags])
    (dest / 'geometry_bounds.json').write_text(json.dumps(boxes, indent=2))
    if preview:
        print('Preview:',dest, boxes, flush=True)
        return
    start = time.time()
    model.commit_geometry()
    # 3. Global and local mesh refinement, then tetrahedral meshing.
    generate_mesh(model, metal, ports, config)
    nodes = gmsh.model.mesh.getNodes()[0].size
    types, tags, _ = gmsh.model.mesh.getElements(3)
    mesh = dict(nodes=int(nodes), volume_elements=sum(len(x) for x in tags),
                emerge=em.__version__, geometry_seconds=time.time()-start)
    (dest/'mesh.json').write_text(json.dumps(mesh,indent=2))
    # 4. Port boundary conditions and directly sampled frequency solve.
    for i, port in enumerate(ports): model.mw.bc.ModalPort(port,i+1,modetype='TEM')
    sol = model.mw.run_sweep(parallel=False)
    grid = sol.scalar.grid
    f, s, z = np.asarray(grid.freq), grid.Smat, np.asarray(grid.Z0)
    if not np.all(np.isfinite(z)) or np.min(z.real)<35 or np.max(z.real)>65:
        np.savez(dest/'invalid_port_result.npz',f=f,Smat=s,Z0=z)
        raise RuntimeError('Port impedance outside physical control range; result excluded')
    # 5. Preserve modal S/Z0 as well as the 50-ohm matrices used in reports.
    s50 = renormalise_s(s,z,50.)
    np.savez(dest/'raw.npz', f=f, Smat=s, Smat50=s50, Z0=z)
    db = lambda x: 20*np.log10(np.maximum(abs(x),1e-30))
    result = dict(seconds=time.time()-start, Z0_real=np.real(z).tolist(),
                  S11=db(s50[:,0,0]).tolist(), S21=db(s50[:,1,0]).tolist())
    if len(ports)==4:
        result.update(S31=db(s50[:,2,0]).tolist(), S41=db(s50[:,3,0]).tolist(),
                      directivity=(db(s50[:,2,0])-db(s50[:,3,0])).tolist())
    (dest/'metrics.json').write_text(json.dumps(result,indent=2))
    print('RESULT',ident,json.dumps(result),flush=True)


DEFAULT = dict(name='candidate', w=.37, gap=.14, length=7.15, feed_w=.37,
               y=1., jog=.80, bend=45., symmetric=True, fingers=2,
               fw=.10, fg=.10, overlap=.30, h=.2104, t=.035, er=4.4, tand=.02,
               straight=False, legacy_ground=False, port_width=1.85,
               resolution=.15, trace_mesh=.30, port_mesh=.20, edge_mesh=0.,
               fmin=5.7, fmax=5.9, nf=3, shift=0.)

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('config', help='JSON overrides for DEFAULT')
    ap.add_argument('--preview',action='store_true')
    args=ap.parse_args()
    config={**DEFAULT, **json.loads(Path(args.config).read_text())}
    run(config,args.preview)

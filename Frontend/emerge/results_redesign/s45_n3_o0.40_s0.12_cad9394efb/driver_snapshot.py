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
import subprocess

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import emerge as em
import gmsh
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import coupler_sim as old
from emerge._emerge.physics.microwave.microwave_data import renormalise_s

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'results_redesign'


def outline(path):
    right, left = [], []
    for previous, edge, following in path.iter_right():
        points = list(edge.right)
        if following.rcutprev and points: points.pop(-1)
        if previous.rcutnext and points: points.pop(0)
        right.extend(points)
    for previous, edge, following in path.iter_left():
        points = list(edge.left)
        if following.lcutprev and points: points.pop(-1)
        if previous.lcutnext and points: points.pop(0)
        left.extend(points)
    return right + left[::-1]


def run(c, preview=False):
    ident = c['name'] + '_' + hashlib.sha256(json.dumps(c, sort_keys=True).encode()).hexdigest()[:10]
    dest = OUT / ident
    dest.mkdir(parents=True, exist_ok=True)
    if (dest / 'raw.npz').exists():
        print('Already completed:', dest, flush=True)
        return
    (dest / 'config.json').write_text(json.dumps(c, indent=2), encoding='utf-8')
    (dest / 'driver_snapshot.py').write_text(Path(__file__).read_text(),encoding='utf-8')
    em.cleanup()
    old._install_polygon_dedupe()
    old.Y_COMB, old.JOG, old.BEND_DEG = c['y'], c['jog'], c['bend']
    mat = em.Material(er=c['er'], tand=c['tand'])
    copper = em.Material(cond=5.8e7, name='PEC')
    model = em.Simulation(ident)
    lo = em.geo.PCBNew(c['h'], unit=1e-3, material=mat, layers=2,
                       trace_material=copper, thick_traces=True, trace_thickness=c['t']*1e-3)
    g = dict(W_C=c['w'], S_GAP=c['gap'], L_C=c['length'], W_50=c['feed_w'],
             t_um=c['t']*1e3, fw=c['fw'], fgap=c['fg'], overlap=c['overlap'], ctarget=0.0)
    if c['straight']:
        lo.new(0, 0, c['feed_w'], (1, 0), z=0).store('p1_end').straight(10).store('p2_end')
        info = dict(total_x=10, straight=True)
        names = ('p1_end', 'p2_end')
    else:
        assert c['fw'] >= .10 and c['fg'] >= .10 and c['gap'] >= .10
        clearance=c['y']-c['feed_w']
        assert (clearance-c['overlap'])/2 >= .099999, 'Finger-to-opposite-bus clearance below 0.10 mm'
        if (c['fw'], c['fg']) not in old.CM_PF_PER_M:
            old.CM_PF_PER_M[c['fw'], c['fg']] = 0.0  # explicit overlap; no synthesis
        original_seg=old.Layout.seg
        def shifted(self,x,y,*a,**kw):
            return original_seg(self,x+(c['shift'] if x<7 else -c['shift']),y,*a,**kw)
        old.Layout.seg=shifted
        try:
            info = old.build(lo, 0, g, c['fingers'], comb=c['fingers']>0,
                             overlap_mm=c['overlap'], symmetric=c['symmetric'])
        finally:
            old.Layout.seg=original_seg
        names = ('p1_end', 'p2_end', 'p3_end', 'p4_end')
    polys = [outline(p) for p in lo.paths]
    (dest / 'layout.json').write_text(json.dumps(dict(polygons=polys, info=info), indent=2))
    fig, ax = plt.subplots(figsize=(12, 4))
    for poly in polys:
        xy = np.array(poly)
        ax.fill(xy[:,0], xy[:,1], color='#bd7138', ec='#663718', lw=.6)
    ax.set(aspect='equal', xlabel='x (mm)', ylabel='y (mm)', title=c['name'])
    ax.grid(alpha=.2)
    fig.tight_layout(); fig.savefig(dest / 'layout.png', dpi=170); plt.close(fig)
    ports = [lo.modal_port(lo.load(n), height=2.5, width=c['port_width']) for n in names]
    metal = lo.compile_paths(merge=True)
    lo.determine_bounds(leftmargin=0, rightmargin=0, topmargin=2, bottommargin=2)
    pcb = lo.generate_pcb(True, merge=True)
    # PCBNew extrudes ground upward too. Put its TOP at -h, not its bottom.
    ground_z = lo.z(0) if c['legacy_ground'] else lo.z(0)-c['t']
    ground = lo.plane(ground_z, name='GND')
    ground.prio_set(lo.conductor_priority)
    lo.generate_air(2.5)
    gmsh.model.occ.synchronize()
    boxes = dict(ground=[gmsh.model.getBoundingBox(*dt) for dt in ground.dimtags],
                 traces=[gmsh.model.getBoundingBox(*dt) for dt in metal.dimtags])
    (dest / 'geometry_bounds.json').write_text(json.dumps(boxes, indent=2))
    if preview:
        print('Preview:',dest, boxes, flush=True)
        return
    start = time.time()
    model.commit_geometry()
    model.mw.set_resolution(c['resolution'])
    model.mw.set_frequency_range(c['fmin']*1e9, c['fmax']*1e9, c['nf'])
    model.mesher.set_boundary_size(metal, c['trace_mesh']*1e-3, growth_rate=1.3)
    for port in ports:
        model.mesher.set_face_size(port,c['port_mesh']*1e-3)
    if c['edge_mesh']:
        model.mesher.set_trace_refinement(metal.face('-z'), qualtity_factor=2,
                                          min_size=c['edge_mesh']*1e-3,
                                          edge_size=c['edge_mesh']*1e-3,
                                          growth_rate=1.5)
    model.generate_mesh()
    nodes = gmsh.model.mesh.getNodes()[0].size
    types, tags, _ = gmsh.model.mesh.getElements(3)
    mesh = dict(nodes=int(nodes), volume_elements=sum(len(x) for x in tags),
                emerge=em.__version__, geometry_seconds=time.time()-start)
    (dest/'mesh.json').write_text(json.dumps(mesh,indent=2))
    for i, port in enumerate(ports): model.mw.bc.ModalPort(port,i+1,modetype='TEM')
    sol = model.mw.run_sweep(parallel=False)
    grid = sol.scalar.grid
    f, s, z = np.asarray(grid.freq), grid.Smat, np.asarray(grid.Z0)
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
    c={**DEFAULT, **json.loads(Path(args.config).read_text())}
    run(c,args.preview)

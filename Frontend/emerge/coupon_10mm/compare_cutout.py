"""Compare the L2-pad-cutout trial with the unchanged connector control."""
from .report_paths import REPORTS, write_report
import argparse
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon,Rectangle,Circle
from .compare import HERE,MEASUREMENTS,measured,db
from .connector_model import variant_paths,CONNECTOR

WIDTH_SECTION='<!-- L2-WIDTH-COMPARISON -->'
STEP_SECTION='<!-- LAUNCH-STEP-COMPARISON -->'


def geometry_plan(out,width,length,reference_width=None):
    """Left launch in plan: actual KiCad contours and the L2 removal mask."""
    pcb=json.loads((HERE/'pcb_geometry.json').read_text(encoding='utf-8'))
    fig,axes=plt.subplots(1,2,figsize=(10,5),sharex=True,sharey=True,constrained_layout=True)
    for ax,cut in zip(axes,(False,True)):
        for layer in pcb['layers']:
            if layer['name']=='In1.Cu':
                for region in layer['copper']:
                    ax.add_patch(Polygon(region['outer'],facecolor='#c0dbe9',edgecolor='#397da4',lw=1))
        plot_width=width if cut else reference_width
        if plot_width:
            ax.add_patch(Rectangle((.28,-plot_width/2),length,plot_width,facecolor='white',edgecolor='#009e73',lw=2))
        for layer in pcb['layers']:
            if layer['name']=='F.Cu':
                for region in layer['copper']:
                    signal=region['net']!='GND_1'
                    ax.add_patch(Polygon(region['outer'],facecolor='none',
                        edgecolor='#c66d13' if signal else '#7a6946',lw=1.8 if signal else 1))
        for via in pcb['vias']:
            ax.add_patch(Circle(via['xy_mm'],via['drill_mm']/2,facecolor='white',edgecolor='#7a6946',lw=.8))
        for yc in (-CONNECTOR.ground_y,CONNECTOR.ground_y):
            ax.add_patch(Rectangle((-.1,yc-.45),4,.9,fill=False,edgecolor='#71549c',ls='--',lw=1.2))
        ax.axvline(0,color='#333333',ls=':',lw=1)
        ax.set(xlim=(-.15,6.5),ylim=(-3.5,3.5),xlabel='x from board edge (mm)',
               title=f'{plot_width:g} mm cutout width' if plot_width else 'Original L2 ground')
        ax.set_aspect('equal');ax.grid(alpha=.15)
    axes[0].set_ylabel('y (mm)')
    axes[1].annotate(f'{length:g} mm',xy=(.28+length/2,-3.32),ha='center',va='center',color='#007d5c')
    axes[1].annotate(f'{width:g} mm',xy=(.28+length+.2,0),va='center',rotation=90,color='#007d5c')
    fig.suptitle('Left launch: L2 ground in blue; signal outline in orange\n'
                 'Dashed purple: ground-pin projection; right launch is mirrored')
    fig.savefig(out/'l2_cutout_plan.png',dpi=170,bbox_inches='tight');plt.close(fig)


def width_study():
    """Append a reproducible three-variant comparison to the existing report."""
    variants=[('Original ground',None,'#0072b2','--'),
              ('1.6 mm cutout width',[1.6,4.8],'#009e73','-'),
              ('4.2 mm cutout width',[4.2,4.8],'#d55e00','-')]
    loaded=[]
    for label,opening,color,style in variants:
        out,stem=variant_paths(opening)
        meta=json.loads((HERE/f'{stem}.json').read_text(encoding='utf-8'))
        assert meta['status']=='completed' and meta.get('l2_opening_mm')==opening
        data=np.load(HERE/f'{stem}.npz')
        loaded.append((label,opening,color,style,meta,data))
    f=loaded[0][5]['f'].reshape(-1)
    baseline=loaded[0][4]
    for _,_,_,_,meta,data in loaded:
        assert np.array_equal(data['f'].reshape(-1),f)
        assert data['Smat50'].shape==(len(f),2,2) and np.all(np.isfinite(data['Smat50']))
        for key in ('source_board_sha256','connector_parameters_mm','pcb_layers','air_box_mm','port_x_mm','mesh_targets_mm','element_order'):
            assert meta[key]==baseline[key],f'Width study control differs: {key}'
    out,stem=variant_paths([4.2,4.8])
    geometry_plan(out,4.2,4.8,reference_width=1.6)
    fig,axes=plt.subplots(2,1,figsize=(10,8),sharex=True,constrained_layout=True)
    for label,_,color,style,meta,data in loaded:
        s=data['Smat50']
        for ax,i,j in ((axes[0],1,0),(axes[1],0,0)):
            ax.plot(f/1e9,db(s[:,i,j]),marker='o',ms=4,color=color,ls=style,lw=1.8,label=label)
    for ax in axes:
        ax.grid(alpha=.25);ax.legend(fontsize=9,loc='lower left');ax.set_xlim(0,6.1)
    axes[0].set(ylabel='S21 (dB)',ylim=(-10,.3))
    axes[1].set(ylabel='S11 (dB)',ylim=(-50,1),xlabel='Frequency (GHz)')
    fig.suptitle('L2 cutout width: 1.6 mm versus 4.2 mm up to ground pins\n'
                 '4.8 mm length; L3 and connectors unchanged; 20 direct frequencies')
    fig.savefig(out/'cutout_width_comparison.png',dpi=170,bbox_inches='tight');plt.close(fig)
    # A tighter plot exposes changes between the two successful cutout variants.
    fig,axes=plt.subplots(2,1,figsize=(10,7),sharex=True,constrained_layout=True)
    for label,_,color,style,_,data in loaded[1:]:
        s=data['Smat50']
        for ax,i,j in ((axes[0],1,0),(axes[1],0,0)):
            ax.plot(f/1e9,db(s[:,i,j]),'o-',color=color,ms=4,lw=1.8,label=label)
    for ax in axes:ax.grid(alpha=.25);ax.legend(fontsize=9);ax.set_xlim(.5,6)
    axes[0].set(ylabel='S21 (dB)')
    axes[1].set(ylabel='S11 (dB)',xlabel='Frequency (GHz)')
    fig.suptitle('Cutout variants only: transmission and matching')
    fig.savefig(out/'cutout_width_detail.png',dpi=170,bbox_inches='tight');plt.close(fig)
    s=loaded[-1][5]['Smat50'];narrow=loaded[1][5]['Smat50'];z=loaded[-1][5]['Z0']
    meta=loaded[-1][4]
    metrics=dict(width_mm=4.2,length_mm=4.8,frequencies=len(f),nodes=meta['nodes'],tetrahedra=meta['tetrahedra'],
                 max_reciprocity_error=float(abs(s[:,1,0]-s[:,0,1]).max()),
                 max_symmetry_error=float(abs(s[:,0,0]-s[:,1,1]).max()),
                 max_singular_value=float(np.linalg.svd(s,compute_uv=False).max()),
                 modal_Z0_real_range_ohm=[float(z.real.min()),float(z.real.max())],
                 worst_sampled_S21_dB=float(db(s[:,1,0]).min()),
                 worst_sampled_S11_dB=float(db(s[:,0,0]).max()),
                 rows=[dict(f_GHz=float(freq/1e9),S21_dB=float(db(s[k,1,0])),S11_dB=float(db(s[k,0,0])),
                       S21_change_vs_1p6mm_dB=float(db(s[k,1,0])-db(narrow[k,1,0]))) for k,freq in enumerate(f)])
    (out/'width_comparison_metrics.json').write_text(json.dumps(metrics,indent=2)+'\n',encoding='utf-8')
    lines=['! PCB + BWSMA; two 4.2 x 4.8 mm L2 cutouts; stop at ground-pin inner edges',
           '! Reference planes: coax annuli x=-8.10 and 28.26 mm; connectors included',
           '# Hz S RI R 50']
    for freq,m in zip(f,s):
        lines.append(f'{freq:.12g} '+' '.join(f'{v.real:.12g} {v.imag:.12g}' for v in (m[0,0],m[1,0],m[0,1],m[1,1])))
    (HERE/f'{stem}.s2p').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    table=['| GHz | 1.6 mm S21, dB | 4.2 mm S21, dB | Change, dB | 1.6 mm S11, dB | 4.2 mm S11, dB |',
           '|---:|---:|---:|---:|---:|---:|']
    for k,freq in enumerate(f):
        table.append(f'| {freq/1e9:g} | {db(narrow[k,1,0]):.2f} | {db(s[k,1,0]):.2f} | '
                     f'{db(s[k,1,0])-db(narrow[k,1,0]):+.2f} | {db(narrow[k,0,0]):.2f} | {db(s[k,0,0]):.2f} |')
    folder=out.name
    k4=int(np.argmin(abs(f-4e9)))
    k6=int(np.argmin(abs(f-6e9)))
    section=[WIDTH_SECTION,'','## Wider cutout: up to the ground pins','',
        '**Second cutout trial completed: two 4.2 × 4.8 mm openings, 20 frequencies.** '
        'The intact-ground control and first 1.6 mm trial above are preserved. '
        'This width comparison uses three completed connector sweeps: original ground, narrow cutouts and wide cutouts.', '',
        f'At 4 GHz, widening changes S21 from **{db(narrow[k4,1,0]):.2f} to '
        f'{db(s[k4,1,0]):.2f} dB**. At 6 GHz, S21 changes from '
        f'**{db(narrow[k6,1,0]):.2f} to {db(s[k6,1,0]):.2f} dB**, and S11 from '
        f'**{db(narrow[k6,0,0]):.2f} to {db(s[k6,0,0]):.2f} dB**. '
        f'The worst sampled S21 of the wider variant over 0.5–6 GHz is '
        f'{metrics["worst_sampled_S21_dB"]:.2f} dB; its worst sampled S11 is '
        f'{metrics["worst_sampled_S11_dB"]:.2f} dB.', '',
        '**Wider is a tradeoff, not a uniform improvement.** The 4.2 mm window improves '
        'low-frequency matching and the response at 5.8–6 GHz, but introduces a broad '
        'transmission reduction around the sampled 4 GHz point, where reflection also '
        'increases. The 1.6 mm window performs better through roughly 3–5 GHz. '
        'Neither width dominates the other across the full band; maximum width alone '
        'is therefore not an optimization rule. An intermediate width or a shaped '
        'window would be a reasonable next trial. The present 4–5 GHz sampling does '
        'not locate the exact frequency or depth of the wider window’s worst response.', '',
        'Ground-pin centres are at y=±2.55 mm and the pins are 0.9 mm wide. Their inner '
        'edges are therefore y=±2.10 mm, so the maximum cutout width without going beneath '
        'the pins is **2×(2.55−0.45)=4.20 mm**. The length stays 4.8 mm; x limits remain '
        '0.28…5.08 mm and 15.08…19.88 mm. Ground vias remain outside the windows.', '',
        'The top ground pads extend inward to y=±1.95 mm. The wider window therefore removes '
        'L2 under their inner 0.15 mm overhang, but not under the metal pins or their ideal '
        'contact bridges. Top copper is unchanged. Occupancy checks explicitly confirm L2 '
        'beneath both pins at y=±2.11 mm, as well as L3 beneath the windows and L2 beneath the tapers.', '',
        f'![Cutout widened to pin edges]({folder}/l2_cutout_plan.png)','',
        f'![All three connector simulations]({folder}/cutout_width_comparison.png)','',
        f'![Narrow versus wide cutouts]({folder}/cutout_width_detail.png)','',
        *table,'',
        'Positive S21 change means more transmission than the 1.6 mm cutout at that frequency. '
        'A more negative S11 indicates less reflection. The original-board measurement is '
        'not a measurement of either cutout design.','',
        '### Mesh and numerical checks','',
        f'The wider geometry has {meta["tetrahedra"]:,} tetrahedra and {meta["nodes"]:,} nodes. '
        f'The sweep took {meta["solve_seconds"]/60:.1f} minutes. Mesh size targets, first-order '
        'basis, frequency grid, connector assumptions, materials, air box and coax reference '
        'planes match the preceding two sweeps. Only cutout width changed; the mesh was regenerated.', '',
        f'Native modal Z0: {z.real.min():.3f}–{z.real.max():.3f} Ω; '
        f'maximum |S21−S12|: {metrics["max_reciprocity_error"]:.3g}; '
        f'maximum |S11−S22|: {metrics["max_symmetry_error"]:.3g}; '
        f'maximum singular value: {metrics["max_singular_value"]:.6f}. '
        'This is another geometry trial on one mesh, not a convergence result.','',
        '### Reproduce the wide variant','', 'From `C:\\Fun\\ToyRadar\\Frontend\\emerge`:', '', '```powershell',
        '.\\.venv\\Scripts\\python.exe -m coupon_10mm.connector_model --l2-opening 4.2 4.8 --reuse-mesh --view-mesh',
        '.\\.venv\\Scripts\\python.exe -m coupon_10mm.connector_model --l2-opening 4.2 4.8 --reuse-mesh --solve',
        '.\\.venv\\Scripts\\python.exe -m coupon_10mm.compare_cutout --compare-widths','```','',
        f'Results: `{stem}.npz`, `{stem}.json` and `{stem}.s2p`. '
        f'Geometry, mesh metadata and comparison plots: `{folder}/`.']
    path=REPORTS/'05_L2_CUTOUT_RESULTS.md'
    existing=path.read_text(encoding='utf-8')
    original=existing.split(WIDTH_SECTION)[0].rstrip()
    step_tail='\n\n'+STEP_SECTION+existing.split(STEP_SECTION,1)[1] if STEP_SECTION in existing else ''
    write_report(path, original+'\n\n'+'\n'.join(section)+'\n'+step_tail)
    print(json.dumps({k:v for k,v in metrics.items() if k!='rows'},indent=2))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--l2-opening',nargs=2,type=float,default=[1.6,4.8])
    parser.add_argument('--compare-widths',action='store_true',help='Append 1.6 versus 4.2 mm width comparison to the report')
    args=parser.parse_args()
    if args.compare_widths:
        width_study()
        return
    out,stem=variant_paths(args.l2_opening)
    new=np.load(HERE/f'{stem}.npz')
    old=np.load(HERE/'result_coax_intact.npz')
    meta=json.loads((HERE/f'{stem}.json').read_text(encoding='utf-8'))
    baseline=json.loads((HERE/'result_coax_intact.json').read_text(encoding='utf-8'))
    assert meta['status']=='completed' and meta['l2_opening_mm']==args.l2_opening
    for key in ('connector_parameters_mm','pcb_layers','air_box_mm','port_x_mm','mesh_targets_mm','element_order'):
        assert meta[key]==baseline[key],f'Control comparison differs in {key}'
    f=new['f'].reshape(-1);s=new['Smat50'];b=old['Smat50'];z=new['Z0']
    assert np.array_equal(f,old['f'].reshape(-1)) and s.shape==b.shape==(len(f),2,2)
    assert np.all(np.isfinite(s))
    width,length=args.l2_opening
    geometry_plan(out,width,length)
    mf,m11,m21=measured(MEASUREMENTS/'coupon_7628_horizontal_10mm.s2p')
    fig,axes=plt.subplots(2,1,figsize=(10,8),sharex=True,constrained_layout=True)
    for ax,i,j,m in [(axes[0],1,0,m21),(axes[1],0,0,m11)]:
        ax.plot(mf/1e9,db(m),color='#a0a0a0',lw=1,alpha=.65,label='Measurement: ORIGINAL board, no cutouts')
        ax.plot(f/1e9,db(b[:,i,j]),'o--',color='#0072b2',ms=4,lw=1.6,label='Simulation: original ground')
        ax.plot(f/1e9,db(s[:,i,j]),'o-',color='#009e73',ms=4,lw=2,label=f'Simulation: two {width:g} x {length:g} mm L2 cutouts')
        ax.set_xlim(0,6.1);ax.grid(alpha=.25);ax.legend(fontsize=8,loc='lower left')
    axes[0].set(ylabel='S21 (dB)',ylim=(-14,1))
    axes[1].set(ylabel='S11 (dB)',ylim=(-50,1),xlabel='Frequency (GHz)')
    fig.suptitle('L2 copper removed beneath the two launch pads; L3 remains\n'
                 'Same simplified BWSMA connectors, coax references and 20 frequencies')
    fig.savefig(out/'cutout_vs_original.png',dpi=170,bbox_inches='tight');plt.close(fig)
    fig,axes=plt.subplots(3,1,figsize=(9,8),sharex=True,constrained_layout=True)
    for ax,label,values,control in [
        (axes[0],'Reflected',abs(s[:,0,0])**2,abs(b[:,0,0])**2),
        (axes[1],'Transmitted',abs(s[:,1,0])**2,abs(b[:,1,0])**2),
        (axes[2],'Remaining',1-abs(s[:,0,0])**2-abs(s[:,1,0])**2,1-abs(b[:,0,0])**2-abs(b[:,1,0])**2)]:
        ax.plot(f/1e9,control,'o--',color='#0072b2',ms=3,label='Original ground')
        ax.plot(f/1e9,values,'o-',color='#009e73',ms=3,label='L2 pad cutouts')
        ax.set(ylabel=label+' power fraction',ylim=(-.03,1.03));ax.grid(alpha=.25);ax.legend(fontsize=8)
    axes[-1].set_xlabel('Frequency (GHz)')
    fig.suptitle('Power balance: reflection, transmission, remaining loss / radiation / numerical')
    fig.savefig(out/'cutout_power.png',dpi=170,bbox_inches='tight');plt.close(fig)
    rows=[]
    for k,freq in enumerate(f):
        rows.append(dict(f_GHz=float(freq/1e9),original_S21_dB=float(db(b[k,1,0])),
                         cutout_S21_dB=float(db(s[k,1,0])),
                         S21_improvement_dB=float(db(s[k,1,0])-db(b[k,1,0])),
                         original_S11_dB=float(db(b[k,0,0])),cutout_S11_dB=float(db(s[k,0,0]))))
    checks=dict(l2_opening_mm=args.l2_opening,frequencies=len(f),nodes=meta['nodes'],tetrahedra=meta['tetrahedra'],
                modal_Z0_real_range_ohm=[float(z.real.min()),float(z.real.max())],
                max_reciprocity_error=float(abs(s[:,1,0]-s[:,0,1]).max()),
                max_symmetry_error=float(abs(s[:,0,0]-s[:,1,1]).max()),
                max_singular_value=float(np.linalg.svd(s,compute_uv=False).max()),
                mean_S21_improvement_dB=float(np.mean(db(s[:,1,0])-db(b[:,1,0]))),rows=rows)
    (out/'comparison_metrics.json').write_text(json.dumps(checks,indent=2)+'\n',encoding='utf-8')
    lines=[f'! 10 mm PCB + simplified BWSMA; two L2 cutouts {width:g} x {length:g} mm; L3 intact',
           '! Coax reference planes x=-8.10 and 28.26 mm; connectors included; no de-embedding',
           '! 20 directly solved frequencies; first-order FEM; 50-ohm reference','# Hz S RI R 50']
    for freq,m in zip(f,s):
        vals=[m[0,0],m[1,0],m[0,1],m[1,1]]
        lines.append(f'{freq:.12g} '+' '.join(f'{v.real:.12g} {v.imag:.12g}' for v in vals))
    (HERE/f'{stem}.s2p').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    table=['| GHz | Original S21, dB | Cutout S21, dB | Improvement, dB | Original S11, dB | Cutout S11, dB |',
           '|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        table.append(f'| {r["f_GHz"]:g} | {r["original_S21_dB"]:.2f} | {r["cutout_S21_dB"]:.2f} | '
                     f'{r["S21_improvement_dB"]:+.2f} | {r["original_S11_dB"]:.2f} | {r["cutout_S11_dB"]:.2f} |')
    folder=out.name
    r4=min(rows,key=lambda r:abs(r['f_GHz']-4))
    r6=min(rows,key=lambda r:abs(r['f_GHz']-6))
    reflected6=float(abs(s[-1,0,0])**2)
    transmitted6=float(abs(s[-1,1,0])**2)
    report=['# L2 cutouts beneath the launch pads: first trial', '',
        f'**One new completed sweep: two {width:g} × {length:g} mm L2 cutouts, 20 frequencies.** '
        'Compared below with the completed original-ground connector control; no parameter search or extra mesh variant.', '',
        f'**The cutouts substantially improve broadband transmission in this model.** '
        f'At 4 GHz, S21 changes from {r4["original_S21_dB"]:.2f} to {r4["cutout_S21_dB"]:.2f} dB. '
        f'At 6 GHz, it changes from {r6["original_S21_dB"]:.2f} to {r6["cutout_S21_dB"]:.2f} dB '
        f'({r6["S21_improvement_dB"]:.2f} dB improvement), while S11 improves from '
        f'{r6["original_S11_dB"]:.2f} to {r6["cutout_S11_dB"]:.2f} dB. '
        'The former high-frequency mismatch is greatly reduced; this supports the pad-capacitance '
        'diagnosis. The initial cutout size is promising but still leaves appreciable reflection '
        'at the upper end of the band.', '',
        f'![Cutout and original-ground simulations]({folder}/cutout_vs_original.png)', '',
        '## Exactly what changed', '',
        f'Only L2 copper is removed: left x=0.28…{.28+length:g} mm, '
        f'right x={19.88-length:g}…19.88 mm, y=±{width/2:g} mm. '
        'The dielectric remains. L3 and bottom copper, ground tabs, vias, signal pads, '
        'tapers and both connectors are unchanged. The cutouts stop at the inner edges of '
        'the wide signal pads, before the tapers. These are copper keepouts, not milled board slots.', '',
        'The hypothesis is that removing the nearest ground reduces the wide pad’s excess '
        'capacitance. The next continuous plane beneath the pad is now L3, approximately '
        '1.29 mm below the top surface instead of L2 at 0.2104 mm. Fringing fields still '
        'reach the nearby L2 edges, and the return-current path also changes; this is not '
        'equivalent to changing only a lumped capacitor.', '',
        'The occupancy checks confirm empty L2 at both cutout centres; L3 remains beneath '
        'them, and L2 remains beneath the tapers and ground contacts and beside the windows. '
        'The CAD still has one continuous signal network and one separate ground network.', '',
        f'![L2 removal mask in plan]({folder}/l2_cutout_plan.png)', '',
        f'![Connector assembly]({folder}/assembly.png)', '',
        f'![Launch cutaway]({folder}/launch_cutaway.png)', '',
        '## Controlled comparison', '',
        '| Parameter | Original ground | L2 cutouts |', '|---|---:|---:|',
        f'| Tetrahedra | {baseline["tetrahedra"]:,} | {meta["tetrahedra"]:,} |',
        f'| Nodes | {baseline["nodes"]:,} | {meta["nodes"]:,} |',
        '| Signal-edge / signal-surface target | 0.06 / 0.18 mm | same |',
        '| Substrate / connector / port target | 0.90 / 0.45 / 0.22 mm | same |',
        '| FEM order / direct frequencies | 1 / 20 | same |',
        '| Connector, material and air-box parameters | baseline | unchanged |', '',
        'Both curves include the connectors at coax reference planes x=−8.10 and '
        '28.26 mm and use a common 50 Ω reference. New meshing is necessary because '
        'the geometry changed; the element count need not remain identical. '
        f'The new frequency sweep took {meta["solve_seconds"]/60:.1f} minutes.', '',
        '**The grey measurement is the original unmodified board.** There is no measured '
        'cutout board yet, so it is shown for context, not as a fit target for the redesign.', '',
        *table, '',
        f'![Power balance]({folder}/cutout_power.png)', '',
        '“Remaining” power includes dissipation, radiation and numerical error; it is not '
        'a separate measurement of dielectric loss. Positive S21 improvement means increased '
        'transmission relative to the original-ground simulation at that frequency.', '',
        f'At 6 GHz with cutouts: {100*transmitted6:.1f}% transmitted, '
        f'{100*reflected6:.1f}% reflected, '
        f'{100*(1-transmitted6-reflected6):.1f}% remaining. '
        'The dominant benefit is reduced reflection rather than a claim that the substrate '
        'has become less lossy.', '',
        '## Numerical checks and limits', '',
        f'Native modal impedance: {checks["modal_Z0_real_range_ohm"][0]:.3f}–'
        f'{checks["modal_Z0_real_range_ohm"][1]:.3f} Ω. '
        f'Maximum |S21−S12|: {checks["max_reciprocity_error"]:.3g}; '
        f'maximum |S11−S22|: {checks["max_symmetry_error"]:.3g}; '
        f'maximum singular value: {checks["max_singular_value"]:.6f}.', '',
        'This is one initial cutout size on one first-order mesh, not an optimized design '
        'or a convergence study. Connector interior and ideal solder-contact assumptions '
        'are the same as in [the geometry report](03_CONNECTOR_GEOMETRY.md).', '',
        '## Reproduce', '', 'From `C:\\Fun\\ToyRadar\\Frontend\\emerge`:', '', '```powershell',
        f'.\\.venv\\Scripts\\python.exe -m coupon_10mm.connector_model --l2-opening {width:g} {length:g} --reuse-mesh --view-mesh',
        f'.\\.venv\\Scripts\\python.exe -m coupon_10mm.connector_model --l2-opening {width:g} {length:g} --reuse-mesh --solve',
        f'.\\.venv\\Scripts\\python.exe -m coupon_10mm.compare_cutout --l2-opening {width:g} {length:g}', '```', '',
        f'Raw/native and 50 Ω S, Z0 and β: `{stem}.npz`; solve metadata: `{stem}.json`; '
        f'50 Ω Touchstone: `{stem}.s2p`. The original control files remain separate.']
    path=REPORTS/'05_L2_CUTOUT_RESULTS.md' if args.l2_opening==[1.6,4.8] else out/'RESULTS.md'
    tail=''
    if path.exists() and WIDTH_SECTION in path.read_text(encoding='utf-8'):
        tail='\n\n'+WIDTH_SECTION+path.read_text(encoding='utf-8').split(WIDTH_SECTION,1)[1]
    write_report(path, '\n'.join(report)+'\n'+tail)
    print(json.dumps({k:v for k,v in checks.items() if k!='rows'},indent=2))


if __name__=='__main__':main()

"""Compare abrupt versus tapered pad transitions with 4.2 mm L2 cutouts."""
from .report_paths import REPORTS, write_report
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon,Rectangle
from .compare import HERE,db
from .connector_model import variant_paths
from .compare_cutout import STEP_SECTION


def main():
    out,stem=variant_paths([4.2,4.8],'step')
    _,taper_stem=variant_paths([4.2,4.8])
    data=np.load(HERE/f'{stem}.npz');control=np.load(HERE/f'{taper_stem}.npz')
    meta=json.loads((HERE/f'{stem}.json').read_text(encoding='utf-8'))
    baseline=json.loads((HERE/f'{taper_stem}.json').read_text(encoding='utf-8'))
    assert meta['status']==baseline['status']=='completed'
    assert meta['launch_transition']=='step' and baseline.get('launch_transition','taper')=='taper'
    for key in ('source_board_sha256','connector_parameters_mm','pcb_layers','air_box_mm',
                'port_x_mm','mesh_targets_mm','element_order','l2_opening_mm'):
        assert meta[key]==baseline[key],f'Transition control differs in {key}'
    f=data['f'].reshape(-1);s=data['Smat50'];b=control['Smat50'];z=data['Z0']
    assert np.array_equal(f,control['f'].reshape(-1))
    assert s.shape==b.shape==(len(f),2,2) and np.all(np.isfinite(s))
    pcb=json.loads((HERE/'pcb_geometry.json').read_text(encoding='utf-8'))
    original=next(r['outer'] for l in pcb['layers'] if l['name']=='F.Cu'
                  for r in l['copper'] if r['net']!='GND_1')
    fig,axes=plt.subplots(1,2,figsize=(10,4),sharex=True,sharey=True,constrained_layout=True)
    for ax,outline,title,color in zip(axes,(original,meta['signal_outline_mm']),
                                     ('Original taper','Abrupt 1.2 to 0.37 mm step'),('#d55e00','#8e44ad')):
        ax.add_patch(Rectangle((5.08,-.9),2.1,1.8,facecolor='#d2e8f2',edgecolor='none'))
        ax.add_patch(Polygon(outline,facecolor=color,edgecolor=color,alpha=.7))
        ax.axvline(5.08,color='#444444',ls=':',lw=1)
        ax.set(xlim=(4.4,6.7),ylim=(-.8,.8),xlabel='x from left board edge (mm)',title=title)
        ax.set_aspect('equal');ax.grid(alpha=.2)
    axes[0].set_ylabel('y (mm)')
    fig.suptitle('Left transition: same pad inner edge and L2 cutout end at x=5.08 mm\n'
                 'Blue background: L2 resumes under the microstrip; right launch is mirrored')
    fig.savefig(out/'transition_geometry.png',dpi=170,bbox_inches='tight');plt.close(fig)
    for zoom in (False,True):
        fig,axes=plt.subplots(2,1,figsize=(10,8),sharex=True,constrained_layout=True)
        for ax,i,j in ((axes[0],1,0),(axes[1],0,0)):
            ax.plot(f/1e9,db(b[:,i,j]),'o-',color='#d55e00',lw=1.8,ms=4,label='4.2 mm cutout + original tapers')
            ax.plot(f/1e9,db(s[:,i,j]),'o-',color='#8e44ad',lw=1.8,ms=4,label='4.2 mm cutout + abrupt steps')
            ax.axvspan(5.725,5.875,color='#009e73',alpha=.12,label='Target: 5.8 GHz +/- 75 MHz')
            ax.grid(alpha=.25);ax.legend(fontsize=8)
            ax.set_xlim((5.5,6.05) if zoom else (0,6.1))
        axes[0].set(ylabel='S21 (dB)')
        axes[1].set(ylabel='S11 (dB)',xlabel='Frequency (GHz)')
        if not zoom:axes[1].set_ylim(-50,1)
        fig.suptitle('Remove only the two PCB tapers; retain 4.2 x 4.8 mm L2 cutouts\n'
                     'Same 20 directly solved frequencies, materials and coax connector model')
        fig.savefig(out/('step_target_context.png' if zoom else 'step_vs_taper.png'),dpi=170,bbox_inches='tight')
        plt.close(fig)
    rows=[dict(f_GHz=float(freq/1e9),taper_S21_dB=float(db(b[k,1,0])),step_S21_dB=float(db(s[k,1,0])),
               S21_change_dB=float(db(s[k,1,0])-db(b[k,1,0])),
               taper_S11_dB=float(db(b[k,0,0])),step_S11_dB=float(db(s[k,0,0]))) for k,freq in enumerate(f)]
    checks=dict(frequencies=len(f),nodes=meta['nodes'],tetrahedra=meta['tetrahedra'],
                max_reciprocity_error=float(abs(s[:,1,0]-s[:,0,1]).max()),
                max_symmetry_error=float(abs(s[:,0,0]-s[:,1,1]).max()),
                max_singular_value=float(np.linalg.svd(s,compute_uv=False).max()),
                modal_Z0_real_range_ohm=[float(z.real.min()),float(z.real.max())],rows=rows)
    (out/'transition_metrics.json').write_text(json.dumps(checks,indent=2)+'\n',encoding='utf-8')
    lines=['! PCB + BWSMA; 4.2 x 4.8 mm L2 cutouts; abrupt 1.2-to-0.37 mm PCB steps',
           '! Coax reference planes x=-8.10 and 28.26 mm; connectors included; no de-embedding',
           '# Hz S RI R 50']
    for freq,m in zip(f,s):
        lines.append(f'{freq:.12g} '+' '.join(f'{v.real:.12g} {v.imag:.12g}' for v in (m[0,0],m[1,0],m[0,1],m[1,1])))
    (HERE/f'{stem}.s2p').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    table=['| GHz | Taper S21, dB | Step S21, dB | Change, dB | Taper S11, dB | Step S11, dB |',
           '|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        table.append(f'| {r["f_GHz"]:g} | {r["taper_S21_dB"]:.2f} | {r["step_S21_dB"]:.2f} | '
                     f'{r["S21_change_dB"]:+.2f} | {r["taper_S11_dB"]:.2f} | {r["step_S11_dB"]:.2f} |')
    centre=min(rows,key=lambda r:abs(r['f_GHz']-5.8))
    folder=out.name
    section=[STEP_SECTION,'','## Abrupt pad-to-microstrip steps with the 4.2 mm cutouts','',
        '**Fourth completed connector sweep: abrupt transitions, same 20 frequencies over 0.5–6 GHz.** '
        'It is compared with the existing 4.2 mm cutout / tapered-transition sweep. '
        'No previous result was overwritten; no additional target-band frequency sweep was run.', '',
        f'At **5.8 GHz**, S21 changes from **{centre["taper_S21_dB"]:.2f} to '
        f'{centre["step_S21_dB"]:.2f} dB**, and S11 changes from '
        f'**{centre["taper_S11_dB"]:.2f} to {centre["step_S11_dB"]:.2f} dB**.', '',
        '| At 5.8 GHz | Original tapers | Abrupt steps |', '|---|---:|---:|',
        f'| S21, dB | {centre["taper_S21_dB"]:.2f} | {centre["step_S21_dB"]:.2f} |',
        f'| S11, dB | {centre["taper_S11_dB"]:.2f} | {centre["step_S11_dB"]:.2f} |', '',
        '**For the sampled 5.8 GHz point, retain the tapered design as the reference.** '
        'The abrupt steps cost approximately 0.30 dB of transmission and increase '
        'reflection there. They improve matching at lower frequencies and slightly '
        'improve transmission through roughly 2–4 GHz, but that benefit is outside '
        'the application band. This comparison supports keeping the original tapers '
        'while investigating other options for the 5.8 GHz launch.', '',
        'The application band is **5.725–5.875 GHz**. Of the retained broad-band grid, '
        'only 5.8 GHz lies inside it. The shading marks the requested band; line segments '
        'through it are visual guides, not additional solved points or a band-edge guarantee.', '',
        f'![Broadband comparison]({folder}/step_vs_taper.png)','',
        f'![Target-band context]({folder}/step_target_context.png)','',
        '### Geometry change','',
        'Each top signal pad remains 4.8 × 1.2 mm, at the same position. At its inner '
        'edge (x=5.08 or 15.08 mm), the width changes abruptly from 1.2 to 0.37 mm. '
        'The intervening 10 mm region is now a uniform 0.37 mm strip. The approximately '
        '1.195 mm taper at each end has become narrow microstrip; pad spacing and '
        'connector positions are unchanged. Both 4.2 × 4.8 mm L2 windows, L3, ground '
        'contacts, vias, solder approximations, materials and air box are unchanged.', '',
        f'![Transition geometry]({folder}/transition_geometry.png)','',
        'CAD occupancy checks confirm the two taper wings are absent, the narrow strip '
        'and full-width pads remain, and signal and ground still form two separate '
        'continuous networks. The saved `signal_outline_mm` records the actual replacement polygon.', '',
        *table,'',
        '### Mesh, checks and reproduction','',
        f'The step model has {meta["tetrahedra"]:,} tetrahedra and {meta["nodes"]:,} nodes, '
        'using the same mesh size targets and first-order basis as the tapered reference. '
        f'The frequency sweep took {meta["solve_seconds"]/60:.1f} minutes. '
        'The geometry was remeshed; a mesh-refinement study was not added.', '',
        f'Native modal Z0: {z.real.min():.3f}–{z.real.max():.3f} Ω; '
        f'maximum |S21−S12|: {checks["max_reciprocity_error"]:.3g}; '
        f'maximum |S11−S22|: {checks["max_symmetry_error"]:.3g}; '
        f'maximum singular value: {checks["max_singular_value"]:.6f}. '
        'All plotted results are normalized to 50 Ω at the same coax annuli, with connectors included.', '',
        'From `C:\\Fun\\ToyRadar\\Frontend\\emerge`:', '', '```powershell',
        '.\\.venv\\Scripts\\python.exe -m coupon_10mm.connector_model --l2-opening 4.2 4.8 --transition step --view',
        '.\\.venv\\Scripts\\python.exe -m coupon_10mm.connector_model --l2-opening 4.2 4.8 --transition step --reuse-mesh --solve',
        '.\\.venv\\Scripts\\python.exe -m coupon_10mm.compare_step','```','',
        f'Raw/native and 50 Ω S, modal data, completed-run metadata and Touchstone export: `{stem}.*`.']
    path=REPORTS/'05_L2_CUTOUT_RESULTS.md'
    existing=path.read_text(encoding='utf-8').split(STEP_SECTION)[0].rstrip()
    write_report(path, existing+'\n\n'+'\n'.join(section)+'\n')
    print(json.dumps(dict(centre_5p8GHz=centre,**{k:v for k,v in checks.items() if k!='rows'}),indent=2))


if __name__=='__main__':main()

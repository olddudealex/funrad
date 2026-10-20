"""Compare successive first-order meshes of the fixed 2.8 x 4.8 mm cutout."""
from .report_paths import REPORTS, write_report
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .compare import HERE, db
from .report_flatness import metrics

BASE = 'result_coax_open_2.8x4.8mm_5p3to6p3GHz'
FINE = BASE + '_mesh_refined'
OUT = HERE / 'mesh_refinement'


def load(stem):
    meta = json.loads((HERE/f'{stem}.json').read_text(encoding='utf-8'))
    assert meta['status'] == 'completed'
    with np.load(HERE/f'{stem}.npz') as data:
        return meta, data['f'].reshape(-1).copy(), data['Smat50'].copy(), data['Z0'].copy()


def main():
    OUT.mkdir(exist_ok=True)
    specs=[('Standard',BASE,'#0072b2'),('Refined',FINE,'#d55e00'),
           ('Finer',BASE+'_mesh_finer','#009e73')]
    runs=[]
    for label,stem,color in specs:
        path=HERE/f'{stem}.json'
        if label=='Finer' and (not path.exists() or json.loads(path.read_text(encoding='utf-8'))['status']!='completed'):
            continue
        meta,f,s,z=load(stem)
        assert s.shape==(11,2,2) and np.isfinite(s).all()
        if runs:
            base=runs[0]['meta']
            assert np.allclose(f,runs[0]['f'],rtol=0,atol=1)
            for key in ('source_board_sha256','connector_parameters_mm','pcb_layers',
                        'air_box_mm','port_x_mm','element_order','l2_opening_mm',
                        'launch_transition','signal_outline_mm','assumptions'):
                assert meta[key]==base[key],f'Unexpected physical-model change: {key}'
            prev=runs[-1]['meta']
            assert meta['tetrahedra']>prev['tetrahedra']
            assert all(meta['mesh_targets_mm'][k]<v for k,v in prev['mesh_targets_mm'].items())
        runs.append(dict(label=label,stem=stem,color=color,meta=meta,f=f,s=s,z=z,metrics=metrics(s)))
    assert len(runs)>=2
    pairs=[]
    # Working comparison limits chosen before inspecting the first refinement.
    limits=dict(max_S21_change_dB=.05,max_reflection_amplitude_change=.01)
    for a,b in zip(runs,runs[1:]):
        dt=db(b['s'][:,1,0])-db(a['s'][:,1,0])
        dr=abs(b['s'][:,0,0])-abs(a['s'][:,0,0])
        pairs.append(dict(label=a['label']+' → '+b['label'],
                          max_S21_change_dB=float(abs(dt).max()),
                          max_reflection_amplitude_change=float(abs(dr).max()),
                          max_complex_S_change=float(abs(b['s']-a['s']).max())))
    latest=pairs[-1]
    stable=all(latest[k]<=v for k,v in limits.items())
    summary=dict(status='completed',completed_meshes=len(runs),frequency_points_per_mesh=11,
                 working_limits=limits,within_working_limits=stable,successive_comparisons=pairs,
                 runs=[dict(label=r['label'],stem=r['stem'],tetrahedra=r['meta']['tetrahedra'],
                            nodes=r['meta']['nodes'],mesh_targets_mm=r['meta']['mesh_targets_mm'],
                            **r['metrics']) for r in runs])
    (OUT/'metrics.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    fig,axes=plt.subplots(3,1,figsize=(10,10),sharex=True,constrained_layout=True)
    for r,marker in zip(runs,('o','s','^')):
        f,s=r['f'],r['s']
        for ax,y in ((axes[0],db(s[:,1,0])),(axes[1],db(s[:,0,0])),(axes[2],abs(s[:,0,0]))):
            ax.plot(f/1e9,y,marker+'-',ms=4,color=r['color'],label=r['label'])
    for ax in axes:
        ax.grid(alpha=.25);ax.legend();ax.set_xlim(5.3,6.3)
    axes[0].set_ylabel('S21 (dB)');axes[1].set_ylabel('S11 (dB)')
    axes[2].set(ylabel='Reflection amplitude |S11|',xlabel='Frequency (GHz)')
    fig.suptitle('Mesh refinement: fixed 2.8 × 4.8 mm L2 cutout\n'
                 '11 directly solved frequencies per mesh; first-order FEM; same geometry and materials')
    fig.savefig(OUT/'responses.png',dpi=170);plt.close(fig)
    fig,axes=plt.subplots(2,1,figsize=(10,6),sharex=True,constrained_layout=True)
    for ax,limit,label in ((axes[0],.05,'Δ S21 (dB)'),(axes[1],.01,'Δ |S11|')):
        ax.axhspan(-limit,limit,color='#009e73',alpha=.12,label='Working comparison limits')
        ax.axhline(0,color='#555555',lw=.8);ax.set_ylabel(label);ax.grid(alpha=.25)
    for a,b,pair in zip(runs,runs[1:],pairs):
        axes[0].plot(f/1e9,db(b['s'][:,1,0])-db(a['s'][:,1,0]),'o-',color=b['color'],label=pair['label'])
        axes[1].plot(f/1e9,abs(b['s'][:,0,0])-abs(a['s'][:,0,0]),'o-',color=b['color'],label=pair['label'])
    for ax in axes:ax.legend()
    axes[-1].set_xlabel('Frequency (GHz)')
    fig.suptitle('Successive mesh changes: later minus earlier; identical frequency points')
    fig.savefig(OUT/'differences.png',dpi=170);plt.close(fig)
    for r in runs[1:]:
        lines=['! Fixed 2.8 x 4.8 mm L2 cutout; '+r['label']+' first-order mesh',
               '! 11 direct FEM points; coax references; connectors included','# Hz S RI R 50']
        for freq,smat in zip(f,r['s']):
            lines.append(f'{freq:.12g} '+' '.join(f'{z.real:.12g} {z.imag:.12g}' for z in
                                                (smat[0,0],smat[1,0],smat[0,1],smat[1,1])))
        (HERE/f'{r["stem"]}.s2p').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    verdict=('**The last refinement is within both working comparison limits.**' if stable else
             '**The last refinement exceeds a working comparison limit.**')
    text=['# Mesh refinement: selected L2 cutout','',verdict,'',
          f'**{len(runs)} meshes, 11 directly solved frequencies per mesh over 5.3–6.3 GHz.** '
          f'The standard result is reused; {len(runs)-1} new meshes add {11*(len(runs)-1)} frequency solves. '
          f'For {latest["label"]}, maximum pointwise change is '
          f'**{latest["max_S21_change_dB"]:.4f} dB in S21** and '
          f'**{latest["max_reflection_amplitude_change"]:.4f} in |S11|**. '
          'Working limits are 0.05 dB and 0.01 respectively. These were selected before '
          'inspecting the first refinement and are numerical comparison criteria, '
          'not fabrication or product acceptance limits.','',
          *(['**Retain the 2.8 × 4.8 mm geometry.** The smaller changes in the last '
             'refinement support using the finest result as the present numerical '
             'reference. Further mesh refinement is not needed for the current '
             'geometry decision; material sensitivity is the next useful check.',''] if stable else []),
          '## Mesh definitions','',
          'The geometry stays at **2.8 × 4.8 mm**, with original tapers, L3 intact '
          'and the same simplified BWSMA connectors. The first-order basis, material '
          'parameters, air box and coax reference planes stay fixed.','',
          '| Mesh target / actual mesh | '+' | '.join(r['label'] for r in runs)+' |',
          '|---|'+'---:|'*len(runs)]
    labels=dict(substrate='Substrate volume, mm',signal_surface='Signal surface, mm',
                signal_edge='Signal edge, mm',connector_surface='Connector surface, mm',coax_port='Coax port face, mm')
    for key,label in labels.items():
        text.append('| '+label+' | '+' | '.join(f'{r["meta"]["mesh_targets_mm"][key]:.3f}' for r in runs)+' |')
    for key,label in (('tetrahedra','Tetrahedra'),('nodes','Nodes')):
        text.append('| '+label+' | '+' | '.join(f'{r["meta"][key]:,}' for r in runs)+' |')
    text+=['| Solve time, min | '+' | '.join(f'{r["meta"]["solve_seconds"]/60:.1f}' for r in runs)+' |','',
           'The global wavelength-resolution setting, mesh growth rates and maximum '
           'boundary-size cap remain fixed. Targets guide local refinement; actual '
           'element sizes also depend on geometry and mesher constraints. '
           'Separate `_mesh_refined` and `_mesh_finer` folders/suffixes preserve all runs.','',
           '## Response comparison','','![Mesh responses](mesh_refinement/responses.png)','',
           '| Metric over 5.3–6.3 GHz | '+' | '.join(r['label'] for r in runs)+' |',
           '|---|'+'---:|'*len(runs)]
    for key,label in (('worst_loss_dB','Worst insertion loss, dB'),('transmission_ripple_dB','S21 span, dB'),
                      ('worst_S11_dB','Worst S11, dB'),('reflection_ripple','Reflection amplitude span')):
        text.append('| '+label+' | '+' | '.join(f'{r["metrics"][key]:.4f}' for r in runs)+' |')
    text+=['','| Successive comparison | Max Δ S21, dB | Max Δ reflection amplitude |',
           '|---|---:|---:|']
    for pair in pairs:
        text.append(f'| {pair["label"]} | {pair["max_S21_change_dB"]:.4f} | {pair["max_reflection_amplitude_change"]:.4f} |')
    text+=['','![Pointwise differences](mesh_refinement/differences.png)','',
           'The first refinement exceeded the 0.01 reflection-amplitude limit '
           '(0.0128), although S21 changed by only 0.0352 dB. This motivated the '
           'additional finer mesh. S11 in dB can move appreciably near a deep '
           'minimum even when absolute reflected amplitude changes little; both '
           'representations are shown.','',
           '### Direct frequency results','',
           '| GHz | '+' | '.join(r['label']+' S21, dB' for r in runs)+' | '+
           ' | '.join(r['label']+' S11, dB' for r in runs)+' |',
           '|---:|'+'---:|'*(2*len(runs))]
    for i,freq in enumerate(f):
        text.append(f'| {freq/1e9:g} | '+' | '.join(f'{db(r["s"][i,1,0]):.3f}' for r in runs)+' | '+
                    ' | '.join(f'{db(r["s"][i,0,0]):.2f}' for r in runs)+' |')
    text+=['','## Checks and interpretation','',
           'Saved geometry, connector, layer, air-box, port, material-assumption and '
           'element-order metadata agree. Each later mesh has smaller targets and '
           'more tetrahedra. CAD checks verify separate continuous signal/ground '
           'networks, complete coax annuli and the intended L2 cutouts.','',
           '| Numerical check | '+' | '.join(r['label'] for r in runs)+' |',
           '|---|'+'---:|'*len(runs)]
    for key,label in (('max_singular_value','Maximum singular value of S'),
                      ('max_reciprocity_error','Maximum reciprocity error'),
                      ('max_symmetry_error','Maximum mirror-symmetry error')):
        text.append('| '+label+' | '+' | '.join(f'{r["metrics"][key]:.6g}' for r in runs)+' |')
    text+=['| Port Z0 real range, Ω | '+' | '.join(f'{r["z"].real.min():.3f}–{r["z"].real.max():.3f}' for r in runs)+' |','',
           'All S matrices are renormalized to 50 Ω. A small successive change '
           'supports numerical stability for this particular model; it does not '
           'bound the exact solution’s error or validate the simplified connector '
           'against hardware. Air-box, polynomial-order and material-sensitivity '
           'checks are separate. The earlier broadband report uses the standard '
           'mesh; the finer checks cover only 5.3–6.3 GHz.','',
           '## Reproduce','','From `C:\\Fun\\ToyRadar\\Frontend\\emerge`:','','```powershell',
           '.\\.venv\\Scripts\\python.exe -m coupon_10mm.connector_model --l2-opening 2.8 4.8 --frequency-grid flatness --mesh-profile refined --solve',
           '.\\.venv\\Scripts\\python.exe -m coupon_10mm.connector_model --l2-opening 2.8 4.8 --frequency-grid flatness --mesh-profile finer --solve',
           '.\\.venv\\Scripts\\python.exe -m coupon_10mm.report_mesh_refinement','```','',
           'To reuse a mesh, add `--reuse-mesh` with the same `--mesh-profile`. '
           'To inspect it without solving, replace `--solve` with `--reuse-mesh --view-mesh`. '
           'Raw S, 50 Ω S, port Z0 and β are saved in each corresponding NPZ; '
           'matching JSON records completed-run metadata and `.s2p` is the 50 Ω export. '
           '[Geometry sweep](06_L2_CUTOUT_FLATNESS_SWEEP.md) · [Broadband check](07_BROADBAND_CHECK.md).']
    write_report(REPORTS/'08_MESH_REFINEMENT.md', '\n'.join(text)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()

"""Report epsilon-r sensitivity on the selected coupon's fixed finer mesh."""
from .report_paths import REPORTS, write_report
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .compare import HERE,db
from .report_flatness import metrics
from .sweep_dielectric import BASE,OUT

VALUES=(4.2,4.5,4.8)


def main():
    OUT.mkdir(exist_ok=True)
    nominal=json.loads((HERE/f'{BASE}.json').read_text(encoding='utf-8'))
    with np.load(HERE/f'{BASE}.npz') as data:
        nominal_z=data['Z0'].copy();nominal_beta=data['beta'].copy()
    records=[];spectra=[]
    for er in VALUES:
        stem=BASE if er==4.5 else BASE+'_er'+f'{er:g}'.replace('.','p')
        meta=json.loads((HERE/f'{stem}.json').read_text(encoding='utf-8'))
        assert meta['status']=='completed' and meta.get('pcb_er',4.5)==er
        assert meta.get('pcb_loss_tangent',.02)==.02
        assert meta.get('l3_opening_mm') is None
        for key in ('source_board_sha256','connector_parameters_mm','pcb_layers','air_box_mm',
                    'port_x_mm','mesh_targets_mm','element_order','l2_opening_mm',
                    'launch_transition','signal_outline_mm','nodes','tetrahedra'):
            assert meta[key]==nominal[key],f'Unexpected change: {key}'
        # The FR4 material assumption is intentionally the only changed entry.
        assert [s for s in meta['assumptions'] if not s.startswith('FR4 er=')]==[
                s for s in nominal['assumptions'] if not s.startswith('FR4 er=')]
        with np.load(HERE/f'{stem}.npz') as data:
            f,s,z=data['f'].reshape(-1).copy(),data['Smat50'].copy(),data['Z0'].copy()
            beta=data['beta'].copy()
        assert s.shape==(11,2,2) and np.isfinite(s).all()
        assert np.allclose(f,np.linspace(5.3,6.3,11)*1e9,rtol=0,atol=1)
        assert np.allclose(z,nominal_z,rtol=1e-6,atol=1e-6), 'Coax port impedance changed unexpectedly'
        assert np.allclose(beta,nominal_beta,rtol=1e-6,atol=1e-6), 'Coax port propagation changed unexpectedly'
        row=dict(er=er,result_stem=stem,**metrics(s),S21_5p8_dB=float(db(s[5,1,0])),
                 S11_5p8_dB=float(db(s[5,0,0])),
                 sampled_reflection_minimum_GHz=float(f[np.argmin(abs(s[:,0,0]))]/1e9),
                 solve_minutes=meta['solve_seconds']/60,
                 port_Z0_real_min=float(z.real.min()),port_Z0_real_max=float(z.real.max()))
        row.update(max_port_Z0_change_ohm=float(abs(z-nominal_z).max()),
                   max_port_beta_change_per_m=float(abs(beta-nominal_beta).max()))
        records.append(row);spectra.append((er,f,s))
        lines=[f'! PCB epsilon-r={er:g}, loss tangent 0.02; fixed finer mesh',
               '! 2.8 x 4.8 mm L2 windows; L3/Bottom intact; coax reference planes',
               '! 11 direct FEM points; connectors included','# Hz S RI R 50']
        for freq,smat in zip(f,s):
            lines.append(f'{freq:.12g} '+' '.join(f'{v.real:.12g} {v.imag:.12g}' for v in
                                                (smat[0,0],smat[1,0],smat[0,1],smat[1,1])))
        (HERE/f'{stem}.s2p').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    nom_s=spectra[1][2]
    for row,(_,f,s) in zip(records,spectra):
        row['max_S21_change_from_nominal_dB']=float(abs(db(s[:,1,0])-db(nom_s[:,1,0])).max())
        row['max_reflection_amplitude_change_from_nominal']=float(abs(abs(s[:,0,0])-abs(nom_s[:,0,0])).max())
    worst_loss=max(r['worst_loss_dB'] for r in records)
    worst_match=max(r['worst_S11_dB'] for r in records)
    summary=dict(status='completed',er_values=list(VALUES),new_material_cases=2,new_frequency_solves=22,
                 nominal_reused=True,tan_delta=.02,nodes=nominal['nodes'],tetrahedra=nominal['tetrahedra'],
                 range_basis='Exploratory +/-0.3 about CAD nominal 4.5; not manufacturer tolerance limits',
                 worst_loss_across_sampled_cases_dB=worst_loss,
                 worst_S11_across_sampled_cases_dB=worst_match,records=records)
    summary['aborted_port_search_attempts']=int((OUT/'er4.2_mode_failure.log').exists())
    (OUT/'metrics.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    fig,axes=plt.subplots(3,1,figsize=(10,10),sharex=True,constrained_layout=True)
    for (er,f,s),color,marker in zip(spectra,('#0072b2','#333333','#d55e00'),('o','s','^')):
        label=f'εr={er:g}'+(' (CAD nominal)' if er==4.5 else '')
        for ax,y in ((axes[0],db(s[:,1,0])),(axes[1],db(s[:,0,0])),(axes[2],abs(s[:,0,0]))):
            ax.plot(f/1e9,y,marker+'-',color=color,ms=4,label=label)
    for ax in axes:ax.grid(alpha=.25);ax.legend();ax.set_xlim(5.3,6.3)
    axes[0].set_ylabel('S21 (dB)');axes[1].set_ylabel('S11 (dB)')
    axes[2].set(ylabel='Reflection amplitude |S11|',xlabel='Frequency (GHz)')
    fig.suptitle('Dielectric sensitivity: fixed 2.8 × 4.8 mm L2 openings\n'
                 'L3 / Bottom intact; tanδ=0.02; identical finer mesh; 11 direct points per εr')
    fig.savefig(OUT/'responses.png',dpi=170);plt.close(fig)
    # This envelope spans the three sampled values, not every possible material state.
    fig,axes=plt.subplots(2,1,figsize=(10,7),sharex=True,constrained_layout=True)
    for ax,i,j,label in ((axes[0],1,0,'S21 (dB)'),(axes[1],0,0,'S11 (dB)')):
        values=np.array([db(s[:,i,j]) for _,_,s in spectra])
        ax.fill_between(f/1e9,values.min(axis=0),values.max(axis=0),alpha=.2,
                        color='#0072b2',label='Range across three sampled εr values')
        ax.plot(f/1e9,values[1],'o-',color='#333333',ms=4,label='εr=4.5 nominal')
        ax.set_ylabel(label);ax.grid(alpha=.25);ax.legend()
    axes[-1].set_xlabel('Frequency (GHz)')
    fig.suptitle('Sampled material envelope; geometry and loss tangent held fixed')
    fig.savefig(OUT/'sampled_envelope.png',dpi=170);plt.close(fig)
    text=['# Dielectric sensitivity of the selected L2 cutout','',
          '**Two new material sweeps, 22 new frequency solves.** The εr=4.5 '
          'nominal result is reused from [mesh refinement](08_MESH_REFINEMENT.md). '
          'Each of the three εr values is evaluated at the same 11 points from '
          '5.3 to 6.3 GHz, on the same saved finer mesh.','',
          '## Range and fixed parameters','',
          'The [coupon board stack](../../kicad/FrontendPCBCoupon/FrontendPCBCoupon.kicad_pcb) '
          'specifies εr=4.5 for its PCB dielectric layers; the outer dielectrics '
          'are named 7628-FR4. No verified manufacturing tolerance interval was '
          'found in the repository. **4.2, 4.5 and 4.8** are an exploratory '
          '±0.3 (±6.7%) sensitivity range around that CAD nominal, not supplier limits.','',
          '| Parameter | Setting |','|---|---|',
          '| PCB εr | 4.2 / 4.5 / 4.8; uniform and frequency independent in each run |',
          '| PCB loss tangent | 0.020 in all cases |',
          '| L2 windows | Two symmetric 2.8 × 4.8 mm windows |',
          '| L3 / Bottom | Intact |',
          '| Signal transition | Original tapers; all copper and via geometry fixed |',
          '| Connector | Same simplified BWSMA; PTFE εr=2.1 unchanged |',
          '| Mesh | Same saved first-order finer mesh; no remeshing |',
          '| Frequency grid | 5.3, 5.4, …, 6.3 GHz |','',
          'The model uses one homogeneous FR4 substrate volume, so all PCB '
          'dielectric regions change together. This does not model weave, '
          'anisotropy, layer-to-layer variations or dielectric dispersion. '
          'Holding tanδ fixed isolates εr as the input change; it does not '
          'hold dielectric attenuation fixed, because field distribution and '
          'complex permittivity also depend on εr.','',
          '## Results','','![Dielectric responses](dielectric_sensitivity/responses.png)','',
          '| εr | Worst insertion loss, dB | S21 span, dB | Worst S11, dB | Reflection amplitude span |',
          '|---:|---:|---:|---:|---:|']
    for r in records:
        text.append(f'| {r["er"]:g} | {r["worst_loss_dB"]:.4f} | {r["transmission_ripple_dB"]:.4f} | '
                    f'{r["worst_S11_dB"]:.2f} | {r["reflection_ripple"]:.4f} |')
    text+=['',f'Across these three sampled material cases, worst insertion loss is '
           f'**{worst_loss:.3f} dB** and worst S11 is **{worst_match:.2f} dB**. '
           'These are results across the sampled frequencies and εr values, '
           'not continuous tolerance bounds.','',
           '**Retain the current geometry for a revised coupon.** At every '
           'sampled point, changing εr moves S21 by no more than '
           f'{max(r["max_S21_change_from_nominal_dB"] for r in records):.3f} dB '
           'from nominal. Transmission remains smooth over the tested band. '
           'The sampled reflection minimum moves from the upper band edge '
           'at εr=4.2 to 6.2 GHz nominally and 5.9 GHz at εr=4.8. '
           'Matching is material-sensitive, but this range does not produce '
           'a sampled transmission collapse. These results support testing '
           'the fixed geometry in hardware without tuning to one deep '
           'nominal reflection minimum.','',
           '![Sampled material envelope](dielectric_sensitivity/sampled_envelope.png)','',
           '### Centre frequency and movement of the reflection minimum','',
           '| εr | S21 at 5.8 GHz, dB | S11 at 5.8 GHz, dB | Lowest sampled S11 at, GHz | Max S21 change from nominal, dB |',
           '|---:|---:|---:|---:|---:|']
    for r in records:
        text.append(f'| {r["er"]:g} | {r["S21_5p8_dB"]:.3f} | {r["S11_5p8_dB"]:.2f} | '
                    f'{r["sampled_reflection_minimum_GHz"]:g} | {r["max_S21_change_from_nominal_dB"]:.4f} |')
    text+=['','The minimum is located only on the 100 MHz sample grid. '
           'A minimum at a band edge is not a claim that the true minimum lies '
           'at that edge. Assess the whole-band loss and reflection levels '
           'rather than the depth of one minimum. The two exact 5.8 GHz ±75 MHz '
           'application edges are not additional solve points.','',
           '## Numerical checks','',
           f'All three runs use **{nominal["tetrahedra"]:,} tetrahedra / '
           f'{nominal["nodes"]:,} nodes**. Saved metadata match for geometry, '
           'connector, layers, ports, air box, mesh targets, node/element counts '
           'and basis order. The only changed physical input is PCB εr; tanδ, '
           'copper conductivity and PTFE properties remain fixed. Existing meshes '
           'are reused deliberately to avoid adding remeshing differences.','',
           '| εr | Solve, min | Max singular value | Reciprocity error | Port Z0 real range, Ω |',
           '|---:|---:|---:|---:|---:|']
    for r in records:
        text.append(f'| {r["er"]:g} | {r["solve_minutes"]:.1f} | {r["max_singular_value"]:.6f} | '
                    f'{r["max_reciprocity_error"]:.3g} | {r["port_Z0_real_min"]:.3f}–{r["port_Z0_real_max"]:.3f} |')
    text+=['','All responses use 50 Ω coax reference planes and include both '
           'connectors. No material values were fitted to measurements. '
           'The mesh was refined at nominal εr; its convergence was not '
           'repeated separately at each material corner.','',
           '### Port-search diagnostic','',
           'The first εr=4.2 attempt stopped before frequency solves because the '
           'generic iterative port search found no mode. The successful corner '
           'runs explicitly target the analytical uniform-PTFE coax TEM index '
           'sqrt(2.1). This changes the eigensolver search target, not the '
           'port geometry or electromagnetic model. Port Z0 and β are checked '
           'against the saved nominal arrays, each within 1e−6 relative/absolute '
           'comparison tolerance. The failed attempt is excluded from the '
           '22 completed new frequency solves.','',
           '## Reproduce','','From `C:\\Fun\\ToyRadar\\Frontend\\emerge`:','','```powershell',
           '.\\.venv\\Scripts\\python.exe -m coupon_10mm.sweep_dielectric',
           '.\\.venv\\Scripts\\python.exe -m coupon_10mm.report_dielectric','```','',
           'The runner is sequential and resumable; it skips completed matching '
           'corners and reuses the saved nominal result. The saved finer mesh '
           'and completed nominal reference from report 08 are prerequisites. '
           'On a fresh checkout without that mesh, first regenerate the nominal '
           'finer-mesh run using the commands in report 08. One corner can be run with:','','```powershell',
           '.\\.venv\\Scripts\\python.exe -m coupon_10mm.connector_model --l2-opening 2.8 4.8 --frequency-grid flatness --mesh-profile finer --reuse-mesh --pcb-er 4.2 --solve','```','',
           'The non-nominal result suffixes are `_er4p2` and `_er4p8`; nominal '
           'results are preserved. Each result has native S, 50 Ω S, port Z0 and '
           'β in NPZ, completed-run metadata in JSON and a 50 Ω Touchstone export. '
           'Metrics, plots, progress and logs are under `dielectric_sensitivity/`. '
           '[Report index](README.md).']
    write_report(REPORTS/'10_DIELECTRIC_SENSITIVITY.md', '\n'.join(text)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()

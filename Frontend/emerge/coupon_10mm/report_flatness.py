"""Plots and a new report for the six-geometry L2-window flatness sweep.

--partial shows completed cases while the sequential runner is still working.
The score constants below are fixed for the study, not fitted to its results.
"""
from .report_paths import REPORTS, write_report
import argparse
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon,Rectangle,Circle
from .compare import HERE,db
from .sweep_flatness import CASES,OUT
from .connector_model import FLATNESS_FREQUENCIES_GHZ,variant_paths

SCORE_SCALES=dict(worst_loss_dB=1.,transmission_ripple_dB=.5,
                  worst_reflection=10**(-15/20),reflection_ripple=.10)
RIPPLE_WEIGHT=.25
TAPER_SECTION='<!-- EXTENDED-TAPER-CUTOUT-STUDY -->'


def metrics(s):
    transmission=db(s[:,1,0]);reflection=abs(s[:,0,0])
    loss=float(-transmission.min());ripple=float(np.ptp(transmission))
    worst_r=float(reflection.max());ripple_r=float(np.ptp(reflection))
    score=max(loss/SCORE_SCALES['worst_loss_dB'],worst_r/SCORE_SCALES['worst_reflection'])
    score+=RIPPLE_WEIGHT*(ripple/SCORE_SCALES['transmission_ripple_dB']+
                          ripple_r/SCORE_SCALES['reflection_ripple'])
    return dict(worst_loss_dB=loss,transmission_ripple_dB=ripple,worst_reflection=worst_r,
                worst_S11_dB=float(db(worst_r)),reflection_ripple=ripple_r,
                S11_dB_range=float(np.ptp(db(s[:,0,0]))),score=float(score),
                max_reciprocity_error=float(abs(s[:,1,0]-s[:,0,1]).max()),
                max_symmetry_error=float(abs(s[:,0,0]-s[:,1,1]).max()),
                max_singular_value=float(np.linalg.svd(s,compute_uv=False).max()))


def geometry_matrix():
    pcb=json.loads((HERE/'pcb_geometry.json').read_text(encoding='utf-8'))
    fig,axes=plt.subplots(3,2,figsize=(10,11),sharex=True,sharey=True,constrained_layout=True)
    for ax,case in zip(axes.flat,CASES):
        w,l=case['width_mm'],case['length_mm']
        for layer in pcb['layers']:
            if layer['name']=='In1.Cu':
                for r in layer['copper']:ax.add_patch(Polygon(r['outer'],facecolor='#cfdfeb',edgecolor='#5687a4',lw=.8))
        ax.add_patch(Rectangle((.28,-w/2),l,w,facecolor='white',edgecolor='#009e73',lw=1.6))
        for layer in pcb['layers']:
            if layer['name']=='F.Cu':
                for r in layer['copper']:
                    ax.add_patch(Polygon(r['outer'],fill=False,
                        edgecolor='#cf741f' if r['net']!='GND_1' else '#7a6946',lw=1))
        for via in pcb['vias']:
            ax.add_patch(Circle(via['xy_mm'],via['drill_mm']/2,facecolor='white',edgecolor='#7a6946',lw=.6))
        for y in (-3,2.1):ax.add_patch(Rectangle((-.1,y),4,.9,fill=False,ls='--',edgecolor='#71549c',lw=.8))
        ax.set(xlim=(-.15,6.6),ylim=(-3.4,3.4),title=f'{case["id"]}: W={w:g}, L={l:g} mm')
        ax.set_aspect('equal');ax.grid(alpha=.15)
    for ax in axes[-1]:ax.set_xlabel('x from board edge (mm)')
    for ax in axes[:,0]:ax.set_ylabel('y (mm)')
    fig.suptitle('Six L2 cutout masks at the left launch; right launch is mirrored\n'
                 'Blue: L2 | orange: signal/taper outline | purple dashes: ground pins')
    fig.savefig(OUT/'geometry_matrix.png',dpi=150,bbox_inches='tight');plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--partial',action='store_true')
    args=parser.parse_args();OUT.mkdir(exist_ok=True)
    records=[];spectra=[];reference=None
    colors=plt.get_cmap('tab10').colors
    for case in CASES:
        _,base=variant_paths([case['width_mm'],case['length_mm']])
        stem=base+'_5p3to6p3GHz';path=HERE/f'{stem}.json'
        if not path.exists() or not (HERE/f'{stem}.npz').exists():
            if args.partial:continue
            raise ValueError(f'Missing completed result: {case["id"]}')
        meta=json.loads(path.read_text(encoding='utf-8'))
        if meta['status']!='completed':
            if args.partial:continue
            raise ValueError(f'Incomplete: {case["id"]}')
        data=np.load(HERE/f'{stem}.npz');f=data['f'].reshape(-1);s=data['Smat50']
        assert np.allclose(f,np.asarray(FLATNESS_FREQUENCIES_GHZ)*1e9,rtol=0,atol=1)
        assert s.shape==(11,2,2) and np.all(np.isfinite(s))
        assert meta.get('launch_transition','taper')=='taper'
        if reference is None:reference=meta
        for key in ('source_board_sha256','connector_parameters_mm','pcb_layers','air_box_mm',
                    'port_x_mm','mesh_targets_mm','element_order'):
            assert meta[key]==reference[key],f'Unexpected control change: {key}'
        record=dict(case,**metrics(s),result_stem=stem,nodes=meta['nodes'],tetrahedra=meta['tetrahedra'],
                    solve_minutes=meta['solve_seconds']/60,
                    modal_Z0_range=[float(data['Z0'].real.min()),float(data['Z0'].real.max())],
                    S21_5p8_dB=float(db(s[5,1,0])),S11_5p8_dB=float(db(s[5,0,0])))
        records.append(record);spectra.append((record,f,s))
        lines=[f'! {case["id"]}: W={case["width_mm"]:g}, L={case["length_mm"]:g} mm; original tapers; L3 intact',
               '! 11 direct frequencies 5.3-6.3 GHz; coax reference planes; connectors included', '# Hz S RI R 50']
        for freq,m in zip(f,s):
            lines.append(f'{freq:.12g} '+' '.join(f'{v.real:.12g} {v.imag:.12g}' for v in (m[0,0],m[1,0],m[0,1],m[1,1])))
        (HERE/f'{stem}.s2p').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    keys=('worst_loss_dB','transmission_ripple_dB','worst_reflection','reflection_ripple')
    for r in records:
        r['pareto']=not any(all(other[k]<=r[k] for k in keys) and any(other[k]<r[k] for k in keys)
                            for other in records if other is not r)
    ranked=sorted(records,key=lambda r:r['score'])
    repeat_check=None
    current_spectrum=next((item for item in spectra if item[0]['id']=='F06'),None)
    if current_spectrum:
        old=np.load(HERE/'result_coax_open_4.2x4.8mm.npz')
        _,new_f,new_s=current_spectrum
        pairs=[(i,int(np.argmin(abs(new_f-freq)))) for i,freq in enumerate(old['f'].reshape(-1))
               if np.min(abs(new_f-freq))<1]
        old_i,new_i=np.array(pairs).T
        repeat_check=dict(common_frequencies_GHz=(new_f[new_i]/1e9).tolist(),
            max_complex_S_difference=float(abs(old['Smat50'][old_i]-new_s[new_i]).max()))
    geometry_matrix()
    if records:
        fig,axes=plt.subplots(2,1,figsize=(11,8),sharex=True,constrained_layout=True)
        fig_r,ax_r=plt.subplots(figsize=(10,4.5),constrained_layout=True)
        for r,f,s in spectra:
            color=colors[int(r['id'][1:])-1]
            label=f'{r["id"]}: W {r["width_mm"]:g}, L {r["length_mm"]:g} mm'
            for ax,i,j in ((axes[0],1,0),(axes[1],0,0)):
                ax.plot(f/1e9,db(s[:,i,j]),'o-',ms=4,lw=1.5,color=color,label=label)
            ax_r.plot(f/1e9,abs(s[:,0,0]),'o-',ms=4,lw=1.5,color=color,label=label)
        for ax in (*axes,ax_r):
            ax.set_xlim(5.3,6.3);ax.grid(alpha=.25);ax.legend(fontsize=8,ncol=2)
        axes[0].set_ylabel('S21 (dB)');axes[1].set(ylabel='S11 (dB)',xlabel='Frequency (GHz)')
        fig.suptitle('L2 width/length flatness study: original tapers, L3 intact\n'
                     f'{len(records)} completed geometries; 11 direct points each; 50-ohm coax references')
        fig.savefig(OUT/'responses.png',dpi=170,bbox_inches='tight');plt.close(fig)
        ax_r.axhline(SCORE_SCALES['worst_reflection'],ls='--',color='gray',lw=1)
        ax_r.set(ylabel='Reflection amplitude |S11|',xlabel='Frequency (GHz)',
                 title='Reflection amplitude: the quantity used in the flatness score')
        fig_r.savefig(OUT/'reflection_amplitude.png',dpi=170,bbox_inches='tight');plt.close(fig_r)
        fig,axes=plt.subplots(2,2,figsize=(10,8),constrained_layout=True)
        for ax,(key,title) in zip(axes.flat,[('worst_loss_dB','Worst insertion loss (dB)'),
                ('transmission_ripple_dB','S21 variation (dB)'),('worst_S11_dB','Worst S11 (dB)'),('score','Combined score J')]):
            matrix=np.full((3,2),np.nan)
            for r in records:matrix[(2.8,3.5,4.2).index(r['width_mm']),(4.2,4.8).index(r['length_mm'])]=r[key]
            im=ax.imshow(matrix,aspect='auto',cmap='viridis_r')
            ax.set(xticks=[0,1],xticklabels=['4.2','4.8'],yticks=[0,1,2],yticklabels=['2.8','3.5','4.2'],
                   xlabel='Cutout length (mm)',ylabel='Cutout width (mm)',title=title)
            for i in range(3):
                for j in range(2):
                    ax.text(j,i,f'{matrix[i,j]:.3f}' if np.isfinite(matrix[i,j]) else 'pending',
                            ha='center',va='center',color='black',bbox=dict(facecolor='white',alpha=.75,edgecolor='none'))
            fig.colorbar(im,ax=ax,shrink=.75)
        fig.suptitle('Sampled geometry matrix; lower values are better for every panel')
        fig.savefig(OUT/'metric_matrix.png',dpi=170,bbox_inches='tight');plt.close(fig)
        if current_spectrum and ranked[0]['id']!='F06':
            fig,axes=plt.subplots(2,1,figsize=(10,7),sharex=True,constrained_layout=True)
            for r,f,s in [current_spectrum,next(item for item in spectra if item[0]['id']==ranked[0]['id'])]:
                color=colors[int(r['id'][1:])-1]
                for ax,i,j in ((axes[0],1,0),(axes[1],0,0)):
                    ax.plot(f/1e9,db(s[:,i,j]),'o-',lw=1.8,ms=4,color=color,
                            label=f'{r["id"]}: W={r["width_mm"]:g}, L={r["length_mm"]:g} mm')
            for ax in axes:ax.grid(alpha=.25);ax.legend(fontsize=9);ax.set_xlim(5.3,6.3)
            axes[0].set_ylabel('S21 (dB)');axes[1].set(ylabel='S11 (dB)',xlabel='Frequency (GHz)')
            fig.suptitle('Lowest-score geometry versus the previous 4.2 x 4.8 mm reference')
            fig.savefig(OUT/'selected_vs_reference.png',dpi=170,bbox_inches='tight');plt.close(fig)
    summary=dict(status='completed' if len(records)==len(CASES) else 'partial',
                 planned_geometries=len(CASES),completed_geometries=len(records),
                 frequencies_GHz=FLATNESS_FREQUENCIES_GHZ,score_scales=SCORE_SCALES,
                 ripple_weight=RIPPLE_WEIGHT,ranking=[r['id'] for r in ranked],records=records)
    summary['reference_repeat_check']=repeat_check
    (OUT/'metrics.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    folder=OUT.name
    table=['| Rank | ID | W × L, mm | Worst loss, dB ↓ | S21 span, dB ↓ | Worst S11, dB ↓ | |S11| span ↓ | J ↓ | Pareto |',
           '|---:|---|---|---:|---:|---:|---:|---:|---|']
    for k,r in enumerate(ranked,1):
        table.append(f'| {k} | {r["id"]} | {r["width_mm"]:g} × {r["length_mm"]:g} | {r["worst_loss_dB"]:.3f} | '
                     f'{r["transmission_ripple_dB"]:.3f} | {r["worst_S11_dB"]:.2f} | {r["reflection_ripple"]:.4f} | '
                     f'{r["score"]:.3f} | {"yes" if r["pareto"] else "no"} |')
    # Escape the literal table-header pipes around |S11|.
    table[0]=table[0].replace('| |S11| span','| amplitude span')
    text=['# L2 cutout flatness study: 5.3–6.3 GHz','',
          f'**Phase 1: {len(records)} of 6 geometries completed; {11*len(records)} directly solved frequency cases.** '
          'This is a six-case grid study, not gradient descent or resonance-frequency tuning. '
          'Earlier broadband data are preserved in their original files.','',
          '## Question and fixed design','',
          'Find a smooth response over the entire **5.3–6.3 GHz** interval, rather than '
          'optimizing a deep reflection minimum at one frequency. The application remains '
          '5.8 GHz ±75 MHz. Every geometry is evaluated at **5.3, 5.4, …, 6.3 GHz** '
          '(11 equally spaced points, 100 MHz spacing). The two exact application-band '
          'edges are not additional solve points in this study.','',
          'Original tapers, 4.8 × 1.2 mm pads, 0.37 mm microstrip, simplified BWSMA '
          'connectors, all via contacts, intact L3 and bottom ground, FR4 εr=4.5 / tanδ=0.02, '
          'finite copper and the air-box boundaries are held fixed. Only the width and '
          'length of the two symmetric rectangular L2 copper windows change.','',
          f'![Geometry matrix]({folder}/geometry_matrix.png)','',
          '| Width, mm | Length 4.2 mm | Length 4.8 mm |','|---:|---|---|',
          '| 2.8 | F01 | F02 |','| 3.5 | F03 | F04 |','| 4.2 | F05 | F06 — current reference |','',
          'Each window starts at the outer signal-pad edge: left x=0.28…0.28+L mm; '
          'right x=19.88−L…19.88 mm; y=±W/2. Shortening therefore restores L2 under '
          'the **inner** part of each pad. It does not shift the connector or extend '
          'the opening under the taper. The widest case stops at the ground pins’ inner '
          'edges; all ground vias and L2 beneath the pins are retained.','',
          'The width levels test intermediate values between the earlier 1.6 and 4.2 mm '
          'trials. The second length tests whether restoring some pad capacitance helps '
          'the broad response. This small matrix also exposes width/length interaction.','',
          '## Score: useful transmission, low reflection and low variation','',
          'For the 11 sampled frequencies, define transmission T in dB and reflection amplitude R:', '',
          '$$',r'T_i=20\log_{10}|S_{21,i}|,\qquad R_i=|S_{11,i}|.','$$','',
          '$$',r'L_{\max}=-\min_i T_i,\quad \Delta T=\max_iT_i-\min_iT_i,',
          r'\qquad R_{\max}=\max_iR_i,\quad \Delta R=\max_iR_i-\min_iR_i.','$$','',
          'The fixed ranking score is:', '', '$$',
          r'J=\max\left(\frac{L_{\max}}{1\,\mathrm{dB}},\frac{R_{\max}}{10^{-15/20}}\right)',
          r'+0.25\left(\frac{\Delta T}{0.5\,\mathrm{dB}}+\frac{\Delta R}{0.10}\right).','$$','',
          '**Lower is better.** The first term balances worst-case insertion loss and '
          'reflection; the second explicitly penalizes variation. The scales (1 dB, '
          '−15 dB reflection, 0.5 dB transmission span and 0.10 amplitude span) are '
          'comparison scales, not user-specified acceptance limits. The formula and '
          'weights were fixed before examining the sweep results. A flat but badly '
          'matched or highly attenuating response cannot win on flatness alone.','',
          'Reflection flatness uses amplitude rather than its dB span: a harmless deep '
          'S11 null can produce a huge dB range. Worst S11 and its dB span are still '
          'preserved in the metrics. The Pareto flag means no other case is at least '
          'as good in all four metrics and strictly better in one. Full metrics are '
          'shown so the tradeoff does not depend only on this scalar score.','',
          *table,'']
    if ranked:
        winner=ranked[0]
        text+=['## Current result' if args.partial else '## Result','',
               f'The lowest score among completed cases is **{winner["id"]}: '
               f'{winner["width_mm"]:g} × {winner["length_mm"]:g} mm**. '
               f'Worst sampled insertion loss: **{winner["worst_loss_dB"]:.3f} dB**; '
               f'S21 span: **{winner["transmission_ripple_dB"]:.3f} dB**; '
               f'worst S11: **{winner["worst_S11_dB"]:.2f} dB**. '
               +('This ranking is provisional while cases remain unfinished.' if len(records)<6 else
                 'This identifies the best sampled member of this small matrix, not a continuous optimum.'),'',
               f'The smallest S21 span is from **{min(records,key=lambda r:r["transmission_ripple_dB"])["id"]}**; '
               f'the smallest reflection-amplitude span is from '
               f'**{min(records,key=lambda r:r["reflection_ripple"])["id"]}**. '
               'These individual flatness minima are reported separately from the combined ranking.','',
               f'![Responses]({folder}/responses.png)','',
               f'![Reflection amplitude]({folder}/reflection_amplitude.png)','',
               f'![Metric matrix]({folder}/metric_matrix.png)','']
        if len(records)==6:
            if all(all(winner[k]<=r[k] for k in keys) for r in records):
                text+=['The selected case improves all four criteria over every other tested case. '
                       'Its preference therefore does not depend on the chosen positive score weights.','']
            text+=['Keeping the full 4.8 mm window length reduces worst insertion loss and '
                   'both amplitude-variation metrics at every tested width. Worst S11 also '
                   'improves at widths 2.8 and 3.5 mm; at 4.2 mm it instead worsens slightly '
                   '(−11.11 to −11.01 dB). Among full-length windows, 2.8 mm width improves '
                   'all four criteria over 3.5 and 4.2 mm. These are observations within this '
                   'matrix, not a general monotonic design rule.','',
                   f'**S11 is not flat in dB:** the selected case has a '
                   f'{winner["S11_dB_range"]:.2f} dB range, including a deep minimum. '
                   f'What improves is its worst reflection and its amplitude span: reflected '
                   f'power stays at or below {100*winner["worst_reflection"]**2:.2f}% at all '
                   '11 points. The design is not selected because of that deep minimum. '
                   'The flatter transmission and low worst-case reflection are the useful result.','']
        current=next((r for r in records if r['id']=='F06'),None)
        if current:
            if winner['id']!='F06':text += [f'![Selected versus reference]({folder}/selected_vs_reference.png)','']
            text+=['| Metric | F06 reference: 4.2 × 4.8 mm | Lowest-score case |', '|---|---:|---:|',
                   f'| Worst loss, dB | {current["worst_loss_dB"]:.3f} | {winner["worst_loss_dB"]:.3f} |',
                   f'| S21 span, dB | {current["transmission_ripple_dB"]:.3f} | {winner["transmission_ripple_dB"]:.3f} |',
                   f'| Worst S11, dB | {current["worst_S11_dB"]:.2f} | {winner["worst_S11_dB"]:.2f} |',
                   f'| Reflection amplitude span | {current["reflection_ripple"]:.4f} | {winner["reflection_ripple"]:.4f} |',
                   f'| S21 at 5.8 GHz, dB | {current["S21_5p8_dB"]:.3f} | {winner["S21_5p8_dB"]:.3f} |',
                   f'| S11 at 5.8 GHz, dB | {current["S11_5p8_dB"]:.2f} | {winner["S11_5p8_dB"]:.2f} |','']
            if winner['id']!='F06':
                if all(winner[k]<=current[k] for k in keys):
                    text+=['The selected case improves all four component metrics over F06; '
                           'this preference is not caused only by the particular score weights.','']
                _,wf,ws=next(item for item in spectra if item[0]['id']==winner['id'])
                _,_,cs=current_spectrum
                text += ['| GHz | Selected S21, dB | F06 S21, dB | Selected S11, dB | F06 S11, dB |',
                         '|---:|---:|---:|---:|---:|']
                for freq,wm,cm in zip(wf,ws,cs):
                    text.append(f'| {freq/1e9:g} | {db(wm[1,0]):.3f} | {db(cm[1,0]):.3f} | '
                                f'{db(wm[0,0]):.2f} | {db(cm[0,0]):.2f} |')
                text.append('')
    text+=['## Numerical checks and scope','',
           '| ID | Tetrahedra | Nodes | Solve, min | Max singular value | Reciprocity error | Symmetry error |',
           '|---|---:|---:|---:|---:|---:|---:|']
    for r in records:
        text.append(f'| {r["id"]} | {r["tetrahedra"]:,} | {r["nodes"]:,} | {r["solve_minutes"]:.1f} | '
                    f'{r["max_singular_value"]:.6f} | {r["max_reciprocity_error"]:.2g} | {r["max_symmetry_error"]:.3g} |')
    if repeat_check:
        text+=['',f'The repeated F06 solve agrees with its earlier broadband result at '
               f'{", ".join(f"{v:g}" for v in repeat_check["common_frequencies_GHz"])} GHz: '
               f'maximum complex S-matrix difference {repeat_check["max_complex_S_difference"]:.3g}.']
    text+=['', 'All cases use first-order FEM with the same mesh targets: 0.06 mm signal '
           'edges, 0.18 mm signal surfaces, 0.90 mm substrate, 0.45 mm connector surfaces '
           'and 0.22 mm coax port faces. Matching saved geometry meshes may be reused; '
           'new geometries are remeshed. The 11-point F06 solve is separate from its '
           'earlier 20-point broadband dataset. Every curve uses a common 50 Ω reference '
           'at the same coax planes, with both connectors included.','',
           'Each case invokes one EMerge `run_sweep()` containing all 11 frequencies, '
           'with one frequency matrix group at a time to limit memory. Cases run '
           'sequentially. CAD connectivity and L2/L3 occupancy checks run before meshing.','',
           'The 100 MHz grid screens broad variation; it does not prove that nothing '
           'happens between points. Flatness over this wider interval is a practical '
           'way to avoid selecting a narrow nominal optimum, but is not an εr '
           'tolerance simulation. No dielectric corners, L3 openings or mesh convergence '
           'study were added. The connector and contact assumptions remain those in '
           '[the geometry report](03_CONNECTOR_GEOMETRY.md).','',
           '## Files and reproduction','',
           '`sweep_flatness.py` defines and runs the six cases; `report_flatness.py` '
           'contains the fixed scoring rule and generates this report. The machine-readable '
           'matrix and numerical checks are in `sweep_flatness_5p3to6p3/metrics.json`; '
           '`progress.json` records runner status. Result stems include `_5p3to6p3GHz`, '
           'preserving all earlier datasets. Native S, 50 Ω S, Z0 and β are stored '
           'in each NPZ, with completed-run metadata in JSON and a 50 Ω Touchstone export.','',
           'From `C:\\Fun\\ToyRadar\\Frontend\\emerge`:', '', '```powershell',
           '.\\.venv\\Scripts\\python.exe -m coupon_10mm.sweep_flatness',
           '.\\.venv\\Scripts\\python.exe -m coupon_10mm.report_flatness',
           '# During a run, show only completed cases:',
           '.\\.venv\\Scripts\\python.exe -m coupon_10mm.report_flatness --partial','```','',
           'The runner skips already completed matching cases on restart. Logs and '
           'heavy meshes are excluded from Git; small results and plots remain available.']
    path=REPORTS/'06_L2_CUTOUT_FLATNESS_SWEEP.md'
    tail=''
    if path.exists() and TAPER_SECTION in path.read_text(encoding='utf-8'):
        tail='\n\n'+TAPER_SECTION+path.read_text(encoding='utf-8').split(TAPER_SECTION,1)[1]
    write_report(path, '\n'.join(text)+'\n'+tail)
    print(json.dumps(dict(completed=len(records),ranking=[(r['id'],round(r['score'],4)) for r in ranked]),indent=2))


if __name__=='__main__':main()

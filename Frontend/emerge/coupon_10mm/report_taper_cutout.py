"""Append the under-taper L2 extension study to the flatness report."""
from .report_paths import REPORTS, write_report
import argparse
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon,Rectangle
from .compare import HERE,db
from .connector_model import variant_paths,FLATNESS_FREQUENCIES_GHZ
from .report_flatness import metrics,TAPER_SECTION
from .sweep_taper_cutout import OUT,CASES


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--partial',action='store_true')
    args=parser.parse_args();OUT.mkdir(exist_ok=True)
    reference=dict(id='F02',width_mm=2.8,length_mm=4.8)
    records=[];spectra=[];baseline=None
    for case in sorted([reference]+CASES,key=lambda c:c['length_mm']):
        _,base=variant_paths([case['width_mm'],case['length_mm']]);stem=base+'_5p3to6p3GHz'
        path=HERE/f'{stem}.json'
        if not path.exists() or not (HERE/f'{stem}.npz').exists():
            if args.partial:continue
            raise ValueError(f'Missing result: {case["id"]}')
        meta=json.loads(path.read_text(encoding='utf-8'))
        if meta['status']!='completed':
            if args.partial:continue
            raise ValueError(f'Incomplete result: {case["id"]}')
        data=np.load(HERE/f'{stem}.npz');f=data['f'].reshape(-1);s=data['Smat50']
        assert s.shape==(11,2,2) and np.all(np.isfinite(s))
        assert np.allclose(f,np.asarray(FLATNESS_FREQUENCIES_GHZ)*1e9,rtol=0,atol=1)
        if baseline is None:baseline=meta
        for key in ('source_board_sha256','connector_parameters_mm','pcb_layers','air_box_mm',
                    'port_x_mm','mesh_targets_mm','element_order','launch_transition'):
            assert meta[key]==baseline[key],f'Unexpected change: {key}'
        r=dict(case,**metrics(s),result_stem=stem,nodes=meta['nodes'],tetrahedra=meta['tetrahedra'],
               solve_minutes=meta['solve_seconds']/60,S21_5p8_dB=float(db(s[5,1,0])),S11_5p8_dB=float(db(s[5,0,0])),
               reflected_power_5p8_pct=float(100*abs(s[5,0,0])**2),
               transmitted_power_5p8_pct=float(100*abs(s[5,1,0])**2))
        records.append(r);spectra.append((r,f,s))
        lines=[f'! {case["id"]}: W=2.8, L={case["length_mm"]:g} mm L2 windows; original tapers; L3 intact',
               '! 11 direct frequencies 5.3-6.3 GHz; 50-ohm coax reference; connectors included','# Hz S RI R 50']
        for freq,m in zip(f,s):
            lines.append(f'{freq:.12g} '+' '.join(f'{v.real:.12g} {v.imag:.12g}' for v in (m[0,0],m[1,0],m[0,1],m[1,1])))
        (HERE/f'{stem}.s2p').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    ranked=sorted(records,key=lambda r:r['score'])
    colors=['#ff7f0e','#009e73','#0072b2','#9467bd','#d55e00']
    pcb=json.loads((HERE/'pcb_geometry.json').read_text(encoding='utf-8'))
    signal=next(region['outer'] for layer in pcb['layers'] if layer['name']=='F.Cu'
                for region in layer['copper'] if region['net']!='GND_1')
    fig,axes=plt.subplots(3,2,figsize=(10,9),sharex=True,sharey=True,constrained_layout=True)
    for ax in axes.flat[len(CASES)+1:]:ax.set_visible(False)
    for ax,case in zip(axes.flat,sorted([reference]+CASES,key=lambda c:c['length_mm'])):
        length=case['length_mm']
        ax.add_patch(Rectangle((.3,-1.7),7,3.4,facecolor='#cfdfeb',edgecolor='none'))
        ax.add_patch(Rectangle((.28,-1.4),length,2.8,facecolor='white',edgecolor='#009e73',lw=1.5))
        ax.add_patch(Polygon(signal,fill=False,edgecolor='#c87520',lw=1.3))
        ax.axvline(5.08,color='#555555',ls='--',lw=.8)
        ax.axvline(6.275,color='#555555',ls=':',lw=.8)
        ax.set(xlim=(0,7),ylim=(-1.7,1.7),title=f'{case["id"]}: L={length:g} mm, extension {length-4.8:g} mm')
        ax.set_aspect('equal');ax.grid(alpha=.15)
    for ax in axes[-1]:ax.set_xlabel('x from board edge (mm)')
    for ax in axes[:,0]:ax.set_ylabel('y (mm)')
    fig.suptitle('L2 opening extended beneath the unchanged left taper; width fixed at 2.8 mm\n'
                 'Blue: L2 | orange: top signal | dashed: pad end | dotted: taper end')
    fig.savefig(OUT/'extended_geometry.png',dpi=170,bbox_inches='tight');plt.close(fig)
    if spectra:
        fig,axes=plt.subplots(2,1,figsize=(10,8),sharex=True,constrained_layout=True)
        fig_r,ax_r=plt.subplots(figsize=(10,4),constrained_layout=True)
        for r,f,s in spectra:
            color=colors[0 if r['id']=='F02' else int(r['id'][1:])]
            label=f'{r["id"]}: L={r["length_mm"]:g} mm'
            for ax,i,j in ((axes[0],1,0),(axes[1],0,0)):
                ax.plot(f/1e9,db(s[:,i,j]),'o-',ms=4,lw=1.6,color=color,label=label)
            ax_r.plot(f/1e9,abs(s[:,0,0]),'o-',ms=4,lw=1.6,color=color,label=label)
        for ax in (*axes,ax_r):ax.set_xlim(5.3,6.3);ax.grid(alpha=.25);ax.legend(fontsize=9)
        axes[0].set_ylabel('S21 (dB)');axes[1].set(ylabel='S11 (dB)',xlabel='Frequency (GHz)')
        fig.suptitle('Extend the 2.8 mm-wide L2 opening under the original taper\n'
                     '11 directly solved points; L3, connectors and top copper unchanged')
        fig.savefig(OUT/'extended_responses.png',dpi=170,bbox_inches='tight');plt.close(fig)
        ax_r.set(ylabel='Reflection amplitude |S11|',xlabel='Frequency (GHz)',title='Reflection amplitude for length comparison')
        fig_r.savefig(OUT/'extended_reflection.png',dpi=170,bbox_inches='tight');plt.close(fig_r)
    all_records=json.loads((HERE/'sweep_flatness_5p3to6p3/metrics.json').read_text())['records']
    all_records += [r for r in records if r['id']!='F02']
    all_ranked=sorted(all_records,key=lambda r:r['score'])
    criteria=('worst_loss_dB','transmission_ripple_dB','worst_reflection','reflection_ripple')
    pareto_ids=[r['id'] for r in all_records if not any(
        all(other[k]<=r[k] for k in criteria) and any(other[k]<r[k] for k in criteria)
        for other in all_records if other is not r)]
    done=len(records)-1
    summary=dict(status='completed' if done==len(CASES) else 'partial',completed_new_geometries=done,
                 total_geometries=6+done,total_frequency_cases=11*(6+done),records=records,
                 ranking=[r['id'] for r in ranked],combined_ranking=[r['id'] for r in all_ranked],
                 pareto_ids=pareto_ids)
    summary['all_records']=all_records
    (OUT/'metrics.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    table=['| ID | Length, mm | Worst loss, dB ↓ | S21 span, dB ↓ | Worst S11, dB ↓ | S11 dB span | Amplitude span ↓ | J ↓ |',
           '|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in records:
        table.append(f'| {r["id"]} | {r["length_mm"]:g} | {r["worst_loss_dB"]:.3f} | '
                     f'{r["transmission_ripple_dB"]:.3f} | {r["worst_S11_dB"]:.2f} | {r["S11_dB_range"]:.2f} | '
                     f'{r["reflection_ripple"]:.4f} | {r["score"]:.3f} |')
    folder=OUT.name
    winner=all_ranked[0]
    interpretation=[]
    if done==len(CASES):
        new=next(r for r in records if r['id']=='T04')
        minima={key:min(records,key=lambda r:r[key])['id'] for key in criteria}
        interpretation=['### Interpretation','',
            f'**The added 5.0 mm case (T04)** gives {new["worst_loss_dB"]:.3f} dB '
            f'worst insertion loss, {new["transmission_ripple_dB"]:.3f} dB S21 span, '
            f'and {new["worst_S11_dB"]:.2f} dB worst S11. Its reflection-amplitude '
            f'span is {new["reflection_ripple"]:.4f}; its S11 span in dB is '
            f'{new["S11_dB_range"]:.2f} dB.','',
            f'Among these five lengths, the metric minima are: worst loss — '
            f'{minima["worst_loss_dB"]}; S21 variation — {minima["transmission_ripple_dB"]}; '
            f'worst reflection — {minima["worst_reflection"]}; reflection variation — '
            f'{minima["reflection_ripple"]}. These are separate objectives: flatter '
            'S11 can mean a flatter but higher reflected signal.','',
            f'The unchanged balanced score selects **{winner["id"]}, '
            f'{winner["width_mm"]:g} × {winner["length_mm"]:g} mm**, across all '
            f'{6+done} geometries. T02 (5.6 mm) remains the alternative for very '
            'flat S11 (0.51 dB span), accepting about 10.3 dB return loss and '
            '0.976 dB worst insertion loss. T03 (6.0 mm) is worse than T02 in '
            'all four criteria. Extending the opening as far as possible gives '
            'no benefit in this comparison.','']

    section=[TAPER_SECTION,'','## Phase 2: extend the opening beneath the taper','',
        f'**{done} of {len(CASES)} new geometries complete.** Together with phase 1: '
        f'**{6+done} unique geometries and {11*(6+done)} directly solved frequency cases** '
        'on the same 11-point grid. F02 is reused as the reference, not solved again.','',
        'Width stays **2.8 mm**. Lengths are **5.0, 5.2, 5.6 and 6.0 mm**, extending '
        '0.2, 0.4, 0.8 and 1.2 mm beyond each pad’s inner edge. Top copper, original '
        'tapers, connector geometry, L3 and bottom ground remain unchanged. '
        'The left windows still start at x=0.28 mm; only their inner ends move. '
        'The right windows are mirrored about x=10.08 mm.','',
        'The original taper ends at approximately x=6.275 mm on the left. The '
        '6.0 mm window ends at x=6.28 mm: it covers the full approximately 1.195 mm '
        'taper and extends about 5 µm into the uniform line. The 5.2 and 5.6 mm '
        'windows end at x=5.48 and 5.88 mm respectively. T04 (5.0 mm), added after '
        'the first three extensions, ends at x=5.28 mm: just 0.2 mm beneath the taper.','',
        f'![Opening extensions]({folder}/extended_geometry.png)','',
        'The physical tradeoff is different from widening only beneath the pad: '
        'this also removes the nearby return plane beneath part of the impedance '
        'transition. Both local capacitance and return-current inductance change. '
        'More removal is therefore not automatically better.','',
        *table,'',
        f'![Length response comparison]({folder}/extended_responses.png)','',
        f'![Reflection amplitude]({folder}/extended_reflection.png)','',
        f'The lowest score among all {6+done} completed geometries is **{winner["id"]}: '
        f'{winner["width_mm"]:g} × {winner["length_mm"]:g} mm**. '
        +('This is provisional while the extension study runs.' if done<len(CASES) else
          'The score and its four component metrics are unchanged from phase 1.'),'',
        f'Non-dominated cases across the combined study: **{", ".join(pareto_ids)}**. '
        'An extended opening may give flatter reflection but a worse reflection level; '
        'the full component metrics show that tradeoff separately from the score.','',
        *interpretation,
        '### At 5.8 GHz','',
        '| ID | S21, dB | S11, dB | Transmitted power, % | Reflected power, % |','|---|---:|---:|---:|---:|']
    for r in records:
        section.append(f'| {r["id"]} | {r["S21_5p8_dB"]:.3f} | {r["S11_5p8_dB"]:.2f} | '
                       f'{r["transmitted_power_5p8_pct"]:.2f} | {r["reflected_power_5p8_pct"]:.2f} |')
    section += ['', '### Mesh and checks','',
        '| ID | Tetrahedra | Solve, min | Max singular value | Reciprocity error |',
        '|---|---:|---:|---:|---:|']
    for r in records:
        section.append(f'| {r["id"]} | {r["tetrahedra"]:,} | {r["solve_minutes"]:.1f} | '
                       f'{r["max_singular_value"]:.6f} | {r["max_reciprocity_error"]:.2g} |')
    section += ['', 'Mesh size targets, first-order basis, material assumptions, air box '
        'and coax references are held fixed. New length geometries are remeshed. '
        'The occupancy checks now verify that L2 is absent inside the extended windows '
        'and present beyond their inner ends; L3 remains below the windows. '
        'Ground-pin support, via connections and separate continuous signal/ground '
        'networks are checked as before. These are nominal-material trials, not '
        'dielectric-tolerance or mesh-convergence simulations.','',
        '### Reproduce the extension study','',
        'From `C:\\Fun\\ToyRadar\\Frontend\\emerge`:', '', '```powershell',
        '.\\.venv\\Scripts\\python.exe -m coupon_10mm.sweep_taper_cutout',
        '.\\.venv\\Scripts\\python.exe -m coupon_10mm.report_taper_cutout','```','',
        'Individual cases use `--l2-opening 2.8 LENGTH --frequency-grid flatness --solve`. '
        'Raw S, 50 Ω S, Z0 and β are saved in the corresponding '
        '`result_coax_open_2.8xLENGTHmm_5p3to6p3GHz.npz`; matching JSON records the '
        'completed solve and `.s2p` is the 50 Ω export. '
        f'Progress, metrics and figures are under `{folder}/`.']
    if (REPORTS/'07_BROADBAND_CHECK.md').exists():
        section += ['', '### Broadband verification', '',
                    '[Selected 2.8 × 4.8 mm design: 0.5–6.5 GHz check](07_BROADBAND_CHECK.md) '
                    'compares the wider response with the saved intact-L2 and wide-cutout controls.']
    if (REPORTS/'08_MESH_REFINEMENT.md').exists():
        section += ['', '### Mesh refinement', '',
                    '[First-order mesh comparison for the selected geometry](08_MESH_REFINEMENT.md) '
                    'compares standard and refined targets over the same 11 frequencies.']
    path=REPORTS/'06_L2_CUTOUT_FLATNESS_SWEEP.md'
    original=path.read_text(encoding='utf-8').split(TAPER_SECTION)[0].rstrip()
    write_report(path, original+'\n\n'+'\n'.join(section)+'\n')
    print(json.dumps(dict(completed_new=done,overall_ranking=[r['id'] for r in all_ranked]),indent=2))


if __name__=='__main__':main()

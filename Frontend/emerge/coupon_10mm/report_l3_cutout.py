"""Report the matching L3-window experiment against the saved finer-mesh control."""
from .report_paths import REPORTS, write_report
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon
from .compare import HERE, db
from .report_flatness import metrics

CONTROL = 'result_coax_open_2.8x4.8mm_5p3to6p3GHz_mesh_finer'
TRIAL = 'result_coax_open_2.8x4.8mm_l3_open_5p3to6p3GHz_mesh_finer'
OUT = HERE/'l3_cutout'


def geometry_figure():
    """Dimensioned PCB sections and plan view from the saved geometry polygons."""
    pcb = json.loads((HERE/'pcb_geometry.json').read_text(encoding='utf-8'))
    signal = next(region['outer'] for layer in pcb['layers'] if layer['name']=='F.Cu'
                  for region in layer['copper'] if region['net']!='GND_1')
    fig = plt.figure(figsize=(12, 7), constrained_layout=True)
    grid = fig.add_gridspec(2, 2, height_ratios=(1.5, 1))
    for col, opened in enumerate((False, True)):
        ax = fig.add_subplot(grid[0, col])
        ax.add_patch(Rectangle((-3, -1.5512), 6, 1.5512, facecolor='#e2eee8', edgecolor='none'))
        ax.add_patch(Rectangle((-.6, 0), 1.2, .035, facecolor='#c87520'))
        ax.text(0, .15, 'Top signal pad, 1.2 mm', ha='center', color='#9c551a')
        for name, z, thickness, cut in (('L2', -.2104, .0152, True),
                                         ('L3', -1.2906, .0152, opened),
                                         ('Bottom', -1.5162, .035, False)):
            spans = ((-3, -1.4), (1.4, 3)) if cut else ((-3, 3),)
            for lo, hi in spans:
                ax.add_patch(Rectangle((lo, z-thickness), hi-lo, thickness, facecolor='#497b99'))
            if cut:ax.plot([-1.4, 1.4], [z, z], '--', lw=1.2, color='#b33c3c')
            ax.text(3.15, z, name, va='center', fontsize=10)
        ax.set(xlim=(-3.3, 4.7), ylim=(-1.75, .4), xlabel='y (mm)', ylabel='z (mm)',
               title='Trial: matching L2 + L3 windows' if opened else 'Control: L2 window, L3 intact')
        ax.set_xticks([-3, -1.4, 0, 1.4, 3]);ax.grid(alpha=.15)
    ax = fig.add_subplot(grid[1, :])
    ax.add_patch(Rectangle((0, -3.1), 20.16, 6.2, facecolor='#e2eee8', edgecolor='#888888'))
    for xa in (.28, 15.08):
        ax.add_patch(Rectangle((xa, -1.4), 4.8, 2.8, facecolor='#ffffff',
                               edgecolor='#b33c3c', linestyle='--', lw=1.5))
    ax.add_patch(Polygon(signal, fill=False, edgecolor='#c87520', lw=1.4))
    xy = np.asarray([via['xy_mm'] for via in pcb['vias']])
    ax.scatter(xy[:, 0], xy[:, 1], s=16, color='#497b99', label='Ground vias')
    ax.set(xlim=(-.2, 20.4), ylim=(-3.2, 3.2), xlabel='x (mm)', ylabel='y (mm)',
           title='Plan view: both 2.8 × 4.8 mm windows; top signal contour and ground vias')
    ax.set_aspect('equal');ax.grid(alpha=.15);ax.legend(loc='upper center', fontsize=9)
    fig.suptitle('Matching L3 relief beneath the existing L2 openings\n'
                 'PCB sections at x=2.68 mm; connector omitted; blue: ground copper; dashed red: removed copper')
    fig.savefig(OUT/'geometry.png', dpi=170);plt.close(fig)


def load(stem):
    meta = json.loads((HERE/f'{stem}.json').read_text(encoding='utf-8'))
    assert meta['status']=='completed'
    with np.load(HERE/f'{stem}.npz') as data:
        f, s = data['f'].reshape(-1).copy(), data['Smat50'].copy()
    assert s.shape==(11, 2, 2) and np.isfinite(s).all()
    return meta, f, s


def main():
    OUT.mkdir(exist_ok=True)
    control, f, a = load(CONTROL)
    trial, ff, b = load(TRIAL)
    assert np.allclose(f, ff, rtol=0, atol=1)
    for key in ('source_board_sha256', 'connector_parameters_mm', 'pcb_layers', 'air_box_mm',
                'port_x_mm', 'mesh_targets_mm', 'element_order', 'l2_opening_mm',
                'launch_transition', 'signal_outline_mm'):
        assert control[key]==trial[key], f'Unexpected change: {key}'
    assert control['assumptions'][1:]==trial['assumptions'][1:]
    assert control.get('l3_opening_mm') is None and trial['l3_opening_mm']==[2.8, 4.8]
    assert all(trial['opening_checks'].values())
    ma, mb = metrics(a), metrics(b)
    delta_t = db(b[:, 1, 0])-db(a[:, 1, 0])
    delta_r = abs(b[:, 0, 0])-abs(a[:, 0, 0])
    criteria = ('worst_loss_dB', 'transmission_ripple_dB', 'worst_reflection', 'reflection_ripple')
    if all(mb[k]<ma[k] for k in criteria):
        verdict = 'The L3 windows improve all four nominal comparison metrics in this trial.'
    elif all(ma[k]<mb[k] for k in criteria):
        verdict = 'Retaining L3 is better in all four nominal comparison metrics.'
    else:
        verdict = 'The L3 windows produce a tradeoff; the individual metrics must be compared.'
    score_winner = 'matching L2/L3 windows' if mb['score']<ma['score'] else 'L2 windows with L3 intact'
    summary = dict(status='completed', new_geometries=1, new_frequency_solves=11,
                   control_stem=CONTROL, trial_stem=TRIAL, control=ma, trial=mb,
                   max_S21_change_dB=float(abs(delta_t).max()),
                   max_reflection_amplitude_change=float(abs(delta_r).max()),
                   verdict=verdict, fixed_score_winner=score_winner)
    (OUT/'metrics.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
    geometry_figure()
    fig, axes = plt.subplots(3, 1, figsize=(10, 10), sharex=True, constrained_layout=True)
    for s, label, color, marker in ((a, 'L3 intact', '#0072b2', 'o'),
                                     (b, 'Matching L3 windows', '#d55e00', 's')):
        for ax, y in ((axes[0], db(s[:, 1, 0])), (axes[1], db(s[:, 0, 0])), (axes[2], abs(s[:, 0, 0]))):
            ax.plot(f/1e9, y, marker+'-', ms=4, color=color, label=label)
    for ax in axes:ax.grid(alpha=.25);ax.legend();ax.set_xlim(5.3, 6.3)
    axes[0].set_ylabel('S21 (dB)');axes[1].set_ylabel('S11 (dB)')
    axes[2].set(ylabel='Reflection amplitude |S11|', xlabel='Frequency (GHz)')
    fig.suptitle('L3 relief experiment: 2.8 × 4.8 mm windows on both inner ground planes\n'
                 'Original tapers; Bottom intact; same finer mesh targets; 11 directly solved points')
    fig.savefig(OUT/'responses.png', dpi=170);plt.close(fig)
    lines = ['! Matching L2/L3 2.8 x 4.8 mm cutouts; Bottom intact; finer first-order mesh',
             '! Coax reference planes; connectors included; 11 direct FEM points', '# Hz S RI R 50']
    for freq, smat in zip(f, b):
        lines.append(f'{freq:.12g} '+' '.join(f'{z.real:.12g} {z.imag:.12g}' for z in
                                            (smat[0,0], smat[1,0], smat[0,1], smat[1,1])))
    (HERE/f'{TRIAL}.s2p').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    text = ['# L3 cutout experiment', '', '**'+verdict+'**', '',
            '**One new geometry, 11 new frequency solves over 5.3–6.3 GHz.** '
            'The control is the saved finest-mesh result from '
            '[the refinement study](08_MESH_REFINEMENT.md); it was not solved again.', '',
            '## Geometry: only L3 changes', '',
            'Remove L3 copper directly beneath the existing **2.8 × 4.8 mm L2 windows**: '
            'left x=0.28…5.08 mm, right x=15.08…19.88 mm, y=±1.4 mm. '
            'The rest of L3, Bottom copper, dielectric, original top pads/tapers, '
            'connector contacts and ground vias remain. These are copper clearances, '
            'not board slots. The entire L3 layer is not removed.', '',
            '![L3 experiment geometry](l3_cutout/geometry.png)', '',
            'L3 copper spans approximately z=−1.2906…−1.3058 mm. Bottom spans '
            'z=−1.5162…−1.5512 mm and becomes the nearest continuous ground plane '
            'directly under the two aligned windows. Return currents can also '
            'flow around the windows through the remaining L2/L3 copper.', '',
            'Removing more ground can reduce local capacitance and change return-path '
            'inductance. The net effect is evaluated by the complete connector-inclusive '
            'S-matrix; it is not assumed to improve the match.', '',
            '## Response', '', '![L3 response comparison](l3_cutout/responses.png)', '',
            '| Metric, 5.3–6.3 GHz | L3 intact | Matching L3 windows |', '|---|---:|---:|']
    for key, label in (('worst_loss_dB', 'Worst insertion loss, dB'),
                       ('transmission_ripple_dB', 'S21 span, dB'),
                       ('worst_S11_dB', 'Worst S11, dB'),
                       ('reflection_ripple', 'Reflection amplitude span'), ('score', 'Fixed score J')):
        text.append(f'| {label} | {ma[key]:.4f} | {mb[key]:.4f} |')
    text += ['', f'The unchanged score from the geometry search favors **{score_winner}**. '
             f'Maximum pointwise differences are **{abs(delta_t).max():.4f} dB in S21** '
             f'and **{abs(delta_r).max():.4f} in |S11|**.', '',
             'For scale, the last mesh-refinement step on the intact-L3 control changed '
             'S21 by at most 0.0157 dB and |S11| by 0.00155. Those values are a '
             'reference for numerical sensitivity, not error bounds for this new geometry.', '',
             *(['**Keep L3 intact for the current design.** The aligned L3 windows '
                'worsen worst-case loss, transmission variation, worst reflection '
                'and reflection-amplitude variation. The curves approach each other '
                'near the upper band edge, but the low-frequency end deteriorates. '
                'This trial gives no reason to add these L3 windows. It does not '
                'rule out every possible L3 clearance shape; that would require '
                'another geometry search.',''] if all(ma[k]<mb[k] for k in criteria) else []),
             '### Direct frequency results', '',
             '| GHz | Intact S21, dB | L3-window S21, dB | Intact S11, dB | L3-window S11, dB |',
             '|---:|---:|---:|---:|---:|']
    for i, freq in enumerate(f):
        text.append(f'| {freq/1e9:g} | {db(a[i,1,0]):.3f} | {db(b[i,1,0]):.3f} | '
                    f'{db(a[i,0,0]):.2f} | {db(b[i,0,0]):.2f} |')
    text += ['', '## Mesh and checks', '',
             'Both cases use first-order FEM and the same finer targets: substrate '
             '0.600 mm, signal surface 0.120 mm, signal edge 0.035 mm, connector '
             'surface 0.300 mm, coax port 0.150 mm. The changed geometry is remeshed.', '',
             '| Run | Tetrahedra | Nodes | Solve time, min | Max singular value | Reciprocity error |',
             '|---|---:|---:|---:|---:|---:|']
    for name, meta, m in (('L3 intact', control, ma), ('Matching L3 windows', trial, mb)):
        text.append(f'| {name} | {meta["tetrahedra"]:,} | {meta["nodes"]:,} | '
                    f'{meta["solve_seconds"]/60:.1f} | {m["max_singular_value"]:.6f} | {m["max_reciprocity_error"]:.3g} |')
    text += ['', 'CAD checks verify empty L2/L3 window centres and inner ends, copper '
             'beside and past the windows, L3 beneath the ground pins, Bottom beneath '
             'the windows, separate continuous signal/ground networks and complete '
             'coax annuli. Saved metadata confirm unchanged geometry elsewhere, '
             'materials, air box, frequency grid and mesh targets. S is referenced '
             'to 50 Ω at the coax planes and includes both connectors.', '',
             'This is one nominal-material L3 geometry, not an L3 optimization or '
             'a mesh-refinement study of this new geometry. No Bottom openings, '
             'dielectric changes or additional frequency points were simulated.', '',
             '## Reproduce', '', 'From `C:\\Fun\\ToyRadar\\Frontend\\emerge`:', '', '```powershell',
             '.\\.venv\\Scripts\\python.exe -m coupon_10mm.connector_model --l2-opening 2.8 4.8 --l3-opening --frequency-grid flatness --mesh-profile finer --solve',
             '.\\.venv\\Scripts\\python.exe -m coupon_10mm.report_l3_cutout', '```', '',
             'For interactive geometry, replace `--solve` with `--view`; for the saved '
             'mesh, replace it with `--reuse-mesh --view-mesh`. '
             f'Results use `{TRIAL}.npz`, matching JSON and 50 Ω `.s2p`; '
             'the `_l3_open` name keeps them separate from the intact-L3 reference. '
             '[Report index](README.md).']
    write_report(REPORTS/'09_L3_CUTOUT_RESULTS.md', '\n'.join(text)+'\n')
    print(json.dumps(summary, indent=2))


if __name__=='__main__':main()

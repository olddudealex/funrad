"""Compare the selected cutout's broadband sweep with saved connector controls."""
from .report_paths import REPORTS, write_report
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .compare import HERE, db
from .report_flatness import metrics

STEM = 'result_coax_open_2.8x4.8mm_0p5to6p5GHz'
OUT = HERE / 'broadband_check'


def load(stem):
    meta = json.loads((HERE / f'{stem}.json').read_text(encoding='utf-8'))
    assert meta['status'] == 'completed'
    with np.load(HERE / f'{stem}.npz') as data:
        f, s = data['f'].reshape(-1).copy(), data['Smat50'].copy()
    assert s.shape == (len(f), 2, 2) and np.isfinite(s).all()
    return meta, f, s


def main():
    OUT.mkdir(exist_ok=True)
    meta, f, s = load(STEM)
    cases = [('Selected: 2.8 × 4.8 mm', STEM, '#009e73'),
             ('Earlier: 4.2 × 4.8 mm', 'result_coax_open_4.2x4.8mm', '#0072b2'),
             ('Original: L2 intact', 'result_coax_intact', '#777777')]
    datasets = []
    for label, stem, color in cases:
        other, freq, smat = load(stem)
        for key in ('source_board_sha256', 'connector_parameters_mm', 'pcb_layers',
                    'air_box_mm', 'port_x_mm', 'mesh_targets_mm', 'element_order'):
            assert other[key] == meta[key], f'Control differs: {key}'
        # Early connector reports predate the step option and always used the original taper.
        assert other.get('launch_transition', 'taper') == meta['launch_transition']
        datasets.append((label, freq, smat, color))
    fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True, constrained_layout=True)
    for label, freq, smat, color in datasets:
        for ax, i, j in ((axes[0], 1, 0), (axes[1], 0, 0)):
            ax.plot(freq / 1e9, db(smat[:, i, j]), 'o-', ms=3, lw=1.6,
                    color=color, label=label)
    for ax in axes:
        ax.axvspan(5.3, 6.3, color='#f0bb4b', alpha=.15)
        ax.grid(alpha=.25)
        ax.legend(fontsize=9)
        ax.set_xlim(.5, 6.5)
    axes[0].set_ylabel('S21 (dB)')
    axes[1].set(ylabel='S11 (dB)', xlabel='Frequency (GHz)')
    fig.suptitle('Broadband check of the selected L2 cutout\n'
                 'Dots: direct FEM points; controls stop at 6 GHz; shaded: optimization band')
    fig.savefig(OUT / 'responses.png', dpi=170)
    plt.close(fig)
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True, constrained_layout=True)
    for label, freq, smat, color in datasets[:2]:
        for ax, i, j in ((axes[0], 1, 0), (axes[1], 0, 0)):
            ax.plot(freq/1e9, db(smat[:, i, j]), 'o-', ms=3, color=color, label=label)
    for ax in axes:
        ax.grid(alpha=.25)
        ax.axvspan(5.3, 6.3, color='#f0bb4b', alpha=.15)
        ax.set_xlim(.5, 6.5)
        ax.legend(fontsize=9)
    axes[0].set_ylabel('S21 (dB)')
    axes[1].set(ylabel='S11 (dB)', xlabel='Frequency (GHz)')
    fig.suptitle('Cutout comparison at a readable transmission scale\n'
                 'Same data as the overview; earlier wide cutout stops at 6 GHz')
    fig.savefig(OUT / 'cutout_comparison.png', dpi=170)
    plt.close(fig)

    old, old_f, old_s = load('result_coax_open_2.8x4.8mm_5p3to6p3GHz')
    assert meta['nodes'] == old['nodes'] and meta['tetrahedra'] == old['tetrahedra']
    indices = [int(np.flatnonzero(np.isclose(f, v, rtol=0, atol=1))[0]) for v in old_f]
    repeat_error = float(np.max(np.abs(s[indices] - old_s)))
    band = (f >= 5.3e9) & (f <= 6.3e9)
    all_metrics, band_metrics = metrics(s), metrics(s[band])
    worst_loss_i = int(np.argmin(db(s[:, 1, 0])))
    worst_s11_i = int(np.argmax(db(s[:, 0, 0])))
    summary = dict(status='completed', result_stem=STEM, points=len(f),
                   frequencies_GHz=(f / 1e9).tolist(), broadband=all_metrics,
                   optimization_band=band_metrics, repeated_point_max_complex_error=repeat_error,
                   worst_loss_frequency_GHz=float(f[worst_loss_i] / 1e9),
                   worst_S11_frequency_GHz=float(f[worst_s11_i] / 1e9))
    (OUT / 'metrics.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    touchstone = ['! 2.8 x 4.8 mm L2 cutouts; original tapers; L3 intact',
                 '! Coax planes; connectors included; direct FEM points', '# Hz S RI R 50']
    for freq, smat in zip(f, s):
        touchstone.append(f'{freq:.12g} ' + ' '.join(f'{z.real:.12g} {z.imag:.12g}' for z in
                                                  (smat[0, 0], smat[1, 0], smat[0, 1], smat[1, 1])))
    (HERE / f'{STEM}.s2p').write_text('\n'.join(touchstone) + '\n', encoding='utf-8')
    text = ['# Broadband verification: 2.8 × 4.8 mm L2 cutout', '',
            f'**Completed: one geometry, {len(f)} directly solved frequencies over 0.5–6.5 GHz.** '
            'The original tapers, L3 and simplified BWSMA connectors are retained. '
            'The saved mesh of the selected F02 geometry is reused.', '',
            '## Response', '', '![Broadband response](broadband_check/responses.png)', '',
            '| Range | Worst insertion loss, dB | S21 span, dB | Worst S11, dB |',
            '|---|---:|---:|---:|']
    for label, m in (('0.5–6.5 GHz', all_metrics), ('5.3–6.3 GHz', band_metrics)):
        text.append(f'| {label} | {m["worst_loss_dB"]:.3f} | '
                    f'{m["transmission_ripple_dB"]:.3f} | {m["worst_S11_dB"]:.2f} |')
    text += ['', f'The worst sampled broadband insertion loss occurs at '
             f'**{f[worst_loss_i]/1e9:g} GHz**; the worst sampled S11 at '
             f'**{f[worst_s11_i]/1e9:g} GHz**.', '',
             '**Retain the 2.8 × 4.8 mm design for verification.** No deep transmission '
             'notch appears at the sampled frequencies. There is a broad insertion-loss '
             'depression around 4.5 GHz, but it remains below 1 dB at the sampled points. '
             'The original launch’s severe upper-band roll-off is absent. The 5.3–6.3 GHz '
             'response repeats the earlier optimization result; the next check is mesh '
             'refinement of this fixed geometry.', '',
             '![Cutouts at a closer scale](broadband_check/cutout_comparison.png)', '',
             '### Selected frequencies', '',
             '| Frequency, GHz | Selected S21, dB | Selected S11, dB | Wide cutout S21, dB | Intact L2 S21, dB |',
             '|---|---:|---:|---:|---:|']
    for ghz in (1, 2.6, 4, 5, 5.3, 5.8, 6, 6.3, 6.5):
        i = int(np.flatnonzero(np.isclose(f, ghz*1e9, rtol=0, atol=1))[0])
        controls = []
        for _, cf, cs, _ in datasets[1:]:
            found = np.flatnonzero(np.isclose(cf, ghz*1e9, rtol=0, atol=1))
            controls.append(f'{db(cs[found[0],1,0]):.3f}' if len(found) else '—')
        text.append(f'| {ghz:g} | {db(s[i,1,0]):.3f} | {db(s[i,0,0]):.2f} | '
                    + ' | '.join(controls) + ' |')
    text += ['', '## Sampling and numerical checks', '',
             'Grid, GHz: ' + ', '.join(f'{v/1e9:g}' for v in f) + '.', '',
             'This combines the earlier broadband and optimization grids, adding 4.5 and '
             '6.5 GHz. Lines only connect directly solved points; no extra resonances '
             'are inferred between samples. The two saved controls cover 0.5–6 GHz '
             'and are plotted only over that range.', '',
             f'The 11 repeated optimization-band points agree with the preceding F02 '
             f'sweep to **{repeat_error:.3g}** maximum absolute complex S difference. '
             f'The reused mesh has **{meta["tetrahedra"]:,} tetrahedra** and '
             f'**{meta["nodes"]:,} nodes**; first-order basis, εr=4.5, tanδ=0.02. '
             f'Solve time: {meta["solve_seconds"]/60:.1f} min.', '',
             f'Maximum singular value of S: {all_metrics["max_singular_value"]:.6f}; '
             f'maximum reciprocity error: {all_metrics["max_reciprocity_error"]:.3g}. '
             'All results use 50 Ω coax reference planes and include both connectors.', '',
             'This checks the sampled broadband response with the existing mesh. '
             'Mesh refinement and dielectric sensitivity remain separate verification steps.', '',
             '## Reproduce', '', 'From `C:\\Fun\\ToyRadar\\Frontend\\emerge`:', '', '```powershell',
             '.\\.venv\\Scripts\\python.exe -m coupon_10mm.connector_model --l2-opening 2.8 4.8 --frequency-grid broadband-check --reuse-mesh --solve',
             '.\\.venv\\Scripts\\python.exe -m coupon_10mm.report_broadband_check', '```', '',
             f'Results: `{STEM}.npz`, matching JSON and 50 Ω `.s2p`. '
             'The `_0p5to6p5GHz` suffix preserves the previous datasets. '
             '[Return to the geometry sweep](06_L2_CUTOUT_FLATNESS_SWEEP.md).']
    write_report(REPORTS/'07_BROADBAND_CHECK.md', '\n'.join(text) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()

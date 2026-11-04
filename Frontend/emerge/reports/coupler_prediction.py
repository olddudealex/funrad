"""Plot the final coupler's saved S11/S21/S31/S41; no EM solve.

From Frontend/emerge: python -m reports.coupler_prediction
"""
from pathlib import Path
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parents[1]
NARROW = HERE/'results_redesign/final51_copper9_e61849bc8c'
def wide_run():
    completed = [p for p in (HERE/'results_redesign').glob('final51_copper_5p3to6p3GHz_*')
                 if (p/'raw.npz').exists()]
    if len(completed) != 1:
        raise RuntimeError('Expected one completed 1 GHz sweep; run its configuration first.')
    return completed[0]
OUT = HERE.parents[1]/'Notes/FunRad/images/coupler/final_prediction_sparams_1GHz.png'


def main():
    RUN = wide_run()
    config = json.loads((RUN/'config.json').read_text(encoding='utf-8'))
    assert config['name'] == 'final51_copper_5p3to6p3GHz' and config['copper_loss']
    old_config = json.loads((NARROW/'config.json').read_text(encoding='utf-8'))
    for key in set(config) | set(old_config):
        if key not in ('name', 'fmin', 'fmax', 'nf', 'frequency_group_size',
                       'pardiso_ooc_mb', 'pardiso_numeric_phase'):
            assert config.get(key) == old_config.get(key), key
    with np.load(RUN/'raw.npz') as raw:
        f = raw['f'].reshape(-1)/1e9
        s = raw['Smat50'].copy()
    assert s.shape == (11, 4, 4) and np.isfinite(s).all()
    assert np.allclose(f, np.linspace(5.3, 6.3, 11), atol=1e-10, rtol=0)
    values = 20*np.log10(np.maximum(abs(s[:, :, 0]), 1e-15))
    saved = json.loads((RUN/'metrics.json').read_text(encoding='utf-8'))
    for i in range(4):
        assert np.allclose(values[:, i], saved[f'S{i+1}1'], atol=1e-8)
    with np.load(NARROW/'raw.npz') as old:
        old_f = old['f'].reshape(-1)/1e9
        old_s = old['Smat50'].copy()
    old_values = 20*np.log10(np.maximum(abs(old_s[:, :, 0]), 1e-15))
    layout = json.loads((RUN/'layout.json').read_text(encoding='utf-8'))['polygons']
    old_layout = json.loads((NARROW/'layout.json').read_text(encoding='utf-8'))['polygons']
    assert len(layout) == len(old_layout)
    assert all(np.allclose(a, b, rtol=0, atol=1e-10) for a, b in zip(layout, old_layout))
    new_indices = [int(np.argmin(abs(f-key))) for key in [5.7, 5.8, 5.9]]
    old_indices = [int(np.argmin(abs(old_f-key))) for key in [5.7, 5.8, 5.9]]
    comparison = dict(frequencies_GHz=f.tolist(),
                      S_dB={f'S{i+1}1': values[:, i].tolist() for i in range(4)},
                      directivity_dB=(values[:, 2]-values[:, 3]).tolist(),
                      max_shared_point_delta_dB={f'S{i+1}1': float(np.max(abs(
                          values[new_indices, i]-old_values[old_indices, i]))) for i in range(4)},
                      max_shared_complex_delta=float(np.max(abs(s[new_indices]-old_s[old_indices]))),
                      max_shared_directivity_delta_dB=float(np.max(abs(
                          (values[new_indices, 2]-values[new_indices, 3])-
                          (old_values[old_indices, 2]-old_values[old_indices, 3])))),
                      max_singular_value=float(np.linalg.svd(s, compute_uv=False).max()),
                      max_reciprocity_residual=float(np.max(abs(s-s.swapaxes(1, 2)))),
                      old_mesh=json.loads((NARROW/'mesh.json').read_text(encoding='utf-8')),
                      wide_mesh=json.loads((RUN/'mesh.json').read_text(encoding='utf-8')),
                      raw_source=RUN.relative_to(HERE).as_posix()+'/raw.npz')
    fig, axes = plt.subplots(2, 2, figsize=(11, 7), constrained_layout=True)
    panels = [(0, 'S11 — input reflection',
               (min(-40, np.floor(values[:, 0].min()/5)*5-5),
                max(-20, np.ceil(values[:, 0].max()/5)*5+5)), '#0072b2'),
              (1, 'S21 — through transmission',
               (min(-1, np.floor(values[:, 1].min()*10)/10-.1), 0), '#009e73'),
              (2, 'S31 — coupled output',
               (min(-17, np.floor(values[:, 2].min()*2)/2-.5),
                max(-13.5, np.ceil(values[:, 2].max()*2)/2+.5)), '#8822aa'),
              (3, 'S41 — isolated output',
               (np.floor(values[:, 3].min()/5)*5-5, np.ceil(values[:, 3].max()/5)*5+5), '#d55e00')]
    for ax, (column, title, limits, color) in zip(axes.flat, panels):
        ax.axvspan(5.7, 5.9, color='#dddddd', alpha=.25)
        if column == 2:
            ax.fill_between([5.7, 5.9], -15.3, -14.7, color='#bde3c7', alpha=.6,
                            label='Target in 5.7–5.9 GHz: −15 ± 0.3 dB')
        ax.plot(f, values[:, column], 'o-', color=color, lw=1.8, ms=5,
                label='New 1 GHz sweep: direct EM samples')
        ax.plot(old_f, old_values[:, column], '--', color='#777777', lw=1,
                label='Earlier R058: 5.7–5.9 GHz')
        ax.axvline(5.8, color='#aaaaaa', ls=':', lw=1)
        ax.scatter([5.8], [values[5, column]], color=color, marker='*', s=140, zorder=4)
        ax.text(.97, .95, f'5.8 GHz: {values[5, column]:.3f} dB',
                transform=ax.transAxes, va='top', ha='right', fontsize=10,
                bbox=dict(facecolor='white', edgecolor='none', alpha=.85))
        ax.set(title=title, xlabel='Frequency (GHz)', ylabel=f'S{column+1}1 (dB)',
               xlim=(5.3, 6.3), ylim=limits)
        ax.set_xticks(f)
        ax.tick_params(axis='x', labelsize=9)
        ax.grid(alpha=.25)
        if column == 2:
            ax.legend(loc='lower left', fontsize=8)
    fig.suptitle('Predicted final coupler response — 5.3–6.3 GHz, finite copper and dielectric loss\n'
                 '50-ohm references; dots: 11 solved frequencies; shaded: original 5.7–5.9 GHz band')
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=180)
    plt.close(fig)
    OUT.with_suffix('.json').write_text(json.dumps(comparison, indent=2)+'\n', encoding='utf-8')
    print('Wrote 1 GHz coupler predictions and comparison with R058.')


if __name__ == '__main__':
    main()

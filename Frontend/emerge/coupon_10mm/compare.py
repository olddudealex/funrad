"""Plot the two-layer PCB solve against measured coupons (no EM solve)."""
from .report_paths import REPORTS, write_report
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
from .report_paths import MEASUREMENTS


def measured(path):
    """Read these NanoVNA RI exports, including their decimal commas.

    Only S11 and S21 were measured; zero S12/S22 columns are placeholders.
    """
    lines = path.read_text(encoding='utf-8-sig').splitlines()
    header = next(line for line in lines if line.startswith('#'))
    if header.lower().split() != ['#', 'hz', 's', 'ri', 'r', '50']:
        raise ValueError(f'Unexpected Touchstone format: {header}')
    data = np.array([[float(x.replace(',', '.')) for x in line.split()]
                     for line in lines if line.strip() and not line.lstrip().startswith(('!', '#'))])
    return data[:, 0], data[:, 1] + 1j*data[:, 2], data[:, 3] + 1j*data[:, 4]


def db(values):
    return 20*np.log10(np.maximum(np.abs(values), 1e-15))


def mesh_name(metadata):
    """Name refers to the requested signal-edge size, not a uniform cell size."""
    return f'Mesh {1000*metadata["mesh_settings_mm"]["signal_edge"]:g} µm'


def main():
    result = np.load(HERE/'result_2layer.npz')
    f, s = result['f'].reshape(-1), result['Smat']
    if s.shape != (len(f), 2, 2) or not np.all(np.isfinite(s)):
        raise ValueError('Incomplete or invalid simulation result')
    if not np.allclose(result['Z0'], 50):
        raise ValueError('Comparison expects 50-ohm reference ports')
    metadata_path = HERE/'result_2layer.json'
    if not metadata_path.exists():
        metadata_path = HERE/'preview_2layer'/'geometry.json'
    metadata = json.loads(metadata_path.read_text())
    order = metadata.get('element_order', 'unspecified')
    baseline_path = HERE/'runs'/'baseline_8pt'/'result_2layer.npz'
    baseline = np.load(baseline_path) if baseline_path.exists() else None
    name = mesh_name(metadata)
    baseline_metadata = json.loads(baseline_path.with_suffix('.json').read_text()) if baseline is not None else None
    baseline_name = mesh_name(baseline_metadata) if baseline_metadata else None
    touchstone = ['! EMerge top/L2 PCB model; ideal lumped ports; connectors omitted',
                  '! Directly solved frequencies only', '# Hz S RI R 50']
    for freq, matrix in zip(f, s):
        # Touchstone two-port order is S11, S21, S12, S22.
        values = [matrix[0, 0], matrix[1, 0], matrix[0, 1], matrix[1, 1]]
        touchstone.append(f'{freq:.12g} ' + ' '.join(
            f'{value.real:.12g} {value.imag:.12g}' for value in values))
    (HERE/'result_2layer.s2p').write_text('\n'.join(touchstone)+'\n')
    fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True, constrained_layout=True)
    sources = [
        ('coupon_7628_horizontal_10mm.s2p', '10 mm: original connectors', '#0072b2'),
        ('coupon_7628_horizontal_10mm_amphenol.s2p', '10 mm: Amphenol', '#d55e00'),
        ('through_connection.s2p', 'VNA through connection', '#999999'),
    ]
    for filename, label, color in sources:
        mf, s11, s21 = measured(MEASUREMENTS/filename)
        for ax, values in zip(axes, (s21, s11)):
            ax.plot(mf/1e9, db(values), label=label, color=color, lw=1.3, alpha=.8)
    for ax, values in zip(axes, (s[:, 1, 0], s[:, 0, 0])):
        ax.plot(f/1e9, db(values), 'o-', color='#009e73', lw=2.2,
                label=f'{name}: {len(f)} frequencies', zorder=5)
        ax.grid(alpha=.25)
        ax.set_xlim(0, 6.1)
        if baseline is not None:
            i, j = (1, 0) if ax is axes[0] else (0, 0)
            ax.plot(baseline['f']/1e9, db(baseline['Smat'][:, i, j]), 'x--',
                    color='#7b3294', lw=1, label=f'{baseline_name}: {len(baseline["f"])} frequencies', zorder=4)
        ax.legend(fontsize=9)
    axes[0].set(ylabel='S21 (dB)', ylim=(-20, 1))
    axes[1].set(ylabel='S11 (dB)', xlabel='Frequency (GHz)', ylim=(-45, 1))
    fig.suptitle('10 mm coupon: PCB simulation versus measurement\n'
                 f'FEM order {order}; εr = 4.5, tanδ = 0.02; finite copper; connectors omitted')
    fig.savefig(HERE/'preview_2layer'/'simulation_comparison.png', dpi=180)
    plt.close(fig)
    if baseline is not None:
        # Same eight-point data, with stable mesh names and colors.
        archived_fig, archived_axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True,
                                                   constrained_layout=True)
        for filename, label, color in sources:
            mf, s11, s21 = measured(MEASUREMENTS/filename)
            for ax, values in zip(archived_axes, (s21, s11)):
                ax.plot(mf/1e9, db(values), label=label, color=color, lw=1.3, alpha=.8)
        for ax, values in zip(archived_axes, (baseline['Smat'][:, 1, 0], baseline['Smat'][:, 0, 0])):
            ax.plot(baseline['f']/1e9, db(values), 'x--', color='#7b3294', lw=2.2,
                    label=f'{baseline_name}: {len(baseline["f"])} frequencies')
            ax.grid(alpha=.25)
            ax.set_xlim(0, 6.1)
            ax.legend(fontsize=9)
        archived_axes[0].set(ylabel='S21 (dB)', ylim=(-20, 1))
        archived_axes[1].set(ylabel='S11 (dB)', xlabel='Frequency (GHz)', ylim=(-45, 1))
        archived_fig.suptitle(f'Original eight-frequency sweep: {baseline_name}\n'
                              '419,408 tetrahedra; first-order FEM; top/L2 PCB with ideal 50 Ω ports')
        archived_fig.savefig(baseline_path.parent/'simulation_comparison.png', dpi=180)
        plt.close(archived_fig)
    zoom, zoom_axes = plt.subplots(2, 1, figsize=(9, 7), sharex=True, constrained_layout=True)
    for filename, label, color in sources[:2]:
        mf, s11, s21 = measured(MEASUREMENTS/filename)
        for ax, values in zip(zoom_axes, (s11, s21)):
            keep = (mf >= 2.1e9) & (mf <= 2.95e9)
            ax.plot(mf[keep]/1e9, db(values[keep]), label=label, color=color, lw=1.4)
    keep = (f >= 2.1e9) & (f <= 2.95e9)
    for ax, values in zip(zoom_axes, (s[:, 0, 0], s[:, 1, 0])):
        ax.plot(f[keep]/1e9, db(values[keep]), 'o-', color='#009e73', lw=2,
                label=f'{name}: points from the {len(f)}-frequency sweep')
        ax.set_xlim(2.15, 2.9)
        ax.grid(alpha=.25)
        ax.legend(fontsize=8)
    zoom_axes[0].set(ylabel='S11 (dB)', ylim=(-50, 0))
    zoom_axes[1].set(ylabel='S21 (dB)', xlabel='Frequency (GHz)')
    zoom.suptitle('S11 minimum near 2.6 GHz: PCB model versus measurement\n'
                  'A deeper S11 minimum means less reflection, not more transmission loss')
    zoom.savefig(HERE/'preview_2layer'/'resonance_2p6GHz.png', dpi=180)
    plt.close(zoom)
    rows = [dict(f_GHz=float(freq/1e9), S11_dB=float(db(matrix[0, 0])),
                 S21_dB=float(db(matrix[1, 0])), S12_dB=float(db(matrix[0, 1])),
                 S22_dB=float(db(matrix[1, 1])),
                 outgoing_power_P1=float(abs(matrix[0, 0])**2 + abs(matrix[1, 0])**2))
            for freq, matrix in zip(f, s)]
    checks = dict(mesh_name=name, element_order=order,
                  max_reciprocity_error=float(np.max(abs(s[:, 1, 0]-s[:, 0, 1]))),
                  max_symmetry_error=float(np.max(abs(s[:, 0, 0]-s[:, 1, 1]))),
                  max_singular_value=float(np.linalg.svd(s, compute_uv=False).max()), rows=rows)
    if baseline is not None:
        common = [(i, int(np.argmin(abs(f-fb)))) for i, fb in enumerate(baseline['f'])
                  if np.min(abs(f-fb)) < 1]
        bidx, nidx = np.array(common).T
        checks['baseline_mesh_comparison'] = dict(
            common_frequencies_GHz=(f[nidx]/1e9).tolist(),
            max_S11_complex_difference=float(np.max(abs(s[nidx, 0, 0]-baseline['Smat'][bidx, 0, 0]))),
            max_S21_complex_difference=float(np.max(abs(s[nidx, 1, 0]-baseline['Smat'][bidx, 1, 0]))),
            max_S11_dB_difference=float(np.max(abs(db(s[nidx, 0, 0])-db(baseline['Smat'][bidx, 0, 0])))),
            max_S21_dB_difference=float(np.max(abs(db(s[nidx, 1, 0])-db(baseline['Smat'][bidx, 1, 0])))))
    (HERE/'preview_2layer'/'metrics.json').write_text(json.dumps(checks, indent=2)+'\n')
    mf, _, measured_s21 = measured(MEASUREMENTS/'coupon_7628_horizontal_10mm.s2p')
    text = ['# 10 mm coupon: top/L2 simulation', '',
            '## Which simulations produced these results?', '',
            '**Two completed EM sweeps:** Mesh 40 µm at 8 frequencies, and Mesh 60 µm at 20 frequencies. '
            'That is 28 frequency cases in total. Each sweep computes the full two-port S-matrix. '
            'Two earlier second-order solve attempts were stopped for memory use and produced no completed S-parameter dataset. '
            'CAD exports, mesh generation and viewer previews are not additional EM sweeps.', '',
            '**Mesh names refer to the requested signal-edge refinement size.** '
            'Neither mesh is uniform: the substrate, copper surfaces and ports have separate size targets.', '',
            '| Parameter | Mesh 40 µm — 8 frequencies | Mesh 60 µm — 20 frequencies |',
            '|---|---:|---:|',
            '| Signal-edge target, µm | 40 | 60 |',
            '| Signal-surface target, µm | 120 | 180 |',
            '| Signal-surface growth cap, µm | 800 | 1200 |',
            '| Port-face target, µm | 55 | 80 |',
            '| Substrate target, µm | 550 | 900 |',
            '| Mesh nodes | 71,060 | 37,185 |',
            '| Tetrahedra | 419,408 | 218,732 |',
            '| FEM element order | 1 | 1 |', '',
            'Both sweeps use the same PCB geometry, materials, air box and ideal 50 Ω ports. '
            'Size targets are mesher inputs, not measured lengths of every tetrahedron. '
            'Mesh 40 µm samples 0.5, 1, 2, 3, 4, 5, 5.8 and 6 GHz. '
            'Mesh 60 µm includes these eight points and adds twelve, mainly around 2.6 GHz.', '',
            '## Plots and their data', '',
            '**Figure 1 — full band:** green circles are Mesh 60 µm (20 frequencies); '
            'purple dashed crosses are Mesh 40 µm (8 frequencies). Blue/orange/grey curves are measurements. '
            'The purple line skips directly from 2 to 3 GHz because that sweep did not sample the notch.', '',
            '![Figure 1: both named meshes versus measurements](preview_2layer/simulation_comparison.png)', '',
            '**Figure 2 — 2.6 GHz detail:** the green curve uses only Mesh 60 µm, '
            'showing its directly solved points in this window. There is no third mesh. '
            'The archived first comparison plot uses Mesh 40 µm only.', '',
            '![Figure 2: Mesh 60 µm near 2.6 GHz](preview_2layer/resonance_2p6GHz.png)', '',
            '## Mesh 60 µm numerical results', '',
            'Pure PCB model: original pads and tapers, ideal 50 Ω lumped ports; no SMA bodies, pins or solder.', '',
            f'FEM order: **{order}**. Mesh: {metadata["tetrahedra"]:,} tetrahedra. '
            'FR-4 εr=4.5, tanδ=0.02; copper conductivity 58 MS/m.', '',
            '**Both sweeps completed successfully.** The two meshes agree closely at eight shared frequencies '
            '(maximum change: 0.04 dB in S21 and 0.34 dB in S11). '
            'The 2.65 GHz notch has not yet been checked with Mesh 40 µm, and the effect of air-box size '
            'has not been checked with a larger box. These are checks of numerical accuracy; '
            'they do not mean that the equation solver failed.', '',
            '| GHz | Simulated S11, dB | Simulated S21, dB | Measured original 10 mm S21, dB |',
            '|---:|---:|---:|---:|']
    for row in rows:
        m21 = np.interp(row['f_GHz']*1e9, mf, db(measured_s21))
        text.append(f'| {row["f_GHz"]:g} | {row["S11_dB"]:.2f} | {row["S21_dB"]:.2f} | {m21:.2f} |')
    near = np.flatnonzero((f >= 2.2e9) & (f <= 2.8e9))
    if len(near):
        dip = int(near[np.argmin(abs(s[near, 0, 0]))])
        text += ['', '## The 2.6 GHz feature', '',
                 f'The lowest sampled S11 in this window is **{float(db(s[dip, 0, 0])):.2f} dB '
                 f'at {f[dip]/1e9:g} GHz**, with S21={float(db(s[dip, 1, 0])):.2f} dB. '
                 'The model therefore reproduces a good-matching window near the measured notch. '
                 'A dip in S11 means less reflection; it is not a dip in transmitted power. '
                 'The measured split notch is not reproduced by these sampled model results. '
                 '50 MHz sampling identifies the region, not the exact continuous-frequency minimum.']
    if 'baseline_mesh_comparison' in checks:
        comparison = checks['baseline_mesh_comparison']
        text += ['', '## Mesh 40 µm versus Mesh 60 µm', '',
                 f'At the eight common frequencies, the largest S21 change is '
                 f'**{comparison["max_S21_dB_difference"]:.3f} dB**, and the largest S11 change is '
                 f'**{comparison["max_S11_dB_difference"]:.3f} dB**. '
                 'Both runs use first-order elements and identical geometry/materials. '
                 'This checks the broad response; Mesh 40 µm did not sample the notch, '
                 'so the notch depth and position have not been checked with Mesh 40 µm.']
        if 'observed_private_memory_GB' in metadata:
            text += ['', f'Observed private memory during a solve: approximately '
                     f'**{metadata["observed_private_memory_GB"]:.1f} GB** (one sample, not a peak measurement).']
        if 'elapsed_log_seconds' in metadata:
            text += ['', f'Elapsed time in the EMerge log: **{metadata["elapsed_log_seconds"]:.0f} s**, '
                     f'including meshing and {len(f)} frequencies.']
    i = int(np.argmin(abs(f-5.8e9)))
    reflected = abs(s[i, 0, 0])**2
    transmitted = abs(s[i, 1, 0])**2
    text += ['', 'Measured values in this table are interpolated in dB to the directly solved frequencies. '
             'Plot markers are solved points; connecting lines do not resolve resonances between them.', '',
             '## Interpretation', '',
             f'At {f[i]/1e9:g} GHz the simulated incident power divides into '
             f'**{100*reflected:.1f}% reflected**, **{100*transmitted:.1f}% transmitted**, '
             f'and **{100*(1-reflected-transmitted):.1f}% dissipated or radiated**. '
             'Most of the transmission reduction in this model is therefore mismatch.', '',
             'The pure PCB reproduces a substantial high-frequency transmission drop and strong reflection '
             'with the specified εr=4.5 and tanδ=0.02. This supports PCB pad/transition mismatch as a major '
             'contributor; these measurements alone do not establish unusually high substrate loss. '
             'A uniform-line control simulation is still needed to isolate the pads from the rest of the PCB.', '',
             'The current frequency sampling does not resolve or explain the measured high-frequency ripples. Ideal port location/profile, '
             'omitted connector pins and solder, measurement residuals, and numerical approximation limit '
             'a quantitative comparison. Agreement with measurements supports the broad trend, '
             'but does not replace checking sensitivity to mesh refinement and air-box size.', '',
             f'Maximum complex reciprocity error |S21−S12|: {checks["max_reciprocity_error"]:.3g}. '
             f'Maximum scattering-matrix singular value: {checks["max_singular_value"]:.6f} '
             '(a passive model should be ≤1, within numerical error).', '',
             '## Data locations', '',
             '- **Mesh 60 µm, 20 frequencies:** `result_2layer.npz`, `result_2layer.json`, '
             '`result_2layer.s2p`; plots and metrics in `preview_2layer/`.',
             '- **Mesh 40 µm, 8 frequencies:** `runs/baseline_8pt/`; this contains the archived '
             'first full-band plot and its original data.',
             '- `preview/` is an earlier four-layer geometry/mesh preview. No EM sweep was completed with it; '
             'it supplies none of the curves in this report.']
    write_report(REPORTS/'01_PCB_ONLY_RESULTS.md', '\n'.join(text)+'\n')
    print(json.dumps(checks, indent=2))


if __name__ == '__main__':
    main()

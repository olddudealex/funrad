"""Compare saved revision B measurements with the selected FEM geometry.

Run from Frontend/emerge: python -m coupon_10mm.report_revb_measurements
No EM solves, smoothing, fitting, or measurement de-embedding are performed.
"""
from io import StringIO
import hashlib
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from .report_paths import HERE, MEASUREMENTS, REPORTS

ASSETS = REPORTS / 'assets/revb_measurements'
# Preserve report 11's initial measurements after the later files were renamed.
BROAD = 'coupon_revB_7628_horizontal_10mm_100Mhz_6.5GHz_nanoVNA_0.s2p'
NARROW = 'coupon_revB_7628_horizontal_10mm_5.3_6.3GHz_nanoVNA_0.s2p'
TERMINATED = 'coupon_revB_7628_horizontal_10mm_5.3_6.3GHz_nanoVNA_terminated_0.s1p'
TERMINATED_BROAD = 'coupon_revB_7628_horizontal_10mm_100MHz_6.5GHz_nanoVNA_terminated_0.s1p'
SIM_BROAD = 'result_coax_open_2.8x4.8mm_0p5to6p5GHz.s2p'
SIM_NARROW = 'result_coax_open_2.8x4.8mm_5p3to6p3GHz_mesh_finer.s2p'


def load(file):
    # NanoVNA export uses decimal commas; retain the source file unchanged.
    text = file.read_text(encoding='utf-8-sig').replace(',', '.')
    option = next(line.lower().split() for line in text.splitlines() if line.startswith('#'))
    assert option == ['#', 'hz', 's', 'ri', 'r', '50'], (file, option)
    a = np.loadtxt(StringIO(text), comments=['!', '#'])
    expected_columns = 3 if file.suffix.lower() == '.s1p' else 9
    assert a.shape[1] == expected_columns and np.isfinite(a).all()
    assert np.all(np.diff(a[:, 0]) > 0)
    # Touchstone two-port order: S11, S21, S12, S22.
    return a[:, 0] / 1e9, a[:, 1::2] + 1j * a[:, 2::2]


def db(s):
    return 20 * np.log10(np.maximum(np.abs(s), 1e-15))


def metrics(data, lo, hi):
    f, s = data
    mask = (f >= lo - 1e-9) & (f <= hi + 1e-9)
    d = db(s[mask])
    result = dict(points=int(mask.sum()), S11_worst_dB=float(d[:, 0].max()))
    if d.shape[1] > 1:
        result.update(S21_median_dB=float(np.median(d[:, 1])),
                      S21_min_dB=float(d[:, 1].min()), S21_max_dB=float(d[:, 1].max()))
    return result


def plot(measured, simulated, name, title, limits, original=None, terminated=None):
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True, constrained_layout=True)
    for ax, column in zip(axes, [1, 0]):
        if original is not None:
            ax.plot(original[0], db(original[1])[:, column], color='#888888', lw=.8,
                    alpha=.65, label='Rev A measured (original launches)')
        if column == 1 or terminated is None:
            ax.plot(measured[0], db(measured[1])[:, column], color='#0072b2', lw=.8,
                    label='Rev B measured (S21 provisional)' if column == 1 else 'Rev B measured')
        if terminated is not None and column == 0:
            ax.plot(terminated[0], db(terminated[1])[:, 0], color='#009e73', lw=1.2,
                    label='Rev B measured')
        ax.plot(simulated[0], db(simulated[1])[:, column], 'o-', color='#d55e00',
                ms=4, lw=1.7, label='Rev B FEM — direct solved points')
        ax.grid(alpha=.25)
        ax.set_xlim(*limits)
        ax.set_ylabel(f'S{21 if column == 1 else 11} (dB)')
        ax.legend(fontsize=8, loc='lower left')
    if original is not None:
        for ax in axes:
            ax.axvspan(5.3, 6.3, color='#e6ab02', alpha=.10)
    else:
        axes[0].set_ylim(-1.8, .25)
        axes[1].set_ylim(-48, -8)
        axes[1].axhline(-10, color='#777777', ls=':', lw=1, label='_nolegend_')
        axes[1].text(5.32, -10.5, '−10 dB reference', fontsize=8, va='top')
    axes[1].set_xlabel('Frequency (GHz)')
    fig.suptitle(title)
    fig.savefig(ASSETS / name, dpi=170)
    plt.close(fig)


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    broad = load(MEASUREMENTS / BROAD)
    narrow = load(MEASUREMENTS / NARROW)
    terminated = load(MEASUREMENTS / TERMINATED)
    terminated_broad = load(MEASUREMENTS / TERMINATED_BROAD)
    sim_broad = load(HERE / SIM_BROAD)
    sim_narrow = load(HERE / SIM_NARROW)
    original = load(MEASUREMENTS / 'coupon_7628_horizontal_10mm.s2p')
    plot(broad, sim_broad, 'broadband.png',
         '10 mm coupon, both launches included: broadband comparison\n'
         'S21 measurement stops at 6.0 GHz',
         (.5, 6.5), original, terminated=terminated_broad)
    plot(narrow, sim_narrow, 'narrowband.png',
         'Revision B: 5.3–6.3 GHz\n'
         '2.8 × 4.8 mm L2 cutouts; original tapers; L3 / Bottom intact',
         (5.3, 6.3), terminated=terminated)
    cases = [('Measured S21, broad sweep (provisional)', broad, .5, 6),
             ('Measured S11, external termination / broad sweep', terminated_broad, .5, 6.5),
             ('FEM, standard mesh', sim_broad, .5, 6.5),
             ('Measured S11, external termination / broad sweep overlap', terminated_broad, 5.3, 6.3),
             ('Measured S21, narrow sweep (provisional)', narrow, 5.3, 6.3),
             ('Measured S11, external termination', terminated, 5.3, 6.3),
             ('FEM, finer mesh', sim_narrow, 5.3, 6.3)]
    rows = []
    summary = {}
    for label, data, lo, hi in cases:
        m = metrics(data, lo, hi)
        if label.startswith('Measured S21,'):
            m.pop('S11_worst_dB')
        summary[label] = m
        transmission = (f'{m["S21_median_dB"]:.2f} | {m["S21_min_dB"]:.2f}…{m["S21_max_dB"]:.2f}'
                        if 'S21_median_dB' in m else '— | —')
        reflection = f'{m["S11_worst_dB"]:.2f}' if 'S11_worst_dB' in m else '—'
        rows.append(f'| {label} | {lo}–{hi} | {transmission} | {reflection} |')
    center = [np.array([np.interp(5.8, f, db(s)[:, i]) for i in [0, 1]])
              for f, s in [narrow, sim_narrow]]
    terminated_center = float(np.interp(5.8, terminated[0], db(terminated[1])[:, 0]))
    worst = summary['Measured S11, external termination']['S11_worst_dB']
    broad_overlap = summary['Measured S11, external termination / broad sweep overlap']
    broad_d = db(terminated_broad[1])[:, 0]
    broad_worst_i = int(np.argmax(broad_d))
    broad_worst = float(broad_d[broad_worst_i])
    broad_worst_f = float(terminated_broad[0][broad_worst_i])
    reflected = 100 * 10 ** (worst / 10)
    sources = [MEASUREMENTS / BROAD, MEASUREMENTS / NARROW, MEASUREMENTS / TERMINATED,
               MEASUREMENTS / TERMINATED_BROAD,
               HERE / SIM_BROAD, HERE / SIM_NARROW]
    summary['source_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    (ASSETS / 'metrics.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    text = f'''# Revision B coupon: simulation versus measurement

Initial measurement set (17:49–18:35 on 2026-11-01), preserved under the renamed `_0` files. For the later same-calibration line comparison, see [Line parameters and solder mask](12_LINE_PARAMETERS_AND_MASK.md).

**Verdict: the launch redesign works, and matching is good.** Broadband S11 stays below **{broad_worst:.1f} dB over 0.1–6.5 GHz**. In 5.3–6.3 GHz, worst S11 is **{worst:.1f} dB in the narrow sweep** and **{broad_overlap['S11_worst_dB']:.1f} dB in the broad sweep**. S21 remains provisional.

**S11 was measured with an external termination at the far end of the coupon**, using the two 1001-point S1P sweeps. S21 comes from the earlier two-port measurements.

![Broadband comparison](assets/revb_measurements/broadband.png)

![Narrow-band comparison](assets/revb_measurements/narrowband.png)

| Dataset | Band, GHz | Median S21, dB | S21 min…max, dB | Worst S11, dB |
|---|---|---:|---:|---:|
{chr(10).join(rows)}

At **5.8 GHz**, measured / simulated **S11 = {terminated_center:.1f} / {center[1][0]:.1f} dB**. Earlier measured / simulated **S21 = {center[0][1]:.2f} / {center[1][1]:.2f} dB**, but its ripple must not be attributed to the PCB before checking the transmission measurement. Ranges include every sample in each stated band; medians use each dataset's own grid. The narrow-sweep worst reflection corresponds to **{reflected:.2f}% reflected power**.

The new broad sweep covers **0.1–6.5 GHz**; its worst S11 is **{broad_worst:.2f} dB at {broad_worst_f:.4f} GHz**. The plot/table compare **0.5–6.5 GHz**, where broadband FEM exists. Its 5.3–6.3 GHz worst S11 differs from the narrow sweep by **{broad_overlap['S11_worst_dB'] - worst:.2f} dB**; retain both results rather than treating them as identical repeats. Both measured worst-band values are better than the finer FEM prediction of **−16.2 dB**, although the curve shapes differ.

Comparison uses the selected **2.8 × 4.8 mm L2 cutouts, original tapers, L3 / Bottom intact**, εr=4.5, tanδ=0.02 and simplified BWSMA connectors. Broadband FEM: [standard mesh, 31 points over 0.5–6.5 GHz](07_BROADBAND_CHECK.md); narrow-band FEM: [finer mesh, 11 points](08_MESH_REFINEMENT.md). Lines join solved points and do not imply dense FEM sampling. Both measurement and simulation use 50 Ω references and include both launches; no per-launch loss is inferred.

The **earlier S2P** broadband filename says 100 MHz–6.5 GHz, but its recorded frequencies cover **10 MHz–6.0 GHz**; its S21 trace ends at 6.0 GHz. The earlier narrow S2P contains **1001 points over 5.3–6.3 GHz**. Its S21 briefly exceeds 0 dB, indicating measurement uncertainty. No smoothing, calibration correction or de-embedding was applied. The S2P files contain zero-filled S12/S22 columns; the S1P files contain only input reflection. None establishes reciprocity or output matching.

Measurements: [earlier broad S2P](measurements/{BROAD}) · [earlier narrow S2P](measurements/{NARROW}) · [externally terminated narrow S1P](measurements/{TERMINATED}) · [externally terminated broad S1P](measurements/{TERMINATED_BROAD}). [Computed metrics and source hashes](assets/revb_measurements/metrics.json).

Regenerate from `Frontend/emerge` with `python -m coupon_10mm.report_revb_measurements` (using the project venv). [Coupon overview](index.md).
'''
    (REPORTS / '11_REVB_MEASUREMENT_COMPARISON.md').write_text(text, encoding='utf-8')
    print('Wrote revision B comparison report, two figures, and metrics.json.')


if __name__ == '__main__':
    main()

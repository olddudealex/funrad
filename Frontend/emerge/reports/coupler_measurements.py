"""Compare the horizontal revision-B coupler with saved FEM and line coupons.

Run from Frontend/emerge: python -m reports.coupler_measurements
No EM solve. External-line and frequency-scaling curves are diagnostics only.
"""
from pathlib import Path
import hashlib
import json
import re
from urllib.parse import quote

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from coupon_10mm.report_revb_measurements import load, db
from coupon_10mm.report_line_parameters import derive
from reports.coupler_prediction import HERE, wide_run
from reports.coupler_loads import analyse as analyse_loads

ROOT = HERE.parents[1]
VAULT = ROOT/'Notes/FunRad'
REPORT = VAULT/'Frontend/Coupler/Coupler Measurement Comparison.md'
MEAS = VAULT/'Frontend/Coupon/measurements'
SOURCE = MEAS/'coupler_coupon_revB_7628_horizontal'
OUT = REPORT.parent/'assets/measurements'
BOARD = ROOT/'Frontend/kicad/FrontendPCBCoupon/FrontendPCBCoupon.kicad_pcb'
FILES = {
    'S11': 'S11_(loads_2a_3b_4c).s1p',
    'S21': 'S21_(loads_3b_4c).s2p',
    'S31': 'S31_(loads_2a_4c).s2p',
    'ab': 'S41_(loads_2a_3b).s2p',
    'cb': 'S41_(loads_2c_3b).s2p',
    'ac': 'S41_(loads_2a_3c-tightened-fully).s2p',
    'ac_loose': 'S41_(loads_2a_3c-not-tightened-fully).s2p',
    'ab2': 'S41_(loads_2a_3b)_2.s2p',
    'ac2': 'S41_(loads_2a_3c-tightened-fully)_2.s2p',
    'ac3': 'S41_(loads_2a_3c-tightened-fully)_3.s2p',
    'S31repeat': 'S31_(loads_2a_4c)_2.s2p',
    'S31ab': 'S31_(loads_2a_4b).s2p',
}
REPEATS = {'ab2': 'ab', 'ac2': 'ac', 'ac3': 'ac', 'S31repeat': 'S31'}
COLORS = dict(ab='#0072b2', cb='#009e73', ac='#d55e00', ac_loose='#999999')
LABELS = dict(ab='P2=a, P3=b', cb='P2=c, P3=b', ac='P2=a, P3=c (tight)',
              ac_loose='P2=a, P3=c (partly tightened)')


def format_axis(ax, ylabel):
    ax.set(xlabel='Frequency (GHz)', ylabel=ylabel, xlim=(5.3, 6.3))
    ax.axvline(5.8, color='#cccccc', ls=':', lw=1)
    ax.grid(alpha=.25)
    ax.legend(fontsize=8)


def save(fig, name):
    fig.savefig(OUT/name, dpi=170)
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    data = {key: load(SOURCE/file) for key, file in FILES.items()}
    f = data['S21'][0]
    assert len(f) == 1001 and np.allclose(f[[0, -1]], [5.3, 6.3])
    assert all(np.array_equal(value[0], f) for value in data.values())
    y = {key: value[1][:, 0 if key == 'S11' else 1] for key, value in data.items()}
    # Reverse columns in NanoVNA exports are placeholders, not measured reciprocity.
    assert all(np.all(value[1][:, 2:] == 0) for key, value in data.items() if key != 'S11')
    run = wide_run()
    with np.load(run/'raw.npz') as raw:
        sf, s = raw['f'].reshape(-1)/1e9, raw['Smat50'].copy()
    nominal = db(s[:, :, 0])
    i = int(np.argmin(abs(f-5.8)))
    si = int(np.argmin(abs(sf-5.8)))
    fig, axes = plt.subplots(2, 2, figsize=(11, 7), constrained_layout=True)
    for col, (key, ax) in enumerate(zip(['S11', 'S21', 'S31', 'ab'], axes.flat)):
        ax.plot(sf, nominal[:, col], 'o--', color='#333333', label='FEM core, 50 Ω loads')
        if col == 3:
            for arrangement in COLORS:
                ax.plot(f, db(y[arrangement]), color=COLORS[arrangement], lw=1,
                        ls=':' if arrangement == 'ac_loose' else '-', label=LABELS[arrangement])
        else:
            ax.plot(f, db(y[key]), color='#0072b2', lw=1, label='Measured coupon')
        ax.set_title(['S11 — three external loads', 'S21 — through',
                      'S31 — coupled', 'S41 — isolated'][col])
        format_axis(ax, f'S{col+1}1 (dB)')
    fig.suptitle('Horizontal revision B: connector-plane measurement versus coupler-core FEM\n'
                 'Different reference planes; raw measurements, no loss correction')
    save(fig, 'comparison.png')

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), constrained_layout=True)
    axes[0].plot(sf, nominal[:, 2]-nominal[:, 3], 'o--', color='#333333', label='FEM core')
    for key in COLORS:
        axes[0].plot(f, db(y['S31'])-db(y[key]), color=COLORS[key], lw=1,
                     ls=':' if key == 'ac_loose' else '-', label=LABELS[key])
        if key != 'ab':
            axes[1].plot(f, db(y[key])-db(y['ab']), color=COLORS[key], lw=1,
                         ls=':' if key == 'ac_loose' else '-', label=LABELS[key])
    axes[0].set_title('Apparent directivity: one coupling trace / each isolation trace')
    axes[1].set_title('Change from P2=a, P3=b isolation')
    format_axis(axes[0], 'S31 − S41 (dB)')
    format_axis(axes[1], 'ΔS41 (dB)')
    save(fig, 'load_sensitivity.png')

    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2), constrained_layout=True)
    for ax, keys, title in zip(axes, [('ab', 'ab2'), ('ac', 'ac2', 'ac3'),
                                     ('S31', 'S31repeat', 'S31ab')],
                               ['Isolation: P2=a / P3=b', 'Isolation: P2=a / P3=c, tight',
                                'Coupling: repeat and load swap']):
        for n, key in enumerate(keys):
            label = ('P2=a / P4=b' if key == 'S31ab' else
                     ('P2=a / P4=c, ' if key.startswith('S31') else '')+f'measurement {n+1}')
            ax.plot(f, db(y[key]), lw=1, label=label)
        ax.set_title(title, fontsize=11)
        format_axis(ax, 'S31 (dB)' if keys[0] == 'S31' else 'S41 (dB)')
    save(fig, 'repeatability.png')
    repeat_stats = {}
    for key, base in REPEATS.items():
        delta = db(y[key])-db(y[base])
        repeat_stats[key] = dict(reference=base, delta_5p8GHz_dB=float(delta[i]),
                                 median_absolute_delta_dB=float(np.median(abs(delta))),
                                 max_absolute_delta_dB=float(np.max(abs(delta))))

    # Equal feed routes checked directly from board segments. These lengths end
    # at pad centres and include the underlying track through the taper area.
    board_text = BOARD.read_text(encoding='utf-8')
    routes = {}
    for j in [7, 9, 8, 10, 1]:
        length = 0.
        for block in re.findall(r'\n\t\(segment\b.*?\n\t\)', board_text, re.S):
            if f'(net "Net-(J{j}-In)")' in block:
                a = np.fromstring(re.search(r'\(start ([^)]+)\)', block).group(1), sep=' ')
                b = np.fromstring(re.search(r'\(end ([^)]+)\)', block).group(1), sep=' ')
                length += np.linalg.norm(a-b)
        routes[f'J{j}'] = float(length)
    assert np.allclose([routes[f'J{j}'] for j in [7, 9, 8, 10]], 25.8236551084)
    assert np.isclose(routes['J1'], 14.8)
    delta_length = routes['J7']+routes['J9']-routes['J1']
    prefix = 'coupon_revB_7628_horizontal_'
    short = load(MEAS/(prefix+'10mm_5.3_6.3GHz_nanoVNA.s2p'))
    assert np.array_equal(short[0], f)
    extracts = {}
    line_sources = []
    for length, turns in [(40, 1), (90, 3)]:
        file = MEAS/(prefix+f'{length}mm_5.3_6.3GHz_nanoVNA.s2p')
        line_sources.append(file)
        extracts[length] = derive(load(file), short, (length-10)/1000, turns)
    cross = json.loads((HERE/'coupon_10mm/result_line_cross_section.json').read_text())
    eps0 = next(row['eps_eff'] for row in cross['rows'] if row['label'] == cross['selected'])
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), constrained_layout=True)
    for key, col in [('S21', 1), ('S31', 2)]:
        ax = axes[col-1]
        ax.plot(f, db(y[key]), color='#0072b2', lw=1, label='Measured coupler coupon')
        ax.plot(sf, nominal[:, col], 'o--', color='#333333', label='FEM core')
        for length, color in [(40, '#d55e00'), (90, '#009e73')]:
            # Add measured 10-mm launch pair and only the extra external route.
            estimate = np.interp(f, sf, nominal[:, col])+db(short[1][:, 1])-extracts[length]['attenuation']*delta_length
            ax.plot(f, estimate, color=color, lw=1, label=f'Core + 10 mm coupon + extra route ({length}/10 loss)')
        ax.set_title(f'{key}: external-path loss estimate')
        format_axis(ax, f'{key} (dB)')
    save(fig, 'external_loss.png')

    # Electrical-length rescaling preserves the original sampled response.
    # It is deliberately not presented as an er-retuned FEM calculation.
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), constrained_layout=True)
    axes[0].axhline(eps0, color='#333333', ls='--', label='2-D single line, εr=4.5')
    for length, color in [(40, '#d55e00'), (90, '#009e73')]:
        eps = extracts[length]['eps']
        ratio = np.sqrt(np.median(eps)/eps0)
        axes[0].plot(f, eps, color=color, lw=1, label=f'Measured {length}/10 mm')
        shifted_f = sf/ratio
        axes[1].plot(shifted_f, nominal[:, 2]-nominal[:, 3], 'o-', color=color,
                     label=f'Electrical-length illustration ({length}/10 mm)')
    axes[1].plot(sf, nominal[:, 2]-nominal[:, 3], 'o--', color='#333333', label='Original FEM core')
    axes[1].plot(f, db(y['S31'])-db(y['ab']), color='#0072b2', label='Measured, P2=a/P3=b isolation')
    axes[0].set_title('Straight lines: phase-derived effective permittivity', fontsize=11)
    axes[1].set_title('A frequency shift alone leaves a large gap', fontsize=11)
    format_axis(axes[0], 'Effective permittivity εeff')
    format_axis(axes[1], 'Directivity / apparent directivity (dB)')
    save(fig, 'electrical_length.png')

    load_summary, load_section, load_files = analyse_loads(
        SOURCE, OUT, f, sf, s, short, extracts, delta_length, y)

    stats = {}
    for key in FILES:
        values = db(y[key])
        stats[key] = dict(at_5p8GHz_dB=float(values[i]), min_dB=float(values.min()),
                          max_dB=float(values.max()), file=FILES[key])
        if key in COLORS:
            directivity = db(y['S31'])-values
            stats[key]['apparent_directivity_5p8GHz_dB'] = float(directivity[i])
            stats[key]['minimum_apparent_directivity_dB'] = float(directivity.min())
    paths = [SOURCE/name for name in FILES.values()]+line_sources+load_files+[
        MEAS/(prefix+'10mm_5.3_6.3GHz_nanoVNA.s2p'), BOARD, run/'raw.npz',
        HERE/'coupon_10mm/result_line_cross_section.json']
    summary = dict(measured=stats, repeats=repeat_stats, load_characterization=load_summary,
                   core_5p8GHz_dB=nominal[si].tolist(),
                   external_path_estimate_5p8GHz_dB={str(l): {
                       key: float(nominal[si, col]+db(short[1][i, 1])-e['attenuation'][i]*delta_length)
                       for key, col in [('S21', 1), ('S31', 2)]}
                       for l, e in extracts.items()},
                   route_segment_lengths_mm=routes, extra_route_vs_10mm_mm=delta_length,
                   straight_line_diagnostics={str(l): dict(
                       median_attenuation_dB_per_cm=float(np.median(e['attenuation'])*10),
                       attenuation_at_5p8GHz_dB_per_cm=float(e['attenuation'][i]*10),
                       median_eps_eff=float(np.median(e['eps'])),
                       frequency_scale=float(np.sqrt(np.median(e['eps'])/eps0)))
                       for l, e in extracts.items()},
                   source_sha256={p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in paths})
    (OUT/'metrics.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
    rows = '\n'.join(f'| {key} | {stats[key]["at_5p8GHz_dB"]:.2f} | {nominal[si, col]:.2f} |'
                     for col, key in enumerate(['S11', 'S21', 'S31', 'ab']))
    rows = rows.replace('| ab |', '| S41, P2=a / P3=b |')
    source_labels = dict(LABELS, ab2='P2=a, P3=b; repeat', ac2='P2=a, P3=c; tight, repeat 2',
                         ac3='P2=a, P3=c; tight, repeat 3', S31repeat='P2=a, P4=c; repeat',
                         S31ab='P2=a, P4=b', S11='P2=a, P3=b, P4=c', S21='P3=b, P4=c',
                         S31='P2=a, P4=c')
    source_rows = '\n'.join(f'| [{name}](../Coupon/measurements/coupler_coupon_revB_7628_horizontal/{quote(name, safe="")}) | '
                            f'{source_labels[key]} |'
                            for key, name in FILES.items())
    text = rf'''---
title: Coupler — measured versus simulated
---

# Coupler — measured versus simulated

**Horizontal revision B, 5.3–6.3 GHz.** The coupler works, but its connector-plane isolation is much poorer than the nominal core simulation. The long feeds explain much of the transmission loss. Load and connection sensitivity prevent us from assigning the remaining isolation error to PCB material alone.

## 1. Raw comparison

![Measured and simulated S-parameters](assets/measurements/comparison.png)

| At 5.8 GHz | Measured, dB | FEM core, dB |
|---|---:|---:|
{rows}

S11 uses **three external terminations**. Each S21/S31/S41 curve is the forward transmission column of its own two-port file: VNA source → coupon P1, receiver → the named output. The zero S12/S22 columns are export placeholders. Port numbering follows [[TX Coupler EM Method]]: P2 through, P3 coupled, P4 isolated.

The FEM is the saved **11-point finite-copper sweep**, εr=4.4, tanδ=0.020, with ideal 50 Ω reference impedances. It includes the coupler and its short fan-outs; the hardware adds long routes and two SMA launches. These raw curves therefore have different reference planes. The measured S11 also includes the launches, feed reflections and imperfect terminations.

## 2. Load matching changes the answer

![Load arrangements and apparent directivity](assets/measurements/load_sensitivity.png)

At 5.8 GHz, isolation is **{stats['ab']['at_5p8GHz_dB']:.2f} dB** with P2=a/P3=b, **{stats['cb']['at_5p8GHz_dB']:.2f} dB** with P2=c/P3=b, and **{stats['ac']['at_5p8GHz_dB']:.2f} dB** with P2=a/P3=c fully tightened. The partly tightened c connection reaches **{stats['ac_loose']['at_5p8GHz_dB']:.2f} dB**. A deeper dip with a loose connection can come from accidental cancellation; it does not establish better directivity.

Using the available S31 trace, the corresponding **apparent** directivities at 5.8 GHz are **{stats['ab']['apparent_directivity_5p8GHz_dB']:.2f}, {stats['cb']['apparent_directivity_5p8GHz_dB']:.2f}, {stats['ac']['apparent_directivity_5p8GHz_dB']:.2f} dB**, versus **{nominal[si, 2]-nominal[si, 3]:.2f} dB** simulated. The S31 trace uses P2=a/P4=c; it is reused for every ratio, so these are measurement diagnostics rather than several independently measured intrinsic directivities.

Why does a load matter? For excitation at P1, the leading unwanted contributions at P4 are

$$\widetilde S_{{41}}\approx S_{{41}}+S_{{42}}\Gamma_2 S_{{21}}+S_{{43}}\Gamma_3 S_{{31}}.$$

Both extra terms can be substantial: the through-arm load sends a reflected wave back into the coupler, and the coupled-arm load reflects the coupled signal towards P4. They add as **complex amplitudes**, so changing their phase can deepen or spoil a null. The exact terminated-network expression is

$$S_{{\mathrm{{loaded}}}}=S_{{AA}}+S_{{AB}}\Gamma_B
(I-S_{{BB}}\Gamma_B)^{{-1}}S_{{BA}},$$

where A contains the two VNA-connected ports and B the two terminated ports. Here Γ is defined at the coupler reference planes; feed lines and adapters transform the physical load reflection. The receiver's own mismatch is an additional uncertainty. [Keysight's measurement-error guide](https://helpfiles.keysight.com/csg/N1930xB/VNACalAndMeas/Errors.htm) describes load-match errors; [Anritsu's directivity explanation](https://www.anritsu.com/en-us/test-measurement/solutions/en-us/understanding-directivity) shows why the termination matters for isolation.

{load_section}
### Repeatability check

![Repeated isolation and coupling measurements](assets/measurements/repeatability.png)

The original files remain the reference for the plots above. The added traces show:

- **S41, P2=a/P3=b:** −32.46 → **{stats['ab2']['at_5p8GHz_dB']:.2f} dB** at 5.8 GHz. Across the band, the median absolute change is **{repeat_stats['ab2']['median_absolute_delta_dB']:.2f} dB**, with a maximum of **{repeat_stats['ab2']['max_absolute_delta_dB']:.2f} dB**.
- **S41, P2=a/P3=c, fully tightened:** **−36.11 / {stats['ac2']['at_5p8GHz_dB']:.2f} / {stats['ac3']['at_5p8GHz_dB']:.2f} dB** at 5.8 GHz. Repeat 2 stays within **{repeat_stats['ac2']['max_absolute_delta_dB']:.2f} dB** of the original across the band; repeat 3 differs by as much as **{repeat_stats['ac3']['max_absolute_delta_dB']:.2f} dB**, chiefly around the shifted isolation dip.
- **S31, P2=a/P4=c:** −17.65 → **{stats['S31repeat']['at_5p8GHz_dB']:.2f} dB** at 5.8 GHz; the maximum change across the band is only **{repeat_stats['S31repeat']['max_absolute_delta_dB']:.2f} dB**. Swapping P4 to b gives **{stats['S31ab']['at_5p8GHz_dB']:.2f} dB** at 5.8 GHz.

**Coupling is substantially more repeatable than isolation.** The isolation changes include both load-dependent differences and variation between connections with the same named loads. The traces alone cannot separate contact changes, cable movement, instrument drift and load mismatch. The load measurements above establish a strong difference between b and the other two, but do not account for all reconnection variation.

## 3. How much is simply feed loss?

![Transmission with an approximate external-path correction](assets/measurements/external_loss.png)

The PCB has four equal routed feeds: **25.82 mm** from each SMA signal-pad centre to its coupler pad centre (J7/P1, J9/P2, J8/P3, J10/P4). Their 45° bends are included. The 10 mm reference coupon has a **14.80 mm** pad-centre route. Thus a two-feed path has about **36.85 mm more external route** than that reference. Pad-centre versus FEM-edge offsets are below 0.4 mm per path; this is a loss estimate, not exact de-embedding.

For each straight-line pair, estimate total track attenuation and then add the measured launch pair:

$$a(f)=-\frac{{20\log_{{10}}|S_{{21,\ell}}/S_{{21,10}}|}}{{\ell-10}}\quad[\mathrm{{dB/mm}}],$$
$$S_{{j1,\mathrm{{estimate}}}}^{{\mathrm{{dB}}}}\approx
S_{{j1,\mathrm{{core}}}}^{{\mathrm{{dB}}}}+S_{{21,10}}^{{\mathrm{{dB}}}}-a(f)\,(36.85\ \mathrm{{mm}}),\qquad j=2,3.$$

Here ℓ is in mm. The measured 40/10 and 90/10 pairs give median attenuation **{summary['straight_line_diagnostics']['40']['median_attenuation_dB_per_cm']:.2f} and {summary['straight_line_diagnostics']['90']['median_attenuation_dB_per_cm']:.2f} dB/cm**. The two coloured curves show how this uncertainty affects the comparison. The core already contains copper and dielectric loss: we add only the external path, rather than applying the coupon attenuation a second time to the core. Using raw 10 mm transmission also carries its measurement ripple into these estimates.

At 5.8 GHz the two estimates give **S21 ≈ −3.06 / −2.73 dB** and **S31 ≈ −17.70 / −17.37 dB**, versus **−3.16 / −17.65 dB** measured. **The scale of the deficit is consistent with long feeds and launches.** This does not identify a higher dielectric loss tangent: the measured attenuation includes conductor loss, roughness, mismatch and measurement error. The shared ripple can also come from the VNA; agreement here is not independent validation of the launch model. Equal matched feed losses lower S31 and S41 similarly and largely cancel in their ratio. They cannot alone explain the large directivity deficit or its sensitivity to tightening a connector. Loss inside the coupled section could disturb the cancellation differently and needs a separate model.

## 4. Higher effective permittivity shifts the compensation

![Measured effective permittivity and an electrical-length illustration](assets/measurements/electrical_length.png)

[[../Coupon/12_LINE_PARAMETERS_AND_MASK|The line-parameter report]] derives εeff from the extra S21 phase of the 40/10 and 90/10 pairs. Their median values are **{summary['straight_line_diagnostics']['40']['median_eps_eff']:.3f} and {summary['straight_line_diagnostics']['90']['median_eps_eff']:.3f}**, versus **{eps0:.3f}** from our single-line 2-D calculation. **εeff is not substrate Dk.** That reference uses εr=4.5, while the coupler FEM uses 4.4; neither straight-line extraction directly supplies the coupler's even/odd permittivities or comb capacitance.

As a simple electrical-length illustration,

$$\beta\propto f\sqrt{{\varepsilon_{{\mathrm{{eff}}}}}},\qquad
f_{{\mathrm{{new}}}}\approx f_{{\mathrm{{old}}}}
\sqrt{{\frac{{\varepsilon_{{\mathrm{{eff,sim}}}}}}{{\varepsilon_{{\mathrm{{eff,meas}}}}}}}}.$$

These ratios move a 6.0 GHz feature down to roughly **5.83–5.92 GHz**. The plot rescales the saved FEM frequency axis only; it does not rerun Maxwell's equations or predict the change of coupling strength. A frequency shift alone leaves the nominal directivity much higher than measured. A different Dk may also change the modal velocity difference and comb loading, which this illustration cannot test. As-built gap/comb etch, mask coverage and the simulated PEC enclosure versus the measurement surroundings are other untested differences.

## 5. Missing measurements — in useful order

The inventory below covers all pairs of **different** loads. Each column names the two terminated ports; ✓ means a fully connected trace is available, — means missing. The partly tightened a/c trace is an additional diagnostic, not another load arrangement.

| Load pair, in port order | S21: P3/P4 | S31: P2/P4 | S41: P2/P3 |
|---|:---:|:---:|:---:|
| a / b | — | ✓ | ✓ |
| a / c | — | ✓ | ✓ |
| b / a | — | — | — |
| b / c | ✓ | — | — |
| c / a | — | — | — |
| c / b | — | — | ✓ |

There is no need to measure every blank before proceeding. Current status and priorities:

1. **Load S11 measurements are now included**, with calibration at the correct connection plane. Load a was the calibration LOAD standard. An independently characterized calibration load or an independent verification device would be needed to establish absolute load matching; measuring a again under the same calibration will not do that. Meanwhile, a/c are the more consistent pair under this calibration, and b is the outlier.
2. **Repeatability traces are available**, as shown above. They establish that reconnection variability matters, especially for S41. No further repeat sequence is required now.
3. To complete all six distinct-load S41 arrangements, the missing files are **P2=b/P3=a, P2=b/P3=c, P2=c/P3=a**. These are optional diagnostics; the present results already show that a load-only correction of the nominal model is insufficient under the ideal-a assumption.
4. The new **S31 P2=a/P4=b** trace is included. **S31 P2=c/P4=b** is still missing if we want a coupling comparison with the same P2 load as the existing S41 P2=c/P3=b trace. Keep every unused port terminated and every connector fully tightened.

**Verdict:** long feeds explain much of the weaker transmission. Load b differs substantially from a/c, and reconnection changes isolation. Assuming calibration load a is ideal, the measured loads still do not explain the whole isolation gap in the nominal core plus matched-feed model. Absolute load accuracy, launch/receiver mismatch and the as-built core remain unresolved. The existing data do not justify retuning the comb or assigning the gap to Dk alone.

## Data and reproduction

| Raw file | External loads |
|---|---|
{source_rows}

[Numerical summary and source hashes](assets/measurements/metrics.json). Reproduce from `Frontend/emerge` with the project venv: `python -m reports.coupler_measurements`. The script reads saved FEM and measurement files; it runs no new EM simulation. Curves are unsmoothed; FEM lines join the 11 saved samples.
'''
    # Quartz's Markdown math parser needs display delimiters on their own lines.
    text = re.sub(r'\$\$(.*?)\$\$', lambda m: '\n$$\n'+m.group(1).strip()+'\n$$\n',
                  text, flags=re.S)
    REPORT.write_text(text, encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()

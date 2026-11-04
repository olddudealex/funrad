"""Load-characterization figures and a conditional terminated-FEM diagnostic.

The user calibrated at the load connector using load a as the LOAD standard.
Consequently indicated Gamma_a is not an independent measurement of its match.
All absolute loaded-network predictions below assume that standard was ideal.
"""
import json
from urllib.parse import quote

import matplotlib.pyplot as plt
import numpy as np

from coupon_10mm.report_revb_measurements import load, db
from coupon_10mm.report_line_parameters import smith_grid


def terminated_isolation(smatrix, gamma):
    """Terminate P2/P3, retain matched source P1 and matched receiver P4.

    Also bound |S41_loaded| for arbitrary phases of the same load magnitudes.
    The bound includes repeated reflections via a convergent nonnegative
    geometric series. It is conditional on this S-matrix and the load magnitudes.
    """
    values, upper = [], []
    for s, g in zip(smatrix, gamma):
        bb = s[np.ix_([1, 2], [1, 2])]
        r = np.diag(abs(g))
        G = np.diag(g)
        values.append(s[3, 0]+s[3, [1, 2]]@G@np.linalg.solve(
            np.eye(2)-bb@G, s[[1, 2], 0]))
        feedback = abs(bb)@r
        assert np.max(abs(np.linalg.eigvals(feedback))) < 1
        upper.append(abs(s[3, 0])+abs(s[3, [1, 2]])@r@np.linalg.solve(
            np.eye(2)-feedback, abs(s[[1, 2], 0])))
    values, upper = np.array(values), np.array(upper)
    assert np.all(abs(values) <= upper+1e-12)
    return values, upper


def analyse(source, out, f, sf, s, short, extracts, delta_length, measurements):
    files = [source/f'S11_load_{name}.s1p' for name in 'abc']
    gamma, stats = {}, {}
    i = int(np.argmin(abs(f-5.8)))
    for name, file in zip('abc', files):
        lf, ls = load(file)
        assert np.array_equal(lf, f) and ls.shape == (len(f), 1)
        gamma[name] = ls[:, 0]
        values = db(gamma[name])
        stats[name] = dict(indicated_S11_5p8GHz_dB=float(values[i]),
                           indicated_phase_5p8GHz_deg=float(np.angle(gamma[name][i], deg=True)),
                           worst_indicated_S11_dB=float(values.max()),
                           best_indicated_S11_dB=float(values.min()),
                           calibration_standard=(name == 'a'))
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.6), constrained_layout=True)
    smith_grid(axes[1], zoom=True)
    for name, color in zip('abc', ['#0072b2', '#d55e00', '#009e73']):
        label = f'Load {name}'+(' (LOAD calibration standard)' if name == 'a' else '')
        g = gamma[name]
        axes[0].plot(f, db(g), color=color, lw=1, label=label)
        axes[0].plot(5.8, db(g[i]), '*', color=color, ms=10)
        axes[1].plot(g.real, g.imag, color=color, lw=1, label=f'Load {name}')
        axes[1].plot(g[i].real, g[i].imag, '*', color=color, ms=10)
    axes[0].set(xlabel='Frequency (GHz)', ylabel='Indicated S11 (dB)', xlim=(5.3, 6.3),
                title='Load matching under calibration using a')
    axes[0].grid(alpha=.25)
    axes[0].legend(fontsize=8, loc='lower right')
    axes[1].set_title('Smith-chart detail; stars: 5.8 GHz')
    axes[1].legend(fontsize=8, loc='upper left')
    fig.suptitle('Connector-plane load measurements — a is the reference, not independently verified')
    fig.savefig(out/'loads.png', dpi=170)
    plt.close(fig)

    # Interpolate the saved 11-point complex S-matrix; this is not a new EM solve.
    core = np.empty((len(f), 4, 4), complex)
    for a in range(4):
        for b in range(4):
            core[:, a, b] = (np.interp(f, sf, s[:, a, b].real)
                             +1j*np.interp(f, sf, s[:, a, b].imag))
    results = {}
    for length in [40, 90]:
        # Equal matched feeds: S_coupon = q*S_core, q=t^2. q uses the raw
        # 10-mm coupon pair plus the extra route. The differential phase branch
        # is the same one already used in the line-parameter report.
        extracted = extracts[length]
        differential_phase = extracted['phase']
        attenuation = extracted['attenuation']  # dB/mm
        exponent = (-attenuation*np.log(10)/20
                    +1j*differential_phase/(length-10))*delta_length
        pair = short[1][:, 1]*np.exp(exponent)
        network = pair[:, None, None]*core
        assert np.max(np.linalg.svd(network, compute_uv=False)) <= 1+1e-10
        zero, _ = terminated_isolation(network, np.zeros((len(f), 2), complex))
        assert np.allclose(zero, network[:, 3, 0], rtol=1e-12, atol=1e-12)
        case = {'matched': network[:, 3, 0]}
        for key, names in [('ab', 'ab'), ('cb', 'cb'), ('ac', 'ac')]:
            loads = np.column_stack([gamma[names[0]], gamma[names[1]]])
            case[key] = terminated_isolation(network, loads)
        results[length] = case

    fig, axes = plt.subplots(1, 3, figsize=(13, 4.5), constrained_layout=True)
    for ax, key, repeat_keys in zip(axes, ['ab', 'cb', 'ac'],
                                   [('ab', 'ab2'), ('cb',), ('ac', 'ac2', 'ac3')]):
        for n, repeat in enumerate(repeat_keys):
            ax.plot(f, db(measurements[repeat]), lw=1, label=f'Measured {n+1}')
        ax.plot(f, db(results[90][key][0]), color='#333333', ls='--', lw=1.4,
                label='Conditional model (90/10 feeds)')
        ax.plot(f, db(results[40][key][0]), color='#888888', ls=':', lw=1,
                label='Conditional model (40/10 feeds)')
        ax.plot(f, db(results[90][key][1]), color='#aa3377', ls='-.', lw=1.2,
                label='Any-load-phase upper bound (90/10)')
        ax.set(xlabel='Frequency (GHz)', ylabel='S41 (dB)', xlim=(5.3, 6.3),
               title=f'P2={key[0]}, P3={key[1]}', ylim=(-75, -20))
        ax.grid(alpha=.25)
        ax.axvline(5.8, color='#cccccc', ls=':', lw=1)
        ax.legend(fontsize=7, loc='lower left')
    fig.suptitle('Loading the nominal FEM + matched feeds — assuming calibration load a is ideal\n'
                 'The upper bound applies only to this model and the indicated load magnitudes')
    fig.savefig(out/'loaded_model.png', dpi=170)
    plt.close(fig)

    centre = {str(length): {key: dict(
        predicted_S41_5p8GHz_dB=float(db(results[length][key][0][i])),
        any_load_phase_upper_bound_5p8GHz_dB=float(db(results[length][key][1][i])))
        for key in ['ab', 'cb', 'ac']} for length in [40, 90]}
    summary = dict(calibration_plane='Load connector, confirmed by user',
                   calibration_LOAD_standard='a; treated as ideal 50 ohm during calibration',
                   limitation='Indicated load a is not an independent absolute-match measurement',
                   loads=stats, conditional_model=centre,
                   model_assumptions=['Saved nominal core; equal matched feed networks',
                                      'Raw 10-mm transmission and differential line propagation',
                                      'Indicated Gamma treated as true; assumes ideal calibration load a',
                                      'Matched VNA source and receiver; launch reflections excluded'],
                   frequencies_GHz=f.tolist(),
                   indicated_load_S11_dB={n: db(gamma[n]).tolist() for n in 'abc'},
                   predicted_S41_dB={key: db(results[90][key][0]).tolist() for key in ['ab', 'cb', 'ac']},
                   any_load_phase_upper_bound_dB={key: db(results[90][key][1]).tolist() for key in ['ab', 'cb', 'ac']})
    (out/'loads_metrics.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
    lines = '\n'.join(f'| {name} | {stats[name]["indicated_S11_5p8GHz_dB"]:.2f} | '
                      f'{stats[name]["worst_indicated_S11_dB"]:.2f} |'
                      for name in 'abc')
    links = ' · '.join(f'[Load {name}](../Coupon/measurements/coupler_coupon_revB_7628_horizontal/{quote(file.name)})'
                       for name, file in zip('abc', files))
    section = rf'''### Measured loads: b differs strongly from the calibration load

![Measured load reflections and Smith chart](assets/measurements/loads.png)

The user confirmed calibration **at the load connector**, using **load a for the LOAD step**. The reference plane is appropriate. However, the calibration assumes a is 50 Ω: its near-zero indicated reflection mainly checks reconnection and drift, rather than independently proving its match. Load c is close to a; b differs substantially.

| Load | Indicated S11 at 5.8 GHz, dB | Worst indicated S11 in band, dB |
|---|---:|---:|
{lines}

These are **indicated** values under that calibration. At 5.8 GHz, b has |Γ|≈{abs(gamma['b'][i]):.3f}, versus {abs(gamma['c'][i]):.3f} for c. Thus b can introduce much more reflected signal **if a is a good 50 Ω reference**. The deep minima for a/c should not be treated as independently established 40–80 dB return-loss performance.

### Does measured load mismatch explain the isolation gap?

![Conditional loaded-network prediction and measured isolation](assets/measurements/loaded_model.png)

For an illustration, attach equal **matched** feed networks to the saved FEM core, then terminate P2/P3 using the measured complex reflections in the exact formula above. The feed-pair transfer is

$$q(f)=S_{{21,10}}(f)\exp[-\gamma(f)\Delta\ell],\qquad S_{{\mathrm{{coupon,approx}}}}=q(f)S_{{\mathrm{{core}}}},$$

where Δℓ=36.85 mm and γ comes from the 40/10 or 90/10 mm pair, with the phase branches already established in the line report. All four feeds are assumed identical. The core's 11 complex samples are linearly interpolated; no new FEM is run. The measured feed transfer includes instrument ripple, so the exact phase of a predicted null is only illustrative.

At 5.8 GHz the 90/10-feed model gives **S41={centre['90']['ab']['predicted_S41_5p8GHz_dB']:.2f} dB for a/b**, **{centre['90']['cb']['predicted_S41_5p8GHz_dB']:.2f} dB for c/b**, and **{centre['90']['ac']['predicted_S41_5p8GHz_dB']:.2f} dB for a/c**. The magenta line allows **any phase of those same load magnitudes**, including repeated reflections; it bounds the largest leakage within this assumed network. At 5.8 GHz its bounds are **{centre['90']['ab']['any_load_phase_upper_bound_5p8GHz_dB']:.2f} / {centre['90']['cb']['any_load_phase_upper_bound_5p8GHz_dB']:.2f} / {centre['90']['ac']['any_load_phase_upper_bound_5p8GHz_dB']:.2f} dB** for a/b, c/b, a/c. Measurements show more leakage than these conditional bounds at that frequency.

**Under the ideal-a assumption, b explains part of the degradation, but not all of it.** The nominal core plus matched feeds still misses the hardware, particularly a/c. This is not an absolute bound on the real board: unknown error in calibration load a, mismatched launches, VNA receiver match, connection changes and changed core geometry/material are excluded. We cannot uniquely correct the measured directivity from these three load files alone.

The bound follows from replacing each repeated-reflection term by its magnitude. For B={{P2,P3}}, R=diag(|Γ₂|,|Γ₃|), and elementwise magnitudes,

$$|\widetilde S_{{41}}|\le |S_{{41}}|+|S_{{4B}}|R(I-|S_{{BB}}|R)^{{-1}}|S_{{B1}}|.$$

The geometric series converges for every frequency used here. The script checks the bound against the complex prediction and verifies that zero load reflections recover the matched-network S41.

{links} · [Load metrics and conditional model samples](assets/measurements/loads_metrics.json)

'''
    return summary, section, files

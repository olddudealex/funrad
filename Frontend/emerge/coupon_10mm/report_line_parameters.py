"""Publish the same-session rev B line-length and solder-mask comparison.

From Frontend/emerge: python -m coupon_10mm.report_line_parameters
Uses raw phase/amplitude; no EM solve or full two-port de-embedding.
"""
import hashlib
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from .report_paths import HERE, MEASUREMENTS, REPORTS
from .report_revb_measurements import load, db, SIM_NARROW

C = 299792458.0
OUT = REPORTS / 'assets/line_parameters'
PREFIX = 'coupon_revB_7628_horizontal_'
CASES = [
    ('10 mm', '10mm', '5.3_6.3GHz_nanoVNA.s2p', .010, '#0072b2'),
    ('40 mm', '40mm', '5.3_6.3GHz_nanoVNA.s2p', .040, '#d55e00'),
    ('90 mm', '90mm', '5.3_6.3GHz_nanoVNA.s2p', .090, '#009e73'),
    ('40 mm masked', '40mm_masked', '5.3_6.3GHz_nanoVNA.s2p', .040, '#8822aa'),
]


def derive(long, short, length, turns):
    f = long[0] * 1e9
    assert np.array_equal(long[0], short[0])
    ratio = long[1][:, 1] / short[1][:, 1]
    phase = np.unwrap(np.angle(ratio)) - 2 * np.pi * turns
    beta = -phase / length
    ee = (C * beta / (2 * np.pi * f)) ** 2
    slope, intercept = np.polyfit(f - f.mean(), phase, 1)
    delay = -slope / (2 * np.pi)
    fit = slope * (f - f.mean()) + intercept
    return dict(eps=ee, phase=phase, fit=fit, delay_ps=float(delay * 1e12),
                eps_group=float((C * delay / length) ** 2),
                attenuation=-db(ratio) / (length * 1000),
                phase_fit_rms_deg=float(np.sqrt(np.mean((phase-fit)**2))*180/np.pi))


def style(ax, ylabel):
    ax.set(xlabel='Frequency (GHz)', ylabel=ylabel, xlim=(5.3, 6.3))
    ax.grid(alpha=.25)
    ax.legend(fontsize=8)


def smith_grid(ax, zoom=False):
    """Map normalized impedances z to Gamma=(z-1)/(z+1)."""
    theta = np.linspace(0, 2*np.pi, 1000)
    ax.plot(np.cos(theta), np.sin(theta), color='#777777', lw=.8)
    reactance = np.linspace(-100, 100, 20001)
    resistance = np.linspace(0, 100, 10001)
    for r in ([0, .2, .5, 1, 2, 5] if not zoom else [.6, .8, 1, 1.2, 1.5]):
        z = r+1j*reactance
        g = (z-1)/(z+1)
        ax.plot(g.real, g.imag, color='#cccccc', lw=.6)
        x = (r-1)/(r+1)
        ax.text(x, .004 if zoom else .018, f'{r:g}', color='#777777', fontsize=7, clip_on=True)
    for x in ([.2, .5, 1, 2, 5] if not zoom else [.05, .1, .2]):
        for sign in [-1, 1]:
            z = resistance+1j*sign*x
            g = (z-1)/(z+1)
            ax.plot(g.real, g.imag, color='#cccccc', lw=.6)
    ax.axhline(0, color='#aaaaaa', lw=.7)
    ax.plot(0, 0, '+', color='#555555', ms=7)
    ax.set_aspect('equal', adjustable='box')
    ax.set(xlim=(-.17, .12) if zoom else (-1.05, 1.05),
           ylim=(-.17, .08) if zoom else (-1.05, 1.05))
    ax.set_axis_off()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cross_file = HERE / 'result_line_cross_section.json'
    cross = json.loads(cross_file.read_text(encoding='utf-8'))
    assert cross['parameters'] == dict(W_um=370., t_um=35., er=4.5, h_um=210.4, mask_um=0.)
    solver_file = HERE.parent/'simulation/coupled_2d.py'
    assert hashlib.sha256(solver_file.read_bytes()).hexdigest() == cross['solver_sha256'], 'Regenerate 2-D reference'
    assert hashlib.sha256((HERE/'pcb_geometry.json').read_bytes()).hexdigest() == cross['geometry_source_sha256']
    model2d = next(row for row in cross['rows'] if row['label'] == cross['selected'])
    sim_file = HERE / SIM_NARROW
    sim_meta = json.loads(sim_file.with_suffix('.json').read_text(encoding='utf-8'))
    assert sim_meta['status'] == 'completed' and sim_meta['mesh_profile'] == 'finer'
    assert sim_meta['l2_opening_mm'] == [2.8, 4.8] and not sim_meta.get('l3_opening_mm')
    assert sim_meta.get('pcb_er', 4.5) == cross['parameters']['er']
    sim_f, sim_s = load(sim_file)
    assert len(sim_f) == 11 and np.allclose(sim_f, np.linspace(5.3, 6.3, 11))
    data, sources = {}, []
    for label, stem, suffix, length, color in CASES:
        transmission = MEASUREMENTS / (PREFIX + stem + '_' + suffix)
        reflection = MEASUREMENTS / (PREFIX + stem + '_5.3_6.3GHz_nanoVNA_terminated.s1p')
        s21, s11 = load(transmission), load(reflection)
        assert s21[1].shape == (1001, 4) and s11[1].shape == (1001, 1)
        assert np.allclose(s21[0][[0, -1]], [5.3, 6.3])
        assert np.array_equal(s21[0], s11[0])
        data[label] = (s21, s11)
        sources.extend([transmission, reflection])
    f = data['10 mm'][0][0]
    short = data['10 mm'][0]
    # Use the existing 2-D result only to choose the missing integer turns.
    # The continuous phase/epsilon curves still come from the measurements.
    wavelength_mm = C/(f[0]*1e9*np.sqrt(model2d['eps_eff']))*1000
    branches, extracted = {}, {}
    for label, length in [('40 mm', .030), ('90 mm', .080)]:
        wrapped = float(np.angle(data[label][0][1][0, 1]/short[1][0, 1]))
        predicted = -2*np.pi*length/(wavelength_mm/1000)
        turns = int(np.rint((wrapped-predicted)/(2*np.pi)))
        branches[label] = dict(turns=turns, prior_wavelength_mm=float(wavelength_mm),
                               extra_length_mm=length*1000,
                               expected_phase_deg=float(np.rad2deg(predicted)),
                               short_S21_phase_deg=float(np.angle(short[1][0, 1], deg=True)),
                               long_S21_phase_deg=float(np.angle(data[label][0][1][0, 1], deg=True)),
                               initial_wrapped_phase_deg=float(np.rad2deg(wrapped)),
                               corrected_phase_deg=float(np.rad2deg(wrapped-2*np.pi*turns)))
        extracted[label] = derive(data[label][0], short, length, turns)
    bare40, mask40 = data['40 mm'][0], data['40 mm masked'][0]
    mask_phase = np.unwrap(np.angle(mask40[1][:, 1] / bare40[1][:, 1]))
    delta_n = -C * mask_phase / (2*np.pi*f*1e9*.040)
    mask_eps = (np.sqrt(extracted['40 mm']['eps']) + delta_n) ** 2
    mask_extra_loss = -db(mask40[1][:, 1] / bare40[1][:, 1])

    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True, constrained_layout=True)
    summary, rows = {}, []
    for label, stem, suffix, length, color in CASES:
        transmission, reflection = data[label]
        axes[0].plot(f, db(transmission[1])[:, 1], color=color, lw=1, label=label)
        axes[1].plot(f, db(reflection[1])[:, 0], color=color, lw=1, label=label)
        gamma = reflection[1][:, 0]
        zin = 50*(1+gamma)/(1-gamma)
        s21db, s11db = db(transmission[1])[:, 1], db(gamma)
        values = dict(S21_median_dB=float(np.median(s21db)), S21_min_dB=float(s21db.min()),
                      S21_max_dB=float(s21db.max()), S11_worst_dB=float(s11db.max()),
                      Zin_R_min_ohm=float(zin.real.min()), Zin_R_max_ohm=float(zin.real.max()),
                      Zin_X_min_ohm=float(zin.imag.min()), Zin_X_max_ohm=float(zin.imag.max()))
        summary[label] = values
        rows.append(f'| {label} | {np.median(s21db):.2f} | {s11db.max():.1f} |')
    style(axes[0], 'S21 (dB)')
    style(axes[1], 'S11 (dB)')
    fig.suptitle('Revision B line coupons — same calibration session\n'
                 'S11: external termination; S21: NanoVNA port 2; raw samples')
    fig.savefig(OUT/'responses.png', dpi=170)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
    for label, color in [('40 mm', '#d55e00'), ('90 mm', '#009e73')]:
        e = extracted[label]
        axes[0].plot(f, e['eps'], color=color, label=label+' / 10 mm')
        axes[1].plot(f, e['attenuation'], color=color, label=label+' / 10 mm')
        summary[label]['phase_extraction'] = {
            'eps_phase_median': float(np.median(e['eps'])),
            'eps_phase_min': float(e['eps'].min()), 'eps_phase_max': float(e['eps'].max()),
            'differential_delay_ps': e['delay_ps'], 'eps_group': e['eps_group'],
            'phase_fit_rms_deg': e['phase_fit_rms_deg'],
            'phase_branch_choice': branches[label],
        }
    axes[0].plot(f, mask_eps, color='#8822aa', label='40 mm masked (paired estimate)')
    axes[0].axhline(model2d['eps_eff'], color='#222222', ls='--', lw=1.5,
                    label=f'2-D bare strip: {model2d["eps_eff"]:.3f}')
    style(axes[0], 'Phase-derived effective permittivity')
    style(axes[1], 'Apparent added loss (dB/mm)')
    fig.suptitle('Measured effective permittivity versus the 2-D simulation; differential loss\n'
                 'Dashed black line: bare-strip 2-D prediction; coloured curves: measurements')
    fig.savefig(OUT/'extraction.png', dpi=170)
    plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(11, 6), sharex=True,
                             constrained_layout=True)
    for column, (label, color) in enumerate([('40 mm', '#d55e00'), ('90 mm', '#009e73')]):
        e = extracted[label]
        phase_deg, fit_deg = np.rad2deg(e['phase']), np.rad2deg(e['fit'])
        axes[0, column].plot(f, phase_deg, color=color, lw=1.2,
                             label='Measured phase ratio (1,001 samples)')
        axes[0, column].plot(f, fit_deg, color='#222222', ls='--', lw=1.6,
                             label='Least-squares straight line')
        axes[0, column].set_title(
            f'{label} / 10 mm: slope {-0.36*e["delay_ps"]:.2f} deg/GHz; '
            f'delay {e["delay_ps"]:.1f} ps')
        axes[1, column].plot(f, phase_deg-fit_deg, color=color, lw=1,
                             label=f'Fit residual; RMS {e["phase_fit_rms_deg"]:.2f} deg')
        axes[1, column].axhline(0, color='#777777', ls=':', lw=1)
        style(axes[0, column], 'Differential phase (deg)')
        style(axes[1, column], 'Measured minus fitted phase (deg)')
    fig.suptitle('Phase versus frequency: separate fits for the two line pairs\n'
                 'Each fit uses all 1,001 samples; intercept is free')
    fig.savefig(OUT/'phase_fits.png', dpi=170)
    plt.close(fig)

    measured_gamma = data['10 mm'][1][1][:, 0]
    measured_z = 50*(1+measured_gamma)/(1-measured_gamma)
    sim_gamma = sim_s[:, 0]
    sim_z = 50*(1+sim_gamma)/(1-sim_gamma)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
    for ax, component in zip(axes, ('real', 'imag')):
        ax.plot(f, getattr(measured_z, component), color='#0072b2', lw=1.1,
                label='10 mm measured; external termination')
        ax.plot(sim_f, getattr(sim_z, component), 'o-', color='#d55e00', ms=4, lw=1.6,
                label='10 mm 3-D FEM; matched output port')
    axes[0].axhline(50, color='#777777', ls=':', lw=1)
    axes[1].axhline(0, color='#777777', ls=':', lw=1)
    style(axes[0], 'Re(input impedance), ohm')
    style(axes[1], 'Im(input impedance), ohm')
    fig.suptitle('10 mm coupon input impedance: measurement versus saved 3-D FEM\n'
                 'Both include launches; raw reference planes, no fitted phase correction')
    fig.savefig(OUT/'input_impedance.png', dpi=170)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11, 5.5), constrained_layout=True)
    for ax, zoom in zip(axes, [False, True]):
        smith_grid(ax, zoom)
        for freq, gamma, color, label in [
            (f, measured_gamma, '#0072b2', 'Measured; external termination'),
            (sim_f, sim_gamma, '#d55e00', 'Saved 3-D FEM; 11 solved points')]:
            ax.plot(gamma.real, gamma.imag, color=color,
                    lw=.9 if len(gamma)>11 else 1.5,
                    marker=None if len(gamma)>11 else 'o', ms=3, label=label)
            if zoom:
                for key, marker, offset in [(5.3, '^', (7, 5)),
                                             (5.8, '*', (7, 7)),
                                             (6.3, 's', (7, -13))]:
                    index = int(np.argmin(abs(freq-key)))
                    g = gamma[index]
                    if len(gamma)>11:
                        offset = {5.3: (12, 15), 5.8: (0, 65), 6.3: (-48, 15)}[key]
                    ax.plot(g.real, g.imag, marker, color=color, ms=12 if key==5.8 else 5,
                            markerfacecolor='white' if key==5.8 else color,
                            markeredgewidth=1.3, zorder=5)
                    ax.annotate(f'{key:g} GHz', (g.real, g.imag), xytext=offset,
                                textcoords='offset points', color=color, fontsize=9)
                for lo, hi in [(5.45, 5.55), (6.0, 6.1)]:
                    a = complex(np.interp(lo, freq, gamma.real), np.interp(lo, freq, gamma.imag))
                    b = complex(np.interp(hi, freq, gamma.real), np.interp(hi, freq, gamma.imag))
                    ax.annotate('', (b.real, b.imag), (a.real, a.imag),
                                arrowprops=dict(arrowstyle='->', color=color, lw=1.8, mutation_scale=15))
        ax.set_title('Full Smith chart' if not zoom else 'Enlarged near the 50-ohm centre')
    axes[0].legend(loc='lower center', fontsize=9)
    fig.suptitle('10 mm coupon: measured versus simulated S11\n'
                 '50-ohm normalization; arrows: increasing frequency; star: 5.8 GHz')
    fig.savefig(OUT/'smith_chart.png', dpi=170)
    plt.close(fig)

    e40, e90 = extracted['40 mm'], extracted['90 mm']
    mask_center_phase = float(np.interp(5.8, f, mask_phase)*180/np.pi)
    mask_center_eps = float(np.interp(5.8, f, mask_eps))
    bare_center_eps = float(np.interp(5.8, f, e40['eps']))
    summary['mask'] = dict(added_phase_at_5p8GHz_deg=mask_center_phase,
                           eps_phase_at_5p8GHz=mask_center_eps,
                           bare_eps_phase_at_5p8GHz=bare_center_eps,
                           extra_loss_median_dB=float(np.median(mask_extra_loss)),
                           extra_loss_min_dB=float(mask_extra_loss.min()),
                           extra_loss_max_dB=float(mask_extra_loss.max()))
    measured_center_z = complex(np.interp(5.8, f, measured_z.real), np.interp(5.8, f, measured_z.imag))
    sim_center_z = complex(sim_z[5])
    eps_relative_difference = (np.median(e90['eps'])/model2d['eps_eff']-1)*100
    summary['simulation_comparison'] = dict(
        cross_section_2d=cross, coupon_3d_file=SIM_NARROW,
        measured_90_10_eps_difference_percent=float(eps_relative_difference),
        measured_Zin_5p8GHz_ohm=[measured_center_z.real, measured_center_z.imag],
        simulated_Zin_5p8GHz_ohm=[sim_center_z.real, sim_center_z.imag],
        simulated_Zin_R_range_ohm=[float(sim_z.real.min()), float(sim_z.real.max())],
        simulated_Zin_X_range_ohm=[float(sim_z.imag.min()), float(sim_z.imag.max())])
    sources.extend([cross_file, sim_file])
    summary['source_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    (OUT/'metrics.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
    source_rows = []
    for i, (label, *_rest) in enumerate(CASES):
        a,b = sources[2*i:2*i+2]
        source_rows.append(f'| {label} | [S21](measurements/{a.name}) | [S11](measurements/{b.name}) |')
    text = rf'''# Line parameters and solder mask: revision B

**The measured wave travels slightly slower than our 2-D model predicts.** Measured εeff is **{np.median(e40['eps']):.2f}–{np.median(e90['eps']):.2f}**, compared with **{model2d['eps_eff']:.2f} in simulation**. The short coupon matches 50 Ω well, but the 3-D model does not reproduce its measured impedance exactly. Solder mask adds delay.

## Measurements

We compared the **10, 40 and 90 mm bare lines**, plus the **40 mm masked line**, over **5.3–6.3 GHz**, using the same calibration. S11 was measured with an external termination at the far end. S21 was measured with NanoVNA port 2 connected.

The plots use the remeasured 10 mm reference and the replacement masked-line S21. Older measurements ending in _0 are excluded.

![Measured S21 and externally terminated S11](assets/line_parameters/responses.png)

| Line | Median S21, dB | Worst S11, dB |
|---|---:|---:|
{chr(10).join(rows)}

## Effective permittivity and line loss

**εeff tells us how slowly the wave travels along the microstrip.** It includes the fields in both the PCB and the air, so it is not the PCB material's bulk Dk.

![Measured effective permittivity and added line loss](assets/line_parameters/extraction.png)

**Left:** the coloured curves come from the measurements. The black dashed line is our 2-D simulation, **εeff = {model2d['eps_eff']:.3f}**. The 40/10 mm pair gives **{np.median(e40['eps']):.2f}**, and the 90/10 mm pair gives **{np.median(e90['eps']):.2f}**. Ideally they would agree. I would use the longer pair as the better estimate because the same launch error has less influence over 80 mm than over 30 mm. Its value is **{eps_relative_difference:.1f}% above simulation**.

**Right:** dividing the longer line's S21 by the short line's S21 estimates the loss of the extra track. The 90/10 mm pair gives a median of **{np.median(e90['attenuation'])*10:.2f} dB/cm**; 40/10 mm gives **{np.median(e40['attenuation'])*10:.2f} dB/cm**. The difference and ripple mean that launch and measurement errors have not cancelled completely. These are estimates of total line loss, not dielectric loss alone.

### How εeff is calculated

A wave loses amplitude and accumulates phase as it travels:

$$
V(z)=V_0e^{{-(\alpha+j\beta)z}},\qquad
S_{{21}}(\ell)\approx A(f)e^{{-\gamma\ell}}.
$$

Here $\alpha$ describes attenuation, $\beta$ describes phase change per metre, and $A(f)$ represents the two launches. If the launches are the same on both coupons, dividing their transmissions approximately removes $A(f)$:

$$
R=\frac{{S_{{21,L}}}}{{S_{{21,S}}}}\approx e^{{-\gamma\Delta\ell}},\qquad
\phi=\operatorname{{unwrap}}\arg R-2\pi N,\qquad
\beta\approx-\frac{{\phi}}{{\Delta\ell}}.
$$

The extra phase $\phi$ belongs to the extra length $\Delta\ell$. From $v_p=\omega/\beta=c/\sqrt{{\varepsilon_{{\mathrm{{eff}}}}}}$, we obtain:

$$
\boxed{{\varepsilon_{{\mathrm{{eff}}}}(f)\approx
\left(\frac{{-c\phi}}{{2\pi f\Delta\ell}}\right)^2}},\qquad
\alpha_{{\mathrm{{dB/mm}}}}\approx\frac{{-20\log_{{10}}|R|}}{{1000\Delta\ell}}
\quad(\Delta\ell\text{{ in m}}).
$$

The PCB track lengths are **14.8, 44.8 and 94.8 mm**, so the extra lengths are **30 and 80 mm**.

**How we choose N.** Start at the first measured frequency, **5.3 GHz**. Our 2-D simulation predicts εeff ≈ {model2d['eps_eff']:.2f}, giving an approximate wavelength:

$$
\lambda_g\approx\frac{{c}}{{f\sqrt{{\varepsilon_{{eff,2D}}}}}}
=\frac{{299\,792\,458}}{{5.3\times10^9\sqrt{{{model2d['eps_eff']:.3f}}}}}
\approx {wavelength_mm:.1f}\ \mathrm{{mm}}.
$$

We compare **S21 phase at 5.3 GHz for two different coupons**. The phase of their ratio is the difference between the two measured phases, wrapped into −180°…+180°:

$$
\phi_{{wrapped}}=\arg\left(\frac{{S_{{21,L}}}}{{S_{{21,10}}}}\right)
=\operatorname{{wrap}}_{{[-180^\circ,180^\circ]}}
\left(\arg S_{{21,L}}-\arg S_{{21,10}}\right).
$$

- **40/10 mm:** the measured S21 phases are **{branches['40 mm']['long_S21_phase_deg']:+.1f}° for 40 mm** and **{branches['40 mm']['short_S21_phase_deg']:+.1f}° for 10 mm**. Their difference is **{branches['40 mm']['long_S21_phase_deg']:+.1f}° − ({branches['40 mm']['short_S21_phase_deg']:+.1f}°) = {branches['40 mm']['initial_wrapped_phase_deg']:+.1f}°**. The extra 30 mm is about **{30/wavelength_mm:.2f} wavelengths**, so we expect about **{branches['40 mm']['expected_phase_deg']:.0f}°** of extra phase. Subtracting one turn from the measured difference gives **{branches['40 mm']['initial_wrapped_phase_deg']:+.1f}° − 360° = {branches['40 mm']['corrected_phase_deg']:.1f}°**. Therefore **N=1**.
- **90/10 mm:** the measured S21 phases are **{branches['90 mm']['long_S21_phase_deg']:+.1f}° for 90 mm** and **{branches['90 mm']['short_S21_phase_deg']:+.1f}° for 10 mm**. Their difference is **{branches['90 mm']['long_S21_phase_deg']-branches['90 mm']['short_S21_phase_deg']:.1f}°**, which wraps to **{branches['90 mm']['initial_wrapped_phase_deg']:+.1f}°**. The extra 80 mm is about **{80/wavelength_mm:.2f} wavelengths**, so we expect about **{branches['90 mm']['expected_phase_deg']:.0f}°**. Subtracting three turns from the wrapped difference gives **{branches['90 mm']['initial_wrapped_phase_deg']:+.1f}° − 1080° = {branches['90 mm']['corrected_phase_deg']:.1f}°**. Therefore **N=3**.

N counts the turns missing from the reported angle; it is **not** the integer part of length/wavelength. We choose it once at 5.3 GHz, then unwrap the rest of the sweep continuously. The 2-D prediction selects the whole-turn correction only; it does not force the measured εeff to equal the simulated value. A wrong turn count or unequal launches would bias the result. This is a simple line-ratio estimate, not a full [multiline TRL calibration](https://scikit-rf-official.readthedocs.io/en/v2.0.0/examples/metrology/Multiline%20TRL.html).

### What the fitted line means

For each pair, we fit a straight line through **all 1,001 phase samples**:

$$
\phi(f)\approx a+b(f-5.8\,\mathrm{{GHz}}),\qquad
\tau=-\frac{{b}}{{2\pi}},\qquad
n_g^2=\left(\frac{{c\tau}}{{\Delta\ell}}\right)^2.
$$

For the delay equation, $b$ is in radians/Hz. The intercept $a$ is free. **This fit checks the delay; the εeff curves above use measured phase directly.** The lower plots show what the straight line misses.

![Measured phase, straight-line fits and their errors](assets/line_parameters/phase_fits.png)

| Pair | Median phase εeff | Phase εeff range | Added delay, ps | Group-index squared |
|---|---:|---:|---:|---:|
| 40 / 10 mm | {np.median(e40['eps']):.2f} | {e40['eps'].min():.2f}–{e40['eps'].max():.2f} | {e40['delay_ps']:.1f} | {e40['eps_group']:.2f} |
| 90 / 10 mm | {np.median(e90['eps']):.2f} | {e90['eps'].min():.2f}–{e90['eps'].max():.2f} | {e90['delay_ps']:.1f} | {e90['eps_group']:.2f} |

The last column comes from the slope. Phase and group speed can differ when speed changes with frequency. Measurement errors also affect the slope, so the two estimates should not be treated as interchangeable.

## Impedance: measurement versus simulation

There are two different quantities here:

- **$Z_c$:** the characteristic impedance of the uniform track.
- **$Z_{{in}}$:** the impedance seen by the VNA when looking into the whole coupon, including connectors, launches and the far-end load.

Our existing [2-D solver](https://github.com/olddudealex/funrad/blob/main/Frontend/emerge/simulation/coupled_2d.py) predicts **$Z_c={model2d['Zc_ohm']:.2f}$ Ω** and **$\varepsilon_{{eff}}={model2d['eps_eff']:.3f}$** for the bare track. It calculates capacitance once with the PCB dielectric, $C'$, and once with air, $C'_{{air}}$:

$$
\varepsilon_{{eff}}=\frac{{C'}}{{C'_{{air}}}},\qquad
Z_c=\frac{{1}}{{c\sqrt{{C'C'_{{air}}}}}}.
$$

Inputs: **370 µm width, 35 µm copper, 210.4 µm dielectric, εr=4.5, no mask**. This is the same 2-D method used earlier, now applied to one coupon line. It models the straight track above L2; it does not model the launches or frequency dispersion. The selected grid is 5 µm, with 2.5 mm side padding and 4 mm air above the strip. [Grid and box checks](assets/line_parameters/metrics.json) are saved with the results.

To compare the complete coupon, we convert both measured and simulated S11 to input impedance:

$$
\Gamma=\frac{{Z_{{in}}-50}}{{Z_{{in}}+50}}
\quad\Rightarrow\quad
\boxed{{Z_{{in}}=50\frac{{1+S_{{11}}}}{{1-S_{{11}}}}}}.
$$

![10 mm measured and simulated input impedance](assets/line_parameters/input_impedance.png)

At **5.8 GHz**, the measurement gives **{measured_center_z.real:.1f}{measured_center_z.imag:+.1f}j Ω**, while simulation gives **{sim_center_z.real:.1f}{sim_center_z.imag:+.1f}j Ω**. The measurement is closer to 50 Ω. The model does not predict the measured curve accurately.

![Measured and simulated S11 on a Smith chart](assets/line_parameters/smith_chart.png)

The Smith chart shows the same S11 data. **Its centre is a perfect 50 Ω match.** The right panel is enlarged; arrows point towards higher frequency, and stars mark 5.8 GHz.

We reuse only the saved **10 mm, 2.8 × 4.8 mm L2-cutout, finer-mesh 3-D simulation**. Its connector and solder geometry are simplified. Also, the measured and simulated reference planes—the physical points where S11 is defined—have not been aligned exactly. Both can affect this comparison; no phase adjustment was made to force agreement.

The measured εeff helps check wave speed. **It does not give us a measured $Z_c$.** The measured $Z_{{in}}$ above should therefore not be read as the track's characteristic impedance.

## Solder mask

The masked 40 mm line adds **{abs(mask_center_phase):.1f}° of phase lag at 5.8 GHz**: the wave travels more slowly. Assuming 40 mm of changed mask coverage and equal launches,

$$
\Delta n=\frac{{-c\arg(S_{{21,m}}/S_{{21,b}})}}{{2\pi f\,0.040}},\qquad
\varepsilon_{{eff,m}}\approx
\left(\sqrt{{\varepsilon_{{eff,b}}}}+\Delta n\right)^2.
$$

This gives **εeff {bare_center_eps:.2f} → {mask_center_eps:.2f} at 5.8 GHz**. It describes the coated microstrip, not the mask material's own Dk. The median extra loss is **{np.median(mask_extra_loss):.2f} dB**, with differences from **{mask_extra_loss.min():.2f} to {mask_extra_loss.max():.2f} dB** across the band. Some values are negative, so this measurement cannot reliably separate the mask's added loss from mismatch and coupon differences.

## Files and reproduction

| Coupon | S21 | S11 with external termination |
|---|---|---|
{chr(10).join(source_rows)}

[Calculated results and file hashes](assets/line_parameters/metrics.json) · [10 mm 3-D simulation](08_MESH_REFINEMENT.md) · [Coupon overview](index.md)

From Frontend/emerge, use the project venv to run python -m coupon_10mm.report_line_parameters. If the 2-D reference needs rebuilding, first run python -m coupon_10mm.line_cross_section.
'''
    (REPORTS/'12_LINE_PARAMETERS_AND_MASK.md').write_text(text, encoding='utf-8')
    print('Wrote line-parameter report, five figures, and metrics.json.')


if __name__ == '__main__':
    main()

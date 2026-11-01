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

from .report_paths import MEASUREMENTS, REPORTS
from .report_revb_measurements import load, db

C = 299792458.0
OUT = REPORTS / 'assets/line_parameters'
PREFIX = 'coupon_revB_7628_horizontal_'
CASES = [
    ('10 mm', '10mm', '100Mhz_6.5GHz_nanoVNA.s2p', .010, '#0072b2'),
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


def main():
    OUT.mkdir(parents=True, exist_ok=True)
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
    # Explicit phase branches: the near-constant quasi-TEM index is ~1.8.
    # Adjacent branches and group-delay results are recorded as diagnostics.
    extracted = {label: derive(data[label][0], short, length, turns)
                 for label, length, turns in [('40 mm', .030, 1), ('90 mm', .080, 3)]}
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
        rows.append(f'| {label} | {np.median(s21db):.2f} | {s11db.max():.1f} | '
                    f'{zin.real.min():.1f}…{zin.real.max():.1f} | '
                    f'{zin.imag.min():.1f}…{zin.imag.max():.1f} |')
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
            'phase_turns_subtracted': 1 if label == '40 mm' else 3,
        }
    axes[0].plot(f, mask_eps, color='#8822aa', label='40 mm masked (paired estimate)')
    style(axes[0], 'Phase-derived effective permittivity')
    style(axes[1], 'Apparent added loss (dB/mm)')
    fig.suptitle('Differential estimates: nominally identical launches cancel approximately\n'
                 'Branch choice assumes weakly dispersive microstrip; no smoothing')
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

    fig, axes = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
    for label, stem, suffix, length, color in CASES:
        g = data[label][1][1][:, 0]
        z = 50*(1+g)/(1-g)
        axes[0].plot(f, z.real, color=color, label=label)
        axes[1].plot(f, z.imag, color=color, label=label)
    axes[0].axhline(50, color='#777777', ls=':', lw=1)
    axes[1].axhline(0, color='#777777', ls=':', lw=1)
    style(axes[0], 'Re(input impedance), ohm')
    style(axes[1], 'Im(input impedance), ohm')
    fig.suptitle('Input impedance of externally terminated assemblies — not line Zc')
    fig.savefig(OUT/'input_impedance.png', dpi=170)
    plt.close(fig)

    e40, e90 = extracted['40 mm'], extracted['90 mm']
    u = .370/.2104
    fu = 6+(2*np.pi-6)*np.exp(-(30.666/u)**.7528)
    zair = 376.730313668/(2*np.pi)*np.log(fu/u+np.sqrt(1+(2/u)**2))
    zestimate = zair/np.sqrt(np.median(e90['eps']))
    mask_center_phase = float(np.interp(5.8, f, mask_phase)*180/np.pi)
    mask_center_eps = float(np.interp(5.8, f, mask_eps))
    bare_center_eps = float(np.interp(5.8, f, e40['eps']))
    summary['mask'] = dict(added_phase_at_5p8GHz_deg=mask_center_phase,
                           eps_phase_at_5p8GHz=mask_center_eps,
                           bare_eps_phase_at_5p8GHz=bare_center_eps,
                           extra_loss_median_dB=float(np.median(mask_extra_loss)),
                           extra_loss_min_dB=float(mask_extra_loss.min()),
                           extra_loss_max_dB=float(mask_extra_loss.max()))
    summary['thin_strip_Zc_estimate_ohm'] = float(zestimate)
    summary['source_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    (OUT/'metrics.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
    source_rows = []
    for i, (label, *_rest) in enumerate(CASES):
        a,b = sources[2*i:2*i+2]
        source_rows.append(f'| {label} | [S21](measurements/{a.name}) | [S11](measurements/{b.name}) |')
    text = rf'''# Line parameters and solder mask: revision B

**Result:** unmasked effective permittivity is approximately **{np.median(e40['eps']):.2f}–{np.median(e90['eps']):.2f}**. Prefer the 90/10 mm estimate: its larger length difference reduces launch sensitivity. Mask adds delay. Characteristic impedance is **not uniquely extracted**; a nominal-geometry thin-strip estimate is **about {zestimate:.0f} Ω**.

## Measurements

Current line measurements use the same calibration per the measurement record; the **40 mm masked S21 was remeasured to replace a discontinuous trace**. **S11 uses external terminations; S21 uses NanoVNA port 2.** The new 10 mm S21 filename says “100Mhz_6.5GHz” but contains **5.3–6.3 GHz**. All current inputs are linked below without the _0 suffix; older 10 mm _0 measurements are excluded.

![Line responses](assets/line_parameters/responses.png)

| Line | Median S21, dB | Worst S11, dB | Re(Zin), Ω | Im(Zin), Ω |
|---|---:|---:|---:|---:|
{chr(10).join(rows)}

## Effective Dk: derivation

A forward wave is $V(z)=V_0e^{{-(\alpha+j\beta)z}}$. For approximately matched lines with equal launches, $S_{{21}}(\ell)\approx A(f)e^{{-\gamma\ell}}$. Dividing cancels the common launch factor:

$$
R=\frac{{S_{{21,L}}}}{{S_{{21,S}}}}\approx e^{{-\gamma\Delta\ell}},\qquad
\phi=\operatorname{{unwrap}}\arg R-2\pi N,\qquad
\beta\approx-\frac{{\phi}}{{\Delta\ell}}.
$$

Since $v_p=\omega/\beta=c/\sqrt{{\varepsilon_{{\mathrm{{eff}}}}}}$,

$$
\boxed{{\varepsilon_{{\mathrm{{eff}}}}(f)\approx
\left(\frac{{-c\phi}}{{2\pi f\Delta\ell}}\right)^2}},\qquad
\alpha_{{\mathrm{{dB/mm}}}}\approx\frac{{-20\log_{{10}}|R|}}{{1000\Delta\ell}}
\quad(\Delta\ell\text{{ in m}}).
$$

Use $\Delta\ell=30/80$ mm: PCB track lengths are **14.8/44.8/94.8 mm** with equal launch regions. Phase branches **N=1/3** give a weakly dispersive microstrip index near 1.8, broadly consistent with phase-slope delay. This branch choice is an assumption. The ratio method approximates launch cancellation; **it is not multiline TRL**. [Propagation/phase relation](https://scikit-rf-official.readthedocs.io/en/v2.0.0/examples/metrology/Multiline%20TRL.html).

![Differential extraction](assets/line_parameters/extraction.png)

| Pair | Median phase εeff | Phase εeff range | Differential delay, ps | Group-index squared |
|---|---:|---:|---:|---:|
| 40 / 10 mm | {np.median(e40['eps']):.2f} | {e40['eps'].min():.2f}–{e40['eps'].max():.2f} | {e40['delay_ps']:.1f} | {e40['eps_group']:.2f} |
| 90 / 10 mm | {np.median(e90['eps']):.2f} | {e90['eps'].min():.2f}–{e90['eps'].max():.2f} | {e90['delay_ps']:.1f} | {e90['eps_group']:.2f} |

**What is fitted?** For each line pair separately, an unweighted least-squares straight line $\phi(f)\approx a+b(f-5.8\,\mathrm{{GHz}})$ uses **all 1,001 measured frequency samples** over 5.3–6.3 GHz, with a free intercept. This is not a fit through the three coupon lengths. The figure shows the measured phase ratios, fitted lines and residuals.

![Phase fits and residuals](assets/line_parameters/phase_fits.png)

The fitted slope $b$ gives $\tau=-b/(2\pi)$ (with $f$ in Hz) and $n_g^2=(c\tau/\Delta\ell)^2$. It supplies the delay/group-index columns; the phase εeff curves above use the measured phase directly. **Group and phase indices differ under dispersion**; their disagreement and pair spread expose uncertainty. Effective ε includes air fields: **it is not bulk substrate Dk**. Added loss includes residual mismatch, not just dielectric loss.

## Impedance

From $\Gamma=(Z_{{in}}-50)/(Z_{{in}}+50)$,

$$
\boxed{{Z_{{in}}=50\frac{{1+S_{{11}}}}{{1-S_{{11}}}}}}.
$$

This is the **terminated assembly's input impedance**, including launches and load, not uniform-line $Z_c$. Separately loaded S11/S21 and zero-filled S12/S22 do not provide a full two-port matrix for unique de-embedding.

For a geometry estimate, $\beta=\omega\sqrt{{L'C'}}$, $Z_c=\sqrt{{L'/C'}}$, $L'\approx L'_{{air}}$ and $C'/C'_{{air}}\approx\varepsilon_{{eff}}$ give **$Z_c\approx Z_{{air}}/\sqrt{{\varepsilon_{{eff}}}}$**. The [Hammerstad–Jensen air-line model](https://qucs.sourceforge.net/tech/node75.html) gives

$$
u=\frac wh,\quad F=6+(2\pi-6)e^{{-(30.666/u)^{{0.7528}}}},\qquad
Z_{{air}}\approx\frac{{376.73}}{{2\pi}}\ln\left[\frac Fu+\sqrt{{1+(2/u)^2}}\right].
$$

With $w=0.370$ mm and $h=0.2104$ mm, $Z_{{air}}\approx{zair:.1f}$ Ω and $Z_c\approx{zestimate:.1f}$ Ω (90/10 phase estimate). **This neglects 35 µm copper thickness, etch shape, nearby ground and dispersion; it is not measured impedance.**

![Terminated input impedances](assets/line_parameters/input_impedance.png)

## Solder mask

The masked 40 mm coupon adds **{abs(mask_center_phase):.1f}° phase lag at 5.8 GHz**. Assuming 40 mm changed coverage and equal launches, $\Delta n=-c\arg(S_{{21,m}}/S_{{21,b}})/(2\pi f\,0.040)$ and $\varepsilon_{{eff,m}}\approx(\sqrt{{\varepsilon_{{eff,b}}}}+\Delta n)^2$ give **{bare_center_eps:.2f} → {mask_center_eps:.2f}** at 5.8 GHz. This indicates dielectric loading, not the mask's own Dk. Median extra loss is **{np.median(mask_extra_loss):.2f} dB**, but differences span **{mask_extra_loss.min():.2f}…{mask_extra_loss.max():.2f} dB**. Mask loss and impedance shift are not isolated from mismatch/coupon variation.

## Data

| Coupon | Transmission | Externally terminated reflection |
|---|---|---|
{chr(10).join(source_rows)}

[Metrics and input hashes](assets/line_parameters/metrics.json). Regenerate from Frontend/emerge with the project venv: python -m coupon_10mm.report_line_parameters. [Overview](index.md).
'''
    (REPORTS/'12_LINE_PARAMETERS_AND_MASK.md').write_text(text, encoding='utf-8')
    print('Wrote line-parameter report, four figures, and metrics.json.')


if __name__ == '__main__':
    main()

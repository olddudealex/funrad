"""Compare the original PCB + BWSMA connector sweep with measured S11/S21."""
from .report_paths import REPORTS, write_report
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .compare import HERE, MEASUREMENTS, measured, db

OUT=HERE/'preview_coax'


def main():
    data=np.load(HERE/'result_coax_intact.npz')
    meta=json.loads((HERE/'result_coax_intact.json').read_text(encoding='utf-8'))
    f=data['f'].reshape(-1);s=data['Smat50'];z=data['Z0']
    assert meta['status']=='completed' and s.shape==(len(f),2,2) and np.all(np.isfinite(s))
    mf,m11,m21=measured(MEASUREMENTS/'coupon_7628_horizontal_10mm.s2p')
    old=np.load(HERE/'result_2layer.npz')
    m21_at_f=np.interp(f,mf,db(m21))
    m11_at_f=np.interp(f,mf,db(m11))
    checks=dict(frequencies=len(f),nodes=meta['nodes'],tetrahedra=meta['tetrahedra'],
                modal_Z0_real_range_ohm=[float(z.real.min()),float(z.real.max())],
                max_modal_Z0_imag_ohm=float(abs(z.imag).max()),
                max_reciprocity_error=float(abs(s[:,1,0]-s[:,0,1]).max()),
                max_symmetry_error=float(abs(s[:,0,0]-s[:,1,1]).max()),
                max_singular_value=float(np.linalg.svd(s,compute_uv=False).max()),
                mean_abs_S21_error_dB=float(np.mean(abs(db(s[:,1,0])-m21_at_f))),
                prior_PCB_mean_abs_S21_error_dB=float(np.mean(abs(db(old['Smat'][:,1,0])-m21_at_f))),
                sampled_S11_minimum_GHz=float(f[np.argmin(abs(s[:,0,0]))]/1e9))
    rows=[]
    for k,freq in enumerate(f):
        rows.append(dict(f_GHz=float(freq/1e9),S11_dB=float(db(s[k,0,0])),
            S21_dB=float(db(s[k,1,0])),measured_S11_dB=float(m11_at_f[k]),
            measured_S21_dB=float(m21_at_f[k]),
            reflected_power=float(abs(s[k,0,0])**2),transmitted_power=float(abs(s[k,1,0])**2),
            remaining_power=float(1-abs(s[k,0,0])**2-abs(s[k,1,0])**2)))
    checks['rows']=rows
    (OUT/'comparison_metrics.json').write_text(json.dumps(checks,indent=2)+'\n',encoding='utf-8')
    for zoom in (False,True):
        fig,axes=plt.subplots(2,1,figsize=(10,8),sharex=True,constrained_layout=True)
        for ax,i,j,mv in [(axes[0],1,0,m21),(axes[1],0,0,m11)]:
            ax.plot(mf/1e9,db(mv),color='#0072b2',lw=1.5,label='Measured: 10 mm coupon, original connectors')
            ax.plot(f/1e9,db(s[:,i,j]),'o-',color='#009e73',lw=2,ms=4,
                    label='PCB + simplified BWSMA: coax ports, 50 ohm')
            ax.plot(old['f']/1e9,db(old['Smat'][:,i,j]),'x--',color='#8654a0',lw=1.1,ms=4,
                    label='Earlier PCB-only lumped-port reference')
            ax.grid(alpha=.25);ax.legend(fontsize=8,loc='lower left')
            ax.set_xlim((2.1,3.0) if zoom else (0,6.1))
        axes[0].set(ylabel='S21 (dB)',ylim=(-1.5,.1) if zoom else (-14,1))
        axes[1].set(ylabel='S11 (dB)',xlabel='Frequency (GHz)',ylim=(-50,1))
        fig.suptitle('Original PCB: no ground openings; simplified BWSMA connectors\n'
                     '20 directly solved frequencies; first-order FEM; 370,867 tetrahedra')
        fig.savefig(OUT/('coax_detail_2p6GHz.png' if zoom else 'coax_vs_measurement.png'),dpi=170,bbox_inches='tight')
        plt.close(fig)
    fig,axes=plt.subplots(2,1,figsize=(9,6),sharex=True,constrained_layout=True)
    z=z.reshape(len(f),2)
    for p in (0,1):
        axes[0].plot(f/1e9,z[:,p].real,'o-',ms=3,label=f'P{p+1}')
    axes[0].axhline(50,color='gray',ls='--',lw=1,label='Analytical design value')
    axes[0].set(ylabel='Native modal impedance (ohm)');axes[0].legend()
    for label,values in [('Reflected',abs(s[:,0,0])**2),('Transmitted',abs(s[:,1,0])**2),
                         ('Remaining: loss / radiation / numerical',1-abs(s[:,0,0])**2-abs(s[:,1,0])**2)]:
        axes[1].plot(f/1e9,values,'o-',ms=3,label=label)
    axes[1].set(ylabel='Fraction of incident power',xlabel='Frequency (GHz)',ylim=(-.03,1.03))
    axes[1].legend(fontsize=8)
    for ax in axes:ax.grid(alpha=.25)
    fig.suptitle('Coax port impedance and power balance (50-ohm S-matrix)')
    fig.savefig(OUT/'coax_ports_power.png',dpi=170);plt.close(fig)
    lines=['! Original 10 mm PCB, no ground openings; simplified BWSMA connectors included',
           '! Reference planes: coax annuli x=-8.10 and 28.26 mm; renormalized to 50 ohm',
           '! 20 directly solved frequencies; first-order FEM; no de-embedding','# Hz S RI R 50']
    for freq,m in zip(f,s):
        vals=[m[0,0],m[1,0],m[0,1],m[1,1]]
        lines.append(f'{freq:.12g} '+' '.join(f'{v.real:.12g} {v.imag:.12g}' for v in vals))
    (HERE/'result_coax_intact.s2p').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    table=['| GHz | Sim. S21, dB | Meas. S21, dB | Sim. S11, dB | Meas. S11, dB |',
           '|---:|---:|---:|---:|---:|']
    for r in rows:
        table.append(f'| {r["f_GHz"]:g} | {r["S21_dB"]:.2f} | {r["measured_S21_dB"]:.2f} | '
                     f'{r["S11_dB"]:.2f} | {r["measured_S11_dB"]:.2f} |')
    text=['# Original PCB with simplified BWSMA connectors: first control', '',
          '**One new completed sweep: 20 frequencies, original ground beneath both launch pads.** '
          'No ground openings, mesh variants or geometry optimization are included in this result.', '',
          '![S21 and S11 versus the original-connector measurement](preview_coax/coax_vs_measurement.png)', '',
          'The connector-inclusive model reproduces the broad response: low transmission loss '
          'below about 3 GHz, a reflection minimum around 2.7 GHz, and strong reflection / '
          'transmission reduction above 3 GHz. It does not reproduce the measured high-frequency '
          'ripples or both narrow measured reflection minima near 2.5–2.7 GHz. '
          'At 3.5–5 GHz it predicts roughly 1.4–1.8 dB more transmission than measured. '
          'Adding these connectors therefore preserves the main earlier diagnosis, but does '
          'not produce a substantially better overall measurement fit.', '',
          '## Configuration', '',
          'The approved [connector geometry](03_CONNECTOR_GEOMETRY.md) is unchanged. '
          'The model retains all four copper layers, 12 ground vias, original pads and tapers, '
          'and simplified connector signal pins, ground tails, shields and PTFE. '
          'First-order FEM uses 370,867 tetrahedra / 63,157 nodes. One EMerge `run_sweep()` '
          'solves 20 frequencies from 0.5 to 6 GHz; `frequency_groups=1` limits matrix memory. '
          f'The solve took {meta["solve_seconds"]/60:.1f} minutes.', '',
          'The reference planes are coax annuli at x=−8.10 and 28.26 mm. '
          'The connectors remain included: no connector or feed de-embedding is applied. '
          'The raw native S-matrix, modal impedances and propagation constants are preserved; '
          'the plotted matrix and Touchstone export use a common 50 Ω reference. '
          'The measured file is `coupon_7628_horizontal_10mm.s2p`; its S12/S22 zero placeholders '
          'are not used. The Amphenol measurement is not the target of this control.', '',
          '## Numerical comparison', '',
          f'Mean absolute S21 difference across the 20 sampled frequencies: '
          f'**{checks["mean_abs_S21_error_dB"]:.2f} dB**. '
          f'The earlier PCB-only lumped model gives {checks["prior_PCB_mean_abs_S21_error_dB"]:.2f} dB '
          'on the same frequencies. These are descriptive fit statistics, not estimated measurement '
          'or simulation uncertainties. Measurement amplitudes in dB are linearly interpolated '
          'onto the simulation frequencies for the table and this statistic.', '',
          *table, '',
          '![Detail around 2.6 GHz](preview_coax/coax_detail_2p6GHz.png)', '',
          'Markers are directly solved points; connecting segments are only a visual guide. '
          f'The lowest sampled simulated S11 occurs at {checks["sampled_S11_minimum_GHz"]:g} GHz. '
          'This is not a continuous-frequency search for the exact notch.', '',
          '## Port and consistency checks', '',
          '![Port impedance and power fractions](preview_coax/coax_ports_power.png)', '',
          f'Native modal Z0 spans {checks["modal_Z0_real_range_ohm"][0]:.3f}–'
          f'{checks["modal_Z0_real_range_ohm"][1]:.3f} Ω; maximum imaginary part magnitude '
          f'{checks["max_modal_Z0_imag_ohm"]:.3g} Ω. '
          f'Maximum |S21−S12|: {checks["max_reciprocity_error"]:.3g}; '
          f'maximum |S11−S22|: {checks["max_symmetry_error"]:.3g}; '
          f'maximum singular value: {checks["max_singular_value"]:.6f}.', '',
          'The remaining power fraction combines dielectric/conductor dissipation, radiation '
          'and numerical error; it is not an isolated estimate of FR4 loss. Reciprocity, symmetry '
          'and passivity checks do not establish mesh or air-box convergence. This is a first '
          'connector-inclusive control on one mesh, with the documented internal connector '
          'and solder-contact approximations.', '',
          'EMerge emitted overlap-priority warnings where PCB copper, via barrels, connector '
          'tails and ideal contact bridges overlap. Every listed contender in those warnings '
          'uses the same Copper material instance; these overlaps do not request conflicting '
          'dielectric/conductor properties. The CAD connectivity checks still find exactly '
          'one signal network and one separate ground network.', '',
          '## Files and reproduction', '',
          '- `result_coax_intact.npz`: raw/native and 50 Ω S, modal Z0 and β.',
          '- `result_coax_intact.json`: geometry, mesh and completed-sweep metadata.',
          '- `result_coax_intact.s2p`: connector-inclusive 50 Ω S-parameters.',
          '- `preview_coax/comparison_metrics.json`: all sampled comparison values and checks.', '',
          'From `C:\\Fun\\ToyRadar\\Frontend\\emerge`:', '', '```powershell',
          '.\\.venv\\Scripts\\python.exe -m coupon_10mm.connector_model --reuse-mesh --solve',
          '.\\.venv\\Scripts\\python.exe -m coupon_10mm.compare_coax', '```']
    write_report(REPORTS/'04_COAX_RESULTS.md', '\n'.join(text)+'\n')
    print(json.dumps({k:v for k,v in checks.items() if k!='rows'},indent=2))


if __name__=='__main__': main()

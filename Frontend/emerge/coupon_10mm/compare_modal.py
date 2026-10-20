"""Check the unchanged launch using L3/modal ports against the lumped reference."""
from .report_paths import REPORTS, write_report
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .compare import HERE, MEASUREMENTS, measured, db


def main():
    data=np.load(HERE/'result_3layer_modal.npz')
    old=np.load(HERE/'result_2layer.npz')
    meta=json.loads((HERE/'result_3layer_modal.json').read_text())
    f=data['f'].reshape(-1)
    s=data['Smat50_pad']
    z=data['Z0']
    if s.shape!=(len(f),2,2) or not np.all(np.isfinite(s)):
        raise ValueError('Invalid or incomplete modal result')
    if not np.allclose(f,old['f']):
        raise ValueError('Comparison requires the same frequency grid')
    out=HERE/'preview_3layer_modal'
    checks=dict(frequencies=len(f),tetrahedra=meta['tetrahedra'],
                modal_Z0_real_range=[float(z.real.min()),float(z.real.max())],
                max_reciprocity_error=float(abs(s[:,1,0]-s[:,0,1]).max()),
                max_symmetry_error=float(abs(s[:,0,0]-s[:,1,1]).max()),
                max_singular_value=float(np.linalg.svd(s,compute_uv=False).max()),
                max_S21_dB_difference_vs_lumped=float(abs(db(s[:,1,0])-db(old['Smat'][:,1,0])).max()),
                max_S11_complex_difference_vs_lumped=float(abs(s[:,0,0]-old['Smat'][:,0,0]).max()))
    (out/'comparison_metrics.json').write_text(json.dumps(checks,indent=2)+'\n')
    fig,axes=plt.subplots(2,1,figsize=(10,8),sharex=True,constrained_layout=True)
    for filename,label,color in [
        ('coupon_7628_horizontal_10mm.s2p','Measured: original connectors','#0072b2'),
        ('coupon_7628_horizontal_10mm_amphenol.s2p','Measured: Amphenol','#d55e00')]:
        mf,m11,m21=measured(MEASUREMENTS/filename)
        for ax,v in zip(axes,(m21,m11)):
            ax.plot(mf/1e9,db(v),color=color,lw=1.1,alpha=.8,label=label)
    for ax,i,j in [(axes[0],1,0),(axes[1],0,0)]:
        ax.plot(f/1e9,db(s[:,i,j]),'o-',color='#009e73',lw=2,ms=4,
                label='Top/L2/L3, modal ports: feeds removed, 50 Ω')
        ax.plot(f/1e9,db(old['Smat'][:,i,j]),'x--',color='#7b3294',lw=1.3,ms=4,
                label='Top/L2, lumped ports: Mesh 60 µm reference')
        ax.grid(alpha=.25)
        ax.legend(fontsize=8)
        ax.set_xlim(0,6.1)
    axes[0].set(ylabel='S21 (dB)',ylim=(-15,1))
    axes[1].set(ylabel='S11 (dB)',xlabel='Frequency (GHz)',ylim=(-50,1))
    fig.suptitle('Unchanged launch pads and tapers; intact L2 ground\n'
                 'Control test: add L3 and replace lumped excitation with modal ports')
    fig.savefig(out/'modal_vs_lumped.png',dpi=180)
    plt.close(fig)
    # Keep both accessible reference-plane choices; neither is a connector model.
    for suffix,matrix in [('pad',s),('feed',data['Smat50'])]:
        lines=['! Top/L2/L3, intact L2; unchanged pads and tapers',
               '! '+('Uniform feeds de-embedded to outer pad edges' if suffix=='pad' else 'Reference at outer feed ends'),
               '# Hz S RI R 50']
        for freq,m in zip(f,matrix):
            vals=[m[0,0],m[1,0],m[0,1],m[1,1]]
            lines.append(f'{freq:.12g} '+' '.join(f'{v.real:.12g} {v.imag:.12g}' for v in vals))
        (HERE/f'result_3layer_modal_{suffix}.s2p').write_text('\n'.join(lines)+'\n')
    rows=['| GHz | Modal/L3 S11, dB | Lumped/L2 S11, dB | Modal/L3 S21, dB | Lumped/L2 S21, dB |',
          '|---:|---:|---:|---:|---:|']
    for freq,m,b in zip(f,s,old['Smat']):
        rows.append(f'| {freq/1e9:g} | {db(m[0,0]):.2f} | {db(b[0,0]):.2f} | {db(m[1,0]):.2f} | {db(b[1,0]):.2f} |')
    text=['# Modal-port control: unchanged launches', '',
          '**L2 is intact. The two signal pads and their tapers have not been redesigned.** '
          'This test adds L3 and changes the excitation before investigating ground openings.', '',
          '## Outcome', '',
          '**Broad agreement, but the modal fixture is not yet verified as an equivalent replacement.** '
          'It reproduces the high-frequency roll-off and the low-reflection window near 2.6 GHz. '
          'However, below 3.5 GHz it adds approximately 0.4–0.65 dB of transmission reduction compared '
          'with the lumped reference. The sampled S11 notch is also shallower. '
          'At 0.5 GHz, the unprocessed native modal result already has '
          f'|S11|²+|S21|²={abs(data["Smat"][0,0,0])**2+abs(data["Smat"][0,1,0])**2:.3f}; '
          'the additional power deficit therefore exists before converting to 50 Ω or removing the feeds. '
          'It must not be attributed to PCB material loss without a control test.', '',
          'The feed-removal and impedance-conversion operations were checked by reversing them '
          '(round-trip errors below 1e-14). Passivity and reciprocity checks pass, but these checks '
          'do not explain the extra attenuation. The next check should be a uniform through line using '
          'the same stack, feed cross-section and modal ports, compared with its propagation constant. '
          'Do that before using this fixture to select an L2 opening.', '',
          '## Test configuration', '',
          '| Parameter | Lumped reference | Modal control |', '|---|---|---|',
          '| Copper layers | Top, L2 | Top, L2, L3 |',
          '| Excitation | Internal 50 Ω sheets | Quasi-TEM modes on outer feed planes |',
          '| Tetrahedra | 218,732 | '+f'{meta["tetrahedra"]:,} |',
          '| Signal-edge target | 60 µm | 60 µm |',
          '| Port-face target | 80 µm | 250 µm |',
          '| FEM order / frequencies | 1 / 20 | 1 / 20 |',
          '| Reference planes | x=0.40, 19.76 mm | x=0.28, 19.88 mm after feed removal |', '',
          'The artificial access lines are 1.2 mm wide, matching the pads. '
          'Their native impedance is approximately 23 Ω, not 50 Ω. '
          'Uniform dielectric and ground extensions place the modal planes away from the launch. '
          'They are a test fixture, not a model of the SMA connector.', '',
          '![Geometry and port locations](preview_3layer_modal/geometry_3d.png)', '',
          '![Actual surface mesh](preview_3layer_modal/mesh_3d.png)', '',
          '## Comparing reference planes', '',
          'First remove each 5.28 mm feed in its native modal reference, using the solved complex propagation '
          'constant. Then convert the S-matrix to a common 50 Ω reference. With EMerge’s exp(−jβx) convention:', '',
          '$$', 'S_{ij}^{\\mathrm{pad}}=S_{ij}^{\\mathrm{feed}}\\exp[j(\\beta_i l_i+\\beta_j l_j)].', '$$', '',
          'The propagation constant includes the dielectric attenuation found by the mode solver; '
          'a separate calibration of residual finite-copper feed loss has not been performed. '
          'The reference planes differ from the old internal lumped sheets by 0.12 mm at each end. '
          'Adding L3 and changing the port fixture are both part of this test, so it is not an isolated '
          'test of only one of these changes.', '',
          '![Modal control versus lumped reference and measurements](preview_3layer_modal/modal_vs_lumped.png)', '',
          *rows, '', '## Numerical checks', '',
          f'Modal Z0 range: {z.real.min():.2f}–{z.real.max():.2f} Ω. '
          f'Maximum |S21−S12|: {checks["max_reciprocity_error"]:.3g}. '
          f'Maximum singular value after feed removal and conversion to 50 Ω: {checks["max_singular_value"]:.6f}.', '',
          'Raw native S, feed-plane S at 50 Ω, pad-plane S at 50 Ω, Z0 and β are preserved in '
          '`result_3layer_modal.npz`. The two exported Touchstone files explicitly name their reference planes.']
    write_report(REPORTS/'02_MODAL_PORT_CHECK.md', '\n'.join(text)+'\n')
    print(json.dumps(checks,indent=2))


if __name__=='__main__':
    main()

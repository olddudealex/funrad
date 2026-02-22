"""
Compare measurement vs simulation with automatic phase rotation correction
"""

import skrf as rf
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import minimize_scalar

def apply_phase_rotation(ntwk, phase_degrees):
    """
    Apply a constant phase rotation to S11 parameters.

    Parameters:
    - ntwk: scikit-rf Network object
    - phase_degrees: phase rotation in degrees

    Returns:
    - modified Network object
    """
    ntwk_rotated = ntwk.copy()
    # Apply constant phase rotation (frequency-independent)
    phase_rad = phase_degrees * np.pi / 180
    ntwk_rotated.s[:, 0, 0] = ntwk.s[:, 0, 0] * np.exp(1j * phase_rad)
    return ntwk_rotated

def calculate_phase_difference_rms(measured, simulated, phase_degrees, min_freq_ghz=None):
    """
    Calculate RMS phase difference between measured and simulated data
    after applying a phase rotation to the simulation.

    Parameters:
    - min_freq_ghz: Minimum frequency in GHz to include in calculation (None = all frequencies)
    """
    # Interpolate simulated to match measured frequency points
    sim_interp = simulated.interpolate(measured.frequency)
    sim_rotated = apply_phase_rotation(sim_interp, phase_degrees)

    # Get phases in radians and unwrap individually
    phase_measured = np.unwrap(np.angle(measured.s[:, 0, 0]))
    phase_simulated = np.unwrap(np.angle(sim_rotated.s[:, 0, 0]))

    # Calculate phase difference after unwrapping (convert to degrees)
    phase_diff = (phase_measured - phase_simulated) * 180 / np.pi

    # Apply frequency filter if specified
    if min_freq_ghz is not None:
        freq_mask = measured.f >= (min_freq_ghz * 1e9)
        phase_diff = phase_diff[freq_mask]

    # Calculate RMS
    rms = np.sqrt(np.mean(phase_diff**2))
    return rms

def find_optimal_phase_rotation(measured, simulated, min_freq_ghz=5.3):
    """
    Find the optimal phase rotation angle that minimizes phase difference.

    Parameters:
    - min_freq_ghz: Minimum frequency in GHz to include in optimization
    """
    # Interpolate simulated to match measured frequency points
    sim_interp = simulated.interpolate(measured.frequency)

    # Apply frequency filter
    freq_mask = measured.f >= (min_freq_ghz * 1e9)
    print(f"\nOptimization frequency range: >= {min_freq_ghz:.1f} GHz")
    print(f"Using {np.sum(freq_mask)} of {len(measured.f)} frequency points")

    # Initial guess: mean phase difference (filtered)
    phase_measured = np.unwrap(np.angle(measured.s[:, 0, 0]))
    phase_simulated = np.unwrap(np.angle(sim_interp.s[:, 0, 0]))
    phase_diff_rad = phase_measured - phase_simulated

    # Apply filter
    phase_diff_rad_filtered = phase_diff_rad[freq_mask]

    # Convert to degrees and get mean
    phase_diff_deg = phase_diff_rad_filtered * 180 / np.pi
    initial_phase = np.mean(phase_diff_deg)

    print(f"Initial phase offset estimate (mean): {initial_phase:.2f} degrees")
    print(f"Phase difference std dev: {np.std(phase_diff_deg):.2f} degrees")

    # Optimize to find best phase rotation
    # Extended range to handle cases where optimal value is near ±180°
    result = minimize_scalar(
        lambda p: calculate_phase_difference_rms(measured, simulated, p, min_freq_ghz),
        bounds=(-360, 360),  # Extended search range for better convergence
        method='bounded'
    )

    optimal_phase = result.x
    # Normalize to [-180, 180] range for display
    optimal_phase_normalized = ((optimal_phase + 180) % 360) - 180

    print(f"Optimized phase rotation: {optimal_phase:.2f} degrees (normalized: {optimal_phase_normalized:.2f}°)")
    print(f"RMS phase error after correction: {result.fun:.2f} degrees")

    # Calculate equivalent reference plane shift at center frequency
    # Note: This is for reference only - the actual correction is frequency-independent
    center_freq = (measured.f[0] + measured.f[-1]) / 2
    phase_rad = optimal_phase * np.pi / 180
    # For S11 (reflection), phase shift = -2 * 2π * f * (d/c)
    # Solving for d: d = -phase / (2 * 2π * f) * c
    equivalent_distance = -phase_rad / (2 * 2 * np.pi * center_freq) * 3e8

    print(f"\nEquivalent reference plane shift at {center_freq/1e9:.2f} GHz: {equivalent_distance*1000:.2f} mm")
    print("(Note: Actual correction is a constant phase rotation, not a physical shift)")

    return optimal_phase, equivalent_distance

def main():
    # Load the two files
    measured_file = "SN00003_2026-02-07_22-26-34.s1p"
    simulated_file = "emerge 0.15 lambda.s1p"

    print(f"Loading measurement: {measured_file}")
    ntwk_measured = rf.Network(measured_file)

    print(f"Loading simulation: {simulated_file}")
    ntwk_simulated = rf.Network(simulated_file)

    print(f"\nMeasurement frequency points: {len(ntwk_measured.f)}")
    print(f"Simulation frequency points: {len(ntwk_simulated.f)}")
    print(f"Measurement frequency range: {ntwk_measured.f[0]/1e9:.3f} - {ntwk_measured.f[-1]/1e9:.3f} GHz")
    print(f"Simulation frequency range: {ntwk_simulated.f[0]/1e9:.3f} - {ntwk_simulated.f[-1]/1e9:.3f} GHz")

    # Interpolate simulation to match measurement frequency grid
    print("\nInterpolating simulation to match measurement frequency grid...")
    ntwk_sim_interp = ntwk_simulated.interpolate(ntwk_measured.frequency)

    print("\n" + "="*60)
    print("Finding optimal phase rotation to match simulation to measurement...")
    print("="*60)

    # Find optimal phase rotation
    optimal_phase, equiv_distance = find_optimal_phase_rotation(ntwk_measured, ntwk_sim_interp)

    # Apply optimal phase rotation
    ntwk_sim_corrected = apply_phase_rotation(ntwk_sim_interp, optimal_phase)

    print("\n" + "="*60)
    print("Creating comparison plots...")
    print("="*60)

    # Create matplotlib figure with 2x2 subplots
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
    center_freq_ghz = (ntwk_measured.f[0] + ntwk_measured.f[-1]) / 2 / 1e9
    fig.suptitle(f'Measurement vs Simulation (Phase Rotation: {optimal_phase:.2f}° ≈ {equiv_distance*1000:.2f} mm at {center_freq_ghz:.2f} GHz)',
                 fontsize=16, fontweight='bold')

    freq_ghz = ntwk_measured.f / 1e9

    # 1. Magnitude comparison (top-left)
    s11_meas_db = 20 * np.log10(np.abs(ntwk_measured.s[:, 0, 0]))
    s11_sim_db = 20 * np.log10(np.abs(ntwk_sim_interp.s[:, 0, 0]))

    ax1.plot(freq_ghz, s11_meas_db, 'b-', linewidth=2, label='Measured')
    ax1.plot(freq_ghz, s11_sim_db, 'r--', linewidth=2, label='Simulation (Original)')
    ax1.set_xlabel('Frequency (GHz)')
    ax1.set_ylabel('Magnitude (dB)')
    ax1.set_title('S11 Magnitude Comparison', fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.legend()

    # 2. Phase comparison (top-right) - show all three: measured, original, corrected
    # Unwrap phase to avoid 180-degree jumps
    phase_meas_rad = np.angle(ntwk_measured.s[:, 0, 0])
    phase_sim_orig_rad = np.angle(ntwk_sim_interp.s[:, 0, 0])
    phase_sim_corr_rad = np.angle(ntwk_sim_corrected.s[:, 0, 0])

    phase_meas = np.unwrap(phase_meas_rad) * 180 / np.pi
    phase_sim_orig = np.unwrap(phase_sim_orig_rad) * 180 / np.pi
    phase_sim_corr = np.unwrap(phase_sim_corr_rad) * 180 / np.pi

    ax2.plot(freq_ghz, phase_meas, 'b-', linewidth=2, label='Measured')
    ax2.plot(freq_ghz, phase_sim_orig, 'r--', linewidth=2, label='Simulation (Original)')
    ax2.plot(freq_ghz, phase_sim_corr, 'g-', linewidth=2, label='Simulation (Corrected)')
    ax2.set_xlabel('Frequency (GHz)')
    ax2.set_ylabel('Phase (degrees)')
    ax2.set_title('S11 Phase Comparison', fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.legend()

    # 3. Smith chart (bottom-left) - use scikit-rf plotting
    ax3.set_title('Smith Chart', fontweight='bold')
    ntwk_measured.plot_s_smith(m=0, n=0, ax=ax3, label='Measured',
                                show_legend=False, draw_labels=False, color='blue')
    ntwk_sim_interp.plot_s_smith(m=0, n=0, ax=ax3, label='Simulation (Original)',
                                  show_legend=False, draw_labels=False,
                                  color='red', linestyle='--')
    ntwk_sim_corrected.plot_s_smith(m=0, n=0, ax=ax3, label='Simulation (Corrected)',
                                     show_legend=False, draw_labels=False, color='green')
    ax3.legend(fontsize=10)

    # 4. Phase differences (bottom-right) - both before and after on same plot
    phase_diff_before = np.unwrap((phase_meas - phase_sim_orig) * np.pi / 180) * 180 / np.pi
    phase_diff_after = np.unwrap((phase_meas - phase_sim_corr) * np.pi / 180) * 180 / np.pi

    ax4.plot(freq_ghz, phase_diff_before, 'r-', linewidth=2, label='Before Correction')
    ax4.plot(freq_ghz, phase_diff_after, 'g-', linewidth=2, label='After Correction')
    ax4.axhline(y=0, color='gray', linestyle=':', linewidth=1)
    ax4.set_xlabel('Frequency (GHz)')
    ax4.set_ylabel('Phase Error (degrees)')
    ax4.set_title('Phase Difference', fontweight='bold')
    ax4.grid(True, alpha=0.3)
    ax4.legend()

    plt.tight_layout()

    # Save outputs
    output_png = 'comparison_with_delay.png'
    plt.savefig(output_png, dpi=150, bbox_inches='tight')
    print(f"\nPlot saved to: {output_png}")

    # Show plot
    plt.show()

    print("\n" + "="*60)
    print("Analysis complete!")
    print("="*60)

if __name__ == "__main__":
    main()

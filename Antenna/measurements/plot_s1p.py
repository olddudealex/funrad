"""
Simple script to plot S1P files using scikit-rf and Plotly
"""

import skrf as rf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import glob

def apply_phase_rotation(ntwk, phase_degrees):
    """
    Apply a constant phase rotation to S11 parameters.
    """
    ntwk_rotated = ntwk.copy()
    phase_rad = phase_degrees * np.pi / 180
    ntwk_rotated.s[:, 0, 0] = ntwk.s[:, 0, 0] * np.exp(1j * phase_rad)
    return ntwk_rotated

def create_smith_chart():
    """Create Smith Chart grid lines"""
    traces = []

    # Constant resistance circles
    for r in [0.2, 0.5, 1.0, 2.0, 5.0]:
        theta = np.linspace(0, 2*np.pi, 100)
        x = r / (1 + r) + (1 / (1 + r)) * np.cos(theta)
        y = (1 / (1 + r)) * np.sin(theta)
        traces.append(go.Scatter(
            x=x, y=y, mode='lines',
            line=dict(color='lightgray', width=0.5),
            showlegend=False, hoverinfo='skip'
        ))

    # Constant reactance arcs
    for x in [0.2, 0.5, 1.0, 2.0, 5.0]:
        theta = np.linspace(0, np.pi, 50)
        xc = 1 - (1 / (1 + x**2))
        yc = x / (1 + x**2)
        r_arc = 1 / (1 + x**2)
        x_pts = xc + r_arc * np.cos(theta)
        y_pts = yc + r_arc * np.sin(theta)
        traces.append(go.Scatter(
            x=x_pts, y=y_pts, mode='lines',
            line=dict(color='lightgray', width=0.5),
            showlegend=False, hoverinfo='skip'
        ))
        # Negative reactance
        traces.append(go.Scatter(
            x=x_pts, y=-y_pts, mode='lines',
            line=dict(color='lightgray', width=0.5),
            showlegend=False, hoverinfo='skip'
        ))

    # Unit circle
    theta = np.linspace(0, 2*np.pi, 200)
    traces.append(go.Scatter(
        x=np.cos(theta), y=np.sin(theta), mode='lines',
        line=dict(color='black', width=1),
        showlegend=False, hoverinfo='skip'
    ))

    return traces

def main():
    # Find all S1P files in current directory
    s1p_files = sorted(glob.glob("*.s1p"))

    if not s1p_files:
        print("No S1P files found in current directory")
        return

    print(f"Found {len(s1p_files)} S1P file(s):")
    for file in s1p_files:
        print(f"  - {file}")

    # Configure phase corrections for specific files (in degrees)
    # Default is 0 (no correction). Add entries for files that need correction.
    PHASE_CORRECTIONS = {
        "openEms 20th lambda cell": -71.64,
        "openEms 20th lambda cell er=2.95": -109.71,
        "emerge, er=3.0, 0.6mm copper mesh": -134.23,
        "emerge, er=2.95, 0.6mm copper mesh": -170.79,
        "SN00003_LiteVNA_2026-03-29_20-31-41": -171.56
    }

    # Load all networks and apply phase corrections
    networks = []
    for file in s1p_files:
        ntwk = rf.Network(file)

        # Check if this file needs phase correction
        phase_correction = 0.0  # Default: no correction
        for pattern, correction in PHASE_CORRECTIONS.items():
            if pattern == file.removesuffix('.s1p'):
                phase_correction = correction
                break

        # Apply phase correction if needed
        if phase_correction != 0.0:
            print(f"  Applying {phase_correction:+.2f}° phase correction to {file}")
            ntwk = apply_phase_rotation(ntwk, phase_correction)
            file = file + f" (corrected {phase_correction:+.2f}°)"

        networks.append((file, ntwk))

    # Create figure with 4 subplots
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('S11 Magnitude', 'S11 Phase', 'Input Impedance (Z_in)', 'Smith Chart'),
        specs=[[{"type": "scatter"}, {"type": "scatter"}],
               [{"type": "scatter"}, {"type": "scatter"}]],
        vertical_spacing=0.12,
        horizontal_spacing=0.10
    )

    # Color palette for different files
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']

    # Add Smith Chart grid first (so it's in the background)
    smith_traces = create_smith_chart()
    for trace in smith_traces:
        fig.add_trace(trace, row=2, col=2)

    # Plot all networks
    for idx, (file, ntwk) in enumerate(networks):
        color = colors[idx % len(colors)]
        freq_ghz = ntwk.f / 1e9  # Convert to GHz

        # 1. S11 Magnitude in dB
        s11_db = 20 * np.log10(np.abs(ntwk.s[:, 0, 0]))
        fig.add_trace(go.Scatter(
            x=freq_ghz, y=s11_db,
            mode='lines', name=file,
            line=dict(color=color, width=2),
            legendgroup=file,
            showlegend=True
        ), row=1, col=1)

        # 2. S11 Phase in degrees (unwrapped to avoid 180° discontinuities)
        s11_phase_rad = np.angle(ntwk.s[:, 0, 0])
        s11_phase = np.unwrap(s11_phase_rad) * 180 / np.pi
        fig.add_trace(go.Scatter(
            x=freq_ghz, y=s11_phase,
            mode='lines', name=file,
            line=dict(color=color, width=2),
            legendgroup=file,
            showlegend=False
        ), row=1, col=2)

        # 3. Input Impedance (Real and Imaginary parts)
        z_in = ntwk.z[:, 0, 0]
        fig.add_trace(go.Scatter(
            x=freq_ghz, y=z_in.real,
            mode='lines', name=f'{file} (Real)',
            line=dict(color=color, width=2),
            legendgroup=file,
            showlegend=False
        ), row=2, col=1)

        fig.add_trace(go.Scatter(
            x=freq_ghz, y=z_in.imag,
            mode='lines', name=f'{file} (Imag)',
            line=dict(color=color, width=2, dash='dash'),
            legendgroup=file,
            showlegend=False
        ), row=2, col=1)

        # 4. Smith Chart - plot S11 as reflection coefficient
        s11 = ntwk.s[:, 0, 0]
        fig.add_trace(go.Scatter(
            x=s11.real, y=s11.imag,
            mode='lines+markers',
            name=file,
            line=dict(color=color, width=2),
            marker=dict(size=3),
            legendgroup=file,
            showlegend=False,
            text=[f'{f/1e9:.3f} GHz' for f in ntwk.f],
            hovertemplate='%{text}<br>Re: %{x:.3f}<br>Im: %{y:.3f}<extra></extra>'
        ), row=2, col=2)

    # Add 50Ω reference line to impedance plot
    freq_range = [networks[0][1].f[0]/1e9, networks[0][1].f[-1]/1e9]
    fig.add_trace(go.Scatter(
        x=freq_range, y=[50, 50],
        mode='lines', name='50Ω ref',
        line=dict(color='gray', width=1, dash='dot'),
        showlegend=False
    ), row=2, col=1)

    # Update axes labels
    fig.update_xaxes(title_text="Frequency (GHz)", row=1, col=1, gridcolor='lightgray')
    fig.update_xaxes(title_text="Frequency (GHz)", row=1, col=2, gridcolor='lightgray')
    fig.update_xaxes(title_text="Frequency (GHz)", row=2, col=1, gridcolor='lightgray')
    fig.update_xaxes(title_text="Real", row=2, col=2, range=[-1.1, 1.1], zeroline=True, gridcolor='lightgray')

    fig.update_yaxes(title_text="Magnitude (dB)", row=1, col=1, gridcolor='lightgray')
    fig.update_yaxes(title_text="Phase (degrees)", row=1, col=2, gridcolor='lightgray')
    fig.update_yaxes(title_text="Impedance (Ω)", row=2, col=1, gridcolor='lightgray')
    fig.update_yaxes(title_text="Imaginary", row=2, col=2, range=[-1.1, 1.1], zeroline=True,
                     scaleanchor="x4", scaleratio=1, gridcolor='lightgray')

    # Update layout
    fig.update_layout(
        title_text="S-Parameter Analysis - Interactive",
        title_font_size=18,
        height=900,
        width=1600,
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=1.02
        ),
        hovermode='closest'
    )

    # Save as HTML (interactive)
    output_html = 's1p_plot.html'
    fig.write_html(output_html)
    print(f"\nInteractive plot saved to: {output_html}")

    # Save as PNG (static image)
    output_png = 's1p_plot.png'
    fig.write_image(output_png, width=1600, height=900)
    print(f"Static plot saved to: {output_png}")

    # Show plot in browser
    fig.show()

if __name__ == "__main__":
    main()

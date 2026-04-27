"""
Compare simulated directivity vs measured gain pattern.

4 subplots:
  Row 1 — Cartesian:  E-plane  |  H-plane
  Row 2 — Polar:      E-plane  |  H-plane   (go.Scatter with manual polar coords)

All traces are go.Scatter so legendgroup toggling works across all subplots.

Sources:
  Sim 1 (OpenEMS): openEms 20th lambda cell er=2.95 directivity.txt
  Sim 2 (Emerge):  emerge, er=2.95, 0.6mm copper mesh directivity.txt
  Measurement:     directivity_measurements.db

Angular mapping: sim theta −90..+90  ↔  measurement 0..180°
  (boresight = sim theta 0° = measurement 90°)
"""

import os
import sqlite3
import webbrowser
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── Config ────────────────────────────────────────────────────────────────────
SIM1_FILE       = "openEms 20th lambda cell er=2.95 directivity.txt"
SIM1_LABEL      = "OpenEMS"
SIM1_EH_SWAPPED = True    # D_phi0 → H-plane, D_phi90 → E-plane
SIM1_MIRRORED   = False

SIM2_FILE       = "emerge, er=2.95, 0.6mm copper mesh directivity.txt"
SIM2_LABEL      = "Emerge"
SIM2_EH_SWAPPED = False   # G_xz → E-plane, G_yz → H-plane
SIM2_MIRRORED   = True

DB_FILE         = "directivity_measurements.db"
DISTANCE_CM     = 155.5   # measurement antenna separation for Friis gain conversion
MEAS_MIRRORED   = True    # measurement was taken rotating in the opposite direction

# Which test_id rank to use for each plane (0 = latest, 1 = second-to-latest, …)
EPLANE_TEST_RANK = 0
HPLANE_TEST_RANK = 1

# Polar plot dynamic range in dB below the global peak
POLAR_DYNAMIC_RANGE_DB = 40

C_LIGHT = 299_792_458.0


# ── Data loading ──────────────────────────────────────────────────────────────

def fspl_db(freq_hz: float, dist_m: float) -> float:
    return 20 * np.log10(4 * np.pi * dist_m * freq_hz / C_LIGHT)


def load_simulation(path: str, eh_swapped: bool = False):
    """
    Parse a simulation .txt file with two directivity/gain columns.
    Returns (freq_hz, theta_deg, d_eplane_dBi, d_hplane_dBi, meta).
    eh_swapped=True swaps the two columns (col0 → H, col1 → E).
    Handles both Dmax_dBi and Gmax_dBi metadata fields.
    """
    meta = {}
    theta, d0, d90 = [], [], []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("#"):
                content = line[1:].strip()
                if ":" in content:
                    k, v = content.split(":", 1)
                    meta[k.strip()] = v.strip()
                continue
            if line.startswith("theta_deg"):
                continue
            parts = line.split()
            if len(parts) == 3:
                theta.append(float(parts[0]))
                d0.append(float(parts[1]))
                d90.append(float(parts[2]))

    freq_hz = float(meta.get("freq_GHz", 5.8)) * 1e9
    if "Dmax_dBi" not in meta and "Gmax_dBi" in meta:
        meta["Dmax_dBi"] = meta["Gmax_dBi"]

    d0_arr, d90_arr = np.array(d0), np.array(d90)
    d_e, d_h = (d90_arr, d0_arr) if eh_swapped else (d0_arr, d90_arr)
    return freq_hz, np.array(theta), d_e, d_h, meta


def load_measurement(db_path: str, freq_hz: float, rank: int = 0):
    """
    Load the (rank+1)-th latest test from the DB  (rank=0 → latest).
    Returns (angles_deg, gain_dBi, test_id, actual_freq_hz).
    Gain computed via Friis assuming two identical antennas.
    """
    con = sqlite3.connect(db_path)
    row = con.execute(
        "SELECT test_id FROM measurements "
        "GROUP BY test_id ORDER BY test_id DESC "
        f"LIMIT 1 OFFSET {rank}"
    ).fetchone()
    if row is None:
        raise RuntimeError(f"Not enough tests in DB for rank={rank}")
    test_id = row[0]

    rows = con.execute(
        "SELECT angle_deg, start_hz, step_hz, n_pts, s21_data "
        "FROM measurements WHERE test_id=? ORDER BY angle_deg",
        (test_id,),
    ).fetchall()
    con.close()

    start_hz    = rows[0][1]
    step_hz     = rows[0][2]
    n_pts       = rows[0][3]
    freq_idx    = max(0, min(n_pts - 1, int(round((freq_hz - start_hz) / step_hz))))
    actual_freq = start_hz + freq_idx * step_hz

    angles, s21_vals = [], []
    for angle_deg, _, _, _, s21_blob in rows:
        angles.append(angle_deg)
        s21_vals.append(np.frombuffer(s21_blob, dtype=np.complex64)[freq_idx])

    angles   = np.array(angles)
    s21_db   = 20 * np.log10(np.maximum(np.abs(np.array(s21_vals)), 1e-12))
    dist_m   = DISTANCE_CM / 100.0
    fspl     = fspl_db(actual_freq, dist_m)
    s21_peak = float(s21_db.max())
    g_peak   = (s21_peak + fspl) / 2
    gain_dbi = g_peak + (s21_db - s21_peak)

    print(f"  test_id={test_id}  freq={actual_freq/1e9:.4f} GHz  "
          f"S21_peak={s21_peak:.2f} dB  FSPL={fspl:.2f} dB  G_peak={g_peak:.2f} dBi")
    return angles, gain_dbi, test_id, actual_freq


# ── Polar coordinate helpers ──────────────────────────────────────────────────

def sim_slice(theta: np.ndarray, data: np.ndarray):
    """Clip to −90..+90 and shift to 0..180 to align with measurement axis."""
    mask = (theta >= -90) & (theta <= 90)
    return theta[mask] + 90, data[mask]


def polar_r(values: np.ndarray, floor: float) -> np.ndarray:
    """Shift values so floor → 0, clip below floor."""
    return np.maximum(values - floor, 0.0)


def to_polar_xy(theta_deg: np.ndarray, r: np.ndarray):
    """
    Convert (theta_deg, r) to Cartesian (x, y).
    Coordinate convention: theta=0° → left, theta=90° → top (boresight), theta=180° → right.
    """
    angle_rad = (180.0 - theta_deg) * np.pi / 180.0
    return r * np.cos(angle_rad), r * np.sin(angle_rad)


def half_polar_grid_traces(r_max: float, tick_r: list, tick_labels: list,
                            tick_theta: list) -> list:
    """
    Build go.Scatter background traces for a half-polar diagram (0..180°, top half).
    tick_r / tick_labels: radial axis values and their dBi labels.
    tick_theta: angular grid lines in degrees (0..180).
    """
    traces = []
    theta_arc = np.linspace(0, 180, 361)

    # Concentric semicircles
    for r, lbl in zip(tick_r, tick_labels):
        if r == 0:
            continue
        xc, yc = to_polar_xy(theta_arc, np.full(len(theta_arc), float(r)))
        is_outer = abs(r - r_max) < 1e-9
        traces.append(go.Scatter(
            x=xc, y=yc, mode="lines",
            line=dict(color="gray" if is_outer else "lightgray",
                      width=1.0 if is_outer else 0.5),
            showlegend=False, hoverinfo="skip",
        ))

    # Horizontal baseline (theta 0→180)
    traces.append(go.Scatter(
        x=[-r_max, r_max], y=[0, 0], mode="lines",
        line=dict(color="gray", width=1),
        showlegend=False, hoverinfo="skip",
    ))

    # Radial gridlines
    for theta in tick_theta:
        if theta in (0, 180):
            continue
        a = (180 - theta) * np.pi / 180
        traces.append(go.Scatter(
            x=[0, r_max * np.cos(a)], y=[0, r_max * np.sin(a)],
            mode="lines", line=dict(color="lightgray", width=0.5),
            showlegend=False, hoverinfo="skip",
        ))

    # r-axis labels at theta=30° direction (upper-left, away from boresight)
    la = (180 - 30) * np.pi / 180  # math angle for our theta=30°
    for r, lbl in zip(tick_r, tick_labels):
        if r == 0:
            continue
        traces.append(go.Scatter(
            x=[r * np.cos(la)], y=[r * np.sin(la)],
            mode="text", text=[lbl],
            textfont=dict(size=8, color="gray"),
            textposition="top right",
            showlegend=False, hoverinfo="skip",
        ))

    # Angular labels just outside the outer circle
    r_lbl = r_max * 1.12
    for theta in tick_theta:
        a = (180 - theta) * np.pi / 180
        label = f"{theta - 90:.0f}°"
        traces.append(go.Scatter(
            x=[r_lbl * np.cos(a)], y=[r_lbl * np.sin(a)],
            mode="text", text=[label],
            textfont=dict(size=9),
            textposition="middle center",
            showlegend=False, hoverinfo="skip",
        ))

    return traces


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"Loading {SIM1_LABEL}:")
    freq1, theta1, e1, h1, meta1 = load_simulation(SIM1_FILE, SIM1_EH_SWAPPED)
    dmax1 = float(meta1.get("Dmax_dBi", "nan"))
    print(f"  freq={freq1/1e9:.4f} GHz  Dmax={dmax1:.2f} dBi")

    print(f"Loading {SIM2_LABEL}:")
    freq2, theta2, e2, h2, meta2 = load_simulation(SIM2_FILE, SIM2_EH_SWAPPED)
    dmax2 = float(meta2.get("Dmax_dBi", "nan"))
    print(f"  freq={freq2/1e9:.4f} GHz  Gmax={dmax2:.2f} dBi")

    freq_hz = freq1   # both sims are at 5.8 GHz

    print("E-plane measurement:")
    ang_e, gain_e, tid_e, _ = load_measurement(DB_FILE, freq_hz, EPLANE_TEST_RANK)
    print("H-plane measurement:")
    ang_h, gain_h, tid_h, _ = load_measurement(DB_FILE, freq_hz, HPLANE_TEST_RANK)

    # Simulation: clip to −90..+90 and shift to 0..180, then optionally mirror
    x1e, y1e = sim_slice(theta1, e1)
    x1h, y1h = sim_slice(theta1, h1)
    if SIM1_MIRRORED:
        x1e, x1h = 180.0 - x1e, 180.0 - x1h

    x2e, y2e = sim_slice(theta2, e2)
    x2h, y2h = sim_slice(theta2, h2)
    if SIM2_MIRRORED:
        x2e, x2h = 180.0 - x2e, 180.0 - x2h

    # Measurement angle offsets: peak → x=90 (= sim boresight, theta=0)
    offset_e = 90.0 - float(ang_e[np.argmax(gain_e)])
    offset_h = 90.0 - float(ang_h[np.argmax(gain_h)])
    x_meas_e = ang_e + offset_e
    x_meas_h = ang_h + offset_h
    if MEAS_MIRRORED:
        x_meas_e, x_meas_h = 180.0 - x_meas_e, 180.0 - x_meas_h
    print(f"E-plane meas offset: {offset_e:+.1f}°")
    print(f"H-plane meas offset: {offset_h:+.1f}°")

    # Shared Cartesian x-axis ticks (show sim theta, boresight = 0°)
    tick_vals = list(range(0, 181, 15))
    tick_text = [f"{v - 90}°" for v in tick_vals]

    # Consistent polar scale across all plots
    global_peak      = max(y1e.max(), y1h.max(), y2e.max(), y2h.max(),
                           gain_e.max(), gain_h.max())
    polar_floor      = global_peak - POLAR_DYNAMIC_RANGE_DB
    r_max            = float(POLAR_DYNAMIC_RANGE_DB)
    polar_ticks_r    = [i * (POLAR_DYNAMIC_RANGE_DB / 4) for i in range(5)]
    polar_ticks_text = [f"{polar_floor + v:.0f} dBi" for v in polar_ticks_r]
    polar_tick_theta = list(range(0, 181, 30))

    C_SIM1 = "#1f77b4"   # blue  — OpenEMS
    C_SIM2 = "#2ca02c"   # green — Emerge
    C_MEAS = "#d62728"   # red   — Measured

    # ── Figure (all subplots are "scatter" so legendgroup works across rows) ──
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            f"E-plane  (Cartesian)  — meas offset {offset_e:+.1f}°",
            f"H-plane  (Cartesian)  — meas offset {offset_h:+.1f}°",
            f"E-plane  (Polar)  — meas offset {offset_e:+.1f}°",
            f"H-plane  (Polar)  — meas offset {offset_h:+.1f}°",
        ),
        specs=[
            [{"type": "scatter"}, {"type": "scatter"}],
            [{"type": "scatter"}, {"type": "scatter"}],
        ],
        vertical_spacing=0.12,
        horizontal_spacing=0.10,
    )

    planes = [
        # col, plane, x1, y1, x2, y2, x_meas, y_meas, tid, offset
        (1, "E", x1e, y1e, x2e, y2e, x_meas_e, gain_e, tid_e, offset_e),
        (2, "H", x1h, y1h, x2h, y2h, x_meas_h, gain_h, tid_h, offset_h),
    ]

    # ── Row 1: Cartesian ──────────────────────────────────────────────────────
    for col, plane, x1, y1, x2, y2, xa, ya, tid, off in planes:
        g1, g2, gm = f"sim1_{plane}", f"sim2_{plane}", f"meas_{plane}"

        fig.add_trace(go.Scatter(
            x=x1, y=y1, name=SIM1_LABEL, mode="lines",
            line=dict(color=C_SIM1, width=2),
            legendgroup=g1, legendgrouptitle=dict(text=f"{plane}-plane"),
            showlegend=True,
        ), row=1, col=col)
        fig.add_trace(go.Scatter(
            x=x2, y=y2, name=SIM2_LABEL, mode="lines",
            line=dict(color=C_SIM2, width=2),
            legendgroup=g2, showlegend=True,
        ), row=1, col=col)
        fig.add_trace(go.Scatter(
            x=xa, y=ya, name=f"Measured #{tid}  ({off:+.1f}°)", mode="lines",
            line=dict(color=C_MEAS, width=2),
            legendgroup=gm, showlegend=True,
        ), row=1, col=col)

        fig.update_xaxes(
            title_text="Angle (°)  [0 = boresight]",
            tickvals=tick_vals, ticktext=tick_text,
            gridcolor="lightgray", row=1, col=col,
        )
        fig.update_yaxes(
            title_text="Directivity / Gain (dBi)",
            gridcolor="lightgray", row=1, col=col,
        )

    # ── Row 2: Polar (go.Scatter with manual polar coords) ────────────────────
    for col, plane, x1, y1, x2, y2, xa, ya, tid, _ in planes:
        g1, g2, gm = f"sim1_{plane}", f"sim2_{plane}", f"meas_{plane}"

        # Grid background
        for tr in half_polar_grid_traces(r_max, polar_ticks_r, polar_ticks_text,
                                          polar_tick_theta):
            fig.add_trace(tr, row=2, col=col)

        # Data traces — same go.Scatter type as row 1 → legendgroup works
        xp1, yp1 = to_polar_xy(x1, polar_r(y1, polar_floor))
        xp2, yp2 = to_polar_xy(x2, polar_r(y2, polar_floor))
        xpa, ypa = to_polar_xy(xa, polar_r(ya, polar_floor))

        fig.add_trace(go.Scatter(
            x=xp1, y=yp1, name=SIM1_LABEL, mode="lines",
            line=dict(color=C_SIM1, width=2),
            legendgroup=g1, showlegend=False,
        ), row=2, col=col)
        fig.add_trace(go.Scatter(
            x=xp2, y=yp2, name=SIM2_LABEL, mode="lines",
            line=dict(color=C_SIM2, width=2),
            legendgroup=g2, showlegend=False,
        ), row=2, col=col)
        fig.add_trace(go.Scatter(
            x=xpa, y=ypa, name=f"Measured #{tid}", mode="lines",
            line=dict(color=C_MEAS, width=2),
            legendgroup=gm, showlegend=False,
        ), row=2, col=col)

        # Hide all axis decorations for polar subplots
        margin = r_max * 1.2
        fig.update_xaxes(range=[-margin, margin], showgrid=False,
                         zeroline=False, showticklabels=False, row=2, col=col)
        fig.update_yaxes(range=[-r_max * 0.2, margin], showgrid=False,
                         zeroline=False, showticklabels=False, row=2, col=col)

    # Equal aspect ratio for polar subplots (axis numbers: row2,col1=3, row2,col2=4)
    fig.update_layout(
        yaxis3=dict(scaleanchor="x3", scaleratio=1),
        yaxis4=dict(scaleanchor="x4", scaleratio=1),
    )

    # ── Overall layout ─────────────────────────────────────────────────────────
    fig.update_layout(
        title_text=(
            f"Directivity comparison @ {freq_hz/1e9:.4f} GHz<br>"
            f"<sup>{SIM1_LABEL} Dmax={dmax1:.2f} dBi  |  "
            f"{SIM2_LABEL} Gmax={dmax2:.2f} dBi  |  "
            f"Distance={DISTANCE_CM} cm  |  "
            f"E-plane test #{tid_e}  |  H-plane test #{tid_h}</sup>"
        ),
        height=900, width=1400,
        margin=dict(t=100),
        legend=dict(orientation="v", yanchor="top", y=0.99, xanchor="left", x=1.02),
        hovermode="x unified",
    )

    html_path = os.path.abspath("directivity_comparison.html")
    fig.write_html(html_path)
    fig.write_image("directivity_comparison.png", width=1400, height=900)
    print(f"\nSaved: {html_path}")
    print("Saved: directivity_comparison.png")
    webbrowser.open(f"file:///{html_path}")


if __name__ == "__main__":
    main()

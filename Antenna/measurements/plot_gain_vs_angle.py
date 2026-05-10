"""
Plot measured antenna gain vs angle at multiple frequencies on the same axes.
Cartesian and polar subplots. Annotates beam peak angle and HPBW for each frequency.
"""

import os
import sqlite3
import webbrowser
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── Config ────────────────────────────────────────────────────────────────────
DB_FILE                = "directivity_measurements.db"
TEST_RANK              = 0           # 0 = latest, 1 = second-to-latest, …
PLANE_LABEL            = "E-plane"   # shown in title only
DISTANCE_CM            = 155.5
FREQUENCIES_GHZ        = [5.725, 5.8, 5.875]
MEAS_MIRRORED          = True        # flip angular axis (wrong rotation direction)
POLAR_DYNAMIC_RANGE_DB = 30

C_LIGHT = 299_792_458.0
COLORS  = ["#1f77b4", "#d62728", "#2ca02c"]   # blue, red, green


# ── Data loading ──────────────────────────────────────────────────────────────

def fspl_db(freq_hz: float, dist_m: float) -> float:
    return 20 * np.log10(4 * np.pi * dist_m * freq_hz / C_LIGHT)


def load_measurement(db_path: str, freq_hz: float, rank: int = 0):
    """
    Load the (rank+1)-th latest test. Returns (angles_deg, gain_dBi, test_id, actual_freq_hz).
    Gain computed via Friis assuming two identical antennas.
    """
    con = sqlite3.connect(db_path)
    row = con.execute(
        "SELECT test_id FROM measurements GROUP BY test_id "
        "ORDER BY test_id DESC LIMIT 1 OFFSET ?", (rank,)
    ).fetchone()
    if row is None:
        raise RuntimeError(f"No test at rank={rank}")
    test_id = row[0]

    rows = con.execute(
        "SELECT angle_deg, start_hz, step_hz, n_pts, s21_data "
        "FROM measurements WHERE test_id=? ORDER BY angle_deg", (test_id,)
    ).fetchall()
    con.close()

    start_hz = rows[0][1]
    step_hz  = rows[0][2]
    n_pts    = rows[0][3]
    freq_idx = max(0, min(n_pts - 1, int(round((freq_hz - start_hz) / step_hz))))
    actual   = start_hz + freq_idx * step_hz

    angles, s21_vals = [], []
    for angle_deg, _, _, _, blob in rows:
        angles.append(angle_deg)
        s21_vals.append(np.frombuffer(blob, dtype=np.complex64)[freq_idx])

    angles   = np.array(angles)
    s21_db   = 20 * np.log10(np.maximum(np.abs(np.array(s21_vals)), 1e-12))
    fspl     = fspl_db(actual, DISTANCE_CM / 100.0)
    s21_peak = float(s21_db.max())
    gain     = (s21_peak + fspl) / 2 + (s21_db - s21_peak)

    return angles, gain, test_id, actual


# ── Analysis ──────────────────────────────────────────────────────────────────

def compute_hpbw(angles, gain):
    """
    Find −3 dB half-power beamwidth by linear interpolation.
    Returns (peak_angle_deg, hpbw_deg, left_crossing_deg, right_crossing_deg).
    hpbw and crossings are None if −3 dB level not reached on that side.
    """
    pi  = int(np.argmax(gain))
    thr = gain[pi] - 3.0

    def interp(a, b):
        t = (thr - gain[a]) / (gain[b] - gain[a])
        return float(angles[a] + t * (angles[b] - angles[a]))

    left = next(
        (interp(i, i - 1) for i in range(pi, 0, -1) if gain[i - 1] <= thr <= gain[i]),
        None,
    )
    right = next(
        (interp(i, i + 1) for i in range(pi, len(gain) - 1)
         if gain[i] >= thr >= gain[i + 1]),
        None,
    )
    hpbw = (right - left) if left is not None and right is not None else None
    return float(angles[pi]), hpbw, left, right


# ── Polar helpers ─────────────────────────────────────────────────────────────

def polar_r(values: np.ndarray, floor: float) -> np.ndarray:
    return np.maximum(values - floor, 0.0)


def to_polar_xy(theta_deg, r):
    a = (180.0 - np.asarray(theta_deg)) * np.pi / 180.0
    r = np.asarray(r)
    return r * np.cos(a), r * np.sin(a)


def half_polar_grid_traces(r_max, tick_r, tick_labels, tick_theta):
    traces = []
    arc = np.linspace(0, 180, 361)

    for r, lbl in zip(tick_r, tick_labels):
        if r == 0:
            continue
        xc, yc = to_polar_xy(arc, np.full(len(arc), float(r)))
        outer  = abs(r - r_max) < 1e-9
        traces.append(go.Scatter(x=xc, y=yc, mode="lines",
            line=dict(color="gray" if outer else "lightgray",
                      width=1.0 if outer else 0.5),
            showlegend=False, hoverinfo="skip"))

    traces.append(go.Scatter(x=[-r_max, r_max], y=[0, 0], mode="lines",
        line=dict(color="gray", width=1), showlegend=False, hoverinfo="skip"))

    for t in tick_theta:
        if t in (0, 180):
            continue
        a = (180 - t) * np.pi / 180
        traces.append(go.Scatter(x=[0, r_max * np.cos(a)], y=[0, r_max * np.sin(a)],
            mode="lines", line=dict(color="lightgray", width=0.5),
            showlegend=False, hoverinfo="skip"))

    la = (180 - 30) * np.pi / 180
    for r, lbl in zip(tick_r, tick_labels):
        if r == 0:
            continue
        traces.append(go.Scatter(x=[r * np.cos(la)], y=[r * np.sin(la)],
            mode="text", text=[lbl], textfont=dict(size=8, color="gray"),
            textposition="top right", showlegend=False, hoverinfo="skip"))

    r_lbl = r_max * 1.12
    for t in tick_theta:
        a = (180 - t) * np.pi / 180
        traces.append(go.Scatter(x=[r_lbl * np.cos(a)], y=[r_lbl * np.sin(a)],
            mode="text", text=[f"{t - 90:.0f}°"], textfont=dict(size=9),
            textposition="middle center", showlegend=False, hoverinfo="skip"))

    return traces


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # Load each frequency separately; use common angle offset from first frequency
    raw_results = []
    test_id = None
    for freq_ghz in FREQUENCIES_GHZ:
        angles, gain, tid, actual = load_measurement(DB_FILE, freq_ghz * 1e9, TEST_RANK)
        if test_id is None:
            test_id = tid
        raw_results.append((angles, gain, actual))
        print(f"  {actual/1e9:.4f} GHz  G_peak={gain.max():.2f} dBi")

    # Common offset: center first frequency's beam at theta=90 (displayed 0°)
    angles0, gain0, _ = raw_results[0]
    common_offset = 90.0 - float(angles0[np.argmax(gain0)])

    results = []
    for (angles_raw, gain, actual), color in zip(raw_results, COLORS):
        angles = angles_raw + common_offset
        if MEAS_MIRRORED:
            angles = 180.0 - angles

        idx    = np.argsort(angles)
        angles = angles[idx]
        gain   = gain[idx]

        peak_ang, hpbw, left_x, right_x = compute_hpbw(angles, gain)
        beam_angle = peak_ang - 90.0

        hpbw_str = f"{hpbw:.1f}°" if hpbw is not None else "N/A"
        label    = (f"{actual/1e9:.3f} GHz    "
                    f"G={gain.max():.1f} dBi    "
                    f"peak={beam_angle:+.1f}°    "
                    f"HPBW={hpbw_str}")
        print(f"    {label}")

        results.append(dict(
            color=color, label=label,
            angles=angles, gain=gain,
            hpbw=hpbw, left_x=left_x, right_x=right_x,
        ))

    # ── Figure ─────────────────────────────────────────────────────────────────
    global_peak = max(r["gain"].max() for r in results)
    polar_floor = global_peak - POLAR_DYNAMIC_RANGE_DB
    r_max       = float(POLAR_DYNAMIC_RANGE_DB)
    tick_r      = [i * POLAR_DYNAMIC_RANGE_DB / 4 for i in range(5)]
    tick_lbls   = [f"{polar_floor + v:.0f} dBi" for v in tick_r]
    tick_theta  = list(range(0, 181, 30))

    cart_tick_vals = list(range(0, 181, 15))
    cart_tick_text = [f"{v - 90}°" for v in cart_tick_vals]

    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=("Cartesian", "Polar"),
        specs=[[{"type": "scatter"}, {"type": "scatter"}]],
        horizontal_spacing=0.10,
    )

    # Cartesian
    for r in results:
        fig.add_trace(go.Scatter(
            x=r["angles"], y=r["gain"],
            name=r["label"], mode="lines",
            line=dict(color=r["color"], width=2),
        ), row=1, col=1)

        if r["left_x"] is not None and r["right_x"] is not None:
            y3 = r["gain"].max() - 3.0
            fig.add_trace(go.Scatter(
                x=[r["left_x"], r["right_x"]], y=[y3, y3],
                mode="lines+markers",
                marker=dict(symbol="x", size=9, color=r["color"]),
                line=dict(color=r["color"], width=1.5, dash="dot"),
                showlegend=False, hoverinfo="skip",
            ), row=1, col=1)

    fig.update_xaxes(title_text="Angle  [0° = boresight]",
                     tickvals=cart_tick_vals, ticktext=cart_tick_text,
                     gridcolor="lightgray", row=1, col=1)
    fig.update_yaxes(title_text="Gain (dBi)",
                     gridcolor="lightgray", row=1, col=1)

    # Polar
    for tr in half_polar_grid_traces(r_max, tick_r, tick_lbls, tick_theta):
        fig.add_trace(tr, row=1, col=2)

    for r in results:
        xp, yp = to_polar_xy(r["angles"], polar_r(r["gain"], polar_floor))
        fig.add_trace(go.Scatter(
            x=xp, y=yp, name=r["label"], mode="lines",
            line=dict(color=r["color"], width=2),
            showlegend=False,
        ), row=1, col=2)

        for cx in (r["left_x"], r["right_x"]):
            if cx is not None:
                rx, ry = to_polar_xy(cx, polar_r(np.array([r["gain"].max() - 3.0]),
                                                  polar_floor))
                fig.add_trace(go.Scatter(x=rx, y=ry, mode="markers",
                    marker=dict(symbol="x", size=9, color=r["color"]),
                    showlegend=False, hoverinfo="skip",
                ), row=1, col=2)

    margin = r_max * 1.2
    fig.update_xaxes(range=[-margin, margin], showgrid=False, zeroline=False,
                     showticklabels=False, row=1, col=2)
    fig.update_yaxes(range=[-r_max * 0.2, margin], showgrid=False, zeroline=False,
                     showticklabels=False, row=1, col=2)
    fig.update_layout(yaxis2=dict(scaleanchor="x2", scaleratio=1))

    fig.update_layout(
        title_text=(f"Gain pattern — {PLANE_LABEL}  |  test #{test_id}  |  "
                    f"distance={DISTANCE_CM} cm<br>"
                    f"<sup>× markers and dotted lines show −3 dB (HPBW) points</sup>"),
        height=620, width=1300,
        legend=dict(orientation="v", yanchor="top", y=0.99,
                    xanchor="left", x=1.02),
    )

    html_path = os.path.abspath("gain_vs_angle.html")
    fig.write_html(html_path)
    fig.write_image("gain_vs_angle.png", width=1300, height=620)
    print(f"\nSaved: {html_path}")
    print("Saved: gain_vs_angle.png")
    webbrowser.open(f"file:///{html_path}")


if __name__ == "__main__":
    main()

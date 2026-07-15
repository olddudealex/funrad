"""
Run Manager — simulation runner, database tracker, and optimizer.

Usage
-----
  # Single run with default parameters:
  python run_manager.py run

  # Single run with overrides:
  python run_manager.py run --params '{"patch_length": 14.2, "air_gap": 2.0}'

  # Gradient-descent optimization:
  python run_manager.py optimize \
      --params '{"patch_length": 14.5, "aperture_stub": 5.0}' \
      --param-names '["patch_length", "aperture_stub"]' \
      --step-sizes '[0.2, 0.2]' \
      --lr 0.3 --max-iter 15

  # List all runs:
  python run_manager.py list

  # List runs for a specific optimizer run:
  python run_manager.py list --opt-run-id <uuid>

Database
--------
  runs.db  (SQLite, created next to this file on first run)

Schema
------
  runs(id, timestamp, params JSON, results JSON,
       sim_path, pdf_path, opt_run_id, iteration, objective)
"""

import os
import sys
import json
import copy
import uuid
import sqlite3
import tempfile
import argparse
import subprocess
from datetime import datetime, timezone

import numpy as np
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib
matplotlib.use("Agg")   # non-interactive backend — safe to call from threads
import matplotlib.pyplot as plt

# Simulation module
from aperture_coupled_single_patch import (
    P as P_DEFAULT, simulate, simulate_with_farfield, extract_results
)

# =============================================================================
# Database path
# =============================================================================

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runs.db")

# =============================================================================
# Database helpers
# =============================================================================

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT    NOT NULL,
    params      TEXT    NOT NULL,
    results     TEXT,
    sim_path    TEXT,
    pdf_path    TEXT,
    opt_run_id  TEXT,
    iteration   INTEGER,
    objective   REAL
);
CREATE INDEX IF NOT EXISTS idx_opt_run ON runs(opt_run_id, iteration);
"""


def init_db(db_path: str = DB_PATH) -> None:
    """Create the database and table if they do not exist."""
    con = sqlite3.connect(db_path)
    con.executescript(_SCHEMA)
    con.commit()
    con.close()


def _json_default(obj):
    """Fallback JSON serialiser for numpy scalars etc."""
    if isinstance(obj, (np.floating, np.integer)):
        return float(obj)
    return str(obj)


def save_run(
    params:      dict,
    results:     dict | None,
    sim_path:    str  = "",
    pdf_path:    str | None  = None,
    opt_run_id:  str | None  = None,
    iteration:   int | None  = None,
    objective:   float | None = None,
    db_path:     str  = DB_PATH,
) -> int:
    """Insert one run row and return its auto-increment id."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute(
        """INSERT INTO runs
           (timestamp, params, results, sim_path, pdf_path,
            opt_run_id, iteration, objective)
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            ts,
            json.dumps(params,  default=_json_default),
            json.dumps(results, default=_json_default) if results is not None else None,
            sim_path or "",
            pdf_path,
            opt_run_id,
            iteration,
            float(objective) if objective is not None else None,
        ),
    )
    row_id = cur.lastrowid
    con.commit()
    con.close()
    return row_id


def load_runs(
    opt_run_id: str | None = None,
    db_path:    str        = DB_PATH,
) -> list[dict]:
    """
    Return all run rows as a list of dicts (params/results already parsed).
    If opt_run_id is given, filter to that optimizer run ordered by iteration.
    """
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    if opt_run_id:
        cur.execute(
            "SELECT * FROM runs WHERE opt_run_id=? ORDER BY iteration, id",
            (opt_run_id,),
        )
    else:
        cur.execute("SELECT * FROM runs ORDER BY id")
    rows = []
    for row in cur.fetchall():
        d = dict(row)
        d["params"]  = json.loads(d["params"])  if d["params"]  else {}
        d["results"] = json.loads(d["results"]) if d["results"] else None
        rows.append(d)
    con.close()
    return rows


# =============================================================================
# Core evaluate function
# =============================================================================

def _run_tag(P: dict) -> str:
    """Return a short human-readable tag for filenames / DB sim_path column."""
    return (
        f"acsp"
        f"_f0={P['f0']/1e9:.2f}GHz"
        f"_h1={P['h1']:.3f}_h2={P['h2']:.3f}"
        f"_gap={P['air_gap']:.3f}"
        f"_pw={P['patch_width']:.3f}_pl={P['patch_length']:.3f}"
        f"_al={P['aperture_length']:.3f}_aw={P['aperture_width']:.3f}"
        f"_ao={P['aperture_offset']:.3f}_as={P['aperture_stub']:.3f}"
    )


def _generate_pdf(P: dict, freq: np.ndarray, results: dict,
                  farfield: dict | None = None) -> str:
    """
    Generate a PDF report for one simulation run and return its path.
    Saved next to the script in reports/<run_tag>.pdf
    """
    from utils import plot_s11, plot_smith_skrf, write_s1p_file

    reports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
    os.makedirs(reports_dir, exist_ok=True)

    tag = (f"acsp_f0={P['f0']/1e9:.2f}GHz"
           f"_pw={P['patch_width']:.2f}_pl={P['patch_length']:.2f}"
           f"_gap={P['air_gap']:.2f}"
           f"_al={P['aperture_length']:.2f}_as={P['aperture_stub']:.2f}")
    pdf_path = os.path.join(reports_dir, f"{tag}.pdf")

    s11_complex = np.array([complex(r[0], r[1]) for r in results["s11_complex"]])
    s11_dB      = 20.0 * np.log10(np.abs(s11_complex))
    freqInd     = int(np.argmin(np.abs(freq - P["f0"])))

    # Find resonance index ignoring non-finite values (avoid NaN/inf argmin hazard)
    _abs_s11 = np.where(np.isfinite(np.abs(s11_complex)), np.abs(s11_complex), np.inf)
    freqInd2 = int(np.argmin(_abs_s11))

    # Sanitize for matplotlib rendering: non-finite or |Γ|>2 would cause the Agg
    # C backend to integer-overflow on coordinate conversion → silent process kill.
    _bad = ~np.isfinite(s11_complex) | (np.abs(s11_complex) > 2.0)
    s11_plot = np.where(_bad, 0j, s11_complex)
    s11_dB_plot = np.where(np.isfinite(s11_dB), s11_dB, 0.0)

    s11_1 = s11_complex[freqInd];  s11_2 = s11_complex[freqInd2]
    patchR      = (1 + s11_1) / (1 - s11_1) * P["feed_R"]
    patchG_norm = (1 - s11_1) / (1 + s11_1)
    patchR2     = (1 + s11_2) / (1 - s11_2) * P["feed_R"]
    patchG2_norm= (1 - s11_2) / (1 + s11_2)

    sim_diverged = bool(np.any(_bad))

    with PdfPages(pdf_path) as pdf:
        # --- S11 ---
        fig, ax = plt.subplots()
        plot_s11(freq, s11_dB_plot, ax=ax)
        title = (f"S11 — pw={P['patch_width']:.2f} pl={P['patch_length']:.2f} "
                 f"gap={P['air_gap']:.2f} stub={P['aperture_stub']:.2f} mm")
        if sim_diverged:
            title += "  [WARNING: sim diverged — data clipped]"
        ax.set_title(title)
        pdf.savefig(fig); plt.close(fig)

        # --- Smith chart ---
        try:
            fig, ax = plt.subplots()
            plot_smith_skrf(
                s11_plot, freq_hz=freq,
                idx_main=freqInd, idx_res=freqInd2,
                patch_width_mm=P["patch_width"], patch_length_mm=P["patch_length"],
                patchR=patchR, patchG=patchG_norm,
                patchR2=patchR2, patchG2=patchG2_norm,
            )
            pdf.savefig(); plt.close()
        except Exception:
            plt.close("all")

        # --- Summary text page ---
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.axis("off")
        lines = [
            f"Design: Single Aperture-Coupled Patch",
            f"f0 = {P['f0']/1e9:.3f} GHz",
            f"",
            f"Patch:      width={P['patch_width']:.3f} mm   length={P['patch_length']:.3f} mm",
            f"PCB stack:  h1={P['h1']:.3f} mm   air_gap={P['air_gap']:.3f} mm   h2={P['h2']:.3f} mm",
            f"Aperture:   length={P['aperture_length']:.3f} mm   width={P['aperture_width']:.3f} mm",
            f"            offset={P['aperture_offset']:.3f} mm   stub={P['aperture_stub']:.3f} mm",
            f"Feed line:  width={P['feed_line_width']:.3f} mm   R={P['feed_R']} Ω",
            f"",
            f"Results:",
            f"  S11 at f0:        {results['s11_db_at_f0']:+.2f} dB",
            f"  S11 min:          {results.get('s11_min_db', float('nan')):+.2f} dB",
            f"  Resonant freq:    {results['resonant_freq_hz']/1e9:.4f} GHz",
            f"  −10 dB bandwidth: "
            + (f"{results['bandwidth_hz']/1e6:.1f} MHz"
               if results.get("bandwidth_hz") else "< threshold"),
        ]
        if farfield is not None:
            lines.append(f"")
            lines.append(f"  Far-field computed at {farfield['freq']/1e9:.3f} GHz  (pages 4-5)")
        ax.text(0.05, 0.95, "\n".join(lines), transform=ax.transAxes,
                va="top", family="monospace", fontsize=10)
        pdf.savefig(fig); plt.close(fig)

        # --- 2D far-field patterns (XZ and YZ cuts) ---
        if farfield is not None:
            try:
                import matplotlib.cm as _cm
                EISO  = farfield["EISO"]
                f0_hz = farfield["freq"]

                fig = plt.figure(figsize=(12, 9))
                fig.suptitle(
                    f"Far-Field Pattern at {f0_hz/1e9:.3f} GHz", fontsize=12)

                for row_idx, (key, plane_label) in enumerate([
                    ("xz", "XZ-plane (E-plane, phi=0 deg)"),
                    ("yz", "YZ-plane (H-plane, phi=90 deg)"),
                ]):
                    cut     = farfield[key]
                    ang     = np.asarray(cut["ang"])
                    normE   = np.asarray(cut["normE"])
                    ang_deg = np.degrees(ang)

                    e_safe   = np.where(normE > 0, normE, 1e-30)
                    gain_dBi = 20.0 * np.log10(e_safe / EISO)
                    gain_max = float(gain_dBi.max())
                    gain_rel = gain_dBi - gain_max   # dBc, 0 at peak

                    # Cartesian subplot
                    ax_c = fig.add_subplot(2, 2, row_idx * 2 + 1)
                    ax_c.plot(ang_deg, gain_dBi, linewidth=1.5)
                    ax_c.set_xlabel("Angle (deg)")
                    ax_c.set_ylabel("Gain (dBi)")
                    ax_c.set_title(
                        f"{plane_label}\nCartesian  (peak {gain_max:.1f} dBi)")
                    ax_c.grid(True, alpha=0.4)
                    ax_c.set_xlim(ang_deg.min(), ang_deg.max())
                    ax_c.axvline(0, color="k", linewidth=0.5, alpha=0.4)

                    # Polar subplot  (shift so -40 dBc → r=0, 0 dBc → r=40)
                    ax_p = fig.add_subplot(2, 2, row_idx * 2 + 2, polar=True)
                    gain_rel_clip = np.clip(gain_rel, -40, 0)
                    r_polar = gain_rel_clip + 40
                    ax_p.plot(ang, r_polar, linewidth=1.5)
                    ax_p.set_theta_zero_location("N")
                    ax_p.set_theta_direction(-1)   # clockwise = conventional
                    ax_p.set_rticks([0, 10, 20, 30, 40])
                    ax_p.set_yticklabels(["-40", "-30", "-20", "-10", "0 dBc"],
                                         fontsize=7)
                    ax_p.set_title(
                        f"{plane_label}\nPolar (peak {gain_max:.1f} dBi)",
                        pad=14, fontsize=9)

                fig.tight_layout()
                pdf.savefig(fig); plt.close(fig)
            except Exception as _ff2d_err:
                print(f"[WARNING] 2D far-field page failed: {_ff2d_err}")
                plt.close("all")

            # --- 3D directivity surface ---
            try:
                import matplotlib.cm as _cm
                from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

                EISO   = farfield["EISO"]
                f0_hz  = farfield["freq"]
                theta  = np.asarray(farfield["3d"]["theta"])
                phi    = np.asarray(farfield["3d"]["phi"])
                normE  = np.asarray(farfield["3d"]["normE"])

                # Downsample for Agg PDF rendering speed
                if theta.shape[0] > 72 or theta.shape[1] > 72:
                    step  = max(theta.shape[0] // 72, theta.shape[1] // 72, 1)
                    theta = theta[::step, ::step]
                    phi   = phi[::step, ::step]
                    normE = normE[::step, ::step]

                e_safe   = np.where(normE > 0, normE, 1e-30)
                gain_dBi = 20.0 * np.log10(e_safe / EISO)

                # Directivity shape: r proportional to linear directivity
                gain_lin = (e_safe / EISO) ** 2
                r_norm   = gain_lin / gain_lin.max()

                x = r_norm * np.sin(theta) * np.cos(phi)
                y = r_norm * np.sin(theta) * np.sin(phi)
                z = r_norm * np.cos(theta)

                norm_map  = plt.Normalize(float(gain_dBi.min()),
                                          float(gain_dBi.max()))
                face_cols = _cm.jet(norm_map(gain_dBi))

                fig_3d = plt.figure(figsize=(10, 8))
                ax3d   = fig_3d.add_subplot(111, projection="3d")
                ax3d.plot_surface(x, y, z, facecolors=face_cols,
                                  alpha=0.85, linewidth=0, antialiased=False)
                ax3d.set_xlabel("X"); ax3d.set_ylabel("Y"); ax3d.set_zlabel("Z")
                ax3d.set_title(
                    f"3D Directivity Pattern at {f0_hz/1e9:.3f} GHz\n"
                    f"Peak gain: {float(gain_dBi.max()):.1f} dBi",
                    fontsize=11)

                sm = _cm.ScalarMappable(cmap="jet", norm=norm_map)
                sm.set_array([])
                fig_3d.colorbar(sm, ax=ax3d, label="Gain (dBi)",
                                shrink=0.5, pad=0.1)
                fig_3d.tight_layout()
                pdf.savefig(fig_3d); plt.close(fig_3d)
            except Exception as _ff3d_err:
                print(f"[WARNING] 3D far-field page failed: {_ff3d_err}")
                plt.close("all")

    # Also save Touchstone
    touchstone_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "touchstone")
    os.makedirs(touchstone_dir, exist_ok=True)
    s1p_path = os.path.join(touchstone_dir, f"{tag}.s1p")
    write_s1p_file(s1p_path, freq, P["feed_R"], s11_complex)

    return pdf_path


def evaluate(
    params_dict:      dict,
    opt_run_id:       str | None  = None,
    iteration:        int | None  = None,
    sim_path:         str | None  = None,
    num_threads:      int          = 4,
    db_path:          str          = DB_PATH,
    compute_farfield: bool         = False,
) -> dict:
    """
    Run EMerge FEM simulation, extract results, save to DB.

    Parameters
    ----------
    params_dict      : Overrides merged on top of P_DEFAULT.
    opt_run_id       : UUID string for the optimizer run (None = standalone).
    iteration        : Optimizer iteration index (None = standalone).
    sim_path         : Label stored in DB (not used as a real directory).
    num_threads      : Passed to simulate() (PARDISO auto-selects thread count).
    db_path          : Path to the SQLite database.
    compute_farfield : If True, also compute far-field patterns and add them
                       to the PDF report (slower — adds one extra solver pass).

    Returns
    -------
    dict from extract_results(), also contains "run_id" (DB row id).
    """
    P = copy.deepcopy(P_DEFAULT)
    P.update(params_dict)

    if sim_path is None:
        sim_path = _run_tag(P)

    if compute_farfield:
        freq, s11, farfield_data = simulate_with_farfield(P, num_threads=num_threads)
    else:
        freq, s11    = simulate(P, num_threads=num_threads)
        farfield_data = None

    results   = extract_results(freq, s11, P["f0"])
    objective = results["s11_db_at_f0"]

    try:
        pdf_path = _generate_pdf(P, freq, results, farfield=farfield_data)
    except Exception as _pdf_err:
        print(f"[WARNING] PDF generation failed: {_pdf_err}")
        pdf_path = None

    run_id = save_run(
        params     = P,
        results    = results,
        sim_path   = sim_path,
        pdf_path   = pdf_path,
        opt_run_id = opt_run_id,
        iteration  = iteration,
        objective  = objective,
        db_path    = db_path,
    )
    results["run_id"]   = run_id
    results["pdf_path"] = pdf_path
    return results


# =============================================================================
# Subprocess-isolated evaluate
# =============================================================================

def evaluate_isolated(
    params_dict: dict,
    opt_run_id:  str | None  = None,
    iteration:   int | None  = None,
    sim_path:    str | None  = None,
    num_threads: int          = 4,
    db_path:     str          = DB_PATH,
    timeout:     int          = 7200,
) -> dict:
    """
    Run evaluate() in a child process so that any fatal errors in the solver
    are contained here and surface as a Python RuntimeError instead of silently
    killing the caller's process.
    """
    # Write result to a temp file — avoids stdout-parsing fragility
    tf = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    result_file = tf.name
    tf.close()   # close so the subprocess can write to it on Windows

    try:
        cmd = [
            sys.executable, os.path.abspath(__file__),
            "run",
            "--params",      json.dumps(params_dict, default=_json_default),
            "--db",          db_path,
            "--threads",     str(num_threads),
            "--result-file", result_file,
        ]
        if opt_run_id is not None:
            cmd += ["--opt-run-id", opt_run_id]
        if iteration is not None:
            cmd += ["--iteration",  str(iteration)]
        if sim_path is not None:
            cmd += ["--sim-path",   sim_path]

        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

        if proc.returncode != 0:
            stderr = proc.stderr.strip()[-500:]
            raise RuntimeError(
                f"Simulation subprocess exited {proc.returncode}"
                + (f": {stderr}" if stderr else " (no stderr)")
            )

        if not os.path.isfile(result_file) or os.path.getsize(result_file) == 0:
            raise RuntimeError("Simulation subprocess wrote no result")

        with open(result_file, "r") as f:
            return json.load(f)

    finally:
        try:
            os.unlink(result_file)
        except OSError:
            pass


# =============================================================================
# Gradient descent optimizer
# =============================================================================

def _termination_report(
    stop_reason:    str,
    history:        list,
    param_names:    list,
    lr:             float,
    max_stagnation: int,
) -> str:
    """
    Build a human-readable termination report and print it.
    Returns the multi-line string so callers can forward it to a GUI.
    """
    SEP  = "=" * 64
    lines = [SEP, "  OPTIMIZATION STOPPED", SEP]

    reason_text = {
        "converged":      "Gradient norm < tol  — gradient converged to (near) zero",
        "stagnated":      (f"Stagnated — backtracking failed {max_stagnation} iterations "
                           "in a row.\n"
                           "  The gradient direction leads to a worse region;\n"
                           "  reducing the step size further does not help."),
        "max_iterations": "Reached max_iter limit without converging or stagnating",
    }.get(stop_reason, stop_reason)
    lines.append(f"  Reason : {reason_text}")

    finite = [h for h in history if h["objective"] is not None and np.isfinite(h["objective"])]
    if not finite:
        lines += [SEP, ""]
        report = "\n".join(lines)
        print(report)
        return report

    best  = finite[int(np.argmin([h["objective"] for h in finite]))]
    last  = history[-1]

    lines.append(f"  Iters  : {last['iteration'] + 1}  |  "
                 f"best obj = {best['objective']:+.4f}  (iter {best['iteration']})")

    # --- Best params ---------------------------------------------------------
    lines.append("\n  Best params found:")
    for name in param_names:
        val = best["params"].get(name, float("nan"))
        lines.append(f"    {name:25s} = {val:.5f}")

    # --- Gradient breakdown at the last logged iteration --------------------
    last_grad = last.get("gradient", {})
    if last_grad:
        lines.append(f"\n  Gradient at last iteration (iter {last['iteration']}):")
        lines.append(f"    {'Parameter':25s}  {'gradient':>10}  {'update dir':>11}  {'|lr×grad|':>10}")

        sorted_grad = sorted(last_grad.items(), key=lambda x: abs(x[1]), reverse=True)
        for name, g in sorted_grad:
            # Gradient descent moves in -grad direction
            direction = "wants [+]" if g < 0 else "wants [-]"
            lines.append(f"    {name:25s}  {g:>+10.4f}  {direction:>11}  {abs(lr * g):>10.4f}")

        top_name, top_g = sorted_grad[0]
        top_dir = "increase" if top_g < 0 else "decrease"
        lines.append(
            f"\n  Dominant param : '{top_name}'  "
            f"(gradient {top_g:+.4f}, optimizer wants to {top_dir} it "
            f"by ~{abs(lr * top_g):.4f})"
        )

    # --- Stop-reason specific advice ----------------------------------------
    if stop_reason == "stagnated":
        top_name, top_g = sorted(last_grad.items(),
                                 key=lambda x: abs(x[1]), reverse=True)[0] if last_grad else ("?", 0)
        top_dir = "increase" if top_g < 0 else "decrease"
        lines += [
            "",
            "  What this means:",
            f"    The optimizer tried to {top_dir} '{top_name}' (and adjust",
            "    other params proportionally), but every step size from lr",
            f"    down to lr × {0.5**7:.4f}× was rejected — each candidate was",
            "    worse than the current point.",
            "",
            "  Possible causes:",
            "    1. You are at or very near a local minimum (good result).",
            "    2. The objective surface is non-convex and the gradient is",
            "       pointing uphill in the global sense.",
            "    3. The finite-difference step size is too large, so gradient",
            "       direction is inaccurate.",
            "",
            "  Suggestions:",
            f"    • If S11 is already good, this is fine — you are done.",
            f"    • Otherwise try restarting from a different point.",
            f"    • Try reducing the finite-difference step sizes to get a",
            f"      more accurate gradient (current grad_norm={last.get('grad_norm', float('nan')):.4f}).",
            f"    • Try a different objective (e.g. 'Match resonance to f0').",
        ]
    elif stop_reason == "converged":
        lines += ["", "  Gradient is essentially zero — this is a local minimum."]
    elif stop_reason == "max_iterations":
        lines += ["", "  Increase max_iter or inspect the trajectory to decide next steps."]

    lines.append(SEP)
    report = "\n".join(lines)
    print(report)
    return report


def gradient_descent(
    P_init:           dict,
    param_names:      list[str],
    step_sizes:       list[float],
    objective_fn,                  # callable(P, opt_run_id, iteration) -> results dict
    max_iter:         int   = 20,
    lr:               float = 0.1,
    tol:              float = 1e-4,
    backtrack_factor: float = 0.5,
    max_backtrack:    int   = 8,
    max_stagnation:   int   = 3,   # stop after this many consecutive failed backtracks
    bounds:           dict  = None,
    metric_fn         = None,
    progress_fn       = None,
) -> dict:
    """
    Minimise metric_fn(results) using central finite differences + backtracking line search.
    Default metric: s11_db_at_f0.

    Cost per iteration: 2*len(param_names) + 1 centre sims + up to max_backtrack candidates.
    All evaluations are stored in the DB under the same opt_run_id.

    Parameters
    ----------
    P_init           : Starting parameter dict (full).
    param_names      : Names of parameters to optimise (must be keys in P_init).
    step_sizes       : Finite-difference step h per parameter (mm or Hz).
    objective_fn     : evaluate() or a wrapper with the same signature.
    max_iter         : Maximum gradient steps.
    lr               : Initial learning rate (gradient step scale).
    tol              : Stop when ||gradient|| < tol.
    backtrack_factor : Multiply lr_eff by this on each failed backtrack trial (default 0.5).
    max_backtrack    : Max step-size reductions per backtracking round (default 8).
    max_stagnation   : Stop after this many consecutive iterations where backtracking
                       finds no improvement (default 3).

    Returns
    -------
    dict with keys:
        opt_run_id   str    UUID for this optimization run
        best_params  dict   P at the best observed objective
        best_obj     float  Best objective value seen
        history      list   One entry per iteration with params/obj/gradient/lr_eff
        stop_reason  str    "converged" | "stagnated" | "max_iterations"
        n_iters      int    Number of iterations completed
    """
    opt_run_id = uuid.uuid4().hex
    if metric_fn is None:
        metric_fn = lambda r: r["s11_db_at_f0"]

    def _clip(P):
        if not bounds:
            return P
        for name, (lo, hi) in bounds.items():
            if name not in P:
                continue
            if lo is not None:
                P[name] = max(lo, P[name])
            if hi is not None:
                P[name] = min(hi, P[name])
        return P

    P_cur         = copy.deepcopy(P_init)
    history       = []
    stagnation_ct = 0
    stop_reason   = "max_iterations"

    print(f"\n=== Gradient Descent  opt_run_id={opt_run_id} ===")
    print(f"    Params:     {param_names}")
    print(f"    Step sizes: {step_sizes}")
    print(f"    lr={lr}  max_iter={max_iter}  tol={tol}")
    print(f"    backtrack_factor={backtrack_factor}  max_backtrack={max_backtrack}  max_stagnation={max_stagnation}\n")

    for it in range(max_iter):
        # --- Centre evaluation ---
        res_c = objective_fn(P_cur, opt_run_id, it)
        obj_c = metric_fn(res_c)
        if not np.isfinite(obj_c):
            print(f"  iter {it:3d} | centre objective non-finite ({obj_c}); skipping")
            history.append({"iteration": it, "params": copy.deepcopy(P_cur),
                            "objective": obj_c, "gradient": {}, "grad_norm": float("nan"),
                            "lr_eff": 0.0})
            if progress_fn is not None:
                progress_fn(it, obj_c, float("nan"), copy.deepcopy(P_cur))
            continue

        # --- Central finite differences ---
        grad = {}
        for name, h in zip(param_names, step_sizes):
            P_plus  = copy.deepcopy(P_cur);  P_plus[name]  += h;  P_plus  = _clip(P_plus)
            P_minus = copy.deepcopy(P_cur);  P_minus[name] -= h;  P_minus = _clip(P_minus)
            obj_plus  = metric_fn(objective_fn(P_plus,  opt_run_id, it))
            obj_minus = metric_fn(objective_fn(P_minus, opt_run_id, it))
            if not np.isfinite(obj_plus) or not np.isfinite(obj_minus):
                print(f"  iter {it:3d} | non-finite perturbed obj for '{name}'; zeroing gradient")
                grad[name] = 0.0
            else:
                grad[name] = (obj_plus - obj_minus) / (2.0 * h)

        grad_norm = float(np.sqrt(sum(g**2 for g in grad.values())))
        param_str = "  ".join(f"{n}={P_cur[n]:.4f}" for n in param_names)

        # --- Convergence check ---
        if grad_norm < tol:
            history.append({"iteration": it, "params": copy.deepcopy(P_cur),
                            "objective": obj_c, "gradient": copy.copy(grad),
                            "grad_norm": grad_norm, "lr_eff": 0.0})
            print(f"  iter {it:3d} | obj={obj_c:+.6f} | grad_norm={grad_norm:.2e} | {param_str}")
            if progress_fn is not None:
                progress_fn(it, obj_c, grad_norm, copy.deepcopy(P_cur))
            stop_reason = "converged"
            break

        # --- Backtracking line search ---
        lr_eff   = lr
        P_next   = copy.deepcopy(P_cur)
        accepted = False
        for _bt in range(max_backtrack):
            P_cand = copy.deepcopy(P_cur)
            for name in param_names:
                P_cand[name] = P_cur[name] - lr_eff * grad[name]
            P_cand   = _clip(P_cand)
            obj_cand = metric_fn(objective_fn(P_cand, opt_run_id, it))
            if np.isfinite(obj_cand) and obj_cand < obj_c:
                P_next   = P_cand
                accepted = True
                break
            lr_eff *= backtrack_factor

        if accepted:
            stagnation_ct = 0
        else:
            lr_eff         = 0.0
            stagnation_ct += 1
            print(f"  iter {it:3d} | backtracking failed  "
                  f"[stagnation {stagnation_ct}/{max_stagnation}]")

        # --- Log ---
        history.append({"iteration": it, "params": copy.deepcopy(P_cur),
                        "objective": obj_c, "gradient": copy.copy(grad),
                        "grad_norm": grad_norm, "lr_eff": lr_eff})
        print(f"  iter {it:3d} | obj={obj_c:+.6f} | grad_norm={grad_norm:.2e} | "
              f"lr_eff={lr_eff:.2e} | {param_str}")
        if progress_fn is not None:
            progress_fn(it, obj_c, grad_norm, copy.deepcopy(P_cur))

        # --- Stagnation check ---
        if stagnation_ct >= max_stagnation:
            stop_reason = "stagnated"
            break

        P_cur = P_next

    # --- Termination report --------------------------------------------------
    report = _termination_report(stop_reason, history, param_names, lr, max_stagnation)

    finite_h = [h for h in history if h["objective"] is not None and np.isfinite(h["objective"])]
    best_idx = int(np.argmin([h["objective"] for h in finite_h])) if finite_h else 0
    best_h   = finite_h[best_idx] if finite_h else history[0]
    return {
        "opt_run_id":  opt_run_id,
        "best_params": best_h["params"],
        "best_obj":    best_h["objective"],
        "history":     history,
        "stop_reason": stop_reason,
        "n_iters":     len(history),
        "report":      report,
    }


# =============================================================================
# Optimization run plotter (works from DB alone — no simulation needed)
# =============================================================================

def plot_opt_run(opt_run_id: str, db_path: str = DB_PATH):
    """
    Plot objective and parameter trajectories for one optimization run.

    Reads only from the DB (no simulation). Returns the matplotlib Figure so
    callers can embed it in a GUI or save it themselves.

    Strategy: within each iteration, the first row by id (ascending) is the
    centre evaluation (P_cur). Perturbed and backtracking rows follow.
    """
    rows = load_runs(opt_run_id=opt_run_id, db_path=db_path)
    if not rows:
        print(f"[plot_opt_run] No rows for opt_run_id={opt_run_id}")
        return None

    # --- One row per iteration: lowest id = centre eval ----------------------
    by_iter: dict[int, dict] = {}
    for r in rows:
        it = r.get("iteration")
        if it is None:
            continue
        if it not in by_iter or r["id"] < by_iter[it]["id"]:
            by_iter[it] = r

    iters = sorted(by_iter.keys())
    if not iters:
        return None

    params_list = [by_iter[it]["params"]  for it in iters]
    objectives  = [by_iter[it]["objective"] for it in iters]
    ts_start    = by_iter[iters[0]]["timestamp"][:16]
    ts_end      = by_iter[iters[-1]]["timestamp"][:16]

    # Bandwidth from results (may be None if resonance was above -10 dB)
    bws = []
    for it in iters:
        res = by_iter[it].get("results") or {}
        bw  = res.get("bandwidth_hz")
        bws.append(bw / 1e6 if bw else None)

    # --- Which params actually moved? ----------------------------------------
    first_p = params_list[0]
    numeric_keys = [
        k for k, v in first_p.items()
        if isinstance(v, (int, float)) and not isinstance(v, bool) and not k.startswith("_")
    ]
    changed_keys = [
        k for k in numeric_keys
        if max(abs(p.get(k, 0) - first_p.get(k, 0)) for p in params_list) > 1e-9
    ]

    # --- Build figure ---------------------------------------------------------
    _COLORS = [
        "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
        "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
    ]

    fig, (ax_obj, ax_param) = plt.subplots(2, 1, figsize=(10, 8))
    fig.suptitle(
        f"Opt run: {opt_run_id[:12]}…   "
        f"({ts_start} → {ts_end},  {len(iters)} iters)",
        fontsize=10,
    )

    # --- Top: objective -------------------------------------------------------
    finite_obj = [o for o in objectives if o is not None and np.isfinite(o)]
    ax_obj.plot(iters, objectives, "b-o", linewidth=2, markersize=6,
                label="S11 at f0 (dB)")
    if finite_obj:
        best_i = min(range(len(objectives)),
                     key=lambda i: objectives[i] if objectives[i] is not None else 0)
        ax_obj.plot(iters[best_i], objectives[best_i], "r*", markersize=14,
                    zorder=5, label=f"best  {objectives[best_i]:+.2f} dB")
    ax_obj.set_ylabel("Objective (dB)")
    ax_obj.set_title("Objective vs. Iteration")
    ax_obj.grid(True, alpha=0.4)
    ax_obj.legend(fontsize=9, loc="lower left")

    # Bandwidth on twin right axis
    bw_pts = [(it, bw) for it, bw in zip(iters, bws) if bw is not None]
    if bw_pts:
        ax2 = ax_obj.twinx()
        bw_its, bw_vals = zip(*bw_pts)
        ax2.plot(list(bw_its), list(bw_vals), "g--s", linewidth=1.5,
                 markersize=5, alpha=0.8, label="−10 dB BW")
        ax2.set_ylabel("−10 dB BW (MHz)", color="green")
        ax2.tick_params(axis="y", labelcolor="green")
        ax2.legend(fontsize=9, loc="upper right")

    # --- Bottom: parameter trajectory ----------------------------------------
    for i, name in enumerate(changed_keys):
        init = first_p.get(name, 0.0)
        ref  = abs(init) if abs(init) > 1e-6 else 1.0
        y    = [(p.get(name, init) - init) / ref * 100 for p in params_list]
        label = name if abs(init) > 1e-6 else f"{name} (×100 mm)"
        ax_param.plot(iters, y, "-o", color=_COLORS[i % len(_COLORS)],
                      linewidth=1.5, markersize=5, label=label)

    ax_param.axhline(0, color="k", linewidth=0.5, alpha=0.5)
    ax_param.set_xlabel("Iteration")
    ax_param.set_ylabel("Δ from start (%)")
    ax_param.set_title("Parameter Trajectory  (% change from iteration 0)")
    ax_param.grid(True, alpha=0.4)
    if changed_keys:
        ax_param.legend(fontsize=9, loc="best")

    fig.tight_layout()
    return fig


# =============================================================================
# CLI entry point
# =============================================================================

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run manager for aperture-coupled single-patch simulation."
    )
    sub = parser.add_subparsers(dest="command")

    # -- run --
    p_run = sub.add_parser("run", help="Single simulation run")
    p_run.add_argument(
        "--params", type=str, default="{}",
        help='JSON dict of P overrides, e.g. \'{"patch_length": 14.2}\'',
    )
    p_run.add_argument("--db",          type=str, default=DB_PATH)
    p_run.add_argument("--threads",     type=int, default=4)
    p_run.add_argument("--opt-run-id",  type=str, default=None)
    p_run.add_argument("--iteration",   type=int, default=None)
    p_run.add_argument("--sim-path",    type=str, default=None)
    p_run.add_argument("--result-file", type=str, default=None,
                       help="Write JSON result to this file instead of stdout")

    # -- optimize --
    p_opt = sub.add_parser("optimize", help="Gradient-descent optimization")
    p_opt.add_argument(
        "--params", type=str, default="{}",
        help="JSON dict of starting P overrides",
    )
    p_opt.add_argument(
        "--param-names", type=str, required=True,
        help='JSON list of parameter names, e.g. \'["patch_length", "aperture_stub"]\'',
    )
    p_opt.add_argument(
        "--step-sizes", type=str, required=True,
        help="JSON list of finite-difference step sizes (same order as --param-names)",
    )
    p_opt.add_argument("--lr",       type=float, default=0.1)
    p_opt.add_argument("--max-iter", type=int,   default=20)
    p_opt.add_argument("--tol",      type=float, default=1e-4)
    p_opt.add_argument("--db",       type=str,   default=DB_PATH)
    p_opt.add_argument("--threads",  type=int,   default=4)

    # -- list --
    p_list = sub.add_parser("list", help="Print saved runs from database")
    p_list.add_argument("--opt-run-id", type=str, default=None)
    p_list.add_argument("--db", type=str, default=DB_PATH)

    # -- plot-opt --
    p_plot = sub.add_parser("plot-opt", help="Plot objective + params for an opt run")
    p_plot.add_argument("--opt-run-id", type=str, default=None,
                        help="UUID prefix (default: most recent opt run)")
    p_plot.add_argument("--db",  type=str, default=DB_PATH)
    p_plot.add_argument("--out", type=str, default=None,
                        help="Save PNG to this path instead of opening a viewer")

    # -- best --
    p_best = sub.add_parser("best", help="Show the N best runs by objective")
    p_best.add_argument("--n",         type=int, default=5,
                        help="Number of top runs to show (default: 5)")
    p_best.add_argument("--opt-run-id", type=str, default=None,
                        help="Restrict search to one optimizer run")
    p_best.add_argument("--db",        type=str, default=DB_PATH)

    return parser


if __name__ == "__main__":
    parser = _build_parser()
    args   = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    init_db(args.db)

    # ---- Single run --------------------------------------------------------
    if args.command == "run":
        overrides = json.loads(args.params)
        results   = evaluate(
            overrides,
            opt_run_id  = args.opt_run_id,
            iteration   = args.iteration,
            sim_path    = args.sim_path,
            num_threads = args.threads,
            db_path     = args.db,
        )
        result_dict = {k: v for k, v in results.items() if k != "s11_complex"}
        if args.result_file:
            with open(args.result_file, "w") as _rf:
                json.dump(result_dict, _rf, default=_json_default)
        else:
            print(json.dumps(result_dict, indent=2, default=_json_default))

    # ---- Optimization ------------------------------------------------------
    elif args.command == "optimize":
        P_init = copy.deepcopy(P_DEFAULT)
        P_init.update(json.loads(args.params))

        names  = json.loads(args.param_names)
        steps  = json.loads(args.step_sizes)

        def obj_fn(P, oid, it):
            return evaluate(P, opt_run_id=oid, iteration=it,
                            num_threads=args.threads, db_path=args.db)

        result = gradient_descent(
            P_init, names, steps, obj_fn,
            max_iter=args.max_iter,
            lr=args.lr,
            tol=args.tol,
        )

        print(f"\nBest objective : {result['best_obj']:+.3f} dB")
        print(f"Best params    : "
              + "  ".join(f"{n}={result['best_params'][n]:.4f}" for n in names))
        print(f"opt_run_id     : {result['opt_run_id']}")

    # ---- List runs ---------------------------------------------------------
    elif args.command == "list":
        rows = load_runs(opt_run_id=args.opt_run_id, db_path=args.db)
        if not rows:
            print("No runs found.")
        else:
            hdr = f"{'id':>5}  {'timestamp':20}  {'obj (dB)':>10}  {'iter':>4}  {'opt_run_id':32}  sim_path"
            print(hdr)
            print("-" * len(hdr))
            for r in rows:
                obj_s = f"{r['objective']:+.3f}" if r["objective"] is not None else "    N/A"
                it_s  = str(r["iteration"]) if r["iteration"] is not None else "  -"
                oid_s = r["opt_run_id"] or ""
                print(f"{r['id']:5d}  {r['timestamp']:20}  {obj_s:>10}  {it_s:>4}  {oid_s:32}  {r['sim_path']}")

    # ---- Plot optimization run ---------------------------------------------
    elif args.command == "plot-opt":
        con = sqlite3.connect(args.db)
        con.row_factory = sqlite3.Row
        if args.opt_run_id:
            # Accept prefix
            row = con.execute(
                "SELECT opt_run_id FROM runs WHERE opt_run_id LIKE ? LIMIT 1",
                (args.opt_run_id + "%",),
            ).fetchone()
            oid = row["opt_run_id"] if row else None
        else:
            # Latest opt run by largest id
            row = con.execute(
                "SELECT opt_run_id FROM runs "
                "WHERE opt_run_id IS NOT NULL "
                "GROUP BY opt_run_id ORDER BY MAX(id) DESC LIMIT 1"
            ).fetchone()
            oid = row["opt_run_id"] if row else None
        con.close()

        if not oid:
            print("No optimization runs found in the database.")
            sys.exit(1)

        print(f"Plotting opt_run_id: {oid}")
        import tempfile
        fig = plot_opt_run(oid, db_path=args.db)
        if fig is None:
            print("Nothing to plot.")
            sys.exit(1)

        if args.out:
            fig.savefig(args.out, dpi=150)
            print(f"Saved to {args.out}")
        else:
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            fig.savefig(tmp.name, dpi=150)
            tmp.close()
            print(f"Opening {tmp.name}")
            os.startfile(tmp.name)

    # ---- Best runs ---------------------------------------------------------
    elif args.command == "best":
        con = sqlite3.connect(args.db)
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        if args.opt_run_id:
            cur.execute(
                "SELECT * FROM runs WHERE opt_run_id=? AND objective IS NOT NULL "
                "ORDER BY objective ASC LIMIT ?",
                (args.opt_run_id, args.n),
            )
        else:
            cur.execute(
                "SELECT * FROM runs WHERE objective IS NOT NULL "
                "ORDER BY objective ASC LIMIT ?",
                (args.n,),
            )
        rows = [dict(r) for r in cur.fetchall()]
        con.close()

        if not rows:
            print("No runs with recorded objective found.")
        else:
            print(f"\nTop {len(rows)} runs by objective (most negative = best S11 at f0):\n")
            hdr = f"{'id':>5}  {'timestamp':20}  {'obj (dB)':>10}  {'BW (MHz)':>10}  {'iter':>4}  {'opt_run_id':32}  pdf_path"
            print(hdr)
            print("-" * len(hdr))
            for r in rows:
                results = json.loads(r["results"]) if r["results"] else {}
                bw = results.get("bandwidth_hz")
                bw_s  = f"{bw/1e6:.1f}" if bw else "  none"
                it_s  = str(r["iteration"]) if r["iteration"] is not None else "  -"
                oid_s = (r["opt_run_id"] or "")[:32]
                pdf_s = r["pdf_path"] or ""
                print(f"{r['id']:5d}  {r['timestamp']:20}  {r['objective']:+10.3f}  {bw_s:>10}  {it_s:>4}  {oid_s:32}  {pdf_s}")

            best = rows[0]
            best_p = json.loads(best["params"]) if best["params"] else {}
            print(f"\nBest run id={best['id']}  obj={best['objective']:+.3f} dB")
            interesting = ["patch_length", "patch_width", "aperture_length",
                           "aperture_width", "aperture_stub", "air_gap"]
            print("  Params: " + "  ".join(
                f"{k}={best_p[k]:.4f}" for k in interesting if k in best_p
            ))
            if best["pdf_path"]:
                print(f"  PDF:    {best['pdf_path']}")

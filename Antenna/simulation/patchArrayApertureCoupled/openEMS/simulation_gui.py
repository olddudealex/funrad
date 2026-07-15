"""
Antenna Simulation GUI
======================
Supports: Single Patch | 5-Patch Array (aperture-coupled, two-PCB)

Run:  python simulation_gui.py
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import queue
import threading
import copy
import os
import sys

import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# --------------------------------------------------------------------------- #
#  Parameter metadata: (key, group, label, default_step, default_min, max,
#                       can_optimize, is_list)
# --------------------------------------------------------------------------- #

PARAM_META_SINGLE = [
    # key                  group        label                               step    min      max    opt    list
    ("f0",             "Frequency",  "Centre frequency (Hz)",              1e8,   4e9,    8e9,   False, False),
    ("fc",             "Frequency",  "Gaussian corner half-BW (Hz)",       1e7,   1e7,    2e9,   False, False),
    ("substrate_epsR", "Substrate",  "Relative permittivity εr",           0.05,  1.0,    12.0,  False, False),
    ("substrate_tan",  "Substrate",  "Loss tangent",                       5e-4,  0.0,    0.05,  False, False),
    ("substrate_cells","Substrate",  "Mesh layers per substrate",          1,     2,      8,     False, False),
    ("h1",             "PCB Stack",  "PCB1 thickness — feed board (mm)",   0.05,  0.1,    3.2,   True,  False),
    ("h2",             "PCB Stack",  "PCB2 thickness — patch board (mm)",  0.05,  0.1,    3.2,   True,  False),
    ("air_gap",        "PCB Stack",  "Air gap between PCBs (mm)",          0.1,   0.1,    10.0,  True,  False),
    ("sub_width",      "Board",      "Board width X (mm)",                 1.0,   15.0,   100.0, False, False),
    ("sub_length",     "Board",      "Board length Y (mm)",                1.0,   20.0,   150.0, False, False),
    ("patch_width",    "Patch",      "Patch width X (mm)",                 0.2,   5.0,    40.0,  True,  False),
    ("patch_length",   "Patch",      "Patch length Y (mm)",                0.2,   5.0,    30.0,  True,  False),
    ("patch_y0",       "Patch",      "Patch centre Y from board edge (mm)",0.5,   5.0,    55.0,  False, False),
    ("aperture_length","Aperture",   "Slot length along X (mm)",           0.2,   1.0,    20.0,  True,  False),
    ("aperture_width", "Aperture",   "Slot width along Y (mm)",            0.1,   0.2,    5.0,   True,  False),
    ("aperture_offset","Aperture",   "Slot centre offset from patch (mm)", 0.1,   -8.0,   8.0,   True,  False),
    ("aperture_stub",  "Aperture",   "Open stub past slot centre (mm)",    0.2,   0.5,    15.0,  True,  False),
    ("feed_line_width","Feed",       "Feed line width (mm)",               0.1,   0.3,    8.0,   True,  False),
    ("feed_R",         "Feed",       "Port impedance (Ω)",                 5.0,   10.0,   100.0, False, False),
]

PARAM_META_MULTI = [
    ("f0",              "Frequency",   "Centre frequency (Hz)",              1e8,   4e9,   8e9,   False, False),
    ("fc",              "Frequency",   "Gaussian corner half-BW (Hz)",       1e7,   1e7,   2e9,   False, False),
    ("substrate_epsR",  "Substrate",   "Relative permittivity εr",           0.05,  1.0,   12.0,  False, False),
    ("substrate_tan",   "Substrate",   "Loss tangent",                       5e-4,  0.0,   0.05,  False, False),
    ("substrate_cells", "Substrate",   "Mesh layers per substrate",          1,     2,     8,     False, False),
    ("h1",              "PCB Stack",   "PCB1 thickness (mm)",                0.05,  0.1,   3.2,   True,  False),
    ("h2",              "PCB Stack",   "PCB2 thickness (mm)",                0.05,  0.1,   3.2,   True,  False),
    ("air_gap",         "PCB Stack",   "Air gap (mm)",                       0.1,   0.1,   10.0,  True,  False),
    ("sub_width",       "Board",       "Board width X (mm)",                 1.0,   20.0,  150.0, False, False),
    ("sub_length",      "Board",       "Board length Y (mm)",                1.0,   30.0,  250.0, False, False),
    ("patch_width",     "Patches",     "Patch widths X — 5 values (mm)",     0.0,   0.0,   0.0,   False, True),
    ("patch_length",    "Patches",     "Patch lengths Y — 5 values (mm)",    0.0,   0.0,   0.0,   False, True),
    ("patch_pitch",     "Patches",     "Patch pitch — 4 gaps (mm)",          0.0,   0.0,   0.0,   False, True),
    ("patch_y0",        "Patches",     "First patch centre from edge (mm)",  0.5,   5.0,   80.0,  False, False),
    ("aperture_length", "Aperture",    "Slot lengths X — 5 values (mm)",     0.0,   0.0,   0.0,   False, True),
    ("aperture_width",  "Aperture",    "Slot widths Y — 5 values (mm)",      0.0,   0.0,   0.0,   False, True),
    ("aperture_offset", "Aperture",    "Slot offsets — 5 values (mm)",       0.0,   0.0,   0.0,   False, True),
    ("aperture_stub",   "Aperture",    "Stub lengths — 5 values (mm)",       0.0,   0.0,   0.0,   False, True),
    ("input_line_width","T-junction",  "Input line width (mm)",              0.1,   0.5,   8.0,   True,  False),
    ("input_line_length","T-junction", "Input line length (mm)",             0.5,   2.0,   40.0,  True,  False),
    ("j1_stub_length",  "T-junction",  "J1 matching stub length (mm)",       0.2,   0.0,   15.0,  True,  False),
    ("j1_stub_width",   "T-junction",  "J1 stub width (mm)",                 0.1,   0.2,   5.0,   True,  False),
    ("brA_width",       "T-junction",  "Branch A width (mm)",                0.1,   0.5,   6.0,   True,  False),
    ("brA_length",      "T-junction",  "Branch A length (mm)",               0.5,   5.0,   50.0,  True,  False),
    ("j1_qwt_left_width", "T-junction","J1 QWT left width (mm)",             0.1,   0.3,   5.0,   True,  False),
    ("j1_qwt_left_length","T-junction","J1 QWT left length (mm)",            0.2,   2.0,   20.0,  True,  False),
    ("j2_stub_length",  "T-junction",  "J2 stub length (mm)",                0.2,   0.0,   12.0,  True,  False),
    ("j2_stub_width",   "T-junction",  "J2 stub width (mm)",                 0.1,   0.2,   4.0,   True,  False),
    ("feed_p0_width",   "Feed lines",  "Feed to patch 0 width (mm)",         0.1,   0.3,   6.0,   True,  False),
    ("feed_p0_length",  "Feed lines",  "Feed to patch 0 length (mm)",        0.5,   2.0,   40.0,  True,  False),
    ("feed_p1_width",   "Feed lines",  "Feed to patch 1 width (mm)",         0.1,   0.3,   6.0,   True,  False),
    ("feed_p1_length",  "Feed lines",  "Feed to patch 1 length (mm)",        0.5,   2.0,   40.0,  True,  False),
    ("brB_width",       "T-junction",  "Branch B width (mm)",                0.1,   0.5,   6.0,   True,  False),
    ("brB_length",      "T-junction",  "Branch B length (mm)",               0.5,   5.0,   50.0,  True,  False),
    ("j1_qwt_right_width","T-junction","J1 QWT right width (mm)",            0.1,   0.3,   5.0,   True,  False),
    ("j1_qwt_right_length","T-junction","J1 QWT right length (mm)",          0.2,   2.0,   20.0,  True,  False),
    ("j3_stub_length",  "T-junction",  "J3 stub length (mm)",                0.2,   0.0,   12.0,  True,  False),
    ("j3_stub_width",   "T-junction",  "J3 stub width (mm)",                 0.1,   0.2,   4.0,   True,  False),
    ("feed_p2_width",   "Feed lines",  "Feed to patch 2 width (mm)",         0.1,   0.3,   6.0,   True,  False),
    ("feed_p2_length",  "Feed lines",  "Feed to patch 2 length (mm)",        0.5,   2.0,   40.0,  True,  False),
    ("brC_width",       "T-junction",  "Branch C width (mm)",                0.1,   0.5,   6.0,   True,  False),
    ("brC_length",      "T-junction",  "Branch C length (mm)",               0.5,   5.0,   50.0,  True,  False),
    ("j3_qwt_right_width","T-junction","J3 QWT right width (mm)",            0.1,   0.3,   5.0,   True,  False),
    ("j3_qwt_right_length","T-junction","J3 QWT right length (mm)",          0.2,   2.0,   20.0,  True,  False),
    ("j4_stub_length",  "T-junction",  "J4 stub length (mm)",                0.2,   0.0,   12.0,  True,  False),
    ("j4_stub_width",   "T-junction",  "J4 stub width (mm)",                 0.1,   0.2,   4.0,   True,  False),
    ("feed_p3_width",   "Feed lines",  "Feed to patch 3 width (mm)",         0.1,   0.3,   6.0,   True,  False),
    ("feed_p3_length",  "Feed lines",  "Feed to patch 3 length (mm)",        0.5,   2.0,   40.0,  True,  False),
    ("feed_p4_width",   "Feed lines",  "Feed to patch 4 width (mm)",         0.1,   0.3,   6.0,   True,  False),
    ("feed_p4_length",  "Feed lines",  "Feed to patch 4 length (mm)",        0.5,   2.0,   40.0,  True,  False),
    ("feed_R",          "Feed",        "Port impedance (Ω)",                 5.0,   10.0,  100.0, False, False),
]

DESIGNS = {
    "Single Patch": {
        "meta":       PARAM_META_SINGLE,
        "param_file": os.path.join(SCRIPT_DIR, "params_single_patch.json"),
    },
    "5-Patch Array": {
        "meta":       PARAM_META_MULTI,
        "param_file": os.path.join(SCRIPT_DIR, "params_multipatch.json"),
    },
}

def _mean_s11_in_band(r: dict, P: dict, band_half_hz: float) -> float:
    """
    Mean S11 in dB over [f0 - band_half_hz, f0 + band_half_hz].

    Smooth, continuous proxy for bandwidth: rewards both depth and breadth
    of the S11 dip without a threshold step-discontinuity. Defined everywhere
    even when the resonance is above -10 dB.
    Falls back to S11 at f0 if the band is narrower than the freq resolution.
    """
    s11c = r.get("s11_complex")
    if not s11c:
        return float(r.get("s11_db_at_f0", 0.0))
    s11_arr = np.array([complex(v[0], v[1]) for v in s11c])
    f0   = P["f0"]
    fc   = P["fc"]
    freq = np.linspace(f0 - fc, f0 + fc, len(s11_arr))
    mask = np.abs(freq - f0) <= band_half_hz
    if not np.any(mask):
        return float(r.get("s11_db_at_f0", 0.0))
    s11_dB = 20.0 * np.log10(np.abs(s11_arr[mask]) + 1e-30)
    return float(np.mean(s11_dB))


OBJECTIVES = {
    "Minimize S11 at f0 (dB)": {
        "fn":      lambda r, P: r["s11_db_at_f0"],
        "unit":    "dB",
        "better":  "lower",
    },
    "Minimize S11 at resonance (dB)": {
        "fn":      lambda r, P: r.get("s11_min_db", r["s11_db_at_f0"]),
        "unit":    "dB",
        "better":  "lower",
    },
    "Match resonance to f0 (MHz error)": {
        "fn":      lambda r, P: abs(r["resonant_freq_hz"] - P["f0"]) / 1e6,
        "unit":    "MHz",
        "better":  "lower",
    },
    "Maximize bandwidth (MHz)": {
        "fn":      lambda r, P: -(r["bandwidth_hz"] or 0) / 1e6,
        "unit":    "MHz (negated)",
        "better":  "lower (= wider BW)",
    },
    "Mean S11 in band (dB)": {
        "fn":        lambda r, P: r.get("s11_db_at_f0", 0.0),  # overridden at runtime
        "unit":      "dB",
        "better":    "lower",
        "needs_band": True,
    },
}


# --------------------------------------------------------------------------- #
#  Helpers                                                                     #
# --------------------------------------------------------------------------- #

def _fmt(val):
    """Format a parameter value for display."""
    if isinstance(val, list):
        return ", ".join(f"{v:g}" for v in val)
    if isinstance(val, float):
        if abs(val) >= 1e8 or (val != 0 and abs(val) < 1e-2):
            return f"{val:.3e}"
        return f"{val:g}"
    return str(val)


def _parse(text, is_list=False):
    """Parse a text entry back to a Python value. Raises ValueError on bad input."""
    text = text.strip()
    if is_list:
        return [float(x.strip()) for x in text.split(",")]
    try:
        return int(text)
    except ValueError:
        return float(text)


def _load_json(path):
    with open(path, "r") as f:
        d = json.load(f)
    return {k: v for k, v in d.items() if not k.startswith("_")}


def _save_json(path, params):
    data = {"_comment": "Auto-saved by simulation_gui.py — edit or regenerate via GUI."}
    data.update(params)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# --------------------------------------------------------------------------- #
#  Parameter table widget                                                      #
# --------------------------------------------------------------------------- #

COL_PAD = 6

class ParamTable(ttk.Frame):
    """Scrollable parameter table: Name | Value | Optimize | Step | Min | Max"""

    HDR = ["Parameter", "Value", "Opt?", "Step", "Min", "Max"]
    COL_W = [34, 12, 5, 10, 10, 10]   # character widths

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._rows = {}    # key -> dict of tk variables / widgets
        self._build_frame()

    # ---- public ------------------------------------------------------------ #

    def load(self, meta, params):
        """Rebuild table for a new design."""
        for w in self._inner.winfo_children():
            w.destroy()
        self._rows.clear()
        self._add_header()
        current_group = None
        for row_spec in meta:
            key, group, label, step, pmin, pmax, can_opt, is_list = row_spec
            if group != current_group:
                self._add_group_header(group)
                current_group = group
            val = params.get(key, "")
            self._add_param_row(key, label, val, can_opt, is_list, step, pmin, pmax)
        self._inner.update_idletasks()
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def get_params(self):
        """Return {key: value} dict from current UI state. Raises ValueError on bad input."""
        out = {}
        for key, row in self._rows.items():
            out[key] = _parse(row["val_var"].get(), row["is_list"])
        return out

    def get_opt_params(self):
        """Return list of (key, step, min, max) for checked-optimize rows."""
        result = []
        for key, row in self._rows.items():
            if row.get("opt_var") and row["opt_var"].get():
                step = float(row["step_var"].get() or 0.1)
                pmin = row["min_var"].get().strip()
                pmax = row["max_var"].get().strip()
                pmin = float(pmin) if pmin else None
                pmax = float(pmax) if pmax else None
                result.append((key, step, pmin, pmax))
        return result

    def set_value(self, key, val):
        """Update a single value (called from background thread via after())."""
        if key in self._rows:
            self._rows[key]["val_var"].set(_fmt(val))

    # ---- private ----------------------------------------------------------- #

    def _build_frame(self):
        self._canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._inner = ttk.Frame(self._canvas)
        self._win_id = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")

        self._inner.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_inner_configure(self, _e):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, e):
        self._canvas.itemconfig(self._win_id, width=e.width)

    def _on_mousewheel(self, e):
        self._canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

    def _add_header(self):
        f = self._inner
        for c, (text, w) in enumerate(zip(self.HDR, self.COL_W)):
            lbl = ttk.Label(f, text=text, width=w, anchor="center",
                            font=("Segoe UI", 9, "bold"))
            lbl.grid(row=0, column=c, padx=2, pady=(4, 2), sticky="ew")
        ttk.Separator(f, orient="horizontal").grid(
            row=1, column=0, columnspan=len(self.HDR), sticky="ew", pady=2)

    def _add_group_header(self, group):
        row = self._next_row()
        lbl = ttk.Label(self._inner, text=f"  {group}",
                        font=("Segoe UI", 9, "bold", "italic"),
                        foreground="#555555")
        lbl.grid(row=row, column=0, columnspan=len(self.HDR),
                 sticky="w", padx=4, pady=(8, 1))

    def _next_row(self):
        return len(self._inner.grid_slaves()) + 2

    def _add_param_row(self, key, label, value, can_opt, is_list,
                       step, pmin, pmax):
        f   = self._inner
        row = self._next_row()
        bg  = "#f9f9f9" if (row % 2 == 0) else "#ffffff"

        val_var  = tk.StringVar(value=_fmt(value))
        opt_var  = tk.BooleanVar(value=False) if can_opt else None
        step_var = tk.StringVar(value=_fmt(step) if not is_list else "")
        min_var  = tk.StringVar(value=_fmt(pmin) if (not is_list and pmin is not None) else "")
        max_var  = tk.StringVar(value=_fmt(pmax) if (not is_list and pmax is not None) else "")

        # Name label
        lbl = ttk.Label(f, text=label, width=self.COL_W[0], anchor="w")
        lbl.grid(row=row, column=0, padx=(8, 4), pady=1, sticky="w")

        # Value entry
        ent_val = ttk.Entry(f, textvariable=val_var, width=self.COL_W[1])
        ent_val.grid(row=row, column=1, padx=2, pady=1)

        # Optimize checkbox
        if can_opt and not is_list:
            chk = ttk.Checkbutton(f, variable=opt_var,
                                  command=lambda k=key: self._toggle_opt(k))
            chk.grid(row=row, column=2, padx=2, pady=1)
        else:
            ttk.Label(f, text="—", anchor="center").grid(
                row=row, column=2, padx=2, pady=1)

        # Step / Min / Max entries (disabled unless optimize checked)
        ent_step = ttk.Entry(f, textvariable=step_var, width=self.COL_W[3],
                             state="disabled" if not is_list else "disabled")
        ent_step.grid(row=row, column=3, padx=2, pady=1)

        ent_min = ttk.Entry(f, textvariable=min_var, width=self.COL_W[4],
                            state="disabled")
        ent_min.grid(row=row, column=4, padx=2, pady=1)

        ent_max = ttk.Entry(f, textvariable=max_var, width=self.COL_W[5],
                            state="disabled")
        ent_max.grid(row=row, column=5, padx=2, pady=1)

        self._rows[key] = {
            "val_var":  val_var,
            "opt_var":  opt_var,
            "step_var": step_var,
            "min_var":  min_var,
            "max_var":  max_var,
            "ent_step": ent_step,
            "ent_min":  ent_min,
            "ent_max":  ent_max,
            "is_list":  is_list,
            "can_opt":  can_opt,
        }

    def _toggle_opt(self, key):
        row = self._rows[key]
        enabled = row["opt_var"].get()
        state = "normal" if enabled else "disabled"
        row["ent_step"].config(state=state)
        row["ent_min"].config(state=state)
        row["ent_max"].config(state=state)


# --------------------------------------------------------------------------- #
#  History tab                                                                 #
# --------------------------------------------------------------------------- #

class HistoryTab(ttk.Frame):
    COLS = ("id", "timestamp", "design", "objective", "iter", "opt_run_id",
            "s11@f0", "res_freq", "BW")
    WIDTHS = (40, 150, 80, 80, 40, 220, 70, 90, 80)

    def __init__(self, parent, db_path, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path    = db_path
        self._rows_cache = []       # raw rows from last refresh
        self._sort_col   = "id"     # active sort column
        self._sort_rev   = False    # True = descending
        self._build()

    def _build(self):
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=6, pady=4)
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(side="left")
        ttk.Label(bar, text="Filter opt_run_id:").pack(side="left", padx=(12, 4))
        self._filter_var = tk.StringVar()
        ttk.Entry(bar, textvariable=self._filter_var, width=36).pack(side="left")
        ttk.Button(bar, text="Apply", command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="Plot opt run",
                   command=self._plot_selected).pack(side="left", padx=(16, 0))

        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, padx=6, pady=4)

        self._tree = ttk.Treeview(frame, columns=self.COLS, show="headings", height=20)
        vsb = ttk.Scrollbar(frame, orient="vertical",   command=self._tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        for col, w in zip(self.COLS, self.WIDTHS):
            self._tree.heading(col, text=col,
                               command=lambda c=col: self._sort_by(c))
            self._tree.column(col, width=w, minwidth=30, anchor="w")

        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

    def _plot_selected(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("No selection",
                                "Select any row from the opt run you want to plot.")
            return
        values = self._tree.item(sel[0], "values")
        oid = values[5] if len(values) > 5 else ""   # col index 5 = opt_run_id
        if not oid or oid == "—":
            messagebox.showinfo("Not an opt run",
                                "Selected row has no opt_run_id. "
                                "Pick any row from an optimization run.")
            return
        try:
            from run_manager import plot_opt_run
        except ImportError:
            messagebox.showerror("Import error", "Could not import run_manager.")
            return
        fig = plot_opt_run(oid, db_path=self._db_path)
        if fig is None:
            messagebox.showinfo("No data", f"No iterations found for {oid[:12]}…")
            return
        self._show_opt_figure(fig, oid)

    def _show_opt_figure(self, fig, oid):
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        win = tk.Toplevel(self)
        win.title(f"Opt run: {oid[:12]}…")
        win.geometry("900x660")
        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        # Toolbar for zoom/pan/save
        try:
            from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk
            toolbar = NavigationToolbar2Tk(canvas, win)
            toolbar.update()
        except Exception:
            pass

    _INF = float("inf")

    def _sort_key(self, row: dict, col: str):
        """Return a sort-stable key for one raw DB row and column name."""
        res    = row.get("results") or {}
        params = row.get("params") or {}
        INF    = self._INF

        if col == "id":
            return row.get("id") or 0
        if col == "timestamp":
            return row.get("timestamp") or ""
        if col == "design":
            return (params.get("_design") or "").lower()
        if col == "objective":
            v = row.get("objective")
            return v if (v is not None and v == v) else INF   # NaN → INF
        if col == "iter":
            v = row.get("iteration")
            return v if v is not None else INF
        if col == "opt_run_id":
            return row.get("opt_run_id") or ""
        if col == "s11@f0":
            v = res.get("s11_db_at_f0")
            return v if (v is not None and v == v) else INF
        if col == "res_freq":
            v = res.get("resonant_freq_hz")
            return v if v is not None else INF
        if col == "BW":
            v = res.get("bandwidth_hz")
            return v if v is not None else -INF   # no measured BW → sorts last ascending
        return ""

    def _sort_by(self, col: str):
        if self._sort_col == col:
            self._sort_rev = not self._sort_rev
        else:
            self._sort_col = col
            self._sort_rev = False
        self._repopulate_tree()

    def _repopulate_tree(self):
        col = self._sort_col
        rev = self._sort_rev

        # Update heading labels: show ▲ / ▼ on the active column only
        for c in self.COLS:
            indicator = (" ▼" if rev else " ▲") if c == col else ""
            self._tree.heading(c, text=c + indicator)

        try:
            rows = sorted(self._rows_cache,
                          key=lambda r: self._sort_key(r, col),
                          reverse=rev)
        except Exception:
            rows = self._rows_cache

        self._tree.delete(*self._tree.get_children())
        for r in rows:
            res    = r.get("results") or {}
            params = r.get("params") or {}
            design = params.get("_design", "—")
            obj    = f"{r['objective']:+.3f}" if r["objective"] is not None else "—"
            s11f0  = f"{res.get('s11_db_at_f0', ''):+.2f}" if res else "—"
            rf     = f"{res.get('resonant_freq_hz', 0)/1e9:.4f} GHz" if res else "—"
            bw     = (f"{res.get('bandwidth_hz', 0)/1e6:.1f} MHz"
                      if (res and res.get("bandwidth_hz")) else "—")
            self._tree.insert("", "end", values=(
                r["id"], r["timestamp"], design,
                obj, r.get("iteration", "—"),
                r.get("opt_run_id") or "—",
                s11f0, rf, bw,
            ))

    def refresh(self):
        try:
            from run_manager import load_runs
        except ImportError:
            return
        filt = self._filter_var.get().strip() or None
        self._rows_cache = load_runs(opt_run_id=filt, db_path=self._db_path)
        self._repopulate_tree()


# --------------------------------------------------------------------------- #
#  Main application                                                            #
# --------------------------------------------------------------------------- #

DB_PATH = os.path.join(SCRIPT_DIR, "runs.db")


class SimulatorGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Aperture-Coupled Patch Simulator")
        self.root.geometry("1200x780")
        self.root.minsize(900, 600)

        self._design_var       = tk.StringVar(value="Single Patch")
        self._status_var       = tk.StringVar(value="Ready")
        self._obj_var          = tk.StringVar(value=list(OBJECTIVES.keys())[0])
        self._lr_var           = tk.StringVar(value="0.1")
        self._maxiter_var      = tk.StringVar(value="20")
        self._tol_var          = tk.StringVar(value="1e-4")
        self._threads_var      = tk.StringVar(value="4")
        self._show_cad         = tk.BooleanVar(value=False)
        self._compute_farfield = tk.BooleanVar(value=False)
        self._band_half_var    = tk.StringVar(value="100")  # MHz

        self._queue    = queue.Queue()
        self._running  = False
        self._thread   = None

        # Optimization progress plot state (reset each run)
        self._opt_iters       = []
        self._opt_objs        = []
        self._opt_param_names = []
        self._opt_param_traj  = {}   # name -> [values per iteration]
        self._opt_param_init  = {}   # name -> initial value
        # Matplotlib handles (set in _build_opt_plot_tab)
        self._opt_fig      = None
        self._opt_canvas   = None
        self._opt_ax_obj   = None
        self._opt_ax_param = None
        self._notebook     = None
        self._opt_tab_idx  = None

        self._build_ui()
        self._load_design()
        self._poll_queue()

    # ---- UI construction --------------------------------------------------- #

    def _build_ui(self):
        self._build_topbar()
        self._build_notebook()
        self._build_statusbar()

    def _build_topbar(self):
        bar = ttk.Frame(self.root, padding=(6, 4))
        bar.pack(fill="x")

        ttk.Label(bar, text="Design:", font=("Segoe UI", 10, "bold")).pack(side="left")
        cb = ttk.Combobox(bar, textvariable=self._design_var,
                          values=list(DESIGNS.keys()), state="readonly", width=18)
        cb.pack(side="left", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda _: self._load_design())

        ttk.Button(bar, text="Load JSON…",  command=self._load_json_dialog).pack(side="left", padx=4)
        ttk.Button(bar, text="Save JSON…",  command=self._save_json_dialog).pack(side="left", padx=2)
        ttk.Button(bar, text="Save as default", command=self._save_as_default).pack(side="left", padx=2)

    def _build_notebook(self):
        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=6, pady=4)

        # --- Tab 1: Run ---
        run_tab = ttk.Frame(nb)
        nb.add(run_tab, text="  Parameters & Run  ")

        pane = ttk.PanedWindow(run_tab, orient="horizontal")
        pane.pack(fill="both", expand=True)

        # Left: parameter table
        left = ttk.Frame(pane, padding=2)
        pane.add(left, weight=3)
        self._param_table = ParamTable(left)
        self._param_table.pack(fill="both", expand=True)

        # Right: controls
        right = ttk.Frame(pane, padding=6)
        pane.add(right, weight=1)
        self._build_controls(right)

        # --- Tab 2: History ---
        hist_tab = ttk.Frame(nb)
        nb.add(hist_tab, text="  Run History  ")
        self._history = HistoryTab(hist_tab, db_path=DB_PATH)
        self._history.pack(fill="both", expand=True)
        nb.bind("<<NotebookTabChanged>>", lambda _: self._history.refresh())

        # --- Tab 3: Opt. Progress ---
        opt_tab = ttk.Frame(nb)
        nb.add(opt_tab, text="  Opt. Progress  ")
        self._build_opt_plot_tab(opt_tab)
        self._notebook    = nb
        self._opt_tab_idx = 2

    def _build_controls(self, parent):
        # ---- Simulation section ----
        sim_frame = ttk.LabelFrame(parent, text="Simulation", padding=8)
        sim_frame.pack(fill="x", pady=(0, 8))

        ttk.Checkbutton(sim_frame, text="Show CAD (EMerge mesh viewer, no sim)",
                        variable=self._show_cad).pack(anchor="w")
        ttk.Checkbutton(sim_frame,
                        text="Compute gain pattern (slow, single run only)",
                        variable=self._compute_farfield).pack(anchor="w")

        row = ttk.Frame(sim_frame)
        row.pack(fill="x", pady=(4, 0))
        ttk.Label(row, text="Threads:").pack(side="left")
        ttk.Entry(row, textvariable=self._threads_var, width=4).pack(side="left", padx=4)

        self._btn_run = ttk.Button(sim_frame, text="▶  Run Simulation",
                                   command=self._run_single, style="Accent.TButton")
        self._btn_run.pack(fill="x", pady=(8, 2))

        # ---- Optimization section ----
        opt_frame = ttk.LabelFrame(parent, text="Optimization", padding=8)
        opt_frame.pack(fill="x", pady=(0, 8))

        ttk.Label(opt_frame, text="Objective:").pack(anchor="w")
        cb = ttk.Combobox(opt_frame, textvariable=self._obj_var,
                          values=list(OBJECTIVES.keys()), state="readonly")
        cb.pack(fill="x", pady=(0, 6))
        cb.bind("<<ComboboxSelected>>", lambda _: self._on_obj_changed())

        grid = ttk.Frame(opt_frame)
        grid.pack(fill="x")
        for i, (lbl, var, w) in enumerate([
            ("Learning rate:", self._lr_var,      8),
            ("Max iterations:", self._maxiter_var, 5),
            ("Tolerance:",      self._tol_var,     8),
        ]):
            ttk.Label(grid, text=lbl).grid(row=i, column=0, sticky="w", pady=2)
            ttk.Entry(grid, textvariable=var, width=w).grid(row=i, column=1,
                                                             sticky="w", padx=6, pady=2)

        # Band field (row 3) — shown only for "Mean S11 in band"
        self._band_lbl = ttk.Label(grid, text="Band half-width (MHz):")
        self._band_ent = ttk.Entry(grid, textvariable=self._band_half_var, width=8)
        self._band_lbl.grid(row=3, column=0, sticky="w", pady=2)
        self._band_ent.grid(row=3, column=1, sticky="w", padx=6, pady=2)
        self._band_lbl.grid_remove()
        self._band_ent.grid_remove()

        hint = ttk.Label(opt_frame,
                         text="Check 'Opt?' boxes in the table\nto select parameters.",
                         foreground="#777777", font=("Segoe UI", 8, "italic"))
        hint.pack(anchor="w", pady=(6, 4))

        self._btn_opt = ttk.Button(opt_frame, text="⚙  Run Optimization",
                                   command=self._run_optimization)
        self._btn_opt.pack(fill="x", pady=(0, 2))

        self._btn_cancel = ttk.Button(opt_frame, text="✕  Cancel",
                                      command=self._cancel, state="disabled")
        self._btn_cancel.pack(fill="x")

        # ---- Last result section ----
        res_frame = ttk.LabelFrame(parent, text="Last Result", padding=8)
        res_frame.pack(fill="x", pady=(0, 8))

        self._res_vars = {}
        for key, label in [
            ("s11_db_at_f0",    "S11 at f0:"),
            ("resonant_freq_hz","Resonant freq:"),
            ("bandwidth_hz",    "−10 dB BW:"),
            ("opt_iter",        "Opt iteration:"),
        ]:
            row = ttk.Frame(res_frame)
            row.pack(fill="x", pady=1)
            ttk.Label(row, text=label, width=16, anchor="w").pack(side="left")
            var = tk.StringVar(value="—")
            self._res_vars[key] = var
            ttk.Label(row, textvariable=var, foreground="#004488",
                      font=("Segoe UI", 9, "bold")).pack(side="left")

        self._last_pdf_path = None
        self._btn_open_pdf = ttk.Button(res_frame, text="Open PDF report",
                                        command=self._open_pdf, state="disabled")
        self._btn_open_pdf.pack(fill="x", pady=(6, 0))

        # ---- Progress ----
        prog_frame = ttk.Frame(parent)
        prog_frame.pack(fill="x")
        self._progress = ttk.Progressbar(prog_frame, mode="indeterminate")
        self._progress.pack(fill="x", pady=(4, 2))

    def _build_opt_plot_tab(self, parent):
        try:
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        except ImportError:
            ttk.Label(parent,
                      text="matplotlib not available — cannot display plot.",
                      foreground="red").pack(padx=20, pady=20)
            return

        fig = Figure(tight_layout=True)
        self._opt_ax_obj   = fig.add_subplot(211)
        self._opt_ax_param = fig.add_subplot(212)
        self._opt_fig      = fig
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.get_tk_widget().pack(fill="both", expand=True)
        self._opt_canvas = canvas
        self._reset_opt_plot()

    def _reset_opt_plot(self):
        if self._opt_ax_obj is None:
            return
        self._opt_ax_obj.cla()
        self._opt_ax_param.cla()
        self._opt_ax_obj.set_title("Objective vs. Iteration")
        self._opt_ax_obj.set_xlabel("Iteration")
        self._opt_ax_obj.set_ylabel("Objective")
        self._opt_ax_obj.grid(True, alpha=0.4)
        self._opt_ax_param.set_title("Parameter Trajectory  (% change from start)")
        self._opt_ax_param.set_xlabel("Iteration")
        self._opt_ax_param.set_ylabel("Δ from start (%)")
        self._opt_ax_param.axhline(0, color="k", linewidth=0.5, alpha=0.5)
        self._opt_ax_param.grid(True, alpha=0.4)
        self._opt_canvas.draw_idle()

    _OPT_COLORS = [
        "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
        "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
    ]

    def _on_opt_history(self, msg):
        if self._opt_ax_obj is None:
            return
        self._opt_iters.append(msg["it"])
        self._opt_objs.append(msg["obj"])
        for name in self._opt_param_names:
            self._opt_param_traj.setdefault(name, []).append(
                msg["params"].get(name, float("nan")))
        self._redraw_opt_plot()

    def _redraw_opt_plot(self):
        if self._opt_ax_obj is None or not self._opt_iters:
            return
        iters = self._opt_iters

        # --- Objective subplot ---
        ax = self._opt_ax_obj
        ax.cla()
        ax.plot(iters, self._opt_objs, "b-o", markersize=4, linewidth=1.5,
                label="objective")
        best_i = min(range(len(self._opt_objs)), key=lambda i: self._opt_objs[i])
        ax.plot(iters[best_i], self._opt_objs[best_i], "r*", markersize=10,
                zorder=5, label=f"best  {self._opt_objs[best_i]:+.3f}")
        ax.set_title("Objective vs. Iteration")
        ax.set_xlabel("Iteration")
        ax.set_ylabel("Objective")
        ax.grid(True, alpha=0.4)
        ax.legend(fontsize=8)

        # --- Parameter trajectory subplot ---
        ax = self._opt_ax_param
        ax.cla()
        for i, name in enumerate(self._opt_param_names):
            vals = self._opt_param_traj.get(name, [])
            if not vals:
                continue
            init = self._opt_param_init.get(name, 0.0)
            ref  = abs(init) if abs(init) > 1e-6 else 1.0
            y    = [(v - init) / ref * 100 for v in vals]
            label = name if abs(init) > 1e-6 else f"{name} (×100 mm)"
            color = self._OPT_COLORS[i % len(self._OPT_COLORS)]
            ax.plot(iters, y, "-o", color=color, markersize=3,
                    linewidth=1.5, label=label)
        ax.axhline(0, color="k", linewidth=0.5, alpha=0.5)
        ax.set_title("Parameter Trajectory  (% change from start)")
        ax.set_xlabel("Iteration")
        ax.set_ylabel("Δ from start (%)")
        ax.grid(True, alpha=0.4)
        if self._opt_param_names:
            ax.legend(fontsize=8, loc="best")

        self._opt_fig.tight_layout()
        self._opt_canvas.draw_idle()

    def _build_statusbar(self):
        bar = ttk.Frame(self.root, relief="sunken")
        bar.pack(fill="x", side="bottom")
        ttk.Label(bar, textvariable=self._status_var, anchor="w",
                  padding=(6, 2)).pack(side="left", fill="x", expand=True)

    # ---- Design loading ---------------------------------------------------- #

    def _load_design(self):
        design  = self._design_var.get()
        info    = DESIGNS[design]
        pf      = info["param_file"]
        params  = _load_json(pf) if os.path.exists(pf) else {}
        self._param_table.load(info["meta"], params)
        self._status_var.set(f"Loaded design: {design}")

    def _load_json_dialog(self):
        path = filedialog.askopenfilename(
            initialdir=SCRIPT_DIR,
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            params = _load_json(path)
            design = self._design_var.get()
            self._param_table.load(DESIGNS[design]["meta"], params)
            self._status_var.set(f"Loaded: {path}")
        except Exception as e:
            messagebox.showerror("Load error", str(e))

    def _save_json_dialog(self):
        path = filedialog.asksaveasfilename(
            initialdir=SCRIPT_DIR,
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")])
        if not path:
            return
        try:
            params = self._param_table.get_params()
            _save_json(path, params)
            self._status_var.set(f"Saved: {path}")
        except Exception as e:
            messagebox.showerror("Save error", str(e))

    def _save_as_default(self):
        design = self._design_var.get()
        path   = DESIGNS[design]["param_file"]
        try:
            params = self._param_table.get_params()
            _save_json(path, params)
            self._status_var.set(f"Saved as default: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Save error", str(e))

    # ---- Objective / band field visibility --------------------------------- #

    def _on_obj_changed(self):
        needs = OBJECTIVES.get(self._obj_var.get(), {}).get("needs_band", False)
        if needs:
            self._band_lbl.grid()
            self._band_ent.grid()
        else:
            self._band_lbl.grid_remove()
            self._band_ent.grid_remove()

    # ---- Run controls ------------------------------------------------------- #

    def _collect_params(self):
        """Read params from table and add _design tag for DB."""
        params = self._param_table.get_params()
        params["_design"] = self._design_var.get()
        return params

    def _set_running(self, running: bool):
        self._running = running
        state_run    = "disabled" if running else "normal"
        state_cancel = "normal"  if running else "disabled"
        self._btn_run.config(state=state_run)
        self._btn_opt.config(state=state_run)
        self._btn_cancel.config(state=state_cancel)
        if running:
            self._progress.start(12)
        else:
            self._progress.stop()

    def _cancel(self):
        self._status_var.set("Cancelling… (current sim will finish)")
        self._running = False   # thread checks this flag

    # ---- Single run -------------------------------------------------------- #

    def _run_single(self):
        if self._running:
            return
        design = self._design_var.get()
        if design != "Single Patch":
            messagebox.showinfo("Not ready",
                                "Full geometry for 5-Patch Array is still under development.\n"
                                "Single Patch is fully functional.")
            return
        try:
            params = self._collect_params()
        except ValueError as e:
            messagebox.showerror("Parameter error", str(e))
            return

        if self._show_cad.get():
            self._launch_cad(params)
            return

        self._set_running(True)
        want_ff = self._compute_farfield.get()
        self._status_var.set(
            "Running simulation + far-field computation (slow)…"
            if want_ff else "Running simulation…"
        )
        t = threading.Thread(target=self._thread_run_single,
                             args=(params, want_ff), daemon=True)
        t.start()

    def _thread_run_single(self, params, compute_farfield: bool):
        try:
            from run_manager import evaluate, init_db
            init_db(DB_PATH)
            n_threads  = int(self._threads_var.get())
            sim_params = {k: v for k, v in params.items() if not k.startswith("_")}
            results    = evaluate(sim_params, num_threads=n_threads, db_path=DB_PATH,
                                  compute_farfield=compute_farfield)
            self._queue.put({"type": "result", "data": results})
            self._queue.put({"type": "status", "text": "Simulation complete."})
        except Exception as e:
            self._queue.put({"type": "error",  "text": str(e)})
        finally:
            self._queue.put({"type": "done"})

    # ---- CAD viewer -------------------------------------------------------- #

    def _launch_cad(self, params):
        sim_params = {k: v for k, v in params.items() if not k.startswith("_")}
        self._status_var.set("Generating mesh preview…")
        t = threading.Thread(target=self._thread_cad_preview,
                             args=(sim_params,), daemon=True)
        t.start()

    def _thread_cad_preview(self, params):
        try:
            from aperture_coupled_single_patch import preview
            preview(params)
            self._queue.put({"type": "status", "text": "CAD viewer closed."})
        except Exception as e:
            self._queue.put({"type": "status", "text": f"CAD preview error: {e}"})

    # ---- Optimization run -------------------------------------------------- #

    def _run_optimization(self):
        if self._running:
            return
        design = self._design_var.get()
        if design != "Single Patch":
            messagebox.showinfo("Not ready",
                                "Optimization currently supports Single Patch only.")
            return
        try:
            params   = self._collect_params()
            opt_list = self._param_table.get_opt_params()
        except ValueError as e:
            messagebox.showerror("Parameter error", str(e))
            return

        if not opt_list:
            messagebox.showwarning("No parameters selected",
                                   "Check at least one 'Opt?' checkbox in the parameter table.")
            return

        try:
            lr       = float(self._lr_var.get())
            max_iter = int(self._maxiter_var.get())
            tol      = float(self._tol_var.get())
        except ValueError as e:
            messagebox.showerror("Optimization settings error", str(e))
            return

        obj_key  = self._obj_var.get()
        obj_info = dict(OBJECTIVES[obj_key])   # shallow copy — we may replace "fn"

        if obj_info.get("needs_band"):
            try:
                band_half_hz = float(self._band_half_var.get()) * 1e6
            except ValueError:
                messagebox.showerror("Band error",
                                     "Band half-width must be a number (MHz).")
                return
            if band_half_hz <= 0:
                messagebox.showerror("Band error",
                                     "Band half-width must be > 0 MHz.")
                return
            # Capture band_half_hz in the closure via default argument
            obj_info["fn"] = lambda r, P, _bh=band_half_hz: _mean_s11_in_band(r, P, _bh)

        # Reset optimization plot for the new run
        _pnames = [o[0] for o in opt_list]
        self._opt_iters       = []
        self._opt_objs        = []
        self._opt_param_names = _pnames
        self._opt_param_traj  = {n: [] for n in _pnames}
        self._opt_param_init  = {n: params.get(n, 0.0) for n in _pnames}
        self._reset_opt_plot()
        if self._notebook is not None and self._opt_tab_idx is not None:
            self._notebook.select(self._opt_tab_idx)

        self._set_running(True)
        self._status_var.set("Starting optimization…")
        t = threading.Thread(
            target=self._thread_optimize,
            args=(params, opt_list, lr, max_iter, tol, obj_info),
            daemon=True,
        )
        t.start()

    def _thread_optimize(self, params, opt_list, lr, max_iter, tol, obj_info):
        try:
            from run_manager import evaluate, gradient_descent, init_db
            import copy as _copy
            init_db(DB_PATH)

            n_threads   = int(self._threads_var.get())
            param_names = [o[0] for o in opt_list]
            step_sizes  = [o[1] for o in opt_list]
            bounds      = {o[0]: (o[2], o[3]) for o in opt_list}

            sim_params = {k: v for k, v in params.items() if not k.startswith("_")}

            def obj_fn(P, oid, it):
                if not self._running:
                    raise InterruptedError("Cancelled by user")
                try:
                    res = evaluate(P, opt_run_id=oid, iteration=it,
                                   num_threads=n_threads, db_path=DB_PATH)
                except Exception as _sim_err:
                    self._queue.put({"type": "status",
                                     "text": f"Sim error: {_sim_err}"})
                    return {
                        "s11_db_at_f0":     float("nan"),
                        "s11_min_db":       float("nan"),
                        "resonant_freq_hz": float("nan"),
                        "bandwidth_hz":     None,
                    }
                self._queue.put({"type": "result", "data": res})
                return res

            obj_metric = obj_info["fn"]

            def progress_fn(it, obj_val, grad_norm, P_cur):
                self._queue.put({
                    "type": "status",
                    "text": (f"Iter {it} | objective={obj_val:+.4f} | "
                             f"grad_norm={grad_norm:.2e}"),
                })
                self._queue.put({
                    "type": "opt_iter",
                    "text": f"{it + 1} / {max_iter}",
                })
                for name in param_names:
                    self._queue.put({"type": "param_update", "key": name,
                                     "val": P_cur[name]})
                self._queue.put({
                    "type":   "opt_history",
                    "it":     it,
                    "obj":    obj_val,
                    "params": {n: P_cur[n] for n in param_names},
                })

            result = gradient_descent(
                sim_params, param_names, step_sizes,
                objective_fn = obj_fn,
                max_iter     = max_iter,
                lr           = lr,
                tol          = tol,
                bounds       = bounds,
                metric_fn    = lambda r: obj_metric(r, sim_params),
                progress_fn  = progress_fn,
            )

            stop = result.get("stop_reason", "?")
            self._queue.put({
                "type": "status",
                "text": (f"Optimization done [{stop}]. "
                         f"Best obj={result['best_obj']:+.4f}  "
                         f"({result.get('n_iters', '?')} iters, "
                         f"opt_run_id={result['opt_run_id'][:8]}…)"),
            })
            if result.get("report"):
                self._queue.put({"type": "opt_report", "text": result["report"]})
        except InterruptedError:
            self._queue.put({"type": "status", "text": "Optimization cancelled."})
        except Exception as e:
            self._queue.put({"type": "error", "text": str(e)})
        finally:
            self._queue.put({"type": "done"})

    # ---- Queue polling ----------------------------------------------------- #

    def _poll_queue(self):
        try:
            while True:
                msg = self._queue.get_nowait()
                t   = msg["type"]
                if t == "status":
                    self._status_var.set(msg["text"])
                elif t == "result":
                    self._display_result(msg["data"])
                elif t == "opt_iter":
                    self._res_vars["opt_iter"].set(msg["text"])
                elif t == "param_update":
                    self._param_table.set_value(msg["key"], msg["val"])
                elif t == "opt_history":
                    self._on_opt_history(msg)
                elif t == "opt_report":
                    self._show_opt_report(msg["text"])
                elif t == "error":
                    messagebox.showerror("Simulation error", msg["text"])
                    self._set_running(False)
                elif t == "done":
                    self._set_running(False)
        except queue.Empty:
            pass
        except Exception as e:
            self._status_var.set(f"UI error: {e}")
        finally:
            self.root.after(100, self._poll_queue)

    # ---- Result display ---------------------------------------------------- #

    def _show_opt_report(self, text: str):
        """Pop up a scrollable monospace window with the termination report."""
        win = tk.Toplevel(self.root)
        win.title("Optimization Report")
        win.geometry("740x480")
        frame = ttk.Frame(win, padding=6)
        frame.pack(fill="both", expand=True)
        txt = tk.Text(frame, wrap="none", font=("Courier New", 9),
                      background="#1e1e1e", foreground="#d4d4d4",
                      insertbackground="white")
        vsb = ttk.Scrollbar(frame, orient="vertical",   command=txt.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=txt.xview)
        txt.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        txt.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        txt.insert("end", text)
        txt.config(state="disabled")

    def _open_pdf(self):
        if self._last_pdf_path and os.path.exists(self._last_pdf_path):
            os.startfile(self._last_pdf_path)
        else:
            messagebox.showinfo("No PDF", "PDF report not found.")

    def _display_result(self, res: dict):
        s11f0 = res.get("s11_db_at_f0")
        rf    = res.get("resonant_freq_hz")
        bw    = res.get("bandwidth_hz")

        self._res_vars["s11_db_at_f0"].set(
            f"{s11f0:+.2f} dB" if s11f0 is not None else "—")
        self._res_vars["resonant_freq_hz"].set(
            f"{rf/1e9:.4f} GHz" if rf else "—")
        self._res_vars["bandwidth_hz"].set(
            f"{bw/1e6:.1f} MHz" if bw else "—")

        pdf = res.get("pdf_path")
        if pdf and os.path.exists(pdf):
            self._last_pdf_path = pdf
            self._btn_open_pdf.config(state="normal")
            self._status_var.set(f"Done. Report: {os.path.basename(pdf)}")


# --------------------------------------------------------------------------- #
#  Entry point                                                                 #
# --------------------------------------------------------------------------- #

def main():
    # Ensure DB exists
    try:
        from run_manager import init_db
        init_db(DB_PATH)
    except ImportError:
        pass

    root = tk.Tk()

    # Try to set a nicer theme
    style = ttk.Style(root)
    for theme in ("vista", "winnative", "clam"):
        if theme in style.theme_names():
            style.theme_use(theme)
            break

    # Accent button style
    style.configure("Accent.TButton", font=("Segoe UI", 9, "bold"))

    app = SimulatorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

"""Figures for the comb study note."""
import sys
sys.path.insert(0, "c:/Fun/ToyRadar/Frontend/emerge")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import emerge as em
import coupler_sim as cs
import cap_opt

IMG = r"C:/Fun/ToyRadar/Notes/FunRad/images"
R = "results/sparams_opt_comb3"
BAND = (5.7, 5.9)
db = lambda x: 20 * np.log10(np.abs(x) + 1e-30)

SHIPPED = dict(tag="", wc=0.37, y=1.30, j=1.40, gap=0.10,
               lab="shipped:  Y_COMB 1.30, JOG 1.40, gap 0.10")
STUDY = dict(tag="_w0.38s0.11o0.27y1j0.9", wc=0.38, y=1.00, j=0.90, gap=0.11,
             lab="comb study:  Y_COMB 1.00, JOG 0.90, gap 0.11, W_C 0.38")


def load(tag):
    return cap_opt.load(f"{R}{tag}.npz")


def _poly(path):
    Rt, Lt = [], []
    for ep, e, en in path.iter_right():
        c = e.right
        if en.rcutprev and c: c.pop(-1)
        if ep.rcutnext and c: c.pop(0)
        Rt.extend(c)
    for ep, e, en in path.iter_left():
        c = e.left
        if en.lcutprev and c: c.pop(-1)
        if ep.lcutnext and c: c.pop(0)
        Lt.extend(c)
    return Rt + Lt[::-1]


def _build(wc, ycomb, jog, symmetric=False, bend=90.0, gap=None):
    """Build one variant and hand back its polygons plus key x positions."""
    em.cleanup(); cs._install_polygon_dedupe()
    g = dict(cs.GEOM["opt"]); g["W_C"] = wc
    if gap is not None: g["S_GAP"] = gap
    cs.Y_COMB, cs.JOG, cs.BEND_DEG = ycomb, jog, bend
    if gap is not None: g_gap = gap
    lo = em.geo.PCBNew(cs.H_SUB, unit=cs.MM,
                       material=em.Material(er=cs.ER, tand=cs.TAND), layers=2,
                       thick_traces=True, trace_thickness=g["t_um"] * 1e-6)
    info = cs.build(lo, lo.z(1), g, 3, comb=True, symmetric=symmetric)
    polys = [np.array(_poly(p) + [_poly(p)[0]]) for p in lo.paths]
    x_comb = cs.FEED + g["W_50"] + jog / 2.0
    return polys, x_comb, info["x_start"], info["comb"]["finger_len_mm"]


def layout_fig(out="24_Comb_Study_Layout.png"):
    """What actually changed, drawn to scale."""
    fig, axes = plt.subplots(2, 1, figsize=(11, 7.2))
    for ax, v in zip(axes, (SHIPPED, STUDY)):
        polys, x_comb, x_start, flen = _build(v["wc"], v["y"], v["j"])
        for xy in polys:
            ax.fill(xy[:, 0], xy[:, 1], color="#c8763f", ec="#7a4413",
                    lw=.7, alpha=.92)
        ax.axvline(x_comb, color="#1f77b4", lw=1.2, ls="--")
        ax.axvline(x_start, color="#2ca02c", lw=1.2, ls="--")
        ax.annotate("", (x_comb, 0.30), (x_start, 0.30),
                    arrowprops=dict(arrowstyle="<->", color="k", lw=1.3))
        ax.text((x_comb + x_start) / 2, 0.38,
                f"offset {x_start - x_comb:.2f} mm", ha="center", fontsize=10)
        ax.text(x_comb, -1.92, f"comb, finger {flen:.2f} mm",
                fontsize=9, color="#1f77b4", ha="center",
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#1f77b4",
                          alpha=.9))
        ax.text(x_start + 0.08, -0.55, "coupled\nsection starts", fontsize=9,
                color="#2ca02c")
        ax.set_xlim(1.0, 5.2); ax.set_ylim(-2.0, 0.65)
        ax.set_aspect("equal"); ax.grid(alpha=.25)
        ax.set_title(v["lab"], fontsize=11)
        ax.set_ylabel("y, mm")
    axes[1].set_xlabel("x, mm")
    fig.suptitle("The comb moves 0.25 mm in, and its fingers get shorter", y=0.99)
    fig.tight_layout()
    fig.savefig(f"{IMG}/{out}", dpi=125); plt.close(fig)
    print("wrote", out)


def parasitic_fig(out="25_Comb_Study_Parasitic.png"):
    """Finger length at fixed capacitance: the ground parasitic, measured."""
    EPS0, ER, H, FW = 8.854e-12, 4.4, 0.2104e-3, 0.08e-3
    rows = [(0.90, 0.40, "_w0.37s0.1o0.27y0.9"), (1.00, 0.45, "_w0.37s0.1o0.27y1"),
            (1.15, 0.52, "_w0.37s0.1o0.27y1.15"), (1.30, 0.60, ""),
            (1.60, 0.75, "_w0.37s0.1o0.27y1.6")]
    y, fl, s11, dw = [], [], [], []
    for yy, f_, tag in rows:
        f, S, z0 = load(tag); m = cap_opt.metrics(f, S)
        y.append(yy); fl.append(f_); s11.append(m["S11"]); dw.append(m["Dworst"])
    cgnd = [6 * EPS0 * ER * (FW * f_ * 1e-3) / H * 1e15 for f_ in fl]

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12.5, 4.5))
    a1.plot(fl, s11, "o-", color="#1f77b4", lw=2, label="$S_{11}$ measured (3-D)")
    a1.set_xlabel("finger length, mm"); a1.set_ylabel("$S_{11}$, dB", color="#1f77b4")
    a1.grid(alpha=.3)
    ax2 = a1.twinx()
    ax2.plot(fl, cgnd, "s--", color="#d62728", lw=1.6,
             label="$C$ to ground (predicted)")
    ax2.set_ylim(30, 92)
    ax2.axhline(76, color="#2ca02c", ls="--", lw=1.6)
    ax2.text(0.50, 78, "76 fF - the useful line-to-line capacitance",
             fontsize=9, color="#2ca02c")
    ax2.set_ylabel("finger capacitance to ground, fF", color="#d62728")
    a1.set_title("return loss tracks the ground parasitic")
    h1, l1 = a1.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
    a1.legend(h1 + h2, l1 + l2, fontsize=9, loc="lower left")
    a1.set_xlim(0.36, 0.80)
    for xx, yy, lab in zip(fl, s11, y):
        a1.annotate(f"Y_COMB {lab:.2f}", (xx, yy), fontsize=8, color="#1f77b4",
                    textcoords="offset points", xytext=(6, 6))

    a2.plot(fl, dw, "o-", color="#9467bd", lw=2)
    a2.set_xlabel("finger length, mm"); a2.set_ylabel("worst in-band directivity, dB")
    a2.grid(alpha=.3); a2.set_title("directivity, same sweep")
    fig.suptitle("Capacitance held fixed (overlap 0.27) - only the finger stem varies",
                 y=1.0)
    fig.tight_layout(); fig.savefig(f"{IMG}/{out}", dpi=125); plt.close(fig)
    print("wrote", out)


def offset_fig(out="26_Comb_Study_Offset.png"):
    """Walking the comb toward the coupled section."""
    rows = [(0.77, "_w0.37s0.1o0.27j0.9", 0.80), (0.82, "_w0.37s0.1o0.27j0.9", 0.90),
            (0.92, "_w0.37s0.1o0.27j1.1", 1.10), (1.07, "", 1.40)]
    seen, off, d, s31 = set(), [], [], []
    for o, tag, jog in rows:
        if tag in seen and tag != "":
            continue
        seen.add(tag)
        f, S, z0 = load(tag); m = cap_opt.metrics(f, S)
        off.append(o); d.append(m["Dworst"]); s31.append(m["S31"])

    fig, ax = plt.subplots(figsize=(8.6, 5))
    ax.plot(off, d, "o-", color="#9467bd", lw=2.2, label="directivity")
    ax.set_xlabel("comb offset from the coupled section, mm")
    ax.set_ylabel("worst in-band directivity, dB", color="#9467bd")
    ax.grid(alpha=.3); ax.invert_xaxis()
    ax2 = ax.twinx()
    ax2.plot(off, s31, "s--", color="#d62728", lw=1.6, label="coupling $S_{31}$")
    ax2.axhline(-15, color="#d62728", ls=":", lw=1)
    ax2.axhspan(-15.3, -14.7, color="#d62728", alpha=.10)
    ax2.set_ylabel("$S_{31}$, dB", color="#d62728")
    ax2.text(off[0], -14.6, "coupling spec", fontsize=9, color="#d62728")
    ax.set_title("Closer comb: directivity rises, and so does coupling\n"
                 "(the rising coupling IS the parasitic de-coupling shrinking)",
                 fontsize=11)
    h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, fontsize=9, loc="lower left")
    fig.tight_layout(); fig.savefig(f"{IMG}/{out}", dpi=125); plt.close(fig)
    print("wrote", out)


def sparam_fig(out="27_Comb_Study_Sparams.png"):
    """Shipped against the study result."""
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 4.6))
    for v, ls in ((SHIPPED, "--"), (STUDY, "-")):
        f, S, z0 = load(v["tag"]); fg = f / 1e9
        w = 1.4 if ls == "--" else 2.2
        for k, (i, j), col in (("$S_{31}$", (2, 0), "#d62728"),
                               ("$S_{41}$", (3, 0), "#2ca02c"),
                               ("$S_{11}$", (0, 0), "#666666")):
            a1.plot(fg, db(S[:, i, j]), ls, color=col, lw=w,
                    label=f"{k} {'study' if ls=='-' else 'shipped'}")
        a2.plot(fg, db(S[:, 2, 0]) - db(S[:, 3, 0]), ls, color="#9467bd", lw=w,
                label="study" if ls == "-" else "shipped")
    for ax in (a1, a2):
        ax.axvspan(*BAND, color="0.85", zorder=0)
        ax.set_xlim(4.5, 7.5); ax.grid(alpha=.3); ax.set_xlabel("frequency, GHz")
    a1.set_ylim(-55, 0); a1.set_ylabel("dB")
    a1.legend(fontsize=7.5, ncol=2, loc="lower left")
    a1.set_title("isolation deepens 9 dB, return loss 7 dB")
    a2.set_ylabel("directivity, dB"); a2.legend(fontsize=9)
    a2.set_title("directivity: 20.4 -> 28.9 dB worst in band")
    fig.tight_layout(); fig.savefig(f"{IMG}/{out}", dpi=125); plt.close(fig)
    print("wrote", out)



def sym_fig(out="28_Symmetry_Layout.png"):
    """The only comparison that matters: the two layouts, annotated."""
    VAR = [
        dict(sym=False, wc=0.38, y=1.00, j=0.90, gap=0.11,
             name="ASYMMETRIC  -  the candidate design",
             res="D 28.90 dB    S11 -35.8 dB    S41 -44.7 dB"),
        dict(sym=True, wc=0.38, y=1.40, j=0.90, gap=0.11,
             name="SYMMETRIC  -  best that builds",
             res="D 26.37 dB    S11 -30.5 dB    S41 -43.8 dB"),
    ]
    fig, axes = plt.subplots(2, 1, figsize=(12, 8.6))
    for ax, v in zip(axes, VAR):
        polys, x_comb, x_start, flen = _build(v["wc"], v["y"], v["j"],
                                              symmetric=v["sym"], gap=v["gap"])
        for xy in polys:
            ax.fill(xy[:, 0], xy[:, 1], color="#c8763f", ec="#7a4413",
                    lw=.7, alpha=.92)
        ax.axhline(0, color="#1f77b4", lw=1.0, ls="--", alpha=.75)

        ctc = v["wc"] + v["gap"]
        yA = ctc / 2 if v["sym"] else 0.0
        yB = -ctc / 2 if v["sym"] else -ctc
        yCA = v["y"] / 2 if v["sym"] else 0.0
        yCB = -v["y"] / 2 if v["sym"] else -v["y"]

        ax.annotate("", (x_comb, yCA), (x_comb, yCB),
                    arrowprops=dict(arrowstyle="<->", color="#1f77b4", lw=1.5))
        ax.text(x_comb - 0.07, (yCA + yCB) / 2, f"Y_COMB {v['y']:.2f} ",
                ha="right", va="center", fontsize=9.5, color="#1f77b4",
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#1f77b4"))

        # S_GAP is 0.11 mm -- unreadable at this scale and identical in both
        # panels, so it is stated in the figure title instead of drawn.

        ax.annotate(f"comb finger {flen:.2f} mm", (x_comb, yCA - 0.12),
                    xytext=(-165, 40), textcoords="offset points", fontsize=9.5,
                    color="#d62728",
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#d62728"),
                    arrowprops=dict(arrowstyle="->", color="#d62728"))

        ax.axvline(x_start, color="0.35", lw=1.0, ls=":")
        ax.text(x_start + 0.05, 1.30, "coupled run starts", fontsize=8.5,
                color="0.35")

        ax.set_xlim(0.9, 5.8); ax.set_ylim(-1.55, 1.55)
        ax.set_aspect("equal"); ax.grid(alpha=.22)
        ax.set_ylabel("y, mm")
        ax.set_title(f"{v['name']}          {v['res']}", fontsize=11.5)
    axes[1].set_xlabel("x, mm")
    fig.suptitle("Identical in both: W_C 0.38, S_GAP 0.11, L_C 7.39, JOG 0.90, "
                 "comb overlap 0.27.  Only the routing differs.",
                 y=0.985, fontsize=11)
    fig.tight_layout()
    fig.savefig(f"{IMG}/{out}", dpi=130); plt.close(fig)
    print("wrote", out)



if __name__ == "__main__":
    which = sys.argv[1:] or ["layout", "parasitic", "offset", "sparams"]
    if "parasitic" in which: parasitic_fig()
    if "offset" in which: offset_fig()
    if "sparams" in which: sparam_fig()
    if "layout" in which: layout_fig()
    if "sym" in which: sym_fig()
    import os; sys.stdout.flush(); os._exit(0)

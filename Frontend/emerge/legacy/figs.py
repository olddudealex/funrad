"""All documentation figures for the TX coupler note."""
import sys, os
sys.path.insert(0, "c:/Fun/ToyRadar/Frontend/emerge")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import emerge as em, coupler_sim as cs
from cap_opt import load, add_caps, metrics

IMG = r"C:/Fun/ToyRadar/Notes/FunRad/images"
BAND = (5.7, 5.9)
db = lambda x: 20 * np.log10(np.abs(x) + 1e-30)
C_OPT = 0.062e-12


def band(ax):
    ax.axvspan(*BAND, color="0.85", zorder=0)
    ax.grid(alpha=.3); ax.set_xlabel("frequency, GHz"); ax.set_xlim(4.5, 7.5)


def sparam_fig(npz, title, out, extra=None):
    d = np.load(npz); f = d["f"] / 1e9
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 4.6))
    for key, lab, c in (("S11", "$S_{11}$ return", "#666"),
                        ("S21", "$S_{21}$ through", "#1f77b4"),
                        ("S31", "$S_{31}$ coupled", "#d62728"),
                        ("S41", "$S_{41}$ isolated", "#2ca02c")):
        a1.plot(f, db(d[key]), label=lab, color=c, lw=1.8)
    a1.axhline(-15, ls=":", color="#d62728", lw=1)
    band(a1); a1.set_ylabel("dB"); a1.set_ylim(-50, 0); a1.legend(fontsize=9, loc="lower left")
    a1.set_title(title)

    D = db(d["S31"]) - db(d["S41"])
    a2.plot(f, D, color="#9467bd", lw=2)
    inb = (f >= BAND[0]) & (f <= BAND[1])
    a2.plot(f[inb], D[inb], color="#9467bd", lw=4)
    a2.annotate(f"worst in band\n{D[inb].min():.1f} dB",
                (5.8, D[inb].min()), textcoords="offset points", xytext=(10, -28),
                fontsize=10, arrowprops=dict(arrowstyle="->", color="#9467bd"))
    band(a2); a2.set_ylabel("directivity, dB"); a2.set_title("directivity = $S_{31} - S_{41}$")
    if extra:
        a2.axhline(extra, ls="--", color="0.4", lw=1)
    fig.tight_layout(); fig.savefig(f"{IMG}/{out}", dpi=115); plt.close(fig)
    print("wrote", out, f"(Dworst {D[inb].min():.2f})")


def layout_fig(out="12_Coupler_Layout.png"):
    em.cleanup(); cs._install_polygon_dedupe()
    m = em.Simulation("layout")
    g = cs.GEOM["opt"]
    lo = em.geo.PCBNew(cs.H_SUB, unit=cs.MM,
                       material=em.Material(er=cs.ER, tand=cs.TAND), layers=2,
                       thick_traces=True, trace_thickness=g["t_um"] * 1e-6)
    info = cs.build(lo, lo.z(1), g, 3, comb=True)

    def poly(path):
        R, L = [], []
        for ep, e, en in path.iter_right():
            c = e.right
            if en.rcutprev and c: c.pop(-1)
            if ep.rcutnext and c: c.pop(0)
            R.extend(c)
        for ep, e, en in path.iter_left():
            c = e.left
            if en.lcutprev and c: c.pop(-1)
            if ep.lcutnext and c: c.pop(0)
            L.extend(c)
        return R + L[::-1]

    fig, (a1, a2) = plt.subplots(2, 1, figsize=(13, 7.5),
                                 gridspec_kw=dict(height_ratios=[1, 1.15]))
    for ax in (a1, a2):
        for p in lo.paths:
            xy = np.array(poly(p) + [poly(p)[0]])
            ax.fill(xy[:, 0], xy[:, 1], color="#c8763f", ec="#7a4413", lw=.6, alpha=.9)
        ax.set_aspect("equal"); ax.grid(alpha=.25)
    xs = info["x_start"]; tot = info["total_x"]; lc = g["L_C"]
    a1.set_xlim(-0.5, tot + 0.5); a1.set_ylim(-3.0, 0.5)
    a1.annotate("", (xs, 0.3), (xs + lc, 0.3), arrowprops=dict(arrowstyle="<->", color="k"))
    a1.text(xs + lc / 2, 0.36, f"$L_C$ = {lc} mm", ha="center", fontsize=10)
    for x, lab in ((0, "P1 / P3"), (tot, "P2 / P4")):
        a1.text(x, 0.42, lab, ha="center", fontsize=9, color="#333")
    a1.set_title("TX coupler layout (top view), all 90 deg mitred bends")
    a2.set_xlim(1.6, 4.4); a2.set_ylim(-1.7, 0.35)
    a2.set_title(f"comb detail: {3} fingers/side, {g['fw']} wide, {g['fgap']} gap, "
                 f"overlap {info['comb']['overlap_mm']:.3f} mm")
    a2.set_xlabel("x, mm")
    fig.tight_layout(); fig.savefig(f"{IMG}/{out}", dpi=115); plt.close(fig)
    print("wrote", out)


def best_C(npz):
    f, S, z0 = load(npz)
    Cs = np.arange(0.002, 0.141, 0.002) * 1e-12
    D = [metrics(f, add_caps(S, f, z0, C))["Dworst"] for C in Cs]
    i = int(np.argmax(D))
    return float(Cs[i]), float(D[i])


def cap_fig(npz, out="15_Coupler_Cap_Effect.png", Copt=C_OPT):
    f, S, z0 = load(npz); fg = f / 1e9
    cases = [(0.0, "no cap"), (round(Copt * 0.5, 15), f"{Copt*0.5e12:.3f} pF (under)"),
             (Copt, f"{Copt*1e12:.3f} pF (optimum)"),
             (round(Copt * 1.6, 15), f"{Copt*1.6e12:.3f} pF (over)")]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 4.6))
    for C, lab in cases:
        Sc = S if C == 0 else add_caps(S, f, z0, C)
        a1.plot(fg, db(Sc[:, 3, 0]), lw=1.9, label=lab)
        a2.plot(fg, db(Sc[:, 2, 0]) - db(Sc[:, 3, 0]), lw=1.9, label=lab)
    band(a1); a1.set_ylabel("$S_{41}$ isolation, dB"); a1.legend(fontsize=9)
    a1.set_title("the cap pushes $S_{41}$ down across the whole band")
    band(a2); a2.set_ylabel("directivity, dB"); a2.legend(fontsize=9)
    a2.set_title("too little under-corrects, too much over-corrects")
    fig.tight_layout(); fig.savefig(f"{IMG}/{out}", dpi=115); plt.close(fig)
    print("wrote", out)


def window_fig(npz, out="16_Coupler_Cap_Window.png", title="step 2: circuit-level capacitance sweep"):
    f, S, z0 = load(npz)
    D0 = metrics(f, S)["Dworst"]
    Cs = np.arange(0.002, 0.141, 0.002) * 1e-12
    D = [metrics(f, add_caps(S, f, z0, C))["Dworst"] for C in Cs]
    fig, ax = plt.subplots(figsize=(8.5, 5))
    ax.plot(Cs * 1e12, D, color="#9467bd", lw=2.2, label="worst in-band directivity")
    ax.axhspan(20, max(D) + 2, color="#d5f0d5", zorder=0)
    ok = [c * 1e12 for c, d in zip(Cs, D) if d >= 20]
    ax.axvspan(min(ok), max(ok), color="#9467bd", alpha=.12, zorder=0)
    i = int(np.argmax(D))
    ax.plot(Cs[i] * 1e12, D[i], "o", color="#9467bd")
    ax.annotate(f"optimum {Cs[i]*1e12:.3f} pF\n{D[i]:.1f} dB", (Cs[i]*1e12, D[i]),
                textcoords="offset points", xytext=(12, -34), fontsize=10,
                arrowprops=dict(arrowstyle="->"))
    ax.axvline(0.0409, ls="--", color="#d62728", lw=1.4)
    ax.text(0.0409, 2, " closed form\n 40.9 fF", color="#d62728", fontsize=9, va="bottom")
    ax.axhline(D0, ls=":", color="0.4")
    ax.text(max(Cs) * 1e12, D0 + 0.5, f"uncompensated {D0:.1f} dB",
            fontsize=9, color="0.3", ha="right")
    ax.set_xlabel("compensation capacitance per end, pF")
    ax.set_ylabel("worst in-band directivity, dB")
    ax.set_title(title)
    ax.grid(alpha=.3); ax.legend(fontsize=9, loc="upper left")
    fig.tight_layout(); fig.savefig(f"{IMG}/{out}", dpi=115); plt.close(fig)
    print("wrote", out, f"(opt {Cs[i]*1e12:.3f} pF)")


if __name__ == "__main__":
    deemb = "results/sparams_opt_nocomb_atcomb.npz"    # step 1, ports at the comb planes
    final = "results/sparams_opt_comb3.npz"            # step 3, the tuned design
    sparam_fig(deemb, "step 1: uncompensated, ports at the comb planes",
               "14_Coupler_Sparams_Uncompensated.png")
    sparam_fig(final, "step 3: with comb, final", "18_Coupler_Sparams_Final.png")
    Copt, Dopt = best_C(deemb)
    print(f"de-embedded optimum: {Copt*1e12:.4f} pF -> {Dopt:.2f} dB")
    cap_fig(deemb, Copt=Copt)
    window_fig(deemb, title="step 2: capacitance sweep at the comb reference planes")
    layout_fig()
    import os as _os; sys.stdout.flush(); _os._exit(0)

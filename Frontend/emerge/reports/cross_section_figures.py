"""Figures for the "Quasi-static 2-D Solver" note."""
import os
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import numpy as np

from simulation.coupled_2d import field, modes, single, coupling_db

IMG = str(Path(__file__).resolve().parents[3]/'Notes/FunRad/images')
ER, H, T = 4.4, 210.4, 35.0
W50, WC, SGAP = 370.0, 370.0, 100.0   # the adopted design: W_C == W_50


def _extent(V, d):
    NX, NY = V.shape
    return [0, (NX - 1) * d, 0, (NY - 1) * d]


def domain_fig(out="20_2D_Solver_Domain.png"):
    """The grid, what is dielectric, and where the Dirichlet values sit."""
    d = 20.0
    C, V, tags, eps, _ = field(WC, SGAP, odd=True, d_um=d,
                               lid_um=700.0, xpad_um=700.0)
    NX, NY = V.shape
    x = np.arange(NX) * d / 1e3
    y = np.arange(NY) * d / 1e3

    fig, ax = plt.subplots(figsize=(11, 4.4))
    epsn = np.full((NX, NY), np.nan)
    epsn[:-1, :-1] = eps
    ax.pcolormesh(x, y, epsn.T, cmap="Blues", vmin=0, vmax=6,
                  shading="auto", alpha=.55)
    ax.text(0.35, 0.10, f"substrate  $\\varepsilon_r$ = {ER}", fontsize=10)
    ax.text(0.35, 0.55, "air  $\\varepsilon_r$ = 1", fontsize=10)

    for i in range(0, NX, 2):
        ax.plot([x[i], x[i]], [y[0], y[-1]], lw=.25, color="0.75", zorder=0)
    for j in range(0, NY, 2):
        ax.plot([x[0], x[-1]], [y[j], y[j]], lw=.25, color="0.75", zorder=0)

    for tag, col in ((1, "#333333"), (2, "#d62728"), (3, "#2ca02c")):
        pts = np.argwhere(tags == tag)
        ax.plot(pts[:, 0] * d / 1e3, pts[:, 1] * d / 1e3, ".",
                ms=2.2, color=col, zorder=5)

    ax.annotate("strip A,  V = +1", (x[np.argwhere(tags == 3)[:, 0].mean().astype(int)],
                                     (H + T) / 1e3),
                xytext=(20, 38), textcoords="offset points", fontsize=10,
                color="#2ca02c", arrowprops=dict(arrowstyle="->", color="#2ca02c"))
    ax.annotate("strip B,  V = -1 (odd)\n            V = +1 (even)",
                (x[np.argwhere(tags == 2)[:, 0].mean().astype(int)], (H + T) / 1e3),
                xytext=(-140, 38), textcoords="offset points", fontsize=10,
                color="#d62728", arrowprops=dict(arrowstyle="->", color="#d62728"))
    ax.text(.08, -.23, "box walls: V = 0; bottom boundary: ground plane",
                transform=ax.transAxes,
                fontsize=9.5, color="#222222", ha="left",
                bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="0.7", alpha=.85))
    ax.set_xlabel("x, mm"); ax.set_ylabel("y, mm")
    ax.set_title("Domain: uniform grid, permittivity per cell, Dirichlet nodes marked "
                 f"(shown coarse at d = {d:.0f} um)")
    ax.set_aspect("equal")
    fig.tight_layout(); fig.subplots_adjust(bottom=.25)
    fig.savefig(f"{IMG}/{out}", dpi=160); plt.close(fig)
    print("wrote", out)


def fields_fig(out="21_2D_Solver_Fields.png"):
    """Even and odd potential maps -- where the two modes keep their energy."""
    d = 5.0
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.2))
    for ax, odd, lab in ((axes[0], False, "even mode  (+1, +1)"),
                         (axes[1], True, "odd mode  (+1, -1)")):
        C, V, tags, eps, _ = field(WC, SGAP, odd=odd, d_um=d,
                                   lid_um=900.0, xpad_um=900.0)
        NX, NY = V.shape
        x = np.arange(NX) * d / 1e3
        y = np.arange(NY) * d / 1e3
        norm = TwoSlopeNorm(vmin=-1, vcenter=0, vmax=1)
        im = ax.pcolormesh(x, y, V.T, cmap="RdBu_r", norm=norm, shading="auto")
        ax.contour(x, y, V.T, levels=np.linspace(-0.9, 0.9, 19),
                   colors="k", linewidths=.35, alpha=.55)
        ax.axhline(H / 1e3, color="k", lw=1.0, ls="--", alpha=.7)
        ax.set_title(lab); ax.set_xlabel("x, mm")
        ax.set_aspect("equal")
        ax.set_xlim(x[-1] / 2 - 0.85, x[-1] / 2 + 0.85)
        ax.set_ylim(0, 0.75)
        fig.colorbar(im, ax=ax, fraction=.03, pad=.02, label="V")
    axes[0].set_ylabel("y, mm")
    axes[0].text(axes[0].get_xlim()[0] + .05, H / 1e3 - .045,
                 "substrate below, air above", fontsize=9)
    axes[1].annotate("odd mode crowds the gap,\nwhere $\\varepsilon_r$ = 1",
                     (x[-1] / 2, (H + T) / 1e3), xytext=(30, 42),
                     textcoords="offset points", fontsize=10,
                     arrowprops=dict(arrowstyle="->"))
    fig.suptitle(f"Potential for W = {WC/1e3:.3f} mm, S = {SGAP/1e3:.3f} mm "
                 "-- the odd mode is why the two velocities differ", y=1.02)
    fig.tight_layout(); fig.savefig(f"{IMG}/{out}", dpi=120,
                                    bbox_inches="tight"); plt.close(fig)
    print("wrote", out)


def convergence_fig(out="22_2D_Solver_Convergence.png"):
    """Grid step and box size: what the answer is actually sensitive to."""
    ds = [20.0, 15.0, 10.0, 7.5, 5.0]
    pads = [700.0, 1000.0, 1500.0, 2500.0, 4000.0]
    g = [modes(WC, SGAP, d_um=d) for d in ds]
    b = [modes(WC, SGAP, d_um=10.0, xpad_um=p, lid_um=max(2500.0, p))
         for p in pads]

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.2))
    for ax, xs, res, xlab in ((a1, ds, g, "grid step d, um"),
                              (a2, pads, b, "box half-width, um")):
        ze = [r[0] for r in res]; zo = [r[1] for r in res]
        zm = [np.sqrt(a * b_) for a, b_ in zip(ze, zo)]
        ax.plot(xs, ze, "o-", label="$Z_{0e}$", color="#1f77b4")
        ax.plot(xs, zo, "s-", label="$Z_{0o}$", color="#d62728")
        ax.plot(xs, zm, "^--", label=r"$\sqrt{Z_{0e}Z_{0o}}$", color="#2ca02c")
        ax.axhline(50, color="0.5", lw=.8, ls=":")
        ax.set_xlabel(xlab); ax.grid(alpha=.3); ax.legend(fontsize=9)
    a1.invert_xaxis()
    a1.set_ylabel("ohm")
    for dd, zz in zip(ds, [np.sqrt(r[0] * r[1]) for r in g]):
        if abs(round(210.4 / dd) * dd - 210.4) > 1 or abs(round(100.0 / dd) * dd - 100.0) > 1:
            a1.annotate("snaps to\nwrong geometry", (dd, zz), fontsize=8,
                        color="#d62728", ha="center",
                        textcoords="offset points", xytext=(0, -34),
                        arrowprops=dict(arrowstyle="->", color="#d62728", lw=.8))
    a1.set_title("refining the grid (box fixed)")
    a2.set_title("opening the box (d = 10 um)")
    fig.suptitle("Convergence: both effects are ~1 ohm; the grid scatter is "
                 "dimension snapping, not discretisation error", y=1.0)
    fig.tight_layout(); fig.savefig(f"{IMG}/{out}", dpi=120); plt.close(fig)
    print("wrote", out)


def design_fig(out="23_2D_Solver_Design_Curves.png"):
    """The two curves the coupler is designed from, at production resolution.

    d = 5 um throughout: at d = 10 the crossings move by ~0.01 mm, which is
    enough to disagree with the design and is not worth the time saved.
    """
    D = 5.0
    ws_s = np.array([330.0, 350.0, 371.0, 390.0, 410.0])
    z_single = [single(w, d_um=D)[0] for w in ws_s]

    ws_c = np.array([290.0, 310.0, 320.0, 340.0, 360.0])
    coup = [modes(w, SGAP, d_um=D) for w in ws_c]
    zm = [np.sqrt(c[0] * c[1]) for c in coup]

    ss = np.array([80.0, 100.0, 130.0, 160.0, 200.0])
    cdb = [coupling_db(*modes(WC, s, d_um=D)[:2])[0] for s in ss]

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12.5, 4.4))
    a1.plot(ws_s / 1e3, z_single, "o-", color="#1f77b4",
            label="single strip, $Z_0$")
    a1.plot(ws_c / 1e3, zm, "s-", color="#2ca02c",
            label=r"coupled pair, $\sqrt{Z_{0e}Z_{0o}}$ at S = 0.100")
    a1.axhline(50, color="#d62728", lw=1.2, ls="--")
    for xs, ys, lab, dy in ((ws_s / 1e3, z_single, "single line: 50 ohm here", 14),
                            (ws_c / 1e3, zm, "coupled pair: 50 ohm here", -28)):
        w50 = np.interp(50.0, np.array(ys)[::-1], xs[::-1])
        a1.plot(w50, 50, "o", color="#d62728", zorder=5)
        a1.annotate(f"{lab}\n{w50:.3f} mm", (w50, 50),
                    textcoords="offset points", xytext=(10, dy),
                    fontsize=9, color="#d62728")
    a1.axvline(0.37, color="k", lw=1.6, ls="-", alpha=.8, zorder=4)
    a1.annotate("ADOPTED  $W_{50}$ = $W_C$ = 0.37\n"
                "(chosen in 3-D with the comb;\n"
                " the coupled crossing at 0.32\n"
                " measures 4.8 dB worse)",
                (0.37, a1.get_ylim()[0]), textcoords="offset points",
                xytext=(-160, 30), fontsize=9,
                bbox=dict(boxstyle="round,pad=0.3", fc="#fff8dc", ec="0.6"),
                arrowprops=dict(arrowstyle="->", color="k"))
    a1.set_xlabel("strip width, mm"); a1.set_ylabel("ohm")
    a1.set_title("width sets the impedance"); a1.grid(alpha=.3)
    a1.legend(fontsize=9)

    a2.plot(ss / 1e3, cdb, "o-", color="#9467bd")
    a2.axhline(-15, color="0.5", ls=":", lw=1)
    # cdb decreases with S, and np.interp needs increasing xp -- reverse both
    s15 = np.interp(-15.0, np.array(cdb)[::-1], (ss / 1e3)[::-1])
    a2.plot(s15, -15, "o", color="#d62728", zorder=5)
    a2.annotate(f"-15 dB at S = {s15:.3f} mm", (s15, -15),
                textcoords="offset points", xytext=(-30, 20), fontsize=10,
                color="#d62728", arrowprops=dict(arrowstyle="->", color="#d62728"))
    a2.set_xlabel("gap S, mm"); a2.set_ylabel("backward coupling, dB")
    a2.set_title(f"gap sets the coupling  (W = {WC/1e3:.3f} mm)"); a2.grid(alpha=.3)
    fig.suptitle("Design curves, d = 5 um", y=1.0)
    fig.tight_layout(); fig.savefig(f"{IMG}/{out}", dpi=120); plt.close(fig)
    print("wrote", out)
    print(f"   W_50 = {np.interp(50.0, np.array(z_single)[::-1], ws_s[::-1]):.1f} um")
    print(f"   W_C  = {np.interp(50.0, np.array(zm)[::-1], ws_c[::-1]):.1f} um")
    print(f"   S for -15 dB = {s15*1e3:.1f} um")


if __name__ == "__main__":
    which = sys.argv[1:] or ["domain", "fields", "conv", "design"]
    if "domain" in which:
        domain_fig()
    if "fields" in which:
        fields_fig()
    if "conv" in which:
        convergence_fig()
    if "design" in which:
        design_fig()

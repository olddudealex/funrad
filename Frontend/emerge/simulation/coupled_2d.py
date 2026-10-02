#!/usr/bin/env python
"""Quasi-static 2-D solver for a coupled microstrip pair.

Answers the two questions the note could not: where W_C and S_GAP come from.

Method: solve Laplace with a variable-permittivity 5-point stencil on a uniform
grid, twice per mode -- once with the real substrate and once with air -- and
take the induced charge on ONE strip.  Then, as for a single line,

    Z0m = 1 / (c sqrt(Cm * Cm_air))        eps_eff,m = Cm / Cm_air

for m = even (both strips at +1 V) and odd (+1 V and -1 V).  The odd mode puts
field in the air gap between the strips, so its Cm/Cm_air ratio is lower --
that is the velocity split the whole coupler design turns on.

Validated against Qucs Transcalc in __main__.
"""
from __future__ import annotations

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

EPS0 = 8.8541878128e-12
C_LIGHT = 299792458.0


def _solve(W_um, S_um, t_um, er, h_um, d_um, lid_um, xpad_um, odd,
           return_field=False):
    d = d_um
    W = int(round(W_um / d)); S = int(round(S_um / d)); t = int(round(t_um / d))
    h = int(round(h_um / d)); lid = int(round(lid_um / d))
    xpad = int(round(xpad_um / d))

    nx = 2 * xpad + 2 * W + S
    ny = h + t + lid
    NX, NY = nx + 1, ny + 1

    eps = np.ones((nx, ny))
    eps[:, :h] = er

    # face-averaged permittivities, as in the single-line solver
    up = np.zeros((nx, NY)); up[:, :ny] = eps
    dn = np.zeros((nx, NY)); dn[:, 1:] = eps
    cE = np.zeros((nx, NY)); cE[:, :ny] += 1; cE[:, 1:] += 1
    epsE = (up + dn) / cE
    rt = np.zeros((NX, ny)); rt[:nx, :] = eps
    lf = np.zeros((NX, ny)); lf[1:, :] = eps
    cN = np.zeros((NX, ny)); cN[:nx, :] += 1; cN[1:, :] += 1
    epsN = (rt + lf) / cN

    fixed = np.zeros((NX, NY), dtype=np.int8)
    fixed[:, 0] = 1; fixed[0, :] = 1; fixed[-1, :] = 1; fixed[:, -1] = 1

    bL, bR = xpad, xpad + W                      # left strip node span
    aL, aR = xpad + W + S, xpad + 2 * W + S      # right strip ("strip A")
    fixed[bL:bR + 1, h:h + t + 1] = 2            # left  -> tag 2
    fixed[aL:aR + 1, h:h + t + 1] = 3            # right -> tag 3

    val = np.zeros((NX, NY))
    val[fixed == 3] = 1.0
    val[fixed == 2] = -1.0 if odd else 1.0

    nid = lambda i, j: i * NY + j
    rows, cols, data = [], [], []
    rhs = np.zeros(NX * NY)
    for i in range(NX):
        for j in range(NY):
            k = nid(i, j)
            if fixed[i, j]:
                rows.append(k); cols.append(k); data.append(1.0)
                rhs[k] = val[i, j]
                continue
            diag = 0.0
            for ii, jj, ef in ((i + 1, j, epsE[i, j] if i < nx else 0.0),
                               (i - 1, j, epsE[i - 1, j] if i > 0 else 0.0),
                               (i, j + 1, epsN[i, j] if j < ny else 0.0),
                               (i, j - 1, epsN[i, j - 1] if j > 0 else 0.0)):
                if 0 <= ii < NX and 0 <= jj < NY:
                    diag -= ef
                    if fixed[ii, jj]:
                        rhs[k] -= ef * val[ii, jj]
                    else:
                        rows.append(k); cols.append(nid(ii, jj)); data.append(ef)
            rows.append(k); cols.append(k); data.append(diag)

    A = sp.csr_matrix((data, (rows, cols)), shape=(NX * NY, NX * NY))
    V = spla.spsolve(A, rhs).reshape(NX, NY)

    # induced charge on strip A only -> per-line capacitance
    mask = fixed == 3
    q = 0.0
    for i, j in np.argwhere(mask):
        for ii, jj, ef in ((i + 1, j, epsE[i, j] if i < nx else 0.0),
                           (i - 1, j, epsE[i - 1, j] if i > 0 else 0.0),
                           (i, j + 1, epsN[i, j] if j < ny else 0.0),
                           (i, j - 1, epsN[i, j - 1] if j > 0 else 0.0)):
            if 0 <= ii < NX and 0 <= jj < NY and not mask[ii, jj]:
                q += ef * (V[ii, jj] - V[i, j])
    if return_field:
        return -EPS0 * q, V, fixed, eps, d
    return -EPS0 * q


def field(W_um, S_um, odd, t_um=35.0, er=4.4, h_um=210.4, d_um=5.0,
          lid_um=2500.0, xpad_um=1500.0):
    """Potential map for plotting: -> C, V, tags, eps, cell size."""
    return _solve(W_um, S_um, t_um, er, h_um, d_um, lid_um, xpad_um, odd,
                  return_field=True)


def _solve_single(W_um, t_um, er, h_um, d_um, lid_um, xpad_um,
                  mask_um=0.0, er_mask=1.0):
    """One strip, so the domain stays small -- a wide-gap pair is wasteful."""
    d = d_um
    W = int(round(W_um / d)); t = int(round(t_um / d))
    h = int(round(h_um / d)); lid = int(round(lid_um / d))
    xpad = int(round(xpad_um / d))
    nx, ny = W + 2 * xpad, h + t + lid
    NX, NY = nx + 1, ny + 1

    eps = np.ones((nx, ny)); eps[:, :h] = er
    if mask_um > 0.0:
        m = int(round(mask_um / d))
        # conformal coating: beside the strip and over it
        eps[:, h:min(h + t + m, ny)] = er_mask
    up = np.zeros((nx, NY)); up[:, :ny] = eps
    dn = np.zeros((nx, NY)); dn[:, 1:] = eps
    cE = np.zeros((nx, NY)); cE[:, :ny] += 1; cE[:, 1:] += 1
    epsE = (up + dn) / cE
    rt = np.zeros((NX, ny)); rt[:nx, :] = eps
    lf = np.zeros((NX, ny)); lf[1:, :] = eps
    cN = np.zeros((NX, ny)); cN[:nx, :] += 1; cN[1:, :] += 1
    epsN = (rt + lf) / cN

    fixed = np.zeros((NX, NY), dtype=np.int8)
    fixed[:, 0] = 1; fixed[0, :] = 1; fixed[-1, :] = 1; fixed[:, -1] = 1
    fixed[xpad:xpad + W + 1, h:h + t + 1] = 3
    val = np.zeros((NX, NY)); val[fixed == 3] = 1.0

    nid = lambda i, j: i * NY + j
    rows, cols, data = [], [], []
    rhs = np.zeros(NX * NY)
    for i in range(NX):
        for j in range(NY):
            k = nid(i, j)
            if fixed[i, j]:
                rows.append(k); cols.append(k); data.append(1.0)
                rhs[k] = val[i, j]; continue
            diag = 0.0
            for ii, jj, ef in ((i + 1, j, epsE[i, j] if i < nx else 0.0),
                               (i - 1, j, epsE[i - 1, j] if i > 0 else 0.0),
                               (i, j + 1, epsN[i, j] if j < ny else 0.0),
                               (i, j - 1, epsN[i, j - 1] if j > 0 else 0.0)):
                if 0 <= ii < NX and 0 <= jj < NY:
                    diag -= ef
                    if fixed[ii, jj]:
                        rhs[k] -= ef * val[ii, jj]
                    else:
                        rows.append(k); cols.append(nid(ii, jj)); data.append(ef)
            rows.append(k); cols.append(k); data.append(diag)
    A = sp.csr_matrix((data, (rows, cols)), shape=(NX * NY, NX * NY))
    V = spla.spsolve(A, rhs).reshape(NX, NY)
    mask = fixed == 3; q = 0.0
    for i, j in np.argwhere(mask):
        for ii, jj, ef in ((i + 1, j, epsE[i, j] if i < nx else 0.0),
                           (i - 1, j, epsE[i - 1, j] if i > 0 else 0.0),
                           (i, j + 1, epsN[i, j] if j < ny else 0.0),
                           (i, j - 1, epsN[i, j - 1] if j > 0 else 0.0)):
            if 0 <= ii < NX and 0 <= jj < NY and not mask[ii, jj]:
                q += ef * (V[ii, jj] - V[i, j])
    return -EPS0 * q


def single(W_um, t_um=35.0, er=4.4, h_um=210.4, d_um=5.0,
           lid_um=2500.0, xpad_um=1500.0, mask_um=0.0, er_mask=3.8):
    """-> Z0, eps_eff for one isolated microstrip.

    mask_um > 0 adds a conformal soldermask coating of relative permittivity
    er_mask over and beside the strip.  The air reference solve keeps the
    coating region at 1.0, so eps_eff stays C / C_air as before.
    """
    C = _solve_single(W_um, t_um, er, h_um, d_um, lid_um, xpad_um,
                      mask_um, er_mask)
    Ca = _solve_single(W_um, t_um, 1.0, h_um, d_um, lid_um, xpad_um,
                       mask_um, 1.0)
    return 1.0 / (C_LIGHT * np.sqrt(C * Ca)), C / Ca


def modes(W_um, S_um, t_um=35.0, er=4.4, h_um=210.4, d_um=5.0,
          lid_um=2500.0, xpad_um=1500.0):
    """-> Z0e, Z0o, eps_eff_e, eps_eff_o for one (W, S) pair."""
    out = {}
    for name, odd in (("e", False), ("o", True)):
        C = _solve(W_um, S_um, t_um, er, h_um, d_um, lid_um, xpad_um, odd)
        Ca = _solve(W_um, S_um, t_um, 1.0, h_um, d_um, lid_um, xpad_um, odd)
        out["Z0" + name] = 1.0 / (C_LIGHT * np.sqrt(C * Ca))
        out["eps_" + name] = C / Ca
    return out["Z0e"], out["Z0o"], out["eps_e"], out["eps_o"]


def coupling_db(z0e, z0o):
    """Backward coupling of a quarter-wave section, and its match."""
    k = (z0e - z0o) / (z0e + z0o)
    return 20 * np.log10(k), np.sqrt(z0e * z0o)


def synthesise(coupling_target_db, z0=50.0, t_um=35.0, er=4.4, h_um=210.4,
               d_um=10.0, w0=380.0, s0=150.0, tol=0.15, itmax=40):
    """Find (W, S) giving the requested coupling with sqrt(Z0e*Z0o) = z0.

    W mostly sets the geometric-mean impedance, S mostly sets the ratio, so a
    simple alternating secant walk on the two converges.
    """
    k = 10 ** (coupling_target_db / 20.0)
    ze_t = z0 * np.sqrt((1 + k) / (1 - k))
    zo_t = z0 * np.sqrt((1 - k) / (1 + k))
    W, S = w0, s0
    for _ in range(itmax):
        ze, zo, _, _ = modes(W, S, t_um, er, h_um, d_um)
        zm, ratio = np.sqrt(ze * zo), ze / zo
        if abs(zm - z0) < tol and abs(ratio - ze_t / zo_t) < tol / 10:
            break
        W *= (zm / z0) ** 0.85          # wider line -> lower impedance
        S *= (ratio / (ze_t / zo_t)) ** 0.9   # wider gap -> weaker coupling
        W, S = float(np.clip(W, 150, 900)), float(np.clip(S, 40, 600))
    return W, S, ze, zo


if __name__ == "__main__":
    print("VALIDATION against Qucs Transcalc (W 0.383, S 0.151, T 35 um)")
    print("  Transcalc : Z0e 59.85  Z0o 41.77  eps_e 3.549  eps_o 3.029")
    ze, zo, ee, eo = modes(382.963, 151.254)
    print(f"  this solver: Z0e {ze:5.2f}  Z0o {zo:5.2f}  "
          f"eps_e {ee:.3f}  eps_o {eo:.3f}")

    print("\nWHAT THE DESIGN ACTUALLY USES")
    for W, S, lab in ((346.0, 100.0, "W_C 0.346 / S 0.100  (as built)"),
                      (371.0, 100.0, "W_C 0.371 / S 0.100  (= W_50)"),
                      (382.963, 151.254, "Transcalc -15 dB")):
        ze, zo, ee, eo = modes(W, S)
        c, zm = coupling_db(ze, zo)
        print(f"  {lab:34s} Z0e {ze:5.2f}  Z0o {zo:5.2f}  "
              f"sqrt(ZeZo) {zm:5.2f}  coupling {c:6.2f} dB")

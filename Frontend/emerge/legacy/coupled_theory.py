#!/usr/bin/env python
"""Closed-form coupled-line theory behind the TX coupler.

Everything the note's "The idea" section claims is computed here, so no number
in it is quoted from memory:

  1. the Z0e / Z0o a -15 dB coupler needs (standard equations)
  2. what an inhomogeneous (microstrip) medium does to the isolated port
  3. the compensation capacitance that fixes it

Inputs are the Qucs Transcalc synthesis for this substrate -- change them here
if Transcalc is re-run.

The four-port is solved by even/odd decomposition.  For a symmetric coupled
pair, exciting ports 1 and 3 in phase sees a single line of impedance Z0e and
electrical length theta_e; out of phase sees Z0o and theta_o.  Then

    S11 = (Ge + Go)/2      S31 = (Ge - Go)/2      (coupled, backward)
    S21 = (Te + To)/2      S41 = (Te - To)/2      (isolated)

with G, T the reflection/transmission of that one line in a Z0 system.

This is exactly Pozar's coupled-line coupler derivation (Microwave Engineering)
with ONE assumption removed.  Pozar works in a homogeneous medium -- stripline -- where
both modes see the same permittivity, so theta_e = theta_o = theta.  Impose
that here and S41 collapses to zero identically: the isolated port is perfectly
isolated and directivity is infinite.  Microstrip is not homogeneous: the even
mode keeps most of its field in the substrate while the odd mode puts a large
share in the air gap between the strips, so eps_eff_even > eps_eff_odd, the odd
mode runs faster, theta_e != theta_o, and the cancellation at port 4 fails.
That residual IS the directivity limit -- it is a property of the medium, not
of the layout, and no choice of W, S or L removes it.

A capacitor bridging the two lines at each end fixes it because it is invisible
to the even mode (both strips at the same potential -> no voltage across it, no
current) and loads only the odd mode, slowing it until the two lengths match.
"""
from __future__ import annotations

import numpy as np

C0 = 299792458.0
Z0 = 50.0                      # system impedance
F0 = 5.8e9                     # design frequency
BAND = (5.7e9, 5.9e9)
COUPLING_DB = -15.0            # nameplate coupling

# ---- Qucs Transcalc 24.4.0, coupled microstrip, Er 4.4 / H 0.2104 / T 0.035 --
# synthesised at 5.8 GHz for the Z0e / Z0o below, lossless (Tand 0, Cond 1e20)
TC = dict(W=0.382963e-3, S=0.151254e-3, L=7.13645e-3,
          eps_e=3.54887, eps_o=3.02908)


def required_impedances(coupling_db=COUPLING_DB, z0=Z0):
    """Standard -- and the only -- equations that set the coupler.

    The voltage coupling coefficient k is the nameplate coupling; a matched
    backward-wave coupler then requires Z0e*Z0o = Z0**2 together with
        Z0e = Z0 sqrt((1+k)/(1-k)),  Z0o = Z0 sqrt((1-k)/(1+k)).
    """
    k = 10 ** (coupling_db / 20.0)
    return k, z0 * np.sqrt((1 + k) / (1 - k)), z0 * np.sqrt((1 - k) / (1 + k))


def _abcd_line(z, theta):
    c, s = np.cos(theta), np.sin(theta)
    return np.array([[c, 1j * z * s], [1j * s / z, c]])


def _abcd_shunt(y):
    return np.array([[1.0 + 0j, 0], [y, 1.0]])


def _refl_trans(abcd, z0=Z0):
    """Reflection and transmission of a two-port in a z0 system."""
    A, B, C, D = abcd[0, 0], abcd[0, 1], abcd[1, 0], abcd[1, 1]
    den = A + B / z0 + C * z0 + D
    return (A + B / z0 - C * z0 - D) / den, 2.0 / den


def sparams(f, z0e, z0o, eps_e, eps_o, length, cap=0.0, z0=Z0):
    """Four-port S of the coupled section, optional bridging cap at each end.

    `cap` is the capacitance between the two lines at ONE end.  In odd-mode
    excitation the symmetry plane is a virtual ground, so a capacitor C across
    the pair appears as 2C to ground on each line.  In even-mode excitation
    there is no voltage across it at all, so the even mode is untouched --
    which is the whole point.
    """
    f = np.atleast_1d(np.asarray(f, dtype=float))
    out = {k: np.empty(f.shape, dtype=complex) for k in ("S11", "S21", "S31", "S41")}
    for i, fi in enumerate(f):
        k0 = 2 * np.pi * fi / C0
        th_e = k0 * np.sqrt(eps_e) * length
        th_o = k0 * np.sqrt(eps_o) * length
        Ge, Te = _refl_trans(_abcd_line(z0e, th_e), z0)
        y = 2j * np.pi * fi * (2.0 * cap)          # 2C per line to virtual gnd
        odd = _abcd_shunt(y) @ _abcd_line(z0o, th_o) @ _abcd_shunt(y)
        Go, To = _refl_trans(odd, z0)
        out["S11"][i] = (Ge + Go) / 2
        out["S31"][i] = (Ge - Go) / 2
        out["S21"][i] = (Te + To) / 2
        out["S41"][i] = (Te - To) / 2
    return out


def electrical_lengths(f, eps_e, eps_o, length):
    k0 = 2 * np.pi * f / C0
    return k0 * np.sqrt(eps_e) * length, k0 * np.sqrt(eps_o) * length


def cap_closed_form(f, z0o, eps_e, eps_o, length):
    """C = (theta_e - theta_o) / (2 w Z0o).

    A shunt susceptance B at each end of the odd-mode line adds electrical
    length: matching the pi-network shunt arm, tan(th/2)/Z0o grows by B, so
    d(th) * sec^2(th/2)/(2 Z0o) = B with B = w*2C.  At th = 90 deg,
    sec^2(45) = 2 and it reduces to the expression above.
    """
    th_e, th_o = electrical_lengths(f, eps_e, eps_o, length)
    return (th_e - th_o) / (2 * 2 * np.pi * f * z0o)


def worst_directivity(f, S):
    d = 20 * np.log10(np.abs(S["S31"])) - 20 * np.log10(np.abs(S["S41"]))
    return float(d.min())


if __name__ == "__main__":
    db = lambda x: 20 * np.log10(np.abs(x))
    fb = np.linspace(*BAND, 201)

    k, z0e_req, z0o_req = required_impedances()
    print("1. WHAT A -15 dB COUPLER REQUIRES")
    print(f"   voltage coupling k = 10^({COUPLING_DB}/20)   = {k:.6f}")
    print(f"   Z0e = Z0 sqrt((1+k)/(1-k))       = {z0e_req:.2f} ohm")
    print(f"   Z0o = Z0 sqrt((1-k)/(1+k))       = {z0o_req:.2f} ohm")
    print(f"   check Z0e*Z0o = {z0e_req*z0o_req:.1f} = Z0^2 = {Z0**2:.0f}")

    print("\n2. WHAT TRANSCALC SYNTHESISES FOR THOSE")
    print(f"   W = {TC['W']*1e3:.4f} mm   S = {TC['S']*1e3:.4f} mm   "
          f"L = {TC['L']*1e3:.4f} mm")
    print(f"   eps_eff even = {TC['eps_e']:.5f}   odd = {TC['eps_o']:.5f}"
          f"   (ratio of velocities {np.sqrt(TC['eps_e']/TC['eps_o']):.4f})")
    th_e, th_o = electrical_lengths(F0, TC["eps_e"], TC["eps_o"], TC["L"])
    print(f"   theta_e = {np.degrees(th_e):.2f} deg   "
          f"theta_o = {np.degrees(th_o):.2f} deg   "
          f"mean {np.degrees((th_e+th_o)/2):.2f}   "
          f"split {np.degrees(th_e-th_o):.2f} deg")

    print("\n3. WHAT THAT SPLIT COSTS (no compensation)")
    S = sparams(fb, z0e_req, z0o_req, TC["eps_e"], TC["eps_o"], TC["L"])
    i0 = int(np.argmin(np.abs(fb - F0)))
    print(f"   at 5.8 GHz:  S31 {db(S['S31'][i0]):7.2f}   S41 {db(S['S41'][i0]):7.2f}"
          f"   S21 {db(S['S21'][i0]):7.3f}   S11 {db(S['S11'][i0]):7.2f}")
    print(f"   worst-case directivity in band = {worst_directivity(fb, S):.2f} dB")
    Sh = sparams(fb, z0e_req, z0o_req, TC["eps_e"], TC["eps_e"], TC["L"])
    print(f"   same coupler in a HOMOGENEOUS medium (eps_o := eps_e): "
          f"S41 = {db(Sh['S41'][i0]):.1f} dB  <- Pozar's ideal case")

    print("\n4. THE COMPENSATION CAPACITOR")
    c_cf = cap_closed_form(F0, z0o_req, TC["eps_e"], TC["eps_o"], TC["L"])
    print(f"   closed form (theta_e-theta_o)/(2 w Z0o) = {c_cf*1e15:.2f} fF")
    grid = np.arange(1.0, 120.0, 0.1) * 1e-15
    best = max(grid, key=lambda c: worst_directivity(
        fb, sparams(fb, z0e_req, z0o_req, TC["eps_e"], TC["eps_o"], TC["L"], cap=c)))
    Sb = sparams(fb, z0e_req, z0o_req, TC["eps_e"], TC["eps_o"], TC["L"], cap=best)
    print(f"   numerically optimal                     = {best*1e15:.2f} fF")
    print(f"   with it:  S31 {db(Sb['S31'][i0]):7.2f}   S41 {db(Sb['S41'][i0]):7.2f}"
          f"   S21 {db(Sb['S21'][i0]):7.3f}   S11 {db(Sb['S11'][i0]):7.2f}")
    print(f"   worst-case directivity in band = {worst_directivity(fb, Sb):.2f} dB")
    for tgt in (20.0, 25.0):
        ok = [c for c in grid if worst_directivity(
            fb, sparams(fb, z0e_req, z0o_req, TC["eps_e"], TC["eps_o"],
                        TC["L"], cap=c)) >= tgt]
        if ok:
            print(f"   >= {tgt:.0f} dB for C in {min(ok)*1e15:.1f} .. "
                  f"{max(ok)*1e15:.1f} fF")

#!/usr/bin/env python
"""
FunRad Rev.A -- 5.8 GHz microstrip TX coupler, 3-D EM model in EMerge.

    port 1 ---------------------------------------------------------- port 2
              |<------------- coupled length L_C ----------->|          line A

    port 3 --|__|---------------------------------------------|__|-- port 4
              ^  comb            coupled run                   comb      line B

Line A is straight: port 1 from the PA, port 2 to the antenna.  Line B steps in
with pairs of 90 degree mitred bends (no diagonals anywhere), runs parallel at
S_GAP for L_C, then steps away again: port 3 coupled, port 4 isolated.  An
etched interdigital comb bridges the two lines just outside each end of the
coupled run; it equalises the even- and odd-mode velocities, which is what buys
directivity.

Target: -15 dB coupling, high directivity, good return loss over 5.7-5.9 GHz.

Three commands, in order:

    python coupler_sim.py --no-comb --at-comb   # step 1, uncompensated baseline
    python cap_opt.py results/sparams_opt_nocomb_atcomb.npz    # step 2
    python coupler_sim.py                       # step 3, the final design

--at-comb truncates both lines at the comb plane so the ports sit exactly where
the comb will go.  That matters: a lumped capacitor in a circuit solver lands on
the port reference plane, so ports anywhere else give a capacitance the comb
cannot be sized against.

LINE SPACING IS ELECTRICAL.  Y_COMB sets how far the comb fingers reach.  It
looks like a free routing choice and is not: widening it to 2.2 mm to clear
EMerge's default port face lengthened the fingers from 0.60 to 1.05 mm, and cost
~6 dB of directivity and ~8 dB of return loss.  It stays at 1.3 mm, and the
--at-comb model uses a narrower port face instead (see modal_port).

MESH.  The default profile is the only one to trust.  --fast mis-read
directivity by ~8 dB in both directions on identical geometry; it is a flow
check, nothing more.  Run solves ONE AT A TIME -- two concurrent fine-mesh
sweeps exhaust memory and SuperLU dies, sometimes as a confusing
"gstrf was called with invalid arguments".

CONDUCTOR LOSS IS NOT MODELLED.  Copper walls are PEC, so S21 is a lower bound;
conductor loss (28.7 dB/m) is expected to exceed dielectric loss (16.1 dB/m).
--cu-loss exists but is unusable: EMerge auto-attaches SurfaceImpedance to
conductor walls, which drops the extracted port Z0 by ~5 ohm and corrupts the
S-parameters with it.  Applying SurfaceImpedance by hand instead crashes the
port mode solver.  Treat S21 as optimistic and add the conductor term by hand.

COPPER THICKNESS IS REAL.  Traces are drawn as 35 um thick copper (t_um in the
GEOM preset -> thick_traces in PCBNew), because the widths were synthesised for
copper that has thickness; feeding them to a zero-thickness model moves coupling
by >5 dB.  --geom t0 pairs the flat model with the synthesis it belongs to.

S-parameters are reported at the solver's own port reference, not renormalised
to 50 ohm: the extracted Z0 is not converged (47.9 against 49.6 from two
agreeing quasi-static methods), so renormalising spreads that error over all
sixteen terms.  Each run writes both Touchstone files anyway -- use
_portref.s4p for circuit work, the plain .s4p for interchange.

Other options:
    --geom t35        the analytic starting geometry
    --fast            coarse mesh, few frequencies, flow check only
    --overlap 0.19    override the comb finger overlap directly
    --sweep-comb      0, 2, 3, 4 fingers per side
    --preview         geometry, then mesh; exits without solving
    --no-plot         skip the interactive plot (it blocks the process)
"""
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np

import emerge as em
from emerge.plot import plot_sp

try:   # private path, but the only way to renormalise the port-referenced S
    from emerge._emerge.physics.microwave.microwave_data import renormalise_s
except ImportError:                                     # pragma: no cover
    renormalise_s = None

MM = 1e-3
HERE = Path(__file__).resolve().parent
OUT = HERE / "results"

# --------------------------------------------------------------------------
# Substrate — JLC04161H-7628, L1 over L2
# --------------------------------------------------------------------------
ER = 4.4
TAND = 0.020
H_SUB = 0.2104          # mm, L1-L2 prepreg

# Copper, for the SurfaceImpedance walls.  Without these the thick-copper model
# is a PEC void and has NO conductor loss at all -- and the note puts conductor
# loss (28.7 dB/m) ABOVE dielectric loss (16.1 dB/m), so leaving it out makes
# the through loss look far better than the board will.
SIGMA_CU = 5.8e7        # S/m, annealed copper
CU_ROUGH = 0.6e-6       # m RMS; the note's 28.7 dB/m alpha_c includes 0.6 um

def _sigma_eff(sigma=SIGMA_CU, rough=CU_ROUGH, f=5.8e9):
    """Conductivity that reproduces rough-copper surface resistance at f.

    EMerge attaches SurfaceImpedance to conductor walls automatically (see
    _initialize_bcs) but that path passes no surface_roughness, and the manual
    call that does take it breaks the port mode solver ("no edge with indices
    i,j" out of assemble_bma_matrices).  Rs scales by the Hammerstad-Jensen
    factor K, and Rs ~ 1/sqrt(sigma), so folding K into sigma as sigma/K**2
    gives the same Rs.  K is frequency dependent; over 5.7-5.9 GHz it moves by
    under 1 %, so pinning it at 5.8 GHz is fine for this band.
    """
    delta = math.sqrt(2.0 / (2 * math.pi * f * 4e-7 * math.pi * sigma))
    K = 1.0 + (2.0 / math.pi) * math.atan(1.4 * (rough / delta) ** 2)
    return sigma / K ** 2

# --------------------------------------------------------------------------
# Coupler geometry, mm.  Two presets — see the note in the docstring.
# --------------------------------------------------------------------------
GEOM = {
    # ---- OPTIMISED (default).  Coupled length and W_C from the analytic
    # synthesis; feed width, coupled gap and comb tuned in 3-D for the
    # all-90-degree routing.  Fine mesh, PEC copper, worst case over 5.7-5.9 GHz.
    # Tuning, both knobs measured at fine mesh:
    #   S_GAP   sets coupling.  Tighter buys directivity but overshoots the
    #           -15 dB nameplate; looser gives both away.
    #   ctarget sets the comb size (nominal (2n-1)*overlap*Cm).  Directivity is
    #           a flat plateau in ctarget and falls off hard below it, where the
    #           comb goes under-compensated.  Do NOT tune by putting the
    #           isolation null at 5.8 GHz -- the best in-band worst case sits
    #           with the null well below the band, on the skirt of a broader
    #           peak.  Forcing the null into the band makes it worse.
    # EVERY DIMENSION IS ON A 0.01 mm DRAWING GRID, including the derived ones:
    # clearance = Y_COMB - W_50 = 0.93, so overlap 0.27 puts the comb finger
    # length at exactly 0.60.  Micron-resolution widths were false precision --
    # rounding 0.371 -> 0.37 moves the line by 0.08 ohm and 0.346 -> 0.35 by
    # 0.30 ohm, against a fab etch tolerance near 0.02 mm and a solver
    # uncertainty near 1 ohm.  Measured, the rounded design came out slightly
    # BETTER (D 18.25 vs 17.74 dB, S11 -24.2 vs -23.2), i.e. free.
    # W_C == W_50, so the coupled section is the SAME WIDTH as the feed and there
    # is no width step at either end of it.  That was found by measurement, not
    # by theory: the cross-section's own sqrt(Z0e*Z0o) wants a narrower 0.32,
    # and 0.32 measures 4.8 dB worse once the comb is present.  Uncompensated
    # directivity is actively misleading here -- it prefers 0.32 -- so widths
    # must be judged with the comb in place.
    "opt": dict(W_C=0.37, S_GAP=0.10, L_C=7.39, W_50=0.37, t_um=35,
                fw=0.08, fgap=0.06, ctarget=0.036, overlap=0.27),
    # ---- the pre-rounding geometry, kept so the W_C study in the note can be
    # reproduced; superseded by "opt" above.
    "opt_um": dict(W_C=0.346, S_GAP=0.100, L_C=7.394, W_50=0.371, t_um=35,
                   fw=0.08, fgap=0.06, ctarget=0.036),
    # ---- design-note starting geometry, solved WITH 35 um copper thickness -- t_um selects
    # real extruded copper below (see the NOTE ON COPPER THICKNESS in the
    # docstring; this was checked empirically: on the flat/zero-thickness model
    # this preset's coupling was off by >5 dB from the 2-D reference, not the
    # ~0.35 dB the geometry synthesis alone would suggest).  Kept unchanged as
    # the unmodified starting point for comparison.
    "t35": dict(W_C=0.346, S_GAP=0.155, L_C=7.394, W_50=0.371, t_um=35),
    # equivalent zero-thickness synthesis -- t_um=0 keeps the flat surface-PEC
    # model this preset was actually derived for.
    "t0": dict(W_C=0.382, S_GAP=0.129, L_C=7.168, W_50=0.403, t_um=0),
}

# Line spacing.  Y_COMB sets how far the comb fingers have to reach, so it is an
# ELECTRICAL dimension, not a routing choice: widening it to 2.2 mm lengthens the
# fingers from 0.60 to 1.05 mm, and they stop behaving as a lumped capacitor --
# measured, that costs ~6 dB of directivity and ~8 dB of return loss.  Keep it
# tight.  The consequence is handled in modal_port() below.
FAR = 2.50              # mm, line B centre-to-centre spacing away from the coupler
Y_COMB = 1.30           # mm, centre-to-centre where line B jogs for the comb
JOG = 1.40              # mm, straight run of line B at the comb
FEED = 1.50             # mm, straight feed before the first taper
BEND_DEG = 90.0         # deg, corner angle used for every level change
PORT_W_ATCOMB = 1.10    # mm, port face for --at-comb (see modal_port below)


def bend_pair(w, deg=None):
    """(dx, dy) a level-change bend PAIR consumes before any straight run.

    A .turn() advances the path reference by (w/2)*tan(theta/2) along the old
    heading and the same along the new one -- measured against EMerge for 90,
    60, 45 and 30 degrees, exact in all four.  At 90 deg that is w/2 each way,
    so a pair costs the full line width vertically; at 45 deg it costs 0.29*w.
    That difference is the whole reason shallow corners exist here: the
    symmetric layout's floor on Y_COMB is set by this number.
    """
    t = math.radians(BEND_DEG if deg is None else deg)
    adv = (w / 2.0) * math.tan(t / 2.0)
    return 2 * adv * (1 + math.cos(t)), 2 * adv * math.sin(t)


def level_change(w, rise, deg=None):
    """-> (x consumed, straight length) for a level change of `rise`."""
    t = math.radians(BEND_DEG if deg is None else deg)
    dxt, dyt = bend_pair(w, deg)
    run = (rise - dyt) / math.sin(t)
    return dxt + run * math.cos(t), run
POUR_KEEPOUT = 1.00     # mm (documented; the layouter has no coplanar pour here)
LID_H = 2.50            # mm, shield lid above L1 (see AIR_ABOVE)
AIR_ABOVE = LID_H       # mm of air modelled above the board

# --------------------------------------------------------------------------
# Compensation comb.  C ~= (2n-1) * overlap * Cm(finger width, finger gap).
# Cm from the 2-D solve, bare copper on 0.2104 mm FR-4 (design note table 9d).
# VERIFIED: all six entries match the note's table 9d, and match an independent
# 2-D finite-volume electrostatic solve of the same cross-section to within 1 %.
# They already include the 35 um copper -- a zero-thickness cross-section gives
# 22-26 % less (e.g. 0.10/0.08 -> 18.4 rather than 22.8 pF/m).  This table is
# not the source of the old over-compensation; see C_TARGET_PF below.
# --------------------------------------------------------------------------
CM_PF_PER_M = {          # (finger width mm, finger gap mm) -> pF/m
    (0.10, 0.06): 27.9, (0.10, 0.08): 22.8, (0.10, 0.10): 19.1,
    (0.15, 0.08): 24.2, (0.15, 0.10): 20.4, (0.08, 0.06): 26.9,
}
FINGER_W = 0.10         # mm
FINGER_GAP = 0.08       # mm
C_TARGET_PF = 0.025     # NOMINAL facing-edge estimate for THIS layout, not the
                        # note's 0.057 pF.  Both are right; they count different
                        # things.  The note (§8) derives C = (te-to)/(2*w*Z0o)
                        # = 0.0586 pF, one capacitor at each end, and sizes the
                        # comb as facing edge = (2n-1)*finger_length -- valid for
                        # its fully-interleaved comb in a 1.00 x 0.50 mm
                        # footprint.  Here the fingers only partly interleave
                        # across a Y_COMB-W_C = 0.954 mm clearance, so the facing
                        # edge is (2n-1)*overlap and everything else (tip-to-bus,
                        # the non-overlapping finger length, bus-to-bus across
                        # the jog) is uncounted parasitic -- which in this
                        # geometry is not the note's 10-25 % but about +120 %.
                        # Measured in 3-D, directivity peaks at this nominal
                        # ~0.025 pF: overlap 0.20-0.25 mm with the 0.10/0.08
                        # fingers, 0.186 mm with the default preset's finer
                        # 0.08/0.06 pair.  Either way it is the note's 0.057 pF
                        # once the parasitics above are counted.
                        # Sanity check on that factor: the old 0.045 nominal
                        # built ~0.054 (see the finger-tip bug in build()), i.e.
                        # ~0.12 pF real -- and the note's Fig 6 says past 0.11 pF
                        # compensation is worse than none, which is exactly what
                        # the 3-D model showed (D = 2.9 dB vs 6.8 dB bare).

# --------------------------------------------------------------------------
# Frequency and mesh
# --------------------------------------------------------------------------
F_LO, F_HI = 4.5e9, 7.5e9
BAND = (5.7e9, 5.9e9)
F0 = 5.8e9

MESH = dict(
    normal=dict(nfreq=25, resolution=0.15, trace=0.30, comb=0.05, port=0.20),
    fast=dict(nfreq=9, resolution=0.30, trace=0.60, comb=0.12, port=0.40),
)


# ==========================================================================
# geometry helpers — every segment is one straight path; merge=True unions them
# ==========================================================================
OVL = 0.04              # mm of overlap at each joint so the union stays watertight


class Layout:
    """Thin wrapper so all path building goes through one place.

    Used only for the comb fingers: short stubs that butt into a wide line
    rather than continue it, where seg()'s OVL-overlap-and-union trick is
    fine (there's no heading change to mitre). The two main lines are each
    one continuous StripPath built with .new()/.straight()/.turn()/.store().
    """

    def __init__(self, layouter, z):
        self.lo = layouter
        self.z = z
        self.n = 0

    def seg(self, x, y, w, dx, dy, length,
            tag_start=None, tag_end=None, back=True, fwd=True):
        """One straight segment from (x, y) in direction (dx, dy).

        `back` / `fwd` extend the segment by OVL at the near / far end so that
        neighbouring segments union cleanly.  Turn them off at the board edges
        where a port sits, so the port face lands exactly on the boundary.
        """
        norm = math.hypot(dx, dy)
        dx, dy = dx / norm, dy / norm
        b = OVL if back else 0.0
        f = OVL if fwd else 0.0
        p = self.lo.new(x - dx * b, y - dy * b, w, (dx, dy), z=self.z)
        if tag_start:
            p = p.store(tag_start)
        p = p.straight(length + b + f, w)
        if tag_end:
            p = p.store(tag_end)
        self.n += 1
        return p


CORNER = "miter"        # 90 deg bends are mitred, not square
DSRATIO = 0.5           # cut plane starts exactly at the inner corner;
                        # 0.7 (EMerge's default) cuts back into the straights
XY_TOL = 3e-4           # mm = 0.3 um; above OCC's ~0.1 um merge tolerance,
                        # below the smallest legitimate feature (12.5 um step)


def _install_polygon_dedupe():
    """Drop polygon points closer together than XY_TOL before they reach gmsh.

    compile_paths(fragment=True) projects the other traces' mitre vertices onto
    each polygon as extra cut points, and it can land one ~18 nm from a vertex
    that is already there.  That is below OCC's merge tolerance, so both points
    come back as the same tag and gmsh aborts with "Could not create line".
    Measured on this layout: minimum segment 12.5 um before fragment(), 0.018 um
    after.  Turning fragmentation off avoids the crash but then gmsh cannot mesh
    the result at all (it spins indefinitely), so instead keep fragmentation and
    filter its output here.
    """
    cls = em.geo.PCBNew
    if getattr(cls, "_dedupe_installed", False):
        return
    original = cls._gen_poly

    def _gen_poly(self, xys, z, name=None):
        out = []
        for x, y in xys:
            if out and math.hypot(x - out[-1][0], y - out[-1][1]) < XY_TOL:
                continue
            out.append((x, y))
        while len(out) > 3 and math.hypot(out[0][0] - out[-1][0],
                                         out[0][1] - out[-1][1]) < XY_TOL:
            out.pop()
        return original(self, out, z, name)

    cls._gen_poly = _gen_poly
    cls._dedupe_installed = True


def finger_length(y_comb, w_line, overlap):
    """Finger length so two opposing fingers overlap by `overlap` in y.

    `w_line` is the width of the two lines AT THE COMB (the jog), which is
    W_50 -- the coupled-section width W_C only applies from x_start onward.
    """
    clearance = y_comb - w_line       # line A lower edge to line B upper edge
    return (clearance + overlap) / 2.0, clearance


def build(layouter, z, g, n_fingers, comb=True, overlap_mm=None,
          at_comb=False, symmetric=False):
    """Draw both lines and the two combs.  Returns the four port path tags.

    `overlap_mm` overrides the Cm-synthesised finger overlap with an explicit
    value, so the comb can be swept on its physical variable directly.  A preset
    may also carry an `overlap` key, which does the same thing and is how the
    shipped design keeps its finger length on the 0.01 mm grid; an explicit
    `overlap_mm` still wins over it.

    `symmetric` mirrors the two lines about y = 0 instead of running line A
    dead straight.  The compensation theory is an even/odd decomposition, which
    assumes the structure IS mirror-symmetric about the plane between the lines;
    the default layout violates that everywhere outside the coupled run, so the
    "a capacitor C looks like 2C to a virtual ground" step is only approximate
    and the asymmetric transitions can convert even into odd.  See the symmetry
    study note.

    `at_comb` truncates both lines at the comb plane and puts the four ports
    there, so the model is the coupler as seen FROM the comb.  A capacitor
    added across those ports in a circuit solver is then exactly the comb, with
    no intervening feed line -- which is what makes the step 2 capacitance a
    real target for step 3 rather than an equivalent end value.
    """
    L = Layout(layouter, z)
    W_C, S_GAP, L_C, W_50 = g["W_C"], g["S_GAP"], g["L_C"], g["W_50"]

    ctc = W_C + S_GAP                       # coupled centre-to-centre
    if symmetric:
        # each line travels HALF the level change, because both of them move
        rise1 = (FAR - Y_COMB) / 2.0
        rise2 = (Y_COMB - ctc) / 2.0
        _, dy_pair = bend_pair(W_50)
        if rise2 < dy_pair:
            raise SystemExit(
                f"symmetric layout at {BEND_DEG:g} deg corners needs Y_COMB >= "
                f"{ctc + 2 * dy_pair:.3f} mm (have {Y_COMB}); shallower corners "
                f"lower that floor")
        if rise1 < dy_pair:
            raise SystemExit(
                f"symmetric layout at {BEND_DEG:g} deg corners needs FAR >= "
                f"{Y_COMB + 2 * dy_pair:.3f} mm (have {FAR})")
    else:
        rise1 = FAR - Y_COMB                # feed level -> jog level
        rise2 = Y_COMB - ctc                # jog level -> coupled level
    # Every .turn() advances the path reference by (w/2) along the old heading
    # and (w/2) along the new one -- measured, exact for all four cases.  So a
    # 90 deg step costs W_50 of x for its two corners, and a straight that has
    # to climb `rise` between two corners is `rise - W_50` long.
    a = W_50 / 2.0
    if symmetric:
        dx1, run1 = level_change(W_50, rise1)
        dx2, run2 = level_change(W_50, rise2)
        x_lead = FEED + dx1                 # port -> start of the jog
        x_start = x_lead + JOG + dx2        # x where the coupled run begins
    else:
        run1 = rise1 - W_50
        run2 = rise2 - W_50
        x_lead = FEED + W_50
        x_start = FEED + JOG + 2 * W_50     # x where the coupled run begins
    total = 2 * x_start + L_C

    # comb plane: centre of the jog, where the interdigital fingers sit
    x_cL = x_lead + JOG / 2.0
    x_cR = total - x_cL

    if at_comb:
        # Truncated model: both lines start and end on the comb plane, so the
        # ports ARE the comb reference planes.  Same coupled section, same
        # bends, just without the outer feeds.  The comb itself is never drawn
        # here -- the whole point is to leave its place empty so step 2 can put
        # a lumped capacitor exactly there.
        if comb:
            raise ValueError("--at-comb is the uncompensated baseline for "
                             "step 2; combine it with --no-comb")
        (layouter.new(x_cL, 0.0, W_50, (1.0, 0.0), z=z)
                 .store("p1_end")
                 .straight(x_start - x_cL, W_50)
                 .straight(L_C, W_C)
                 .straight(x_cR - x_start - L_C, W_50)
                 .store("p2_end"))
        L.n += 1
        yJ, yC = -Y_COMB, -ctc
        lineB = (layouter.new(x_cL, yJ, W_50, (1.0, 0.0), z=z)
                 .store("p3_end")
                 .straight(JOG / 2.0))
        lineB.turn(-90, corner_type=CORNER, dsratio=DSRATIO)
        lineB.straight(rise2 - W_50)
        lineB.turn(90, corner_type=CORNER, dsratio=DSRATIO)
        lineB.straight(L_C, W_C)
        lineB.turn(90, width=W_50, corner_type=CORNER, dsratio=DSRATIO)
        lineB.straight(rise2 - W_50)
        lineB.turn(-90, corner_type=CORNER, dsratio=DSRATIO)
        lineB.straight(JOG / 2.0)
        lineB.store("p4_end")
        L.n += 1
        return dict(total_x=x_cR - x_cL, x_start=x_start, ctc=ctc,
                    segments=L.n, comb=None, at_comb=True,
                    comb_planes=(x_cL, x_cR))

    if symmetric:
        # Both lines fan out from the coupled run by the same amount, so the
        # structure is a mirror image about y = 0 -- exactly the plane the
        # even/odd decomposition assumes.  sgn = -1 fans downward, +1 upward.
        B = BEND_DEG
        # EMerge sizes the chamfer as a fraction of the CORNER DIAGONAL, which
        # blows up at shallow angles: at 45 deg with dsratio 0.5 the cut is
        # 0.370 mm and the trace edge folds back on itself by a full line width.
        # Measured -- miter and champher both do it, and only dsratio ~0.15
        # gets the fold under a micron.  Square corners are exact at any angle,
        # so anything but a right angle uses them.
        _ctype = CORNER if abs(B - 90.0) < 1e-9 else "square"
        # A level change whose straight run is a few microns is NOT the corner
        # angle it claims to be: the two chamfers merge into one facet.  At
        # Y_COMB 1.24 the 90 deg pair leaves 5 um of straight and the transition
        # measures 45.0 deg.  Refuse it rather than mislabel the geometry.
        _min_run = 0.05
        for _nm, _r in (("rise1", run1), ("rise2", run2)):
            if _r < _min_run:
                raise SystemExit(
                    f"degenerate {B:g} deg level change: {_nm} leaves only "
                    f"{_r*1e3:.1f} um of straight between the two corners, so "
                    f"they merge into a single facet and the corner angle is "
                    f"not what it says.  Raise Y_COMB or use a shallower --bend.")

        def _step(ln, d, run, width=None):
            """One level change: turn, diagonal (or vertical at 90), turn back."""
            kw = dict(corner_type=_ctype, dsratio=DSRATIO)
            ln.turn(B * d, **({**kw, "width": width} if width else kw))
            ln.straight(run)
            ln.turn(-B * d, **kw)

        def _run(sgn, tag_in, tag_out):
            ln = (layouter.new(0.0, sgn * FAR / 2.0, W_50, (1.0, 0.0), z=z)
                  .store(tag_in).straight(FEED))
            _step(ln, sgn, run1)                   # feed level -> jog level
            ln.straight(JOG)                       # the comb sits here
            _step(ln, sgn, run2)                   # jog level -> coupled level
            ln.straight(L_C, W_C)                  # the coupled run
            _step(ln, -sgn, run2, width=W_50)      # and back out, mirrored
            ln.straight(JOG)
            _step(ln, -sgn, run1)
            ln.straight(FEED)
            ln.store(tag_out)

        _run(+1.0, "p1_end", "p2_end")      # line A: starts high, fans down
        _run(-1.0, "p3_end", "p4_end")      # line B: starts low, fans up
        L.n += 2
    else:
        # ---- line A: one continuous path, ports 1 and 2 at its two ends.
        # This is the exact pattern from the EMerge stepped-impedance-filter example:
        # store() before a straight marks the path start, store() after marks the end.
        (layouter.new(0.0, 0.0, W_50, (1.0, 0.0), z=z)
                 .store("p1_end")
                 .straight(x_start, W_50)
                 .straight(L_C, W_C)
                 .straight(x_start, W_50)
                 .store("p2_end"))
        L.n += 1

        # ---- line B: feed -> step up -> jog (comb) -> step up -> coupled -> mirror.
        # Every level change is a pair of 90 deg mitred bends; no diagonals.  Line B
        # is W_50 everywhere outside the coupled run and steps to W_C at x_start,
        # exactly where line A does.  Both corners flanking the coupled run are
        # taken at W_50 so the two ends of it stay symmetric.
        yF, yJ, yC = -FAR, -Y_COMB, -ctc
        lineB = (layouter.new(0.0, yF, W_50, (1.0, 0.0), z=z)
                 .store("p3_end")
                 .straight(FEED))
        lineB.turn(-90, corner_type=CORNER, dsratio=DSRATIO)      # head +y
        lineB.straight(rise1 - W_50)
        lineB.turn(90, corner_type=CORNER, dsratio=DSRATIO)       # head +x, at yJ
        lineB.straight(JOG)                                       # the comb sits here
        lineB.turn(-90, corner_type=CORNER, dsratio=DSRATIO)      # head +y
        lineB.straight(rise2 - W_50)
        lineB.turn(90, corner_type=CORNER, dsratio=DSRATIO)       # head +x, at yC
        lineB.straight(L_C, W_C)                                  # the coupled run
        lineB.turn(90, width=W_50, corner_type=CORNER, dsratio=DSRATIO)   # head -y
        lineB.straight(rise2 - W_50)
        lineB.turn(-90, corner_type=CORNER, dsratio=DSRATIO)      # head +x, at yJ
        lineB.straight(JOG)
        lineB.turn(90, corner_type=CORNER, dsratio=DSRATIO)       # head -y
        lineB.straight(rise1 - W_50)
        lineB.turn(-90, corner_type=CORNER, dsratio=DSRATIO)      # head +x, at yF
        lineB.straight(FEED)
        lineB.store("p4_end")
        L.n += 1

        if overlap_mm is None:
            overlap_mm = g.get("overlap")   # preset-supplied, grid-aligned

    # ---- combs, centred on each jog
    comb_info = None
    if comb and n_fingers > 0:
        # finger geometry travels with the preset when it defines one
        fw = g.get("fw", FINGER_W)
        fgap = g.get("fgap", FINGER_GAP)
        ctgt = g.get("ctarget", C_TARGET_PF)
        cm = CM_PF_PER_M.get((fw, fgap))
        if cm is None:
            raise SystemExit(f"no Cm datum for finger {fw}/{fgap} mm")
        if overlap_mm is not None:
            overlap = overlap_mm
        else:
            overlap = ctgt / ((2 * n_fingers - 1) * cm) * 1e3  # pF / (pF/m) -> m -> mm
        f_len, clearance = finger_length(Y_COMB, W_50, overlap)
        # A finger reaches f_len from its own bus across a `clearance` gap, so
        # its tip touches the opposite bus once f_len >= clearance (equivalently
        # overlap >= clearance).  The old guard ANDed this with
        # `2*f_len > clearance + overlap`, which is false by construction
        # (2*f_len == clearance + overlap), so it never fired -- large overlaps
        # silently shorted the two lines instead of erroring out.
        if f_len >= clearance - OVL:
            raise SystemExit(
                f"fingers would short the two lines (f_len {f_len:.3f} mm vs "
                f"clearance {clearance:.3f} mm) — reduce overlap or raise Y_COMB")
        span = 2 * n_fingers * fw + (2 * n_fingers - 1) * fgap
        if span > JOG:
            raise SystemExit(f"comb span {span:.3f} mm does not fit in JOG {JOG} mm")

        jog_centres = (x_cL, x_cR)
        # the comb sits at the jog, upstream of x_start, where BOTH lines
        # are still W_50 -- keying these off W_C put every finger root
        # 12.5 um inside its own trace edge
        if symmetric:
            y_a = Y_COMB / 2.0 - W_50 / 2.0    # line A lower edge
            y_b = -Y_COMB / 2.0 + W_50 / 2.0   # line B upper edge
        else:
            y_a = -W_50 / 2.0                  # line A lower edge
            y_b = -Y_COMB + W_50 / 2.0         # line B upper edge
        for xc in jog_centres:
            x0 = xc - span / 2.0 + fw / 2.0
            for i in range(2 * n_fingers):
                xf = x0 + i * (fw + fgap)
                # fwd=False: only the root needs the OVL overlap to union into
                # its bus.  Extending the free tip too made every finger 0.04 mm
                # long at each end, so the real facing overlap was `overlap`
                # + 0.08 mm (a ~20 % stronger comb than synthesised) and the
                # short-circuit guard below was 0.04 mm optimistic -- large
                # overlaps actually shorted the two lines together.
                if i % 2 == 0:                 # finger hanging down from line A
                    L.seg(xf, y_a, fw, 0.0, -1.0, f_len, fwd=False)
                else:                          # finger reaching up from line B
                    L.seg(xf, y_b, fw, 0.0, 1.0, f_len, fwd=False)
        comb_info = dict(fingers_per_side=n_fingers, overlap_mm=round(overlap, 4),
                         finger_len_mm=round(f_len, 4), span_mm=round(span, 3),
                         C_target_pF=ctgt, Cm_pF_per_m=cm, fw_mm=fw, fgap_mm=fgap,
                         facing_edge_mm=round((2 * n_fingers - 1) * overlap, 3))

    return dict(total_x=total, x_start=x_start, ctc=ctc,
                segments=L.n, comb=comb_info)


# ==========================================================================
def simulate(args):
    g = GEOM[args.geom]
    prof = MESH["fast" if args.fast else "normal"]
    # Y_COMB and JOG live as module constants, so override them globally before
    # build() reads them.  Investigation knobs -- see the comb study note.
    global Y_COMB, JOG, BEND_DEG
    if getattr(args, "bend", None) is not None:
        BEND_DEG = args.bend
    if getattr(args, "ycomb", None) is not None:
        Y_COMB = args.ycomb
    if getattr(args, "jog", None) is not None:
        JOG = args.jog

    # CLI overrides on the chosen preset, so a tuning point needs no code edit.
    if getattr(args, "gap", None) is not None:
        g["S_GAP"] = args.gap
    if getattr(args, "wc", None) is not None:
        g["W_C"] = args.wc
    if getattr(args, "ctarget", None) is not None:
        g["ctarget"] = args.ctarget
    tag = f"{args.geom}_{'comb%d' % args.fingers if args.fingers else 'nocomb'}"
    if getattr(args, "at_comb", False):
        tag += "_atcomb"
    if getattr(args, "symmetric", False):
        tag += "_sym"
    # --overlap has to be in the tag too, or a comb sweep silently overwrites
    # the shipped design's own result files.
    if any(getattr(args, a, None) is not None
           for a in ("gap", "ctarget", "wc", "overlap", "ycomb", "jog")):
        ov = getattr(args, "overlap", None) or g.get("overlap", 0)
        tag += f"_w{g['W_C']:g}s{g['S_GAP']:g}o{ov:g}"
        if getattr(args, "ycomb", None) is not None:
            tag += f"y{Y_COMB:g}"
        if getattr(args, "jog", None) is not None:
            tag += f"j{JOG:g}"
        if getattr(args, "bend", None) is not None:
            tag += f"b{BEND_DEG:g}"
    OUT.mkdir(exist_ok=True)

    _install_polygon_dedupe()
    pcbmat = em.Material(er=ER, tand=TAND, color="#217627")
    m = em.Simulation(f"FunRad_coupler_{tag}")

    # Real 3-D copper when the preset says so (t35): thick_traces=True extrudes
    # every trace (and .plane()'s ground) into a solid instead of a flat sheet,
    # which is what t35's dimensions were actually synthesized for -- checked
    # empirically (see GEOM's comment) that skipping this costs >5 dB of
    # coupling accuracy, not the ~0.35 dB a first guess would suggest.
    # trace_thickness is in meters and is NOT scaled by `unit` (verified against
    # pcb.py's _gen_poly, unlike every other PCBNew dimension here).
    thick = g["t_um"] > 0
    pcb_kw = dict(thick_traces=True, trace_thickness=g["t_um"] * 1e-6) if thick else {}

    # PCBNew(thickness, unit, material, layers).  layers=2 -> ground on z(0),
    # traces on z(1).  If your build indexes the other way round, flip TRACE_LAYER.
    # (em.geo.PCB is the deprecated 1-indexed alias -- its z(1) resolves to z(0)
    # here, i.e. the *ground* plane, which silently drew the signal trace on top
    # of where the ground belongs and left no ground conductor at all.)
    # trace_material drives conductor loss: a finite-conductivity, non-"PEC"
    # material makes EMerge attach SurfaceImpedance to the copper walls.
    # Default is PEC (lossless) copper.  --cu-loss switches the walls to a
    # finite surface impedance, but see the warning on that flag: in EMerge
    # 2.8.9 it also drags the extracted port Z0 down by ~5 ohm, which is not
    # physical for sigma ~ 3e7 and corrupts every S-parameter with it.
    cu = (em.Material(cond=_sigma_eff(), name="copper") if args.cu_loss
          else em.Material(cond=SIGMA_CU, name="PEC"))
    layouter = em.geo.PCBNew(H_SUB, unit=MM, material=pcbmat, layers=args.layers,
                             trace_material=cu, **pcb_kw)
    z_trace = layouter.z(args.trace_layer)

    info = build(layouter, z_trace, g, args.fingers, comb=args.fingers > 0,
                 overlap_mm=getattr(args, "overlap", None),
                 at_comb=getattr(args, "at_comb", False),
                 symmetric=getattr(args, "symmetric", False))
    print(json.dumps(info, indent=2))

    # height=AIR_ABOVE so the port face spans ground -> substrate -> the modelled
    # air above the trace; a microstrip quasi-TEM mode needs that air field to
    # exist, and modal_port's `height` is the absolute z of the port's top edge.
    # EMerge sizes a port face at 5 x the line width (1.855 mm here).  That is
    # fine on the board edges, where the lines are FAR = 2.5 mm apart, but the
    # --at-comb model puts ports on the comb plane where they are Y_COMB = 1.3
    # apart -- the default faces would OVERLAP, and the mode solver returns
    # garbage (51.8 ohm on line A) rather than raising.  So that model gets a
    # narrower face automatically; nothing to pass on the command line.
    pkw = dict(height=AIR_ABOVE)
    if getattr(args, "at_comb", False):
        pkw["width"] = PORT_W_ATCOMB        # layouter units (mm), not metres
    p1 = layouter.modal_port(layouter.load("p1_end"), **pkw)
    p2 = layouter.modal_port(layouter.load("p2_end"), **pkw)
    p3 = layouter.modal_port(layouter.load("p3_end"), **pkw)
    p4 = layouter.modal_port(layouter.load("p4_end"), **pkw)

    polies = layouter.compile_paths(merge=True)
    if thick and args.cu_loss:
        # the thick-trace branch of _gen_poly never sets a material,
        # so the extruded copper would otherwise default to PEC walls
        polies.set_material(cu)
    layouter.determine_bounds(leftmargin=0, rightmargin=0,
                              topmargin=POUR_KEEPOUT + 1.0,
                              bottommargin=POUR_KEEPOUT + 1.0)
    pcb = layouter.generate_pcb(True, merge=True)

    # Full-sheet ground plane at the bottom of the substrate.  Without this the
    # port cross-section only ever touches one conductor (the signal trace), so
    # the TEM mode solver has no second conductor island to reference the
    # voltage/current to and reports no modes at all.
    gnd = layouter.plane(layouter.z(0), name="GND")

    # Air region above the board (the shield lid cavity), sized to the PCB's
    # own footprint (matches the margins from determine_bounds()).
    airbox = layouter.generate_air(AIR_ABOVE)

    m.commit_geometry()
    m.mw.set_resolution(prof["resolution"])
    m.mw.set_frequency_range(F_LO, F_HI, prof["nfreq"])

    m.mesher.set_boundary_size(polies, prof["trace"] * MM, growth_rate=1.3)
    for p in (p1, p2, p3, p4):
        m.mesher.set_face_size(p, prof["port"] * MM)
    m.generate_mesh()

    if args.preview:
        print("--preview: showing geometry, then mesh. Close each window to proceed.")
        m.view(opacity=0.4)
        m.view(plot_mesh=True, volume_mesh=True)
        return None

    port1 = m.mw.bc.ModalPort(p1, 1, modetype="TEM")
    port2 = m.mw.bc.ModalPort(p2, 2, modetype="TEM")
    port3 = m.mw.bc.ModalPort(p3, 3, modetype="TEM")
    port4 = m.mw.bc.ModalPort(p4, 4, modetype="TEM")
    if thick:
        # polies/gnd are solid GeoVolumes (dim 3).  Conductor loss is driven by
        # the MATERIAL on those volumes, not by a BC here: _initialize_bcs()
        # attaches SurfaceImpedance to the boundary of every 3-D body whose
        # material has cond > mw_3d_surfimplim and whose name is not "PEC".
        # With no material (or a PEC one) the walls default to PEC and the
        # copper is lossless.  See the trace_material passed to PCBNew above.
        pec = pec_gnd = None
    else:
        pec = m.mw.bc.PEC(polies)
        pec_gnd = m.mw.bc.PEC(gnd)

    t0 = time.time()
    sol = m.mw.run_sweep(parallel=not args.serial, n_workers=args.jobs,
                         frequency_groups=args.groups)
    print(f"solve: {time.time() - t0:.1f} s")

    report(sol, tag, args)
    if args.show:
        m.display.add_object(airbox, opacity=0.03)
        m.display.add_object(pcb, opacity=0.10)
        m.display.add_object(polies, opacity=0.60)
        m.display.show()
    return sol


def report(sol, tag, args):
    grid = sol.scalar.grid
    f = np.linspace(F_LO, F_HI, 601)
    Sp = np.zeros((f.size, 4, 4), dtype=complex)      # port-referenced
    for a in range(4):
        for b in range(4):
            Sp[:, a, b] = grid.model_S(a + 1, b + 1, f, _warn=False)

    # The solver references S to each port's own modal impedance, which for a
    # microstrip feed is NOT 50 ohm -- so the raw S11 silently hides an error
    # in the feed width.  Renormalise to the 50 ohm system the board actually
    # sees: that is the return loss that matters, and on the t35 geometry the
    # two differ by more than 20 dB (45.7 ohm line -> S11 -18.9 raw, -15.2 re 50).
    fs = np.asarray(grid.freq)
    Z0 = np.real(np.asarray(grid.Z0))
    if Z0.ndim == 2:
        Z0i = np.vstack([np.interp(f, fs, Z0[:, k])
                         for k in range(Z0.shape[1])]).T
    else:
        Z0i = Z0
    S50 = renormalise_s(Sp, Z0i, 50.0) if renormalise_s is not None else Sp

    S11, S21, S31, S41 = Sp[:, 0, 0], Sp[:, 1, 0], Sp[:, 2, 0], Sp[:, 3, 0]
    S11_50 = S50[:, 0, 0]
    db = lambda x: 20 * np.log10(np.abs(x) + 1e-30)

    z0m = float(np.mean(Z0i))
    print(f"\n  port Z0 = {z0m:.1f} ohm"
          f"{'' if abs(z0m - 50) < 1.0 else '   <-- not 50; S11@50 is the real one'}")
    print(f"\n  f[GHz]    S11   S11@50      S31      S21      S41  directivity")
    for fx in (5.0, 5.7, 5.8, 5.9, 6.5):
        i = int(np.argmin(np.abs(f - fx * 1e9)))
        print(f"  {fx:5.2f} {db(S11)[i]:8.2f} {db(S11_50)[i]:7.2f} "
              f"{db(S31)[i]:8.2f} {db(S21)[i]:8.3f} "
              f"{db(S41)[i]:8.2f} {db(S31)[i] - db(S41)[i]:9.1f}")

    inb = (f >= BAND[0]) & (f <= BAND[1])
    d = (db(S31) - db(S41))[inb]
    print(f"\n  in band {BAND[0]/1e9:.1f}-{BAND[1]/1e9:.1f} GHz:"
          f"  coupling {db(S31)[inb].min():.2f} .. {db(S31)[inb].max():.2f} dB"
          f" | through {db(S21)[inb].min():.3f} dB"
          f" | return loss {-db(S11)[inb].max():.1f} dB"
          f" ({-db(S11_50)[inb].max():.1f} re 50)"
          f" | directivity {d.min():.1f} dB (worst)")
    print("  2-D quasi-static reference, uncompensated: "
          "-14.99 / -0.513 / -21.69 / -36.5, D 6.7 dB")

    np.savez(OUT / f"sparams_{tag}.npz", f=f, S11=S11, S21=S21, S31=S31, S41=S41,
             S11_50=S11_50, Smat=Sp, Smat50=S50, Z0=Z0i)
    # Two Touchstone files, because the reference impedance has to match whatever
    # the consumer assumes.  A 4-port Touchstone is all 16 terms, four rows per
    # frequency, not just the first column.
    def _write_s4p(path, Smat, rz, note):
        with open(path, "w") as fh:
            fh.write(f"! FunRad TX coupler, EMerge -- {note}\n")
            fh.write(f"# GHz S MA R {rz:.4g}\n")
            for i, fi in enumerate(f):
                for r in range(4):
                    pre = f"{fi/1e9:.6f} " if r == 0 else " " * 9
                    fh.write(pre + " ".join(
                        f"{abs(Smat[i, r, c]):.6g} "
                        f"{math.degrees(np.angle(Smat[i, r, c])):.4f}"
                        for c in range(4)) + "\n")

    _write_s4p(OUT / f"sparams_{tag}.s4p", S50, 50.0, "renormalised to 50 ohm")
    # ...and the port-referenced one, which is what cap_opt.py works on.  Drop
    # THIS file into QUCS if the circuit-level result has to agree with step 2;
    # the 50 ohm file will not reproduce it.  Touchstone carries a single real R,
    # so the four ports go in at their mean -- they differ by under 0.05 % here.
    _write_s4p(OUT / f"sparams_{tag}_portref.s4p", Sp, z0m,
               f"port reference {z0m:.2f} ohm (ports span "
               f"{np.min(Z0i.real):.2f}-{np.max(Z0i.real):.2f})")
    print(f"  written: {OUT/f'sparams_{tag}.npz'}, .s4p (50 ohm) "
          f"and _portref.s4p ({z0m:.1f} ohm)")

    if not args.no_plot:
        plot_sp(f / 1e9, [S11, S21, S31, S41],
                labels=["S11", "S21 through", "S31 coupled", "S41 isolated"],
                dblim=[-45, 2])


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--geom", choices=list(GEOM), default="opt")
    ap.add_argument("--fingers", type=int, default=3,
                    help="interdigital fingers per side, 0 = no comb")
    ap.add_argument("--no-comb", action="store_true")
    ap.add_argument("--bend", type=float, default=None, metavar="DEG",
                    help="corner angle for every level change (default 90). "
                         "Shallower corners consume far less vertical travel, "
                         "which is what sets the symmetric layout's Y_COMB floor")
    ap.add_argument("--symmetric", action="store_true",
                    help="mirror both lines about y=0 instead of running line A "
                         "straight, so the structure matches the even/odd "
                         "symmetry the compensation theory assumes")
    ap.add_argument("--at-comb", action="store_true",
                    help="truncate the lines at the comb plane and put the "
                         "ports there (step 1 de-embedded model)")
    ap.add_argument("--gap", type=float, default=None, metavar="MM",
                    help="override the coupled gap S_GAP")
    ap.add_argument("--wc", type=float, default=None, metavar="MM",
                    help="override the coupled-section width W_C")
    ap.add_argument("--ycomb", type=float, default=None, metavar="MM",
                    help="override Y_COMB, the line spacing at the comb.  At a "
                         "fixed --overlap this changes ONLY the finger length "
                         "(hence the comb's series inductance), not its "
                         "capacitance -- which makes it a clean experiment.")
    ap.add_argument("--jog", type=float, default=None, metavar="MM",
                    help="override JOG, the straight run carrying the comb.  "
                         "Shortening it moves the comb closer to the coupled "
                         "section: offset = JOG/2 + W_50.")
    ap.add_argument("--ctarget", type=float, default=None, metavar="PF",
                    help="override the nominal comb capacitance")
    ap.add_argument("--overlap", type=float, default=None,
                    help="finger overlap in mm, overriding the CM_PF_PER_M "
                         "synthesis (the physical tuning knob)")
    ap.add_argument("--sweep-comb", action="store_true",
                    help="run 0, 2, 3 and 4 fingers per side in turn")
    ap.add_argument("--fast", action="store_true", help="coarse mesh, few points")
    ap.add_argument("--layers", type=int, default=2)
    ap.add_argument("--trace-layer", type=int, default=1)
    # 2, not 4: the fine-mesh comb model peaks near 20 GB with four concurrent
    # SuperLU factorisations, which thrashes on a 32 GB machine.  Raise it only
    # if you know the headroom is there.
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--groups", type=int, default=8)
    ap.add_argument("--serial", action="store_true")
    ap.add_argument("--show", action="store_true",
                    help="open the 3-D viewer after solving")
    ap.add_argument("--preview", action="store_true",
                    help="show geometry then mesh (two windows) right after "
                         "meshing, and exit without solving")
    ap.add_argument("--cu-loss", action="store_true",
                    help="finite-conductivity copper walls. BROKEN in EMerge "
                         "2.8.9: it also shifts the extracted port Z0 by ~5 ohm "
                         "(41.6 vs 46.5 lossless, 2-D truth 49.6), so the "
                         "S-parameters come out corrupted. Default is PEC.")
    ap.add_argument("--no-plot", action="store_true")
    args = ap.parse_args()
    if args.no_comb:
        args.fingers = 0

    if args.sweep_comb:
        for n in (0, 2, 3, 4):
            print(f"\n{'='*70}\n  fingers per side: {n}\n{'='*70}")
            args.fingers = n
            simulate(args)
    else:
        simulate(args)


if __name__ == "__main__":
    main()

"""Copper paths for the 54 coupler experiments and four straight-line controls.

All dimensions here are millimetres. No materials, mesh or solver calls belong
here. Geometry is driven by the saved configuration, without mutable globals.
"""
import math
import emerge as em

FAR = 2.50             # Centre spacing of the two feed lines.
FEED = 1.50            # Straight feed length at each end.
OVL = 0.04             # Finger-root overlap into its own conductor.
CORNER = "miter"       # Used only for the 90-degree variants.
DSRATIO = 0.5
XY_TOL = 3e-4          # Polygon deduplication tolerance, mm.

def bend_pair(w, deg):
    """(dx, dy) a level-change bend PAIR consumes before any straight run.

    A .turn() advances the path reference by (w/2)*tan(theta/2) along the old
    heading and the same along the new one -- measured against EMerge for 90,
    60, 45 and 30 degrees, exact in all four.  At 90 deg that is w/2 each way,
    so a pair costs the full line width vertically; at 45 deg it costs 0.29*w.
    That difference is the whole reason shallow corners exist here: the
    symmetric layout's floor on Y_COMB is set by this number.
    """
    t = math.radians(deg)
    adv = (w / 2.0) * math.tan(t / 2.0)
    return 2 * adv * (1 + math.cos(t)), 2 * adv * math.sin(t)

def level_change(w, rise, deg):
    """-> (x consumed, straight length) for a level change of `rise`."""
    t = math.radians(deg)
    dxt, dyt = bend_pair(w, deg)
    run = (rise - dyt) / math.sin(t)
    return dxt + run * math.cos(t), run

class FingerBuilder:
    """Thin wrapper so all path building goes through one place.

    Used only for the comb fingers: short stubs that butt into a wide line
    rather than continue it, where seg()'s OVL-overlap-and-union trick is
    fine (there's no heading change to mitre). The two main lines are each
    one continuous StripPath built with .new()/.straight()/.turn()/.store().
    """

    def __init__(self, layouter, z, shift=0.0):
        self.layouter = layouter
        self.z = z
        self.n = 0
        self.shift = shift

    def seg(self, x, y, w, dx, dy, length,
            tag_start=None, tag_end=None, back=True, fwd=True):
        """One straight segment from (x, y) in direction (dx, dy).

        `back` / `fwd` extend the segment by OVL at the near / far end so that
        neighbouring segments union cleanly.  Turn them off at the board edges
        where a port sits, so the port face lands exactly on the boundary.
        """
        # Retain the original left/right comb-shift convention.
        x += self.shift if x < 7 else -self.shift
        norm = math.hypot(dx, dy)
        dx, dy = dx / norm, dy / norm
        b = OVL if back else 0.0
        f = OVL if fwd else 0.0
        p = self.layouter.new(x - dx * b, y - dy * b, w, (dx, dy), z=self.z)
        if tag_start:
            p = p.store(tag_start)
        p = p.straight(length + b + f, w)
        if tag_end:
            p = p.store(tag_end)
        self.n += 1
        return p

def install_polygon_dedupe():
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
    the feed width; the coupled width applies only to the central run.
    """
    clearance = y_comb - w_line       # line A lower edge to line B upper edge
    return (clearance + overlap) / 2.0, clearance

def build_coupler(layouter, config):
    """Draw two signal paths, then interleave fingers on their two jogs.

    Symmetric variants mirror the two routed lines about y=0. The asymmetric
    90-degree comparison keeps line A straight. Ports are at the feed ends.
    Finger overlap is always supplied explicitly; no capacitance synthesis is
    used in these 54 experiments.
    """
    z = 0
    comb_spacing, jog_length, bend_degrees = config['y'], config['jog'], config['bend']
    symmetric, n_fingers = config['symmetric'], config['fingers']
    overlap_mm = config['overlap']
    fingers = FingerBuilder(layouter, z, config.get('shift', 0.0))
    coupled_width, line_gap, coupled_length, feed_width = config['w'], config['gap'], config['length'], config['feed_w']
    coupled_spacing = coupled_width + line_gap                       # coupled centre-to-centre
    if symmetric:
        # each line travels HALF the level change, because both of them move
        rise1 = (FAR - comb_spacing) / 2.0
        rise2 = (comb_spacing - coupled_spacing) / 2.0
        _, dy_pair = bend_pair(feed_width, bend_degrees)
        if rise2 < dy_pair:
            raise SystemExit(
                f"symmetric layout at {bend_degrees:g} deg corners needs comb_spacing >= "
                f"{coupled_spacing + 2 * dy_pair:.3f} mm (have {comb_spacing}); shallower corners "
                f"lower that floor")
        if rise1 < dy_pair:
            raise SystemExit(
                f"symmetric layout at {bend_degrees:g} deg corners needs FAR >= "
                f"{comb_spacing + 2 * dy_pair:.3f} mm (have {FAR})")
    else:
        rise1 = FAR - comb_spacing                # feed level -> jog level
        rise2 = comb_spacing - coupled_spacing                # jog level -> coupled level
    # Account for corner advances when choosing the straight segment lengths.
    if symmetric:
        dx1, run1 = level_change(feed_width, rise1, bend_degrees)
        dx2, run2 = level_change(feed_width, rise2, bend_degrees)
        x_lead = FEED + dx1                 # port -> start of the jog
        x_start = x_lead + jog_length + dx2        # x where the coupled run begins
    else:
        run1 = rise1 - feed_width
        run2 = rise2 - feed_width
        x_lead = FEED + feed_width
        x_start = FEED + jog_length + 2 * feed_width     # x where the coupled run begins
    total = 2 * x_start + coupled_length

    # comb plane: centre of the jog, where the interdigital fingers sit
    x_cL = x_lead + jog_length / 2.0
    x_cR = total - x_cL

    if symmetric:
        # Both lines fan out from the coupled run by the same amount, so the
        # structure is a mirror image about y = 0 -- exactly the plane the
        # even/odd decomposition assumes.  sgn = -1 fans downward, +1 upward.
        angle = bend_degrees
        # The EMerge miter cut folds shallow-angle edges; use square corners.
        corner_type = CORNER if abs(angle - 90.0) < 1e-9 else "square"
        # Avoid merging two corners into one unintended facet.
        minimum_run = 0.05
        for name, run_length in (("rise1", run1), ("rise2", run2)):
            if run_length < minimum_run:
                raise SystemExit(
                    f"degenerate {angle:g} deg level change: {name} leaves only "
                    f"{run_length*1e3:.1f} um of straight between the two corners, so "
                    f"they merge into a single facet and the corner angle is "
                    f"not what it says.  Raise comb_spacing or reduce bend.")

        def level_step(ln, d, run, width=None):
            """One level change: turn, diagonal (or vertical at 90), turn back."""
            kw = dict(corner_type=corner_type, dsratio=DSRATIO)
            ln.turn(angle * d, **({**kw, "width": width} if width else kw))
            ln.straight(run)
            ln.turn(-angle * d, **kw)

        def route_line(sgn, tag_in, tag_out):
            ln = (layouter.new(0.0, sgn * FAR / 2.0, feed_width, (1.0, 0.0), z=z)
                  .store(tag_in).straight(FEED))
            level_step(ln, sgn, run1)                   # feed level -> jog level
            ln.straight(jog_length)                       # the comb sits here
            level_step(ln, sgn, run2)                   # jog level -> coupled level
            ln.straight(coupled_length, coupled_width)                  # the coupled run
            level_step(ln, -sgn, run2, width=feed_width)      # and back out, mirrored
            ln.straight(jog_length)
            level_step(ln, -sgn, run1)
            ln.straight(FEED)
            ln.store(tag_out)

        route_line(+1.0, "p1_end", "p2_end")      # line A: starts high, fans down
        route_line(-1.0, "p3_end", "p4_end")      # line B: starts low, fans up
        fingers.n += 2
    else:
        # ---- line A: one continuous path, ports 1 and 2 at its two ends.
        # This is the exact pattern from the EMerge stepped-impedance-filter example:
        # store() before a straight marks the path start, store() after marks the end.
        (layouter.new(0.0, 0.0, feed_width, (1.0, 0.0), z=z)
                 .store("p1_end")
                 .straight(x_start, feed_width)
                 .straight(coupled_length, coupled_width)
                 .straight(x_start, feed_width)
                 .store("p2_end"))
        fingers.n += 1

        # ---- line B: feed -> step up -> jog (comb) -> step up -> coupled -> mirror.
        # Every level change is a pair of 90 deg mitred bends; no diagonals.  Line angle
        # is feed_width everywhere outside the coupled run and steps to coupled_width at x_start,
        # exactly where line A does.  Both corners flanking the coupled run are
        # taken at feed_width so the two ends of it stay symmetric.
        yF, yJ, yC = -FAR, -comb_spacing, -coupled_spacing
        lineB = (layouter.new(0.0, yF, feed_width, (1.0, 0.0), z=z)
                 .store("p3_end")
                 .straight(FEED))
        lineB.turn(-90, corner_type=CORNER, dsratio=DSRATIO)      # head +y
        lineB.straight(rise1 - feed_width)
        lineB.turn(90, corner_type=CORNER, dsratio=DSRATIO)       # head +x, at yJ
        lineB.straight(jog_length)                                       # the comb sits here
        lineB.turn(-90, corner_type=CORNER, dsratio=DSRATIO)      # head +y
        lineB.straight(rise2 - feed_width)
        lineB.turn(90, corner_type=CORNER, dsratio=DSRATIO)       # head +x, at yC
        lineB.straight(coupled_length, coupled_width)                                  # the coupled run
        lineB.turn(90, width=feed_width, corner_type=CORNER, dsratio=DSRATIO)   # head -y
        lineB.straight(rise2 - feed_width)
        lineB.turn(-90, corner_type=CORNER, dsratio=DSRATIO)      # head +x, at yJ
        lineB.straight(jog_length)
        lineB.turn(90, corner_type=CORNER, dsratio=DSRATIO)       # head -y
        lineB.straight(rise1 - feed_width)
        lineB.turn(-90, corner_type=CORNER, dsratio=DSRATIO)      # head +x, at yF
        lineB.straight(FEED)
        lineB.store("p4_end")
        fingers.n += 1

    # ---- combs, centred on each jog
    comb_info = None
    if n_fingers > 0:
        fw, fgap = config['fw'], config['fg']
        overlap = overlap_mm
        f_len, clearance = finger_length(comb_spacing, feed_width, overlap)
        # Keep free finger tips clear of the opposite bus.
        if f_len >= clearance - OVL:
            raise SystemExit(
                f"fingers would short the two lines (f_len {f_len:.3f} mm vs "
                f"clearance {clearance:.3f} mm) — reduce overlap or raise comb_spacing")
        span = 2 * n_fingers * fw + (2 * n_fingers - 1) * fgap
        if span > jog_length:
            raise SystemExit(f"comb span {span:.3f} mm does not fit in jog_length {jog_length} mm")

        jog_centres = (x_cL, x_cR)
        # Finger roots attach to the feed-width jogs.
        if symmetric:
            y_a = comb_spacing / 2.0 - feed_width / 2.0    # line A lower edge
            y_b = -comb_spacing / 2.0 + feed_width / 2.0   # line B upper edge
        else:
            y_a = -feed_width / 2.0                  # line A lower edge
            y_b = -comb_spacing + feed_width / 2.0         # line B upper edge
        for xc in jog_centres:
            x0 = xc - span / 2.0 + fw / 2.0
            for i in range(2 * n_fingers):
                xf = x0 + i * (fw + fgap)
                # Extend only the finger root into its bus, never its free tip.
                if i % 2 == 0:                 # finger hanging down from line A
                    fingers.seg(xf, y_a, fw, 0.0, -1.0, f_len, fwd=False)
                else:                          # finger reaching up from line B
                    fingers.seg(xf, y_b, fw, 0.0, 1.0, f_len, fwd=False)
        comb_info = dict(fingers_per_side=n_fingers, overlap_mm=round(overlap, 4),
                         finger_len_mm=round(f_len, 4), span_mm=round(span, 3),
                         fw_mm=fw, fgap_mm=fgap,
                         facing_edge_mm=round((2 * n_fingers - 1) * overlap, 3))

    return dict(total_x=total, x_start=x_start, ctc=coupled_spacing,
                segments=fingers.n, comb=comb_info)

def build_paths(layouter, config):
    """Return layout metadata and ordered port names (P1, P2, P3, P4)."""
    if config['straight']:
        layouter.new(0, 0, config['feed_w'], (1, 0), z=0).store('p1_end').straight(10).store('p2_end')
        return dict(total_x=10, straight=True), ('p1_end', 'p2_end')
    limit = .08 if config.get('tolerance', False) else .10
    assert min(config['fw'], config['fg'], config['gap']) >= limit - 1e-9
    assert (config['y'] - config['feed_w'] - config['overlap']) / 2 >= limit - 1e-9, 'Finger-to-opposite-bus clearance below design limit'
    return build_coupler(layouter, config), ('p1_end', 'p2_end', 'p3_end', 'p4_end')

def outline(path):
    right, left = [], []
    for previous, edge, following in path.iter_right():
        points = list(edge.right)
        if following.rcutprev and points: points.pop(-1)
        if previous.rcutnext and points: points.pop(0)
        right.extend(points)
    for previous, edge, following in path.iter_left():
        points = list(edge.left)
        if following.lcutprev and points: points.pop(-1)
        if previous.lcutnext and points: points.pop(0)
        left.extend(points)
    return right + left[::-1]

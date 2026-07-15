"""
Aperture-Coupled Single Patch — EMerge FEM simulation module.

Two-PCB structure (bottom to top):
  z = 0            : microstrip feed line (bottom copper of PCB1)
  z = h1           : ground plane with aperture slot (top copper of PCB1)
  z = h1 + air_gap : bottom of PCB2
  z = h1+air_gap+h2: patch (top copper of PCB2)

Slot orientation: long axis along X, short axis along Y (feed direction).
The feed line runs along +Y, centred at X=0.
The open-circuit stub extends past the aperture centre toward +Y.

No main simulation loop here — use run_manager.py to run and track results.
"""

import numpy as np
import emerge as em

from utils import plot_s11

# Physical constants
C0   = 299_792_458.0       # m/s
EPS0 = 8.854_187_817e-12   # F/m

# =============================================================================
# Default parameter dict  (all dimensions in mm, frequencies in Hz)
# =============================================================================
P = {
    # --- Frequency -----------------------------------------------------------
    "f0":  5.8e9,   # centre frequency, Hz
    "fc":  0.5e9,   # Gaussian 20 dB corner half-bandwidth, Hz

    # --- Substrate (same material for both PCBs) ----------------------------
    "substrate_epsR":   2.94,    # ZYF300CA-C
    "substrate_tan":    0.0016,  # ZYF300CA-C
    "substrate_cells":  4,       # (unused in FEM — kept for API compatibility)

    # --- PCB thicknesses -----------------------------------------------------
    "h1":  1.524,   # mm, PCB1 (feed board, bottom)
    "h2":  1.524,   # mm, PCB2 (patch board, top)

    # --- Lateral board size (same for both PCBs) ----------------------------
    "sub_width":   40.0,   # mm, X dimension
    "sub_length":  60.0,   # mm, Y dimension

    # --- Air gap between PCB1 top surface and PCB2 bottom surface -----------
    "air_gap":  1.5,   # mm

    # --- Patch (top copper of PCB2) -----------------------------------------
    "patch_width":   20.0,  # mm, X
    "patch_length":  14.5,  # mm, Y

    # Patch centre Y measured from the board bottom edge (board spans 0..sub_length
    # in the board-edge frame; converted to sim-centred coords in compute_derived).
    "patch_y0":  30.0,   # mm from board bottom edge to patch centre

    # --- Aperture slot (in ground plane at top of PCB1) ----------------------
    # Slot long axis  → X direction
    # Slot short axis → Y direction (feed direction)
    "aperture_length":  8.0,   # mm, slot dimension along X  (long axis)
    "aperture_width":   1.5,   # mm, slot dimension along Y  (short axis)

    # Offset of slot centre from patch centre along Y (positive = toward +Y)
    "aperture_offset":  0.0,   # mm

    # Open-circuit stub: feed line extends this far past the slot centre (+Y)
    "aperture_stub":  5.0,   # mm

    # --- Feed line (microstrip, bottom copper of PCB1) -----------------------
    "feed_line_width":  3.9,   # mm (≈50 Ω on h1=1.524 mm, epsR=2.94)

    # --- Port ----------------------------------------------------------------
    "feed_R":  50,   # Ω
}


# =============================================================================
# Derived quantities
# =============================================================================

def compute_derived(P: dict) -> dict:
    """Compute derived/cached values from P.  Pure function — no side effects."""
    f0  = P["f0"]
    fc  = P["fc"]
    eps = P["substrate_epsR"]
    tan = P["substrate_tan"]

    lam_free = 1000.0 * C0 / f0                    # mm, free-space wavelength
    lam_sub  = lam_free / np.sqrt(eps)              # mm, guide wavelength (approx)
    kappa    = tan * 2.0 * np.pi * f0 * EPS0 * eps  # S/m (informational)

    # Z-stack (mm, absolute)
    z_pcb1_bot = 0.0
    z_pcb1_top = P["h1"]
    z_pcb2_bot = P["h1"] + P["air_gap"]
    z_pcb2_top = P["h1"] + P["air_gap"] + P["h2"]

    # Convert patch_y0 (board-edge frame: 0 = board bottom edge)
    # to sim-centred frame (board spans [-sub_length/2, +sub_length/2])
    patch_yc = (P["patch_y0"] - P["sub_length"] / 2.0) + P["patch_length"] / 2.0

    aperture_yc = patch_yc + P["aperture_offset"]
    feed_end_y  = aperture_yc + P["aperture_stub"]  # stub terminus (+Y)

    return dict(
        lam_free    = lam_free,
        lam_sub     = lam_sub,
        kappa       = kappa,
        z_pcb1_bot  = z_pcb1_bot,
        z_pcb1_top  = z_pcb1_top,
        z_pcb2_bot  = z_pcb2_bot,
        z_pcb2_top  = z_pcb2_top,
        patch_yc    = patch_yc,
        aperture_yc = aperture_yc,
        feed_end_y  = feed_end_y,
    )


# =============================================================================
# EMerge FEM simulation
# =============================================================================

def simulate(P: dict, num_threads: int = 4) -> tuple:
    """
    Build and run the EMerge FEM simulation.

    Parameters
    ----------
    P           : Parameter dict (see module-level P for keys/defaults).
    num_threads : Accepted for API compatibility; PARDISO auto-selects thread count.

    Returns
    -------
    freq_hz : np.ndarray, shape (N,)          Frequency array in Hz.
    s11     : np.ndarray, shape (N,), complex  S11 reflection coefficient.
    """
    import threading, signal as _sig

    # EMerge calls signal.signal() during GMSH init for Ctrl+C cleanup.
    # Python forbids signal.signal() from non-main threads → patch it to a
    # no-op for the duration of this call when running in a background thread.
    _orig_signal = None
    if threading.current_thread() is not threading.main_thread():
        _orig_signal = _sig.signal
        _sig.signal = lambda *a, **kw: None

    try:
        return _simulate(P)
    finally:
        if _orig_signal is not None:
            _sig.signal = _orig_signal


def preview(P: dict) -> None:
    """
    Build geometry, generate mesh, and open EMerge's interactive GMSH viewer.
    Blocks until the viewer window is closed.
    """
    import threading, signal as _sig

    _orig_signal = None
    if threading.current_thread() is not threading.main_thread():
        _orig_signal = _sig.signal
        _sig.signal = lambda *a, **kw: None

    try:
        _preview(P)
    finally:
        if _orig_signal is not None:
            _sig.signal = _orig_signal


def simulate_with_farfield(P: dict, num_threads: int = 4) -> tuple:
    """
    Build and run the EMerge FEM simulation, then compute far-field patterns.

    Parameters
    ----------
    P           : Parameter dict (see module-level P for keys/defaults).
    num_threads : Accepted for API compatibility; PARDISO auto-selects thread count.

    Returns
    -------
    freq_hz  : np.ndarray, shape (N,)
    s11      : np.ndarray, shape (N,), complex
    farfield : dict with keys:
        xz   : dict(ang, normE) — XZ-plane 2D cut at f0 (ang in radians)
        yz   : dict(ang, normE) — YZ-plane 2D cut at f0
        3d   : dict(theta, phi, normE) — 3D pattern meshgrids
        EISO : float  — isotropic E-field reference (em.lib.EISO)
        freq : float  — Hz at which farfield was computed
    """
    import threading, signal as _sig

    _orig_signal = None
    if threading.current_thread() is not threading.main_thread():
        _orig_signal = _sig.signal
        _sig.signal = lambda *a, **kw: None

    try:
        return _simulate_with_farfield(P)
    finally:
        if _orig_signal is not None:
            _sig.signal = _orig_signal


def _build_model(P: dict):
    """
    Create EMerge model, build all geometry, commit domain, and generate mesh.

    Returns (model, port_plate, air, fw, h1, f1, f2).
    Caller adds boundary conditions and runs the solver.
    """
    D  = compute_derived(P)
    mm = 1e-3

    f1 = P["f0"] - P["fc"]
    f2 = P["f0"] + P["fc"]

    sub_w = P["sub_width"]       * mm
    sub_l = P["sub_length"]      * mm
    h1    = P["h1"]              * mm
    h2    = P["h2"]              * mm
    fw    = P["feed_line_width"] * mm
    pw    = P["patch_width"]     * mm
    pl    = P["patch_length"]    * mm
    ap_l  = P["aperture_length"] * mm
    ap_w  = P["aperture_width"]  * mm

    z1_bot = D["z_pcb1_bot"] * mm
    z1_top = D["z_pcb1_top"] * mm
    z2_bot = D["z_pcb2_bot"] * mm
    z2_top = D["z_pcb2_top"] * mm

    patch_yc   = D["patch_yc"]    * mm
    ap_yc      = D["aperture_yc"] * mm
    feed_end_y = D["feed_end_y"]  * mm
    port_y     = -sub_l / 2
    margin     = D["lam_free"] * mm / 4.0

    # Simulation object MUST be created before any geometry
    model = em.Simulation("acsp_tmp", save_file=False)
    model.mw.set_resolution(0.25)
    model.mw.set_frequency_range(f1, f2, 11)

    # --- Air box (simulation domain) -----------------------------------------
    air_xmin = -sub_w / 2 - margin;  air_xmax = sub_w / 2 + margin
    air_ymin =  port_y    - margin;  air_ymax = sub_l / 2 + margin
    air_zmin =  z1_bot    - margin;  air_zmax = z2_top    + margin

    air = em.geo.Box(
        air_xmax - air_xmin,
        air_ymax - air_ymin,
        air_zmax - air_zmin,
        position=(air_xmin, air_ymin, air_zmin),
    )

    # --- PCB1 substrate -------------------------------------------------------
    pcb1 = em.geo.Box(sub_w, sub_l, h1, position=(-sub_w/2, -sub_l/2, z1_bot))
    pcb1.set_material(em.Material(P["substrate_epsR"]))

    # --- PCB2 substrate -------------------------------------------------------
    pcb2 = em.geo.Box(sub_w, sub_l, h2, position=(-sub_w/2, -sub_l/2, z2_bot))
    pcb2.set_material(em.Material(P["substrate_epsR"]))

    # --- Ground plane with aperture slot (top face of PCB1) ------------------
    bx_min = -sub_w / 2;  bx_max = sub_w / 2
    by_min = -sub_l / 2;  by_max = sub_l / 2
    sx_min = -ap_l  / 2;  sx_max = ap_l  / 2
    sy_min =  ap_yc - ap_w / 2;  sy_max = ap_yc + ap_w / 2

    gnd_s = em.geo.XYPlate(sub_w,           sy_min - by_min,
                            position=(bx_min, by_min, z1_top))
    gnd_n = em.geo.XYPlate(sub_w,           by_max - sy_max,
                            position=(bx_min, sy_max, z1_top))
    gnd_w = em.geo.XYPlate(sx_min - bx_min, sy_max - sy_min,
                            position=(bx_min, sy_min, z1_top))
    gnd_e = em.geo.XYPlate(bx_max - sx_max, sy_max - sy_min,
                            position=(sx_max, sy_min, z1_top))
    gnd = em.geo.add(em.geo.add(em.geo.add(gnd_s, gnd_n), gnd_w), gnd_e)
    gnd.set_material(em.lib.PEC)

    # --- Patch (top face of PCB2) --------------------------------------------
    patch = em.geo.XYPlate(pw, pl, position=(-pw/2, patch_yc - pl/2, z2_top))
    patch.set_material(em.lib.PEC)

    # --- Feed line (bottom face of PCB1) -------------------------------------
    feed = em.geo.XYPlate(fw, feed_end_y - port_y, position=(-fw/2, port_y, z1_bot))
    feed.set_material(em.lib.PEC)

    # --- Lumped port face ----------------------------------------------------
    port_plate = em.geo.Plate(
        np.array([-fw/2, port_y, z1_bot]),
        np.array([fw,    0,      0      ]),
        np.array([0,     0,      h1     ]),
    )

    model.commit_geometry(air)

    model.mesher.set_boundary_size(gnd,   ap_w / 3)
    model.mesher.set_boundary_size(patch, 1.0 * mm)
    model.mesher.set_boundary_size(feed,  fw  / 3)
    model.mesher.set_face_size(port_plate, fw  / 3)

    model.generate_mesh()

    return model, port_plate, air, fw, h1, f1, f2


def _simulate(P: dict) -> tuple:
    model, port_plate, air, fw, h1, f1, f2 = _build_model(P)

    # --- Boundary conditions (applied after meshing, per EMerge convention) --
    model.mw.bc.LumpedPort(
        port_plate, 1,
        width=fw, height=h1,
        direction=em.ZAX, Z0=float(P["feed_R"]),
    )
    model.mw.bc.AbsorbingBoundary(air.boundary())

    # --- Solver preference ---------------------------------------------------
    try:
        model.set_solver(em.EMSolver.PARDISO)
    except Exception:
        try:
            model.set_solver(em.EMSolver.SUPERLU)
        except Exception:
            pass

    # --- Run -----------------------------------------------------------------
    model.mw.run_sweep()
    data = model.data.mw

    freq_dense = np.linspace(f1, f2, 401)
    s11 = data.scalar.grid.model_S(1, 1, freq_dense)
    return freq_dense, s11


def _preview(P: dict) -> None:
    model, *_ = _build_model(P)
    model.view(plot_mesh=True, volume_mesh=False)


def _simulate_with_farfield(P: dict) -> tuple:
    """
    Same sweep as _simulate, plus far-field computation at f0.

    Returns (freq_dense, s11, farfield) where farfield is a dict:
        xz   : dict(ang, normE) — XZ-plane cut (ang in radians)
        yz   : dict(ang, normE) — YZ-plane cut
        3d   : dict(theta, phi, normE) — 3D meshgrids
        EISO : float — em.lib.EISO, the isotropic E-field reference
        freq : float — Hz at which farfield was computed
    Divide normE by EISO to get the E-field amplitude normalised to isotropic.
    Gain_dBi = 20 * log10(normE / EISO).
    """
    model, port_plate, air, fw, h1, f1, f2 = _build_model(P)

    bnd = air.boundary()   # captured once; reused for BC and farfield

    model.mw.bc.LumpedPort(
        port_plate, 1,
        width=fw, height=h1,
        direction=em.ZAX, Z0=float(P["feed_R"]),
    )
    model.mw.bc.AbsorbingBoundary(bnd)

    try:
        model.set_solver(em.EMSolver.PARDISO)
    except Exception:
        try:
            model.set_solver(em.EMSolver.SUPERLU)
        except Exception:
            pass

    model.mw.run_sweep()
    data = model.data.mw

    freq_dense = np.linspace(f1, f2, 401)
    s11 = data.scalar.grid.model_S(1, 1, freq_dense)

    # Far-field at f0
    f0  = P["f0"]
    fld = data.field.find(freq=f0)

    ff_xz = fld.farfield_2d((0, 0, 1), (1, 0, 0), bnd)   # XZ-plane (E-plane)
    ff_yz = fld.farfield_2d((0, 0, 1), (0, 1, 0), bnd)   # YZ-plane (H-plane)
    ff_3d = fld.farfield_3d(bnd)

    farfield = {
        "xz": {"ang": np.asarray(ff_xz.ang),  "normE": np.asarray(ff_xz.normE)},
        "yz": {"ang": np.asarray(ff_yz.ang),  "normE": np.asarray(ff_yz.normE)},
        "3d": {
            "theta": np.asarray(ff_3d.theta),
            "phi":   np.asarray(ff_3d.phi),
            "normE": np.asarray(ff_3d.normE),
        },
        "EISO": float(em.lib.EISO),
        "freq": float(f0),
    }

    return freq_dense, s11, farfield


# =============================================================================
# Result extraction
# =============================================================================

def extract_results(freq: np.ndarray, s11: np.ndarray, f0: float) -> dict:
    """
    Compute result metrics from S11 data.

    Parameters
    ----------
    freq : Hz, shape (N,)
    s11  : complex, shape (N,)
    f0   : Design centre frequency in Hz.

    Returns
    -------
    dict with keys:
        s11_db_at_f0     float   S11 in dB at f0
        s11_min_db       float   Minimum S11 in dB over the sweep
        resonant_freq_hz float   Frequency of deepest S11 minimum
        bandwidth_hz     float|None  -10 dB bandwidth (None if not found)
        s11_complex      list[[re, im]]  Full S11 array (JSON-serialisable)
    """
    s11_dB  = 20.0 * np.log10(np.abs(s11))
    f0_idx  = int(np.argmin(np.abs(freq - f0)))
    _abs    = np.where(np.isfinite(np.abs(s11)), np.abs(s11), np.inf)
    res_idx = int(np.argmin(_abs))

    info = plot_s11(freq, s11_dB, annotate=False)
    bw   = info.get("BW_Hz")

    return {
        "s11_db_at_f0":     float(s11_dB[f0_idx]),
        "s11_min_db":       float(s11_dB[res_idx]),
        "resonant_freq_hz": float(freq[res_idx]),
        "bandwidth_hz":     float(bw) if bw is not None else None,
        "s11_complex":      [[float(c.real), float(c.imag)] for c in s11],
    }

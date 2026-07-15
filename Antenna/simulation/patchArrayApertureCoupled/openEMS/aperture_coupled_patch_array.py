### Aperture-Coupled 5-Element Patch Array with T-Junction Corporate Feed
### Two-PCB design: feed network on PCB1, patches on PCB2, air gap between.
### Prepared for parameter optimization.

import os, tempfile
import numpy as np
from pylab import *

from CSXCAD import ContinuousStructure
from openEMS import openEMS
from openEMS.physical_constants import *

from utils import *

from matplotlib.backends.backend_pdf import PdfPages

# =============================================================================
# Simulation control flags
# =============================================================================
draw_CAD          = 1
draw_CAD_exit     = 1
enable_simulation = 1
save_to_pdf       = 1

draw_complex_impedance  = 1
draw_s11               = 1
draw_smith_chart        = 1
draw_Ez_absolute        = 1
draw_Ez_snap            = 1
draw_Js_absolute        = 1
draw_Jx                 = 1
draw_Jy                 = 1
draw_directivety_polar  = 1
draw_directivity_db     = 1
draw_3d_pattern         = 1
draw_vtk_field          = 0
vtk_phase_step_deg      = 10

# =============================================================================
# ALL GEOMETRY PARAMETERS
# Kept in a flat dict so an optimizer can replace values easily.
# Units: mm (except where noted).
# =============================================================================
P = {

    # -------------------------------------------------------------------------
    # Frequency
    # -------------------------------------------------------------------------
    "f0":   5.8e9,        # center frequency, Hz
    "fc":   0.5e9,        # 20 dB corner frequency (Gaussian pulse half-BW), Hz

    # -------------------------------------------------------------------------
    # Substrate — same material for both PCBs
    # -------------------------------------------------------------------------
    "substrate_epsR":       2.94,       # ZYF300CA-C
    "substrate_tan":        0.0016,     # ZYF300CA-C
    "substrate_cells":      4,          # mesh layers through substrate thickness

    # PCB1: feed board (bottom)
    "h1":   1.524,        # PCB1 thickness, mm

    # PCB2: patch board (top)
    "h2":   1.524,        # PCB2 thickness, mm

    # Lateral size — same for both PCBs
    "sub_width":  80.0,   # mm, along X (perpendicular to array axis)
    "sub_length": 180.0,  # mm, along Y (array axis)

    # -------------------------------------------------------------------------
    # Air gap between PCB1 top surface and PCB2 bottom surface
    # -------------------------------------------------------------------------
    "air_gap": 1.5,       # mm

    # -------------------------------------------------------------------------
    # Patches (5 elements, indexed 0..4, along +Y from bottom)
    # -------------------------------------------------------------------------
    "patch_width":  [20.0, 20.0, 20.0, 20.0, 20.0],   # mm, X dimension
    "patch_length": [14.5, 14.5, 14.5, 14.5, 14.5],   # mm, Y dimension

    # Distance between adjacent patch centres (edge-to-edge = spacing - length)
    "patch_pitch": [32.0, 32.0, 32.0, 32.0],   # 4 gaps for 5 patches, mm

    # First patch centre Y position measured from PCB bottom edge
    "patch_y0": 30.0,     # mm

    # -------------------------------------------------------------------------
    # Aperture slots (one per patch, in the ground plane of PCB1 top copper)
    # Each aperture is centred under the corresponding patch.
    # -------------------------------------------------------------------------
    "aperture_length": [8.0, 8.0, 8.0, 8.0, 8.0],   # mm, along Y (slot length)
    "aperture_width":  [1.5, 1.5, 1.5, 1.5, 1.5],   # mm, along X (slot width)

    # Offset of aperture centre from patch centre toward open (back-short) end
    # Positive = toward +Y (same as array direction)
    "aperture_offset": [0.0, 0.0, 0.0, 0.0, 0.0],   # mm

    # Open-circuit stub length on feed side past aperture centre (tuning)
    "aperture_stub": [5.0, 5.0, 5.0, 5.0, 5.0],     # mm

    # -------------------------------------------------------------------------
    # Feed network — T-junction corporate feed on PCB1 bottom copper
    # Topology (for 5 equal patches, 2+3 or 2+2+1 split):
    #
    #                           [port]
    #                             |  input_line
    #                             J1 ─── (matching stub J1)
    #                           /    \
    #                   brA_line      brB_line
    #                      /                \
    #                    J2                 J3 ─── (stub J3)
    #                   /  \              /    \
    #             feed_P0  feed_P1   feed_P2   brC_line
    #            (patch0) (patch1) (patch2)       \
    #                                              J4 ─── (stub J4)
    #                                            /    \
    #                                       feed_P3  feed_P4
    #                                      (patch3) (patch4)
    #
    # All widths/lengths describe microstrip lines on PCB1 bottom layer.
    # -------------------------------------------------------------------------

    # Input line (50 Ω)
    "input_line_width":  3.9,     # mm
    "input_line_length": 10.0,    # mm, from port to J1

    # --- Junction J1: 1 → 2/5 (left) + 3/5 (right) -------------------------
    "j1_stub_length": 5.0,        # open-circuit matching stub, mm
    "j1_stub_width":  1.0,        # mm

    # Branch A: J1 → J2 (carries 2/5 power, wider line)
    "brA_width":  2.5,            # mm
    "brA_length": 20.0,           # mm, straight section J1→J2

    # Quarter-wave transformer J1 left output (if needed for impedance match)
    "j1_qwt_left_width":  1.8,    # mm
    "j1_qwt_left_length": 8.0,    # mm

    # --- Junction J2: 2/5 → 1/5 (patch 0) + 1/5 (patch 1) -----------------
    "j2_stub_length": 4.5,
    "j2_stub_width":  0.9,

    # Feed lines J2 → patch apertures
    "feed_p0_width":  1.0,        # mm, narrow line for high-Z match
    "feed_p0_length": 15.0,       # mm
    "feed_p1_width":  1.0,
    "feed_p1_length": 15.0,

    # Branch B: J1 → J3 (carries 3/5 power)
    "brB_width":  3.5,
    "brB_length": 20.0,

    # Quarter-wave transformer J1 right output
    "j1_qwt_right_width":  2.2,
    "j1_qwt_right_length": 8.0,

    # --- Junction J3: 3/5 → 1/5 (patch 2) + 2/5 (right) -------------------
    "j3_stub_length": 5.0,
    "j3_stub_width":  1.0,

    # Feed line J3 → patch 2 aperture (centre patch)
    "feed_p2_width":  1.0,
    "feed_p2_length": 15.0,

    # Branch C: J3 → J4
    "brC_width":  2.5,
    "brC_length": 20.0,

    # Quarter-wave transformer J3 right output
    "j3_qwt_right_width":  1.8,
    "j3_qwt_right_length": 8.0,

    # --- Junction J4: 2/5 → 1/5 (patch 3) + 1/5 (patch 4) -----------------
    "j4_stub_length": 4.5,
    "j4_stub_width":  0.9,

    # Feed lines J4 → patch apertures
    "feed_p3_width":  1.0,
    "feed_p3_length": 15.0,
    "feed_p4_width":  1.0,
    "feed_p4_length": 15.0,

    # -------------------------------------------------------------------------
    # Port
    # -------------------------------------------------------------------------
    "feed_R": 50,         # Ω
}

# =============================================================================
# Derived / computed quantities (do not add to P directly — recompute here
# so that changing P and calling build_geometry() always stays consistent).
# =============================================================================

def compute_derived(P):
    """Return a dict of derived constants from P."""
    f0  = P["f0"]
    fc  = P["fc"]
    eps = P["substrate_epsR"]
    tan = P["substrate_tan"]

    c0       = 299792458.0
    lam_free = 1000.0 * c0 / f0          # mm
    lam_sub  = lam_free / np.sqrt(eps)   # mm
    kappa    = tan * 2 * np.pi * f0 * EPS0 * eps

    # Z-stack (bottom to top), all in mm
    z_pcb1_bot = 0.0
    z_pcb1_top = P["h1"]
    z_pcb2_bot = z_pcb1_top + P["air_gap"]
    z_pcb2_top = z_pcb2_bot + P["h2"]

    # Patch centre Y positions
    patch_y_centers = []
    y = P["patch_y0"] - P["sub_length"] / 2   # convert from board-edge ref to sim centre ref
    for i in range(5):
        patch_y_centers.append(y + P["patch_length"][i] / 2)
        if i < 4:
            y += P["patch_pitch"][i]

    # Aperture centre Y positions (same as patch centre + offset)
    aperture_y_centers = [
        patch_y_centers[i] + P["aperture_offset"][i] for i in range(5)
    ]

    return dict(
        lam_free         = lam_free,
        lam_sub          = lam_sub,
        kappa            = kappa,
        z_pcb1_bot       = z_pcb1_bot,
        z_pcb1_top       = z_pcb1_top,
        z_pcb2_bot       = z_pcb2_bot,
        z_pcb2_top       = z_pcb2_top,
        patch_y_centers  = patch_y_centers,
        aperture_y_centers = aperture_y_centers,
    )

# =============================================================================
# Geometry builder
# =============================================================================

def build_geometry(P):
    """
    Build openEMS FDTD + CSX geometry from parameter dict P.
    Returns (FDTD, CSX, port, nf2ff, sim_box, D) where D = compute_derived(P).
    """
    D   = compute_derived(P)
    f0  = P["f0"]
    fc  = P["fc"]
    lam = D["lam_free"]

    # Simulation box
    air_margin = lam / 4
    sim_box = [
        P["sub_width"]  + air_margin,
        P["sub_length"] + air_margin,
        (D["z_pcb2_top"] + air_margin) * 2,   # centred at mid-stack
    ]

    # ---- FDTD setup --------------------------------------------------------
    FDTD = openEMS(NrTS=60000, EndCriteria=1e-5)
    FDTD.SetGaussExcite(f0, fc)
    FDTD.SetBoundaryCond(['PML_8'] * 6)

    CSX  = ContinuousStructure()
    FDTD.SetCSX(CSX)
    mesh = CSX.GetGrid()
    mesh.SetDeltaUnit(1e-3)
    mesh_res = C0 / (f0 + fc) / 1e-3 / 20

    # Sim-box boundary lines
    mesh.AddLine('x', [-sim_box[0] / 2, sim_box[0] / 2])
    mesh.AddLine('y', [-sim_box[1] / 2, sim_box[1] / 2])
    mesh.AddLine('z', [-sim_box[2] / 3,  sim_box[2] * 2 / 3])

    # ---- Z mesh through stack ----------------------------------------------
    mesh.AddLine('z', np.linspace(D["z_pcb1_bot"], D["z_pcb1_top"], P["substrate_cells"] + 1))
    mesh.AddLine('z', np.linspace(D["z_pcb2_bot"], D["z_pcb2_top"], P["substrate_cells"] + 1))

    # ---- PCB1 substrate ----------------------------------------------------
    sub1_mat = CSX.AddMaterial('pcb1_sub',
                               epsilon=P["substrate_epsR"],
                               kappa=D["kappa"])
    sub1_mat.AddBox(priority=0,
                    start=[-P["sub_width"]/2, -P["sub_length"]/2, D["z_pcb1_bot"]],
                    stop =[ P["sub_width"]/2,  P["sub_length"]/2, D["z_pcb1_top"]])

    # ---- PCB2 substrate ----------------------------------------------------
    sub2_mat = CSX.AddMaterial('pcb2_sub',
                               epsilon=P["substrate_epsR"],
                               kappa=D["kappa"])
    sub2_mat.AddBox(priority=0,
                    start=[-P["sub_width"]/2, -P["sub_length"]/2, D["z_pcb2_bot"]],
                    stop =[ P["sub_width"]/2,  P["sub_length"]/2, D["z_pcb2_top"]])

    # ---- Ground plane (top of PCB1, with aperture cutouts) -----------------
    # Strategy: add full ground, then apertures are left as gaps (not adding metal there).
    # In openEMS the simplest approach: define ground as metal sheet,
    # then apertures are modelled as absence of metal (do not fill those regions).
    # Here we add the ground as four strips around each aperture.
    # TODO: implement ground-plane-with-apertures using complementary metal fills
    #       or use CSX.AddConductingSheet for each non-aperture rectangle.
    gnd = CSX.AddMetal('gnd')
    z_gnd = D["z_pcb1_top"]
    # Full ground placeholder (apertures modelled as gaps — refine in TODO below)
    gnd.AddBox(priority=10,
               start=[-P["sub_width"]/2, -P["sub_length"]/2, z_gnd],
               stop =[ P["sub_width"]/2,  P["sub_length"]/2, z_gnd])
    FDTD.AddEdges2Grid(dirs='xy', properties=gnd)

    # TODO: cut aperture slots from ground plane
    # For each patch i, remove a rectangle:
    #   x: [-aperture_width[i]/2 .. aperture_width[i]/2]
    #   y: [aperture_y_centers[i] - aperture_length[i]/2 ..
    #       aperture_y_centers[i] + aperture_length[i]/2]
    # openEMS workaround: use a dielectric override or split ground into segments.

    # ---- Patches (top of PCB2) ---------------------------------------------
    patch_metal = CSX.AddMetal('patches')
    z_patch = D["z_pcb2_top"]
    rects_mm = []

    for i in range(5):
        pw = P["patch_width"][i]
        pl = P["patch_length"][i]
        yc = D["patch_y_centers"][i]
        x0, x1 = -pw / 2, pw / 2
        y0, y1 = yc - pl / 2, yc + pl / 2

        start = [x0, y0, z_patch]
        stop  = [x1, y1, z_patch]
        patch_metal.AddBox(priority=10, start=start, stop=stop)
        FDTD.AddEdges2Grid(dirs='xy', properties=patch_metal, metal_edge_res=mesh_res / 4)

        rects_mm.append({"x1": x0, "x2": x1, "y1": y0, "y2": y1})

    # ---- Feed network on bottom of PCB1 ------------------------------------
    feed_net = CSX.AddMetal('feed_network')
    z_feed   = D["z_pcb1_bot"]   # bottom copper of PCB1

    # Input port position (at PCB bottom edge, centre X)
    port_y = -P["sub_length"] / 2

    # Input line: from port_y to J1
    iw = P["input_line_width"]
    il = P["input_line_length"]
    feed_net.AddBox(priority=11,
                    start=[-iw/2, port_y,      z_feed],
                    stop =[ iw/2, port_y + il, z_feed])
    mesh.AddLine('x', 0)
    mesh.AddLine('x', [-iw/2 + 0.5, iw/2 - 0.5])

    # TODO: J1 T-junction geometry at y = port_y + il
    # TODO: Branch A (left) to J2 → feeds patch 0 and patch 1
    # TODO: Branch B (right) to J3 → feeds patch 2 and sub-branch to J4
    # TODO: J2, J3, J4 T-junction geometry
    # TODO: Individual feed lines to each aperture stub
    # TODO: Open-circuit stubs at J1, J2, J3, J4 for impedance matching
    # TODO: Quarter-wave transformers where needed

    # Aperture tuning stubs (on feed side, extending past aperture centre)
    for i in range(5):
        yc  = D["aperture_y_centers"][i]
        aw  = P["aperture_width"][i]
        asl = P["aperture_stub"][i]
        # TODO: connect stub to actual feed line end
        # Placeholder: small stub segment centred on aperture
        feed_net.AddBox(priority=11,
                        start=[-aw/2, yc,        z_feed],
                        stop =[ aw/2, yc + asl,  z_feed])

    FDTD.AddEdges2Grid(dirs='x', properties=feed_net, metal_edge_res=mesh_res / 4)

    # ---- Lumped port at PCB bottom edge ------------------------------------
    port = FDTD.AddLumpedPort(
        1, P["feed_R"],
        [-iw/2, port_y, D["z_pcb1_bot"]],
        [ iw/2, port_y, D["z_pcb1_top"]],
        'z', 1.0,
        priority=5,
    )
    mesh.AddLine('y', [port_y, port_y - mesh_res/4, port_y + mesh_res/4])

    # ---- Smooth mesh -------------------------------------------------------
    mesh.SmoothMeshLines('all', mesh_res, 1.05)

    # ---- NF2FF box ---------------------------------------------------------
    nf2ff = FDTD.CreateNF2FFBox()

    # ---- Field dumps -------------------------------------------------------
    et = CSX.AddDump('Et', dump_type=0, file_type=1)
    et.AddBox(start=[-sim_box[0]/2, -sim_box[1]/2, -sim_box[2]/3],
              stop =[ sim_box[0]/2,  sim_box[1]/2,  sim_box[2]*2/3])

    jt = CSX.AddDump('Jt', dump_type=3, file_type=1)
    jt.AddBox(start=[-sim_box[0]/2, -sim_box[1]/2, -sim_box[2]/3],
              stop =[ sim_box[0]/2,  sim_box[1]/2,  sim_box[2]*2/3])

    return FDTD, CSX, port, nf2ff, sim_box, D, rects_mm


# =============================================================================
# Main: single run (no sweep yet — sweep / optimisation to be added)
# =============================================================================

D    = compute_derived(P)
f0   = P["f0"]
fc   = P["fc"]
rects_mm = []

sim_tag = (f"aperture_coupled_5patch"
           f"_h1={P['h1']}_h2={P['h2']}_gap={P['air_gap']}"
           f"_pw={P['patch_width']}_pl={P['patch_length']}")

Sim_Path = os.path.join(tempfile.gettempdir(), sim_tag)

FDTD, CSX, port, nf2ff, sim_box, D, rects_mm = build_geometry(P)

# ---- View in AppCSXCAD -----------------------------------------------------
if draw_CAD:
    CSX_file = os.path.join(Sim_Path, 'aperture_coupled.xml')
    if not os.path.exists(Sim_Path):
        os.mkdir(Sim_Path)
    CSX.Write2XML(CSX_file)
    from CSXCAD import AppCSXCAD_BIN
    os.system(AppCSXCAD_BIN + f' "{CSX_file}"')

if draw_CAD_exit:
    exit()

# ---- Run simulation --------------------------------------------------------
if enable_simulation:
    FDTD.Run(Sim_Path, verbose=3, cleanup=True, numThreads=4)

# =============================================================================
# Post-processing
# =============================================================================

script_dir  = os.path.dirname(os.path.abspath(__file__))
reports_dir = os.path.join(script_dir, "reports")
os.makedirs(reports_dir, exist_ok=True)

filename = (f"aperture_coupled_5patch"
            f"_pw={P['patch_width']}_pl={P['patch_length']}"
            f"_gap={P['air_gap']}mm_results.pdf")
pdf_path = os.path.join(reports_dir, filename)
pdf      = PdfPages(pdf_path) if save_to_pdf else None


def finalize_plot(pdf=pdf, save_to_pdf=save_to_pdf):
    if save_to_pdf and pdf is not None:
        pdf.savefig()
        plt.close()


freq = np.linspace(f0 - fc, f0 + fc, 401)
port.CalcPort(Sim_Path, freq)

# S11
s11    = port.uf_ref / port.uf_inc
s11_dB = 20.0 * np.log10(np.abs(s11))
freqInd  = freq.shape[0] // 2
freqInd2 = int(np.argmin(np.abs(s11)))

if draw_complex_impedance:
    Zin = port.uf_tot / port.if_tot
    figure()
    plot(freq / 1e9, np.real(Zin), 'k-', label='Zin real')
    plot(freq / 1e9, np.imag(Zin), 'r--', label='Zin imag')
    grid(); legend()
    ylabel('Ohm'); xlabel('Frequency (GHz)')
    finalize_plot()

if draw_s11:
    plot_s11(freq, s11_dB)
    finalize_plot()

# Touchstone
touchstone_dir = os.path.join(script_dir, "touchstone")
os.makedirs(touchstone_dir, exist_ok=True)
s1p_path = os.path.join(touchstone_dir,
    f"aperture_coupled_5patch_gap={P['air_gap']}mm.s1p")
write_s1p_file(s1p_path, freq, P["feed_R"], s11)

# Patch equivalent impedance
s11_1 = s11[freqInd];  s11_2 = s11[freqInd2]
patchR      = (1 + s11_1) / (1 - s11_1) * P["feed_R"]
patchG_norm = (1 - s11_1) / (1 + s11_1)
patchR2     = (1 + s11_2) / (1 - s11_2) * P["feed_R"]
patchG2_norm= (1 - s11_2) / (1 + s11_2)

if draw_smith_chart:
    center_w = P["patch_width"][2]
    center_l = P["patch_length"][2]
    ax, meta = plot_smith_skrf(
        s11, freq_hz=freq,
        idx_main=freqInd, idx_res=freqInd2,
        patch_width_mm=center_w, patch_length_mm=center_l,
        patchR=patchR, patchG=patchG_norm,
        patchR2=patchR2, patchG2=patchG2_norm,
    )
    finalize_plot()

# Ez field
if draw_Ez_absolute or draw_Ez_snap:
    fd   = read_hdf5_dump(f"{Sim_Path}/Et.h5")
    E_fd = td_to_fd_fft(fd.F_td, fd.dt, freq[freqInd])
    patch_y_edges = [r["y1"] for r in rects_mm] + [r["y2"] for r in rects_mm]

if draw_Ez_absolute:
    z_slice = D["z_pcb2_top"] / 1000 + 0.5e-3   # just above patches
    plot_ez_2d(fd, E_fd, z_value=z_slice,
               func=lambda Ez: np.abs(Ez), func_str="|Ez|",
               cmap="jet", outside_color="lightgray")
    finalize_plot()
    plot_ez_line_y(fd, E_fd, z_value=z_slice,
                   func=lambda Ez: np.abs(Ez), func_str="|Ez|",
                   x_value=None, y_lines_mm=np.array(patch_y_edges))
    finalize_plot()

if draw_Ez_snap:
    port_y = -P["sub_length"] / 2
    ix, iy1, iz = coord_to_index(x=0, y=port_y/1000, z=D["z_pcb2_top"]/1000+0.5e-3, fd=fd)
    dphi = find_max_ampl_phase(E_fd[ix, iy1:, iz, 2])
    E_snap = np.real(E_fd * np.exp(-1j * dphi))
    plot_ez_2d(fd, E_snap, z_value=D["z_pcb2_top"]/1000+0.5e-3,
               func=lambda Ez: Ez, func_str=f"Ez snap (dphi={dphi*180/np.pi:.1f}°)",
               cmap="jet", outside_color="lightgray")
    finalize_plot()
    plot_ez_line_y(fd, E_snap, z_value=D["z_pcb2_top"]/1000+0.5e-3,
                   func=lambda Ez: Ez, func_str="Ez snap",
                   x_value=None, y_lines_mm=np.array(patch_y_edges))
    finalize_plot()

# Surface currents
if draw_Js_absolute or draw_Jx or draw_Jy:
    fd   = read_hdf5_dump(f"{Sim_Path}/Jt.h5")
    J_fd = td_to_fd_fft(fd.F_td, fd.dt, freq[freqInd])
    z_js = D["z_pcb2_top"] / 1000

if draw_Js_absolute:
    plot_js_2d(fd, J_fd, z_value=z_js,
               func=lambda Jx, Jy, Jz: np.sqrt((Jx*np.conj(Jx)+Jy*np.conj(Jy)).real),
               func_str="|Js|", cmap="jet")
    finalize_plot()

if draw_Jx:
    plot_js_2d(fd, J_fd, z_value=z_js,
               func=lambda Jx, Jy, Jz: np.abs(Jx), func_str="|Jx|", cmap="jet")
    finalize_plot()

if draw_Jy:
    plot_js_2d(fd, J_fd, z_value=z_js,
               func=lambda Jx, Jy, Jz: np.abs(Jy), func_str="|Jy|", cmap="jet")
    finalize_plot()

# Radiation pattern
if draw_directivety_polar or draw_directivity_db:
    theta = np.arange(-180.0, 180.0, 2.0)
    phi   = [0., 90.]
    nf2ff_res = nf2ff.CalcNF2FF(Sim_Path, freq[freqInd], theta, phi,
                                 center=[0, 0, D["z_pcb2_top"] * 1e-3])

if draw_directivety_polar:
    plot_directivity_db_polar(theta, nf2ff_res, freq[freqInd])
    finalize_plot()

if draw_directivity_db:
    plot_directivity_db(theta, nf2ff_res, freq[freqInd])
    finalize_plot()

if draw_3d_pattern:
    theta_3d = np.arange(0.0, 181.0, 5.0)
    phi_3d   = np.arange(0.0, 360.0, 5.0)
    nf2ff_3d = nf2ff.CalcNF2FF(Sim_Path, freq[freqInd], theta_3d, phi_3d,
                                center=[0, 0, D["z_pcb2_top"] * 1e-3])
    plot_directivity_3d(theta_3d, phi_3d, nf2ff_3d, freq[freqInd])
    finalize_plot()
    html_path = os.path.join(reports_dir,
        f"aperture_coupled_5patch_gap={P['air_gap']}mm_3D_pattern.html")
    plot_directivity_3d_interactive(theta_3d, phi_3d, nf2ff_3d, freq[freqInd], html_path)

if draw_vtk_field:
    vtk_dir = os.path.join(reports_dir, f"vtk_aperture_coupled_5patch")
    export_efield_vtk_at_frequency(
        hdf5_path=os.path.join(Sim_Path, 'Et.h5'),
        target_freq=f0,
        output_dir=vtk_dir,
        phase_step_deg=vtk_phase_step_deg,
    )

if save_to_pdf and pdf is not None:
    pdf.close()
elif not save_to_pdf:
    plt.show()

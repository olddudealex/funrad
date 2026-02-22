import emerge as em
import numpy as np
from emerge.plot import plot_sp, smith, plot_ff_polar, plot_ff

""" PATCH ANTENNA DEMO

This design is modeled after this Comsol Demo: https://www.comsol.com/model/microstrip-patch-antenna-11742

In this demo we build and simulate a rectangular patch antenna on a dielectric
substrate with airbox and lumped port excitation, then visualize S-parameters
and far-field radiation patterns. 

This simulation is quite heavy and might take a while to fully compute with SuperLU on ARM Mac's (UMFPACK Advised)

Due to the relatively coarse mesh, the resonance frequency is lower than in reality (expected around 1.59GHz)
"""

# --- Unit and simulation parameters --------------------------------------
mm = 0.001              # meters per millimeter

# --- Antenna geometry dimensions ----------------------------------------
# Array parameters
patch_widths = [13.4, 20.2, 23.4, 20.2, 13.4]  # mm - widths for 5 patches
patch_lengths = [15.1, 14.5, 14.4, 14.5, 15.1]  # mm - lengths for 5 patches
wline = 3.9 * mm        # feed line width
lline_first = 24.2 * mm # first feed line length
lline_rest = 14.5 * mm  # subsequent feed line lengths

# Convert patch dimensions to meters
patch_widths = [w * mm for w in patch_widths]
patch_lengths = [L * mm for L in patch_lengths]

# Substrate dimensions
wsub = 40 * mm         # substrate width (increased for array)
hsub = 180 * mm         # substrate length (increased for array)
th = 1.524 * mm         # substrate thickness
Rair = 100 * mm         # air sphere radius (increased for larger structure)

# Refined frequency range for antenna resonance around 1.54–1.6 GHz
f1 = 5.3e9             # start frequency
f2 = 6.3e9             # stop frequency

# --- Create simulation object -------------------------------------------
model = em.Simulation('SeriesFeedPatchArray', save_file=True)

model.check_version("2.2.1") # Checks version compatibility.

# --- Define geometry primitives -----------------------------------------
# Substrate block centered at origin in XY, thickness in Z (negative down)
dielectric = em.geo.Box(wsub, hsub, th,
                        position=(-wsub/2, -hsub/2, -th))

# Air box above substrate (Z positive)
air = em.geo.Sphere(Rair).background()
# Background makes sure no materials of overlapping domains are overwritten

# Ground plane
ground = (em.geo.XYPlate(wsub, hsub, position=(-wsub/2, -hsub/2, -th))
         .set_material(em.lib.PEC))

# --- Build series-fed patch array using chaining ------------------------
# Starting position for the array (bottom of substrate, centered in X)
y_start = -hsub/2
current_y = y_start

# Create the complete array geometry by chaining patches and feed lines
# Start with first feed line
array_geometry = em.geo.XYPlate(wline, lline_first,
                               position=(-wline/2, current_y, 0))
current_y += lline_first

# Add all 5 patches with their connecting feed lines
for i in range(5):
    w = patch_widths[i]
    L = patch_lengths[i]

    # Add patch centered on feed line using em.geo.add()
    patch = em.geo.XYPlate(w, L, position=(-w/2, current_y, 0))
    array_geometry = em.geo.add(array_geometry, patch)
    current_y += L

    # Add feed line after patch (except after the last patch)
    if i < 4:  # Only 4 feed lines after the first one
        feedline = em.geo.XYPlate(wline, lline_rest, position=(-wline/2, current_y, 0))
        array_geometry = em.geo.add(array_geometry, feedline)
        current_y += lline_rest

# Set material for entire array structure
array_geometry.set_material(em.lib.PEC)

# Plate defining lumped port geometry at the bottom feed line
port = em.geo.Plate(
    np.array([-wline/2, y_start, -th]),          # lower port corner
    np.array([wline, 0, 0]),                     # width vector along X
    np.array([0, 0, th])                         # height vector along Z
)

# --- Assign materials and simulation settings ---------------------------
# Dielectric material with some transparency for display
dielectric.set_material(em.Material(3.0, color="#207020", opacity=0.9))

# Mesh resolution: fraction of wavelength (larger = coarser mesh = less memory)
model.mw.set_resolution(0.15)

# Frequency sweep across the resonance
model.mw.set_frequency_range(f1, f2, 11)

# --- Combine geometry into simulation -----------------------------------
model.commit_geometry()

# --- Mesh refinement settings --------------------------------------------
# Finer boundary mesh on patch edges for accuracy
model.mesher.set_boundary_size(array_geometry, 1.5 * mm)
# Refined mesh on port face for excitation accuracy
model.mesher.set_face_size(port, 1 * mm)

# --- Generate mesh and preview ------------------------------------------
model.generate_mesh()             # build the finite-element mesh
model.view(selections=[port])     # show the mesh around the port

# --- Boundary conditions ------------------------------------------------
# Define lumped port with specified orientation and impedance
port_bc = model.mw.bc.LumpedPort(
    port, 1,
    width=wline, height=th,
    direction=em.ZAX, Z0=50
)

# Predefining selection
# The outside of the air box for the absorbing boundary
boundary_selection = air.boundary()
# The patch array and ground surface for PEC
pec_selection = em.select(array_geometry, ground)

# Assigning the boundary conditions
abc = model.mw.bc.AbsorbingBoundary(boundary_selection)
# --- Run frequency-domain solver ----------------------------------------
model.view(plot_mesh=True, volume_mesh=False)

# Try PARDISO (fast and memory efficient) or remove line to let emerge auto-select
try:
    model.set_solver(em.EMSolver.PARDISO)
    print("Using PARDISO solver")
except:
    try:
        model.set_solver(em.EMSolver.SUPERLU)
        print("Using SUPERLU solver")
    except:
        print("Using default solver")

if model.cache_run():
    data = model.mw.run_sweep(harddisc_threshold=10e3,
                              harddisc_path="./series_feed_patch_array_harddisc")
data = model.data.mw

# --- Post-process S-parameters ------------------------------------------
freqs = data.scalar.grid.freq
freq_dense = np.linspace(f1, f2, 1001)
S11 = data.scalar.grid.model_S(1, 1, freq_dense)# reflection coefficient
plot_sp(freq_dense, S11)                        # plot return loss in dB
smith(S11, f=freq_dense, labels='S11')          # Smith chart of S11

# --- Export S1P Touchstone file -------------------------------------------
data.scalar.grid.export_touchstone('series_feed_patch_array',
                                   format='RI', funit='GHZ',
                                   dense_freq=freq_dense)

# --- Far-field radiation pattern ----------------------------------------
# Extract 2D cut at phi=0 plane and plot E-field magnitude
ff1 = data.field.find(freq=5.8e9)\
    .farfield_2d((0, 0, 1), (1, 0, 0), boundary_selection)
ff2 = data.field.find(freq=5.8e9)\
    .farfield_2d((0, 0, 1), (0, 1, 0), boundary_selection)

plot_ff(ff1.ang*180/np.pi, [ff1.normE/em.lib.EISO, ff2.normE/em.lib.EISO], dB=True, ylabel='Gain [dBi]')                # linear plot vs theta
plot_ff_polar(ff1.ang, [ff1.normE/em.lib.EISO, ff2.normE/em.lib.EISO], dB=True, dBfloor=-20)          # polar plot of radiation

# --- 3D radiation visualization -----------------------------------------
# Add geometry to 3D display
model.display.add_object(array_geometry)
model.display.add_object(dielectric)
# Compute full 3D far-field and display surface colored by |E|
field = data.field.find(freq=5.8e9)
ff3d = field.farfield_3d(boundary_selection)
surf = ff3d.surfplot('normE', rmax=60 * mm,
                      offset=(0, 0, 20 * mm))

model.display.add_surf(*surf)
model.display.show()
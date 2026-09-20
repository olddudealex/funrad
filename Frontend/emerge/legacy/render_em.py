import sys, io, contextlib
sys.path.insert(0, "c:/Fun/ToyRadar/Frontend/emerge")
import emerge as em, coupler_sim as cs

MM = cs.MM
IMG = r"C:/Fun/ToyRadar/Notes/FunRad/images"

def build(comb, mesh=False, shot="out.png", at_comb=False):
    em.cleanup()
    cs._install_polygon_dedupe()
    g = cs.GEOM["opt"]; prof = cs.MESH["fast"]
    pcbmat = em.Material(er=cs.ER, tand=cs.TAND, color="#217627")
    m = em.Simulation("render")
    cu = em.Material(cond=cs.SIGMA_CU, name="PEC")
    lo = em.geo.PCBNew(cs.H_SUB, unit=MM, material=pcbmat, layers=2,
                       trace_material=cu, thick_traces=True,
                       trace_thickness=g["t_um"]*1e-6)
    z = lo.z(1)
    cs.build(lo, z, g, 3 if comb else 0, comb=comb, at_comb=at_comb)
    ports = [lo.modal_port(lo.load(t), height=cs.AIR_ABOVE)
             for t in ("p1_end", "p2_end", "p3_end", "p4_end")]
    polies = lo.compile_paths(merge=True)
    lo.determine_bounds(leftmargin=0, rightmargin=0,
                        topmargin=cs.POUR_KEEPOUT+1.0, bottommargin=cs.POUR_KEEPOUT+1.0)
    lo.generate_pcb(True, merge=True); lo.plane(lo.z(0), name="GND")
    lo.generate_air(cs.AIR_ABOVE)
    m.commit_geometry()
    m.mw.set_resolution(prof["resolution"])
    m.mw.set_frequency_range(cs.F_LO, cs.F_HI, 3)
    m.mesher.set_boundary_size(polies, prof["trace"]*MM, growth_rate=1.3)
    for p in ports:
        m.mesher.set_face_size(p, prof["port"]*MM)
    m.generate_mesh()
    m.view(plot_mesh=mesh, volume_mesh=False, opacity=0.45,
           screenshot=f"{IMG}/{shot}", off_screen=True)
    print("wrote", shot, flush=True)

if __name__ == "__main__":
    which = sys.argv[1]
    if which == "comb": build(True, False, "17_Coupler_Geometry_with_Comb.png")
    elif which == "mesh": build(True, True,  "11_Coupler_Mesh.png")
    elif which == "atcomb": build(False, False, "13_Coupler_Geometry_at_Comb_Planes.png",
                                 at_comb=True)
    import os; sys.stdout.flush(); os._exit(0)

"""EMerge model of the pure PCB, including both launch pads and saved tapers.

Default: CAD export only. --mesh adds tetrahedral meshing. --solve is explicit.
All source dimensions are mm; EMerge/Gmsh coordinates are metres.
"""
from pathlib import Path
import argparse
import json
import time
import sys
import numpy as np
import gmsh
import emerge as em
from emerge._emerge.geometry import GeoPolygon, GeoVolume

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
HERE = Path(__file__).resolve().parent
OUT = HERE / 'preview_2layer'
MM = 1e-3
BOTTOM_MM = -.2256  # bottom of L2: -.2104 - .0152
TOP_MM = .035
# Broad-band coverage plus 50 MHz spacing around the measured return-loss dip.
# Includes all eight baseline frequencies for a direct mesh comparison.
FREQUENCIES_GHZ = [.5, 1, 1.5, 2, 2.2, 2.3, 2.4, 2.45, 2.5, 2.55,
                   2.6, 2.65, 2.7, 2.8, 3, 3.5, 4, 5, 5.8, 6]
MESH_MM = dict(substrate=.9, signal_surface=.18, signal_edge=.06, ports=.08)


def clean_points(points):
    """Coalesce <5 um corner segments from KiCad's teardrop polygonization."""
    output = [points[0]]
    for point in points[1:]:
        if np.linalg.norm(np.asarray(point)-output[-1]) >= .005:
            output.append(point)
    if np.linalg.norm(np.asarray(output[-1])-output[0]) < .005:
        output.pop()
    return output


def face_at(points, z, holes=(), name='PCB_polygon'):
    wires = []
    for loop in [points] + list(holes):
        loop = clean_points(loop)
        tags = [gmsh.model.occ.addPoint(x*MM, y*MM, z*MM) for x, y in loop]
        lines = [gmsh.model.occ.addLine(a, b) for a, b in zip(tags, tags[1:]+tags[:1])]
        wires.append(gmsh.model.occ.addWire(lines))
    return GeoPolygon([gmsh.model.occ.addPlaneSurface(wires)], name=name)


def variant_name(layers, port_type, opening=None):
    name=f'{layers}layer_{port_type}'
    if opening:
        name+=f'_open_{opening[0]:g}x{opening[1]:g}mm'
    return name


def build(write_report=True, layers=2, port_type='lumped', opening=None):
    start = time.time()
    OUT.mkdir(exist_ok=True)
    data = json.loads((HERE/'pcb_geometry.json').read_text(encoding='utf-8'))
    em.cleanup()
    model = em.Simulation(f'Coupon10mm_{layers}layers_{port_type}')
    bottom = BOTTOM_MM if layers == 2 else -1.3058  # bottom of 15.2 µm L3
    modal = port_type == 'modal'
    pcb_x, pcb_length = (-5., 30.16) if modal else (0., 20.16)
    copper = em.Material(name='Copper', cond=5.8e7,color='#c87b30')
    fr4 = em.Material(name='FR4_er4p5_tand0p02', er=4.5, tand=.02,color='#72b18d',opacity=.15)
    air_material = em.Material(name='Air', er=1,opacity=0)
    air = em.geo.Box(30.16*MM, 26*MM, 11.5862*MM,
                     position=(-5*MM,-13*MM,-6.5512*MM), name='Surrounding_air').set_material(air_material).prio_set(0)
    pcb = em.geo.Box(pcb_length*MM,16*MM,-bottom*MM,
                     position=(pcb_x*MM,-8*MM,bottom*MM),name='FR4_substrate').set_material(fr4).prio_set(10)
    pieces, signal = [], None
    for layer in data['layers']:
        retained = ('F.Cu','In1.Cu') if layers == 2 else ('F.Cu','In1.Cu','In2.Cu')
        if layer['name'] not in retained:
            continue
        for i, region in enumerate(layer['copper']):
            face = face_at(region['outer'], layer['z_mm'], region['holes'],
                           name=layer['name']+'_outline_'+str(i))
            dz = layer['thickness_mm'] * (1 if layer['name']=='F.Cu' else -1)
            solid = em.geo.extrude(face, dz=dz*MM).set_material(copper).prio_set(20)
            solid.name = layer['name']+'_'+('signal' if region['net']!='GND_1' else 'ground')+'_'+str(i)
            pieces.append(solid)
            if layer['name']=='F.Cu' and region['net']!='GND_1':
                assert signal is None
                signal = solid
    barrels, drills = [], []
    for via in data['vias']:
        x, y = via['xy_mm']
        radius = via['drill_mm']/2
        barrels.append(gmsh.model.occ.addCylinder(x*MM,y*MM,bottom*MM,0,0,(TOP_MM-bottom)*MM,(radius+.025)*MM))
        drills.append(gmsh.model.occ.addCylinder(x*MM,y*MM,bottom*MM,0,0,(TOP_MM-bottom)*MM,radius*MM))
    barrel_obj=GeoVolume(barrels,name='Ground_via_barrels').set_material(copper).prio_set(20)
    drill_obj=GeoVolume(drills,name='Ground_via_drill_air').set_material(air_material).prio_set(30)
    pieces.append(barrel_obj)
    if modal:
        # Artificial uniform access lines, not SMA connector models.
        # Match the pad width so no extra narrow-to-wide step is introduced.
        for number, (xa, xb) in enumerate(((-5., .31), (19.85, 25.16)), 1):
            feed = em.geo.Box((xb-xa)*MM,1.2*MM,TOP_MM*MM,
                              position=(xa*MM,-.6*MM,0),name=f'Feed_{number}').set_material(copper).prio_set(21)
            pieces.append(feed)
        for layer in data['layers']:
            if layer['name'] not in retained or layer['name']=='F.Cu':
                continue
            for number, (xa, xb) in enumerate(((-5., .6), (19.56, 25.16)), 1):
                ext=em.geo.Box((xb-xa)*MM,6*MM,layer['thickness_mm']*MM,
                               position=(xa*MM,-3*MM,(layer['z_mm']-layer['thickness_mm'])*MM),
                               name=f'{layer["name"]}_feed_ground_{number}').set_material(copper).prio_set(21)
                pieces.append(ext)
    if opening:
        width,length=opening
        # Relief is under the wide pads only. Also cut the overlapping L2
        # feed-ground extensions, so they cannot accidentally fill the windows.
        intervals=[(.28,.28+length),(19.88-length,19.88)]
        for i,solid in enumerate(pieces):
            if not solid.name.startswith('In1.Cu'):
                continue
            name=solid.name
            for xa,xb in intervals:
                tool=em.geo.Box((xb-xa)*MM,width*MM,.05*MM,
                                position=(xa*MM,-width/2*MM,-.24*MM))
                solid=em.geo.remove(solid,tool).set_material(copper)
            solid.name=name
            pieces[i]=solid.prio_set(21 if 'feed_ground' in name else 20)
    ports=[]
    port_x = [-5., 25.16] if modal else [.4, 19.76]
    for number,x in enumerate(port_x,1):
        half_width, top = (3., 2.5) if modal else (.6, 0.)
        coords=[(x,-half_width,-.2104),(x,half_width,-.2104),
                (x,half_width,top),(x,-half_width,top)]
        pts=[gmsh.model.occ.addPoint(*(np.array(p)*MM)) for p in coords]
        lines=[gmsh.model.occ.addLine(a,b) for a,b in zip(pts,pts[1:]+pts[:1])]
        port=GeoPolygon([gmsh.model.occ.addPlaneSurface([gmsh.model.occ.addWire(lines)])],name=f'P{number}_{port_type}')
        ports.append(port)
    model.mw.set_resolution(.12)
    model.mw.set_frequency(np.asarray(FREQUENCIES_GHZ)*1e9)
    model.commit_geometry()
    # Explicit open boundary: this is not a metal shielding enclosure.
    model.mw.bc.AbsorbingBoundary(air.boundary(), order=1)
    for number,port in enumerate(ports,1):
        if modal:
            bc=model.mw.bc.ModalPort(port,number,modetype='TEM',mixed_materials=True)
            bc.set_integration_line((port_x[number-1]*MM,0,0),
                                    (port_x[number-1]*MM,0,-.2104*MM))
        else:
            model.mw.bc.LumpedPort(port,number,width=1.2*MM,height=.2104*MM,direction=(0,0,1),Z0=50)
    gmsh.write(str(OUT/'coupon.brep'))
    gmsh.write(str(OUT/'coupon.geo_unrolled'))
    report=dict(solver_started=False,source=data['board'],source_sha256=data['board_sha256'],
                geometry_seconds=time.time()-start, units='mm in source; metres in BREP/MSH',
                layers=list(retained),board_mm=[20.16,16,TOP_MM-bottom],
                simulated_substrate_x_mm=[pcb_x,pcb_x+pcb_length],port_type=port_type,
                l2_opening_mm=list(opening) if opening else None,
                signal_pad_mm=[4.8,1.2],trace_width_mm=.37,
                frequencies_GHz=FREQUENCIES_GHZ,
                port_x_mm=port_x,port_width_mm=6 if modal else 1.2,
                port_height_mm=2.7104 if modal else .2104,
                uniform_feed_length_mm=5.28 if modal else 0.,
                reference_planes='outer feed ends; not de-embedded' if modal else 'internal lumped sheets',
                er=4.5,tand=.02,copper_conductivity_S_per_m=5.8e7,
                air_box_mm=[[-5,25.16],[-13,13],[-6.5512,5.035]],
                notes=['Pure PCB: connector bodies, pins, solder and panel break-off tabs omitted.',
                       'Saved KiCad copper zones include the existing tapers/teardrops.',
                       'Consecutive polygon corner points closer than 5 um are coalesced for OCC meshing.',
                       'Only F.Cu, top dielectric and L2 retained; original layer thicknesses. No core, L3 or B.Cu.',
                       'Ground barrels terminate at the bottom of L2; via wall assumed 25 um.',
                       'Ideal internal lumped ports connect pads to L2; a connector launch is not being simulated.',
                       'No soldermask; copper conductivity and FR4 loss included.',
                       'CAD er=4.5 is used; earlier coupler models used er=4.4.',
                       'First-order absorbing outer boundary; air-box and mesh convergence remain to be checked.'])
    if write_report:
        report['notes']=[n for n in report['notes'] if not n.startswith(('Only F.Cu', 'Ground barrels', 'Ideal internal'))]
        report['notes'] += [f'Retained layers: {list(retained)}; vias end at z={bottom} mm.',
                            'Symmetric L2 openings beneath signal pads; L3 intact.' if opening else 'L2 is intact.']
        if modal:
            report['notes'] += ['Modal ports at outer ends of artificial 1.2 mm-wide feed extensions.',
                                'Native modal impedance must be checked; report 50-ohm S separately.',
                                'Feed extensions must be de-embedded before quantitative comparison at coupon pad edges.']
        (OUT/'geometry.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return model,signal,pieces,ports,pcb,report


def make_mesh(model,signal,pieces,ports,pcb,report):
    start=time.time()
    model.mesher.set_domain_size(pcb,MESH_MM['substrate']*MM)
    model.mesher.set_boundary_size(signal,MESH_MM['signal_surface']*MM,growth_rate=1.4,max_size=1.2*MM)
    model.mesher.set_trace_refinement(signal.face('-z'),qualtity_factor=2,min_size=MESH_MM['signal_edge']*MM,
                                     edge_size=MESH_MM['signal_edge']*MM,growth_rate=1.5)
    for feed in [p for p in pieces if p.name.startswith('Feed_')]:
        model.mesher.set_boundary_size(feed,MESH_MM['signal_surface']*MM,growth_rate=1.4,max_size=1.2*MM)
        model.mesher.set_trace_refinement(feed.face('-z'),qualtity_factor=2,
                                         min_size=.06*MM,edge_size=.06*MM,growth_rate=1.5)
    port_size=.25 if report.get('port_type')=='modal' else MESH_MM['ports']
    for port in ports:
        model.mesher.set_face_size(port,port_size*MM)
    model.generate_mesh()
    nodes=gmsh.model.mesh.getNodes()[0]
    types,tags,_=gmsh.model.mesh.getElements(3)
    report.update(mesh_seconds=time.time()-start,nodes=int(len(nodes)),
                  tetrahedra=int(sum(len(t) for t in tags)),
                  mesh_settings_mm=dict(MESH_MM,ports=port_size),
                  mesh_name=f'Mesh {1000*MESH_MM["signal_edge"]:g} µm')
    (OUT/'geometry.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    (OUT/'mesh.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    gmsh.write(str(OUT/'coupon.msh'))
    gmsh.write(str(OUT/'coupon.vtk'))
    model.view(selections=ports,plot_mesh=False,volume_mesh=False,
               screenshot=str(OUT/'native_geometry.png'),off_screen=True)
    print(json.dumps(report,indent=2),flush=True)


def load_mesh(model, report):
    """Restore this version's saved mesh for native viewing without remeshing."""
    source=json.loads((HERE/'pcb_geometry.json').read_text(encoding='utf-8'))
    assert report['source_sha256']==source['board_sha256'], 'PCB extraction changed: regenerate the mesh'
    gmsh.merge(str(OUT/'coupon.msh'))
    assert len(gmsh.model.mesh.getNodes()[0])==report['nodes'], 'Saved mesh node count mismatch'
    model.mesh._pre_update(model.mesher._get_periodic_bcs())
    model.mesh.exterior_face_tags=model.mesher.domain_boundary_face_tags
    model.state.store_geometry_data()
    print('Loaded existing top/L2 mesh; no remeshing or EM solve.',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mesh',action='store_true')
    parser.add_argument('--layers',type=int,choices=(2,3),default=2,help='Retain top/L2 or top/L2/L3')
    parser.add_argument('--port-type',choices=('lumped','modal'),default='lumped')
    parser.add_argument('--l2-opening',nargs=2,type=float,metavar=('WIDTH_MM','LENGTH_MM'),
                        help='Symmetric rectangular L2 relief under each pad, e.g. 1.6 4.8')
    parser.add_argument('--geometry-image',action='store_true',help='Save a native geometry preview without a frequency solve')
    parser.add_argument('--solve',action='store_true')
    parser.add_argument('--check-modes',action='store_true',help='Solve port cross-sectional modes at 1 GHz only; no 3-D sweep')
    parser.add_argument('--mesh-image',action='store_true',help='Save the native surface-mesh screenshot')
    parser.add_argument('--reuse-mesh',action='store_true',help='Load the saved top/L2 mesh instead of remeshing')
    parser.add_argument('--order',type=int,choices=(1,2),default=1,
                        help='FEM element order; 1 fits this workstation, 2 requires much more RAM')
    viewer=parser.add_mutually_exclusive_group()
    viewer.add_argument('--view',action='store_true',help="Open EMerge's native interactive geometry viewer")
    viewer.add_argument('--view-mesh',action='store_true',help="Open EMerge's native interactive surface-mesh viewer")
    args=parser.parse_args()
    if args.l2_opening:
        if (args.layers,args.port_type)!=(3,'modal'):
            parser.error('--l2-opening requires --layers 3 --port-type modal')
        if not (0<args.l2_opening[0]<3.6 and 0<args.l2_opening[1]<=4.8):
            parser.error('Opening width must be between 0 and 3.6 mm; length between 0 and 4.8 mm.')
    variant = variant_name(args.layers,args.port_type,args.l2_opening)
    if (args.layers,args.port_type)!=(2,'lumped'):
        OUT=HERE/f'preview_{variant}'
    if args.solve and (args.view or args.view_mesh):
        parser.error('Review and solve are separate commands: omit --solve when opening an interactive viewer.')
    mesh_report=OUT/'mesh.json'
    if not mesh_report.exists():
        mesh_report=OUT/'geometry.json'
    saved_report=json.loads(mesh_report.read_text(encoding='utf-8')) if args.reuse_mesh else None
    model,signal,pieces,ports,pcb,report=build(write_report=not args.reuse_mesh,
                                          layers=args.layers,port_type=args.port_type,opening=args.l2_opening)
    if args.reuse_mesh:
        assert saved_report['layers']==report['layers'], 'Saved mesh layer mismatch'
        assert saved_report.get('port_type','lumped')==args.port_type, 'Saved mesh port mismatch'
        assert saved_report.get('l2_opening_mm')==report['l2_opening_mm'], 'Saved mesh opening mismatch'
        report=saved_report
        load_mesh(model,report)
    elif args.mesh or args.solve or args.view_mesh or args.check_modes or args.mesh_image:
        make_mesh(model,signal,pieces,ports,pcb,report)
    if args.geometry_image:
        model.view(selections=ports,plot_mesh=False,volume_mesh=False,
                   screenshot=str(OUT/'native_geometry.png'),off_screen=True)
    if args.mesh_image:
        model.view(selections=ports,plot_mesh=True,volume_mesh=False,
                   screenshot=str(OUT/'native_mesh.png'),off_screen=True)
    if args.check_modes:
        if args.port_type!='modal':
            parser.error('--check-modes requires --port-type modal')
        from emerge._emerge.physics.microwave.bcs.port_bcs import ModalPort
        model.mw.set_basis_space(element_order=args.order)
        modal_checks=[]
        for bc in model.mw.bc.oftype(ModalPort):
            model.mw.modal_analysis(bc,nmodes=1,direct=False,TEM=True,freq=1e9)
            mode=bc.get_modes(2*np.pi*1e9/299792458.)[0]
            modal_checks.append(dict(port=bc.port_number,f_GHz=1.,
                                     Z0_real=float(np.real(mode.Z0)),Z0_imag=float(np.imag(mode.Z0)),
                                     neff_real=float(np.real(mode.neff)),neff_imag=float(np.imag(mode.neff))))
        (OUT/'port_modes.json').write_text(json.dumps(modal_checks,indent=2)+'\n',encoding='utf-8')
        print('Cross-sectional modes only:',json.dumps(modal_checks),flush=True)
    if args.view or args.view_mesh:
        from .native_view import interactive_view
        interactive_view(model,selections=ports,plot_mesh=args.view_mesh,volume_mesh=False)
    if args.solve:
        model.mw.set_basis_space(element_order=args.order)
        report.update(solver_started=True,status='running',element_order=args.order,
                      frequency_group_size=1,frequencies_GHz=FREQUENCIES_GHZ)
        (OUT/'geometry.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        # Assemble and solve one frequency at a time rather than retaining
        # all the large sparse matrices on a 32 GB workstation.
        result=model.mw.run_sweep(parallel=False,frequency_groups=1)
        grid=result.scalar.grid
        from emerge._emerge.physics.microwave.microwave_data import renormalise_s
        result_name='result_2layer' if (args.layers,args.port_type)==(2,'lumped') else f'result_{variant}'
        smat, z0, beta = grid.Smat, np.asarray(grid.Z0), np.asarray(grid.beta)
        pad_smat=smat
        if args.port_type=='modal':
            # EMerge uses exp(-j beta x). Move both reference planes inward
            # through the uniform feed to the original outer pad edges.
            feed_phase=np.exp(1j*beta*report['uniform_feed_length_mm']*MM)
            pad_smat=smat*feed_phase[:,:,None]*feed_phase[:,None,:]
            report['deembedded_reference_x_mm']=[.28,19.88]
            report['reference_planes']='outer coupon pad edges; uniform feeds de-embedded'
        np.savez(HERE/f'{result_name}.npz',f=np.asarray(grid.freq),Smat=smat,
                 Smat50=renormalise_s(smat,z0,50.),
                 Smat_pad=pad_smat,Smat50_pad=renormalise_s(pad_smat,z0,50.),
                 Z0=z0,beta=beta)
        report.update(status='completed')
        (OUT/'geometry.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        # Preserve solve metadata even if a later CAD preview overwrites its report.
        (HERE/f'{result_name}.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    else:
        print('PREVIEW ONLY: no 3-D electromagnetic frequency sweep started.',flush=True)

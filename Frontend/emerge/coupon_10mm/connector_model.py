"""BWSMA-KE-P001 + original coupon: preview or explicitly requested EM sweep.

Run from Frontend/emerge: python -m coupon_10mm.connector_model --images
--l2-opening WIDTH LENGTH removes L2 copper beneath both signal pads (mm).
--l3-opening adds matching local L3 clearances; Bottom is always retained.
--solve runs an explicit sweep; viewers never solve.
All dimensions below are millimetres; the CAD uses metres.
"""
from dataclasses import dataclass, asdict
import argparse
import json
import time
import numpy as np
import gmsh
import emerge as em
from emerge._emerge.geometry import GeoVolume
from .model import HERE, MM, TOP_MM, FREQUENCIES_GHZ, face_at
from .native_view import interactive_view

OUT = HERE / 'preview_coax'
DRAWING = 'https://www.es.co.th/Schemetic/PDF/BWSMA-KE-P001_EN.PDF'


@dataclass(frozen=True)
class Connector:
    # Drawing / repository STEP dimensions.
    flange_width: float = 6.5
    flange_length: float = 1.5
    barrel_radius: float = 2.65
    exposed_pin_radius: float = .45
    leg_width: float = .9
    leg_length: float = 4.
    ground_y: float = 2.55
    ground_z_spacing: float = 2.5
    # Placement / internal RF assumptions, NOT manufacturer dimensions.
    rear_gap: float = .10
    axis_z: float = .485  # pin underside tangent to top pad at z=.035
    coax_length: float = 8.  # truncate before mating socket / threads
    ptfe_er: float = 2.1
    bore_radius: float = 2.
    pin_taper_length: float = 1.

    @property
    def inner_radius(self):
        # Ideal homogeneous 50-ohm coax, NOT an extracted connector dimension.
        return self.bore_radius / np.exp(50*np.sqrt(self.ptfe_er)/60)


CONNECTOR = Connector()
MESH_MM = dict(substrate=.9, signal_surface=.18, signal_edge=.06,
               connector_surface=.45, coax_port=.22)
# First-order refinement check; fixed physical targets in mm, not a new geometry.
REFINED_MESH_MM = dict(substrate=.75, signal_surface=.15, signal_edge=.045,
                       connector_surface=.375, coax_port=.18)
FINER_MESH_MM = dict(substrate=.6, signal_surface=.12, signal_edge=.035,
                     connector_surface=.3, coax_port=.15)
FLATNESS_FREQUENCIES_GHZ=[round(5.3+.1*k,10) for k in range(11)]


def check_geometry(signal,pieces,ports):
    """Check CAD connectivity and port areas without solving any fields."""
    metal={t for p in pieces if 'PTFE' not in p.name for t in p.tags}
    faces={t:{q for _,q in gmsh.model.getBoundary([(3,t)],oriented=False)} for t in metal}
    remaining=set(metal)
    components=[]
    while remaining:
        todo=[remaining.pop()]
        component=set(todo)
        while todo:
            t=todo.pop()
            neighbours={u for u in remaining if faces[t]&faces[u]}
            component|=neighbours
            todo.extend(neighbours)
            remaining-=neighbours
        components.append(component)
    assert len(components)==2, 'Expected separate continuous signal and ground networks'
    assert sum(set(signal.tags).issubset(c) for c in components)==1
    expected=np.pi*(CONNECTOR.bore_radius**2-CONNECTOR.inner_radius**2)
    areas=[sum(gmsh.model.occ.getMass(2,t) for t in p.tags)/MM**2 for p in ports]
    assert np.allclose(areas,expected), 'Modal planes must be complete coax annuli'
    return dict(continuous_metal_networks=2,signal_ground_separate=True,
                port_areas_mm2=areas,expected_annulus_area_mm2=expected)


def box(xa, xb, ya, yb, za, zb, name, material, priority=20):
    return em.geo.Box((xb-xa)*MM, (yb-ya)*MM, (zb-za)*MM,
                      position=(xa*MM,ya*MM,za*MM),name=name).set_material(material).prio_set(priority)


def cylinder(xa, xb, radius, z, name):
    tag=gmsh.model.occ.addCylinder(xa*MM,0,z*MM,(xb-xa)*MM,0,0,radius*MM)
    return GeoVolume([tag],name=name)


def variant_paths(opening=None,transition='taper',l3_opening=False):
    suffix=f'open_{opening[0]:g}x{opening[1]:g}mm' if opening else 'intact'
    if transition=='step':suffix+='_step'
    if l3_opening:suffix+='_l3_open'
    return (HERE/f'preview_coax_{suffix}' if opening or transition=='step' else HERE/'preview_coax',
            f'result_coax_{suffix}')


def step_signal_outline():
    """Keep 4.8 x 1.2 mm pads; join them with a 10 x 0.37 mm strip.

    The shoulders are at the original pad inner edges, x=5.08 and 15.08 mm.
    No pad or connector is moved. This replaces only the two taper regions.
    """
    return [[.28,.6],[5.08,.6],[5.08,.185],[15.08,.185],[15.08,.6],[19.88,.6],
            [19.88,-.6],[15.08,-.6],[15.08,-.185],[5.08,-.185],[5.08,-.6],[.28,-.6]]


def check_openings(pieces,opening,l3_opening=False):
    """Copper occupancy at window centres, pad edges, tapers and ground tabs."""
    if not opening:return {}
    width,length=opening
    def inside(prefix,point):
        return any(gmsh.model.isInside(3,t,np.array(point)*MM)
                   for p in pieces if p.name.startswith(prefix) for t in p.tags)
    centres=[.28+length/2,19.88-length/2]
    intervals=((.28,.28+length),(19.88-length,19.88))
    inset=min(.1,length/4)
    checks=dict(L2_empty_at_centres=all(not inside('In1.Cu',(x,0,-.218)) for x in centres),
                L3_centre_occupancy_matches_design=all(
                    inside('In2.Cu',(x,0,-1.298))== (not l3_opening) for x in centres),
                L2_present_under_ground_tabs=all(inside('In1.Cu',(x,2.55,-.218)) for x in (2.68,17.48)),
                L2_present_under_pin_inner_edges=all(inside('In1.Cu',(x,y,-.218))
                    for x in (2.68,17.48) for y in (-2.11,2.11)),
                L2_transition_occupancy_matches_windows=all(
                    inside('In1.Cu',(x,0,-.218))==not_in_window
                    for x in (5.5,14.66)
                    for not_in_window in [not any(a<x<b for a,b in intervals)]),
                L2_empty_near_inner_window_edges=all(not inside('In1.Cu',(x,0,-.218))
                    for x in (.28+length-inset,19.88-length+inset)),
                L2_present_past_inner_window_edges=all(inside('In1.Cu',(x,0,-.218))
                    for x in (.28+length+.1,19.88-length-.1)),
                L2_present_beside_windows=all(inside('In1.Cu',(x,width/2+.1,-.218)) for x in centres))
    if l3_opening:
        checks.update(
            L3_empty_near_inner_window_edges=all(not inside('In2.Cu',(x,0,-1.298))
                for x in (.28+length-inset,19.88-length+inset)),
            L3_present_past_inner_window_edges=all(inside('In2.Cu',(x,0,-1.298))
                for x in (.28+length+.1,19.88-length-.1)),
            L3_present_beside_windows=all(inside('In2.Cu',(x,width/2+.1,-1.298)) for x in centres),
            L3_present_under_ground_pins=all(inside('In2.Cu',(x,y,-1.298))
                for x in (2.68,17.48) for y in (-2.55,2.55)),
            Bottom_present_beneath_windows=all(inside('B.Cu',(x,0,-1.53)) for x in centres))
    assert all(checks.values()), f'L2 cutout geometry check failed: {checks}'
    return checks


def build(opening=None,transition='taper',frequencies_ghz=None,result_suffix='',l3_opening=False,pcb_er=4.5):
    """Separate actual PCB polygons, simplified mechanics, and modal planes."""
    # Keep material variants separate for both CLI and direct Python callers.
    if pcb_er!=4.5:result_suffix+='_er'+f'{pcb_er:g}'.replace('.','p')
    OUT.mkdir(exist_ok=True)
    em.cleanup()
    if l3_opening and not opening:raise ValueError('An L3 opening requires the matching L2 opening')
    model=em.Simulation('Coupon10mm_BWSMA_coax_'+variant_paths(opening,transition,l3_opening)[1])
    copper=em.Material(name='Copper',cond=5.8e7,color='#bd873c')
    fr4=em.Material(name='FR4',er=pcb_er,tand=.02,color='#75aa90',opacity=.12)
    ptfe=em.Material(name='PTFE_assumed',er=CONNECTOR.ptfe_er,color='#e7e5d8',opacity=.55)
    air_mat=em.Material(name='Air',er=1,opacity=0)
    c=CONNECTOR
    left_port=-c.rear_gap-c.coax_length
    right_port=20.16-left_port
    air=box(left_port,right_port,-13,13,-7,9,'Air_box',air_mat,0)
    pcb=box(0,20.16,-8,8,-1.5512,0,'FR4_full_board',fr4,10)
    pieces=[]
    signal=None
    signal_outline=None
    data=json.loads((HERE/'pcb_geometry.json').read_text(encoding='utf-8'))
    for layer in data['layers']:
        for i,region in enumerate(layer['copper']):
            name=layer['name']+('_ground_' if region['net']=='GND_1' else '_signal_')+str(i)
            is_signal=layer['name']=='F.Cu' and region['net']!='GND_1'
            outline=step_signal_outline() if is_signal and transition=='step' else region['outer']
            face=face_at(outline,layer['z_mm'],region['holes'],name=name)
            dz=layer['thickness_mm']*(1 if layer['name']=='F.Cu' else -1)
            solid=em.geo.extrude(face,dz=dz*MM).set_material(copper).prio_set(20)
            solid.name=name
            if opening and (layer['name']=='In1.Cu' or (l3_opening and layer['name']=='In2.Cu')):
                width,length=opening
                for xa,xb in ((.28,.28+length),(19.88-length,19.88)):
                    tool=em.geo.Box((xb-xa)*MM,width*MM,.05*MM,
                                    position=(xa*MM,-width/2*MM,
                                              (-.24 if layer['name']=='In1.Cu' else layer['z_mm']-.03)*MM))
                    solid=em.geo.remove(solid,tool).set_material(copper).prio_set(20)
                    solid.name=name
            pieces.append(solid)
            if is_signal:
                signal=solid
                signal_outline=outline
    barrels,drills=[],[]
    for via in data['vias']:
        x,y=via['xy_mm']; r=via['drill_mm']/2
        args=(x*MM,y*MM,-1.5512*MM,0,0,(TOP_MM+1.5512)*MM)
        barrels.append(gmsh.model.occ.addCylinder(*args,(r+.025)*MM))
        drills.append(gmsh.model.occ.addCylinder(*args,r*MM))
    pieces.append(GeoVolume(barrels,name='Ground_vias').set_material(copper).prio_set(20))
    GeoVolume(drills,name='Via_drill_air').set_material(air_mat).prio_set(40)
    ports=[]
    port_dielectrics=[]
    port_x=[]
    for number in (1,2):
        # u increases inward from each connector rear face onto the PCB.
        rear=-c.rear_gap if number==1 else 20.16+c.rear_gap
        sign=1 if number==1 else -1
        def x(u): return rear+sign*u
        def local_box(ua,ub,ya,yb,za,zb,name):
            return box(*sorted((x(ua),x(ub))),ya,yb,za,zb,f'J{number}_{name}',copper)
        def local_cylinder(ua,ub,r,name):
            return cylinder(x(ua),x(ub),r,c.axis_z,f'J{number}_{name}')

        # Smooth barrel and square flange: bore drilled through both.
        barrel=local_cylinder(-c.coax_length,-c.flange_length,c.barrel_radius,'barrel')
        flange=local_box(-c.flange_length,0,-c.flange_width/2,c.flange_width/2,
                         c.axis_z-c.flange_width/2,c.axis_z+c.flange_width/2,'flange')
        body=em.geo.unite(barrel,flange)
        bore=local_cylinder(-c.coax_length,0,c.bore_radius,'bore_tool')
        body=em.geo.remove(body,bore).set_material(copper).prio_set(20)
        body.name=f'J{number}_shield'
        pieces.append(body)
        # Explicit PTFE annulus, with tapered centre conductor at PCB end.
        cs=em.CS((0,1,0),(0,0,sign),(sign,0,0),np.array((x(-c.coax_length),0,c.axis_z))*MM)
        dielectric=em.geo.CoaxCylinder(c.bore_radius*MM,c.inner_radius*MM,
                                       (c.coax_length-c.pin_taper_length)*MM,cs=cs,
                                       name=f'J{number}_PTFE_uniform').set_material(ptfe).prio_set(12)
        port_dielectrics.append(dielectric);port_x.append(x(-c.coax_length))
        pieces.append(dielectric)
        pin=local_cylinder(-c.coax_length,-c.pin_taper_length,c.inner_radius,'inner_conductor')
        pin.set_material(copper).prio_set(20);pieces.append(pin)
        cone=em.geo.Cone((x(-c.pin_taper_length)*MM,0,c.axis_z*MM),
                         (sign*c.pin_taper_length*MM,0,0),c.inner_radius*MM,c.exposed_pin_radius*MM,
                         name=f'J{number}_pin_taper').set_material(copper).prio_set(20)
        pieces.append(cone)
        # Fill taper surroundings with PTFE; conductor takes priority.
        ptfe_transition=local_cylinder(-c.pin_taper_length,0,c.bore_radius,'PTFE_transition')
        ptfe_transition.set_material(ptfe).prio_set(12);pieces.append(ptfe_transition)
        tail=local_cylinder(0,c.leg_length,c.exposed_pin_radius,'signal_tail')
        tail.set_material(copper).prio_set(20);pieces.append(tail)
        # Ideal solid solder/contact bridges remove tangent-only connections.
        # They model electrical contact, not a measured solder fillet profile.
        pieces.append(local_box(.38,4,-.30,.30,.025,.15,'signal_bond'))
        for row,zc in [('upper',c.axis_z),('lower',c.axis_z-c.ground_z_spacing)]:
            for side,yc in [('near',-c.ground_y),('far',c.ground_y)]:
                pieces.append(local_box(0,c.leg_length,yc-.45,yc+.45,zc-.45,zc+.45,
                                         f'ground_{row}_{side}'))
                za,zb=(.025,.08) if row=='upper' else (-1.60,-1.50)
                pieces.append(local_box(.38,4,yc-.45,yc+.45,za,zb,f'bond_{row}_{side}'))
    model.mw.set_resolution(.12)
    frequencies_ghz=FREQUENCIES_GHZ if frequencies_ghz is None else frequencies_ghz
    model.mw.set_frequency(np.asarray(frequencies_ghz)*1e9)
    model.commit_geometry()
    ports=[d.face('front') for d in port_dielectrics]
    model.mw.bc.AbsorbingBoundary(air.boundary(),order=1)
    for number,port in enumerate(ports,1):
        bc=model.mw.bc.ModalPort(port,number,modetype='TEM',mixed_materials=False)
        bc.set_integration_line((port_x[number-1]*MM,c.inner_radius*MM,c.axis_z*MM),
                                (port_x[number-1]*MM,c.bore_radius*MM,c.axis_z*MM))
    report=dict(connector='BWSMA-KE-P001',status='geometry review; no EM or port-mode solve',
                solver_started=False,units='mm',drawing=DRAWING,source_board_sha256=data['board_sha256'],
                connector_parameters_mm=asdict(c),assumed_uniform_inner_radius_mm=c.inner_radius,
                analytic_uniform_coax_Z0_ohm=60/np.sqrt(c.ptfe_er)*np.log(c.bore_radius/c.inner_radius),
                pcb_layers=[l['name'] for l in data['layers']],board_mm=[20.16,16,1.5862],
                port_x_mm=port_x,air_box_mm=[[left_port,right_port],[-13,13],[-7,9]],
                mesh_targets_mm=MESH_MM,l2_opening_mm=list(opening) if opening else None,
                result_stem=variant_paths(opening,transition,l3_opening)[1]+result_suffix,
                l3_opening_mm=list(opening) if l3_opening else None,
                frequencies_GHz=list(frequencies_ghz),
                pcb_er=pcb_er,pcb_loss_tangent=.02,
                launch_transition=transition,signal_outline_mm=signal_outline,
                assumptions=[('Matching symmetric L2 and L3 cutouts beneath signal pads; bottom ground and connectors unchanged.'
                              if l3_opening else
                              'Symmetric L2 cutouts beneath signal pads; L3, bottom ground and connectors unchanged.'
                              if opening else 'Original intact L2; no ground relief, no artificial PCB feed extensions.'),
                  'Full original PCB stack retained for the lower connector ground contacts.',
                  'Drawing/STEP: 6.5 mm flange, 5.3 mm barrel, 4 mm tails, 0.9 mm pin/legs.',
                  'Placement: rear face 0.1 mm outside board; upper tails rest on top copper.',
                  'Assumed PTFE er=2.1, bore radius 2 mm, ideal 50-ohm centre radius; 1 mm internal taper.',
                  'Coax truncated inside the barrel: mating socket, threads and cable plug omitted.',
                  'Ideal solid contact bridges; actual solder geometry and connector plating omitted.',
                  f'FR4 er={pcb_er:g}, loss tangent 0.02; copper conductivity 5.8e7 S/m; no solder mask.',
                  'Port planes are on coax PTFE annuli; solve status is recorded separately.'])
    report['cad_checks']=check_geometry(signal,pieces,ports)
    report['opening_checks']=check_openings(pieces,opening,l3_opening)
    if transition=='step':
        # Probe the two formerly tapered wings and the extended narrow strip.
        def in_signal(x,y):
            return any(gmsh.model.isInside(3,t,np.array((x,y,.0175))*MM) for t in signal.tags)
        checks=dict(taper_wings_removed=all(not in_signal(x,y) for x in (5.3,14.86) for y in (-.4,.4)),
                    narrow_strip_present=all(in_signal(x,0) for x in (5.3,10.08,14.86)),
                    pads_retained=all(in_signal(x,.5) for x in (4.9,15.26)))
        assert all(checks.values()),f'Step transition check failed: {checks}'
        report['step_checks']=checks
        report['assumptions'].append('Top pads unchanged; both original tapers replaced by abrupt 1.2-to-0.37 mm steps at x=5.08 and 15.08 mm.')
    gmsh.write(str(OUT/'coupon_coax.brep'))
    (OUT/'geometry.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return model,pcb,signal,pieces,ports,report


def mesh(model,pcb,signal,pieces,ports,report):
    """Actual simulation mesh; neither port modes nor frequencies are solved."""
    model.mesher.set_domain_size(pcb,MESH_MM['substrate']*MM)
    model.mesher.set_boundary_size(signal,MESH_MM['signal_surface']*MM,growth_rate=1.4,max_size=1.2*MM)
    model.mesher.set_trace_refinement(signal.face('-z'),qualtity_factor=2,
        min_size=MESH_MM['signal_edge']*MM,edge_size=MESH_MM['signal_edge']*MM,growth_rate=1.5)
    for p in pieces:
        if p.name.startswith('J'):
            model.mesher.set_boundary_size(p,MESH_MM['connector_surface']*MM,growth_rate=1.4,max_size=1.2*MM)
    for p in ports: model.mesher.set_face_size(p,MESH_MM['coax_port']*MM)
    model.generate_mesh()
    gmsh.write(str(OUT/'coupon_coax.msh'))
    report['nodes']=len(gmsh.model.mesh.getNodes()[0])
    report['tetrahedra']=sum(len(t) for t in gmsh.model.mesh.getElements(3)[1])
    (OUT/'mesh.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')


def images(pcb,pieces,ports,opening=None,transition='taper',l3_opening=False):
    """Render actual OCC surfaces; this 2-D tessellation is NOT the FEM mesh."""
    import pyvista as pv
    from .view import surface_mesh
    options=('Mesh.MeshSizeMax','Mesh.MeshSizeMin','Mesh.MeshSizeFromCurvature')
    saved={key:gmsh.option.getNumber(key) for key in options}
    gmsh.option.setNumber('Mesh.MeshSizeMax',.8*MM)
    gmsh.option.setNumber('Mesh.MeshSizeMin',.10*MM)
    gmsh.option.setNumber('Mesh.MeshSizeFromCurvature',24)
    gmsh.model.mesh.generate(2)
    for key,value in saved.items():gmsh.option.setNumber(key,value)
    tags,xyz,_=gmsh.model.mesh.getNodes()
    coords=np.asarray(xyz).reshape(-1,3)/MM
    indices={int(t):i for i,t in enumerate(tags)}
    surfaces=[(p.name,surface_mesh(p.boundary().tags,coords,indices)) for p in [pcb]+pieces]
    port_surfaces=[surface_mesh(p.tags,coords,indices) for p in ports]
    for mode in ('assembly','launch_cutaway','coax_section'):
        plot=pv.Plotter(off_screen=True,window_size=(1600,1000))
        plot.set_background('#f3f5f8')
        for name,surf in surfaces:
            if mode=='coax_section' and not name.startswith('J1'):continue
            if mode=='launch_cutaway':surf=surf.clip(normal=(0,1,0),origin=(0,0,0),invert=False)
            if mode=='coax_section':surf=surf.clip(normal=(1,0,0),origin=(-7.7,0,0),invert=True)
            if not surf.n_cells:continue
            if name.startswith('FR4'):color,alpha='#559d7e',.12
            elif 'PTFE' in name:color,alpha='#ebe8db',.65
            elif name.startswith(('In1','In2','B.Cu')):color,alpha='#698c9c',.22
            else:color,alpha='#c18b3e',1.
            plot.add_mesh(surf,color=color,opacity=alpha,smooth_shading=False)
        for surf in port_surfaces:
            plot.add_mesh(surf,color='#9b3cce',opacity=.9)
        if mode=='assembly':
            plot.camera_position=[(-29,-35,32),(10,0,0),(0,0,1)]
            plot.camera.parallel_scale=23
            title=('10 mm coupon with L2 pad cutouts' if opening else 'Original 10 mm coupon')+' + BWSMA-KE-P001'
            if l3_opening:title='10 mm coupon with matching L2/L3 pad cutouts + BWSMA-KE-P001'
            footer='Copper: gold | PCB grounds: blue | PTFE: ivory | Coax modal planes: purple'
        elif mode=='launch_cutaway':
            plot.camera_position=[(-9,-23,15),(1.8,0,-.4),(0,0,1)]
            plot.camera.parallel_scale=5.2
            title='Left launch cutaway: '+('abrupt step' if transition=='step' else 'original taper')
            footer=('Front half removed; L2 cutouts beneath pads; L3 intact' if opening else
                    'Front half removed for visibility; original L2 intact; full board thickness retained')
            if l3_opening:footer='Front half removed; matching L2/L3 pad cutouts; Bottom intact'
        else:
            plot.camera_position=[(-25,0,.485),(-8,0,.485),(0,0,1)]
            plot.camera.parallel_scale=4.1
            title='P1: uniform coax cross-section (end view)'
            footer=f'Assumed PTFE er=2.1 | a={CONNECTOR.inner_radius:.3f} mm | b=2.000 mm | analytical Z0=50 ohm'
        plot.enable_parallel_projection()
        plot.add_text(title,position='upper_left',font_size=17,color='#233849')
        plot.add_text(footer+'\nGEOMETRY PREVIEW ONLY - no electromagnetic solve',position='lower_left',font_size=12,color='#233849')
        plot.add_axes()
        plot.screenshot(str(OUT/(mode+'.png')))
        plot.close()


def load_mesh(model,report):
    saved=json.loads((OUT/'mesh.json').read_text(encoding='utf-8'))
    for key in ('source_board_sha256','connector_parameters_mm','assumed_uniform_inner_radius_mm',
                'pcb_layers','port_x_mm','mesh_targets_mm'):
        assert saved[key]==report[key], f'Saved mesh mismatch: {key}; regenerate with --mesh'
    assert saved.get('l2_opening_mm')==report.get('l2_opening_mm'), 'Saved mesh cutout mismatch'
    assert saved.get('l3_opening_mm')==report.get('l3_opening_mm'), 'Saved mesh L3 cutout mismatch'
    assert saved.get('launch_transition','taper')==report['launch_transition'], 'Saved mesh transition mismatch'
    gmsh.merge(str(OUT/'coupon_coax.msh'))
    assert len(gmsh.model.mesh.getNodes()[0])==saved['nodes']
    model.mesh._pre_update(model.mesher._get_periodic_bcs())
    model.mesh.exterior_face_tags=model.mesher.domain_boundary_face_tags
    model.state.store_geometry_data()
    report.update(nodes=saved['nodes'],tetrahedra=saved['tetrahedra'])
    print(f'Loaded {saved["tetrahedra"]:,} tetrahedra; no remeshing or solve.',flush=True)


def solve(model,report):
    """One explicit frequency sweep; preserve native and 50-ohm references."""
    from emerge._emerge.physics.microwave.microwave_data import renormalise_s
    result_stem=report['result_stem']
    path=HERE/f'{result_stem}.json'
    model.mw.set_basis_space(element_order=1)
    report.update(status='running',solver_started=True,element_order=1,
                  frequency_group_size=1,
                  reference_planes='coax annuli x=-8.10 and 28.26 mm; connectors included')
    path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    start=time.perf_counter()
    try:
        # The ports are uniform PTFE coax, regardless of PCB epsilon-r.
        # Give the iterative eigenmode solver the analytical TEM index instead
        # of its generic estimate. This changes the search target, not the port.
        from emerge._emerge.physics.microwave.bcs.port_bcs import ModalPort
        report['port_mode_target_neff']=float(np.sqrt(CONNECTOR.ptfe_er))
        for port in model.mw.bc.oftype(ModalPort):
            model.mw.modal_analysis(port,nmodes=1,direct=False,TEM=True,
                target_neff=report['port_mode_target_neff'],
                freq=float(np.mean(report['frequencies_GHz']))*1e9)
        result=model.mw.run_sweep(parallel=False,frequency_groups=1)
        grid=result.scalar.grid
        f=np.asarray(grid.freq).reshape(-1)
        s,z,beta=np.asarray(grid.Smat),np.asarray(grid.Z0),np.asarray(grid.beta)
        assert s.shape==(len(report['frequencies_GHz']),2,2) and np.all(np.isfinite(s))
        assert np.allclose(f,np.asarray(report['frequencies_GHz'])*1e9)
        np.savez(HERE/f'{result_stem}.npz',f=f,Smat=s,Z0=z,beta=beta,
                 Smat50=renormalise_s(s,z,50.))
        report.update(status='completed',solve_seconds=time.perf_counter()-start)
    except Exception as error:
        report.update(status='failed',error=repr(error),solve_seconds=time.perf_counter()-start)
        raise
    finally:
        path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')


def main():
    global OUT, MESH_MM
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--images',action='store_true',help='CAD illustrations, no FEM solve')
    parser.add_argument('--mesh',action='store_true',help='Generate FEM mesh without solving')
    parser.add_argument('--reuse-mesh',action='store_true',help='Load the matching saved FEM mesh')
    parser.add_argument('--mesh-profile',choices=('standard','refined','finer'),default='standard',
                        help='Standard targets or finer first-order mesh; saved in separate files')
    parser.add_argument('--mesh-image',action='store_true',help='Save a native FEM surface-mesh screenshot')
    parser.add_argument('--l2-opening',nargs=2,type=float,metavar=('WIDTH_MM','LENGTH_MM'),
                        help='Two symmetric cutouts under pads; e.g. 1.6 4.8. L3 retained by default.')
    parser.add_argument('--l3-opening',action='store_true',
                        help='Also remove L3 copper in the matching L2 windows; Bottom stays intact')
    parser.add_argument('--pcb-er',type=float,default=4.5,
                        help='Relative permittivity of the homogeneous PCB substrate; tan(delta) remains 0.02')
    parser.add_argument('--transition',choices=('taper','step'),default='taper',
                        help='Original KiCad tapers or abrupt 1.2-to-0.37 mm shoulders at pad inner edges')
    parser.add_argument('--frequency-grid',choices=('broadband','flatness','broadband-check'),default='broadband',
                        help='Original 20 points; 11 flatness points; or 0.5–6.5 GHz check including both earlier grids')
    parser.add_argument('--solve',action='store_true',help='Explicit first-order EM sweep')
    viewer=parser.add_mutually_exclusive_group()
    viewer.add_argument('--view',action='store_true',help='EMerge native interactive geometry')
    viewer.add_argument('--view-mesh',action='store_true',help='Generate FEM mesh and keep native viewer open')
    args=parser.parse_args()
    if not np.isfinite(args.pcb_er) or args.pcb_er<=1:parser.error('--pcb-er must be finite and greater than 1')
    max_width=2*(CONNECTOR.ground_y-CONNECTOR.leg_width/2)
    if args.l2_opening and not (0<args.l2_opening[0]<=max_width+1e-12 and 0<args.l2_opening[1]<=6.0):
        parser.error(f'Cutout width must be >0 and <= {max_width:g} mm (inner ground-pin edges); length >0 and <=6.0 mm (through taper).')
    if args.l3_opening and not args.l2_opening:parser.error('--l3-opening requires --l2-opening WIDTH LENGTH')
    OUT,_=variant_paths(args.l2_opening,args.transition,args.l3_opening)
    if args.mesh_profile!='standard':
        MESH_MM=({'refined':REFINED_MESH_MM,'finer':FINER_MESH_MM}[args.mesh_profile]).copy()
        OUT=OUT.with_name(OUT.name+'_mesh_'+args.mesh_profile)
    if args.solve and (args.view or args.view_mesh or args.images):
        parser.error('Solve and interactive/illustration previews are separate commands.')
    if args.images and (args.mesh or args.reuse_mesh or args.view_mesh or args.mesh_image):
        parser.error('Save CAD images and inspect the FEM mesh in separate commands.')
    frequencies=FLATNESS_FREQUENCIES_GHZ if args.frequency_grid=='flatness' else FREQUENCIES_GHZ
    suffix='_5p3to6p3GHz' if args.frequency_grid=='flatness' else ''
    if args.frequency_grid=='broadband-check':
        frequencies=sorted(set(FREQUENCIES_GHZ+FLATNESS_FREQUENCIES_GHZ+
                               [round(.5*k,10) for k in range(1,14)]))
        suffix='_0p5to6p5GHz'
    if args.mesh_profile!='standard':suffix+='_mesh_'+args.mesh_profile
    model,pcb,signal,pieces,ports,report=build(args.l2_opening,args.transition,frequencies,suffix,args.l3_opening,args.pcb_er)
    report['mesh_profile']=args.mesh_profile
    if args.images:images(pcb,pieces,ports,args.l2_opening,args.transition,args.l3_opening)
    if args.reuse_mesh:load_mesh(model,report)
    elif args.mesh or args.view_mesh or args.mesh_image or args.solve:mesh(model,pcb,signal,pieces,ports,report)
    if args.mesh_image:
        model.view(selections=ports,plot_mesh=True,volume_mesh=False,
                   screenshot=str(OUT/'native_mesh.png'),off_screen=True)
    if args.view or args.view_mesh:
        interactive_view(model,selections=ports,plot_mesh=args.view_mesh,volume_mesh=False)
    if args.solve:
        solve(model,report)
        print(f'{report["result_stem"]} sweep completed.',flush=True)
    else:
        print('GEOMETRY/MESH REVIEW ONLY. No modal analysis or frequency sweep was run.',flush=True)


if __name__=='__main__': main()

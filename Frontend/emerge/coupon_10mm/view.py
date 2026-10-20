"""Render the committed EMerge geometry using its existing Gmsh surface mesh.

Does not remesh or run a frequency solve. --interactive opens a rotatable view.
"""
import argparse
import json
import numpy as np
import gmsh
import pyvista as pv
from .model import build, HERE, OUT
from . import model as coupon_model


def surface_mesh(tags, coordinates, index):
    faces=[]
    for tag in sorted(set(tags)):
        types, _, blocks=gmsh.model.mesh.getElements(2,int(tag))
        for kind,block in zip(types,blocks):
            _,dim,order,n,_,_=gmsh.model.mesh.getElementProperties(kind)
            if dim!=2:continue
            nodes=np.asarray(block).reshape(-1,n)
            assert kind in (2,9),f'Unexpected surface element type {kind}'
            faces.extend([[3]+[index[int(t)] for t in tri[:3]] for tri in nodes])
    assert faces,'Missing mesh on requested surfaces'
    return pv.PolyData(coordinates,np.asarray(faces,dtype=np.int64).ravel())


def make_views(interactive=False, layers=2, port_type='lumped', opening=None):
    global OUT
    OUT = HERE/'preview_2layer' if (layers,port_type)==(2,'lumped') else HERE/f'preview_{coupon_model.variant_name(layers,port_type,opening)}'
    coupon_model.OUT=OUT
    stats=json.loads((OUT/'geometry.json').read_text(encoding='utf-8'))
    model,signal,pieces,ports,pcb,_=build(write_report=False,layers=layers,port_type=port_type,opening=opening)
    # Rebuilding the same CAD gives the same entity tags. Merge the already
    # generated mesh; do not call model.generate_mesh() or run_sweep().
    gmsh.merge(str(OUT/'coupon.msh'))
    tags,xyz,_=gmsh.model.mesh.getNodes()
    coordinates=np.asarray(xyz).reshape(-1,3)*1000
    index={int(tag):i for i,tag in enumerate(tags)}
    assert len(tags)==stats['nodes'],'Existing mesh does not match the model report'
    meshes=[]
    for obj in pieces:
        meshes.append((obj.name,surface_mesh(obj.boundary().tags,coordinates,index)))
    substrate=surface_mesh(pcb.boundary().tags,coordinates,index)
    feeds=[surface_mesh(port.tags,coordinates,index) for port in ports]
    for which in ['geometry_3d','mesh_3d','mesh_taper']:
        plot=pv.Plotter(off_screen=not (interactive and which=='geometry_3d'),window_size=(1450,950))
        plot.set_background('#f4f6fa')
        show_mesh=which!='geometry_3d'
        for name,mesh in meshes:
            if name.startswith(('F.Cu','Feed_')):
                plot.add_mesh(mesh,color='#c87b30',show_edges=show_mesh,
                              edge_color='#593b22',line_width=.35)
            elif name=='Ground_via_barrels':
                plot.add_mesh(mesh,color='#ac7c37',show_edges=show_mesh,
                              edge_color='#6d5c45',line_width=.3)
            else:
                plot.add_mesh(mesh,color='#7891a2',opacity=.13,
                              show_edges=False)
        plot.add_mesh(substrate,color='#72b18d',opacity=.09,
                      show_edges=False)
        for i,feed in enumerate(feeds):
            plot.add_mesh(feed,color='#a01d89',show_edges=show_mesh,edge_color='#59124f')
        if which=='mesh_taper':
            plot.camera_position=[(5.65,0,20),(5.65,0,0),(0,1,0)]
            plot.enable_parallel_projection()
            plot.camera.parallel_scale=1.4
            title='EMerge: actual surface triangles at the left pad-to-trace taper'
            plot.add_text(f'Taper from KiCad; 0.37 mm trace; edge target {stats["mesh_settings_mm"]["signal_edge"]:g} mm',position='lower_left',font_size=12,color='#253a48')
        else:
            plot.camera_position=[(32,-29,22),(10.08,0,-.65),(0,0,1)]
            plot.enable_parallel_projection()
            plot.camera.parallel_scale=16 if port_type=='modal' else 12
            title='EMerge: 10 mm pure-PCB geometry' if not show_mesh else 'EMerge: actual tetrahedral mesh on the PCB surfaces'
            plot.add_text(f'{stats["nodes"]:,} nodes; {stats["tetrahedra"]:,} tetrahedra; geometry/mesh preview',
                          position='lower_left',font_size=12,color='#253a48')
            positions=np.array([[x,-.9,.5] for x in stats['port_x_mm']])
            labels=[f'P{i}: modal plane' if port_type=='modal' else f'P{i}: 50 ohm' for i in (1,2)]
            plot.add_point_labels(positions,labels,
                                  font_size=16,text_color='#6e145e',point_size=0,shape_opacity=.1,always_visible=True)
        plot.add_text(title,position='upper_left',font_size=17,color='#253a48')
        plot.add_axes()
        plot.screenshot(str(OUT/(which+'.png')))
        if which=='geometry_3d' and interactive:
            plot.show(auto_close=False)
        plot.close()
    # An internal x-z cut shows the volume mesh, rather than only surface facets.
    reader=pv.read(str(OUT/'coupon.vtk'))
    section=reader.slice(normal=(0,1,0),origin=(0,0,0))
    section.points*=1000
    plot=pv.Plotter(off_screen=True,window_size=(1450,700))
    plot.set_background('#f4f6fa')
    plot.add_mesh(section,color='#d8e4ec',show_edges=True,edge_color='#4d6172',line_width=.35)
    plot.camera_position=[(10.08,-30,-.75),(10.08,0,-.75),(0,0,1)]
    plot.enable_parallel_projection();plot.camera.parallel_scale=2.4
    plot.add_text('EMerge: volume-mesh section through signal centre (y = 0)',position='upper_left',font_size=17,color='#253a48')
    plot.add_text('Actual tetrahedron intersections; x and z are in mm',position='lower_left',font_size=12,color='#253a48')
    plot.screenshot(str(OUT/'mesh_section.png'));plot.close()
    print('Rendered existing EMerge geometry and mesh. No electromagnetic solve started.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--interactive',action='store_true')
    parser.add_argument('--layers',type=int,choices=(2,3),default=2)
    parser.add_argument('--port-type',choices=('lumped','modal'),default='lumped')
    parser.add_argument('--l2-opening',nargs=2,type=float,metavar=('WIDTH_MM','LENGTH_MM'))
    args=parser.parse_args()
    make_views(args.interactive,args.layers,args.port_type,args.l2_opening)

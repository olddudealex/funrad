"""Materials, dielectric stack, ground planes, box and port faces.

Config dimensions are mm; EMerge solid dimensions are metres. Exterior faces
default to PEC. ModalPort overrides are assigned by the driver after meshing.
"""
import emerge as em
import numpy as np

AIR_HEIGHT_MM = 2.5
SIDE_MARGIN_MM = 2.0

def create_simulation(config, name):
    """Create materials and the top-copper layouter; no geometry is built yet."""
    mat = em.Material(er=config['er'], tand=config['tand'])
    # EMerge assigns surface impedance to conducting volumes not named PEC.
    # Keep the original default and hashes unchanged; opt in explicitly per run.
    copper = em.Material(cond=config.get('conductivity',5.8e7),
                         name='Copper' if config.get('copper_loss',False) else 'PEC')
    model = em.Simulation(name)
    layouter = em.geo.PCBNew(config['h'], unit=1e-3, material=mat, layers=2,
                       trace_material=copper, thick_traces=True, trace_thickness=config['t']*1e-3)
    return model, layouter, copper

def build_domain(layouter, config, copper, polygons, names):
    """Extrude paths, add substrate/ground, and define enclosure and ports.

    The optional lower stack and L2 opening reproduce the ground-control runs.
    Default top copper spans z=0..t; L2 top must be at z=-h.
    """
    ports = [layouter.modal_port(layouter.load(n), height=AIR_HEIGHT_MM, width=config['port_width']) for n in names]
    metal = layouter.compile_paths(merge=True)
    layouter.determine_bounds(leftmargin=0, rightmargin=0, topmargin=SIDE_MARGIN_MM, bottommargin=SIDE_MARGIN_MM)
    pcb = layouter.generate_pcb(True, merge=True)
    # PCBNew extrudes ground upward too. Put its TOP at -h, not its bottom.
    ground_z = layouter.z(0) if config['legacy_ground'] else layouter.z(0)-config['t']
    ground = layouter.plane(ground_z, name='GND')
    ground.prio_set(layouter.conductor_priority)
    if config.get('lower_stack',False):
        # Exploratory L2 aperture model: include the core and an intact L3.
        # Core 1.065 mm / er 4.6 from JLC04161H-7628; L2/L3 15.2 um.
        ground_t=.0152
        # Replace the provisional thick ground with actual inner-layer copper.
        ground.remove()
        origin=layouter.origin[:2]*1e-3
        bottom=-config['h']-ground_t-1.065
        em.geo.Box(layouter.width*1e-3,layouter.length*1e-3,(1.065+ground_t)*1e-3,
                   position=(*origin,bottom*1e-3),name='Core').set_material(
                       em.Material(er=4.6,tand=config['tand'])).prio_set(11)
        ground=em.geo.Box(layouter.width*1e-3,layouter.length*1e-3,ground_t*1e-3,
                          position=(*origin,(-config['h']-ground_t)*1e-3),name='L2').set_material(copper).prio_set(13)
        em.geo.Box(layouter.width*1e-3,layouter.length*1e-3,ground_t*1e-3,
                   position=(*origin,(bottom-ground_t)*1e-3),name='L3').set_material(copper).prio_set(13)
        if config.get('relief',0):
            for side in (0,1):
                points=np.vstack(polygons[2+side*2*config['fingers']:2+(side+1)*2*config['fingers']])
                xl,xr=points[:,0].min()-.05,points[:,0].max()+.05
                ym=0 if config['symmetric'] else -config['y']/2
                tool=em.geo.Box((xr-xl)*1e-3,config['relief']*1e-3,(ground_t+.02)*1e-3,
                                position=(xl*1e-3,(ym-config['relief']/2)*1e-3,(-config['h']-ground_t-.01)*1e-3))
                ground=em.geo.remove(ground,tool).set_material(copper).prio_set(13)
    layouter.generate_air(AIR_HEIGHT_MM)
    return ports, metal, ground

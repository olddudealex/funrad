"""Local mesh sizes are mm; global resolution is a fraction of wavelength."""

def generate_mesh(model, metal, ports, config):
    """Apply global, trace-surface, port and optional edge refinement.

    edge_mesh=0 disables only the explicit edge rule; ordinary meshing remains.
    Keep these operations in the original order for comparison with saved runs.
    """
    model.mw.set_resolution(config['resolution'])
    model.mw.set_frequency_range(config['fmin']*1e9, config['fmax']*1e9, config['nf'])
    model.mesher.set_boundary_size(metal, config['trace_mesh']*1e-3, growth_rate=1.3)
    for port in ports:
        model.mesher.set_face_size(port,config['port_mesh']*1e-3)
    if config['edge_mesh']:
        model.mesher.set_trace_refinement(metal.face('-z'), qualtity_factor=2,
                                          min_size=config['edge_mesh']*1e-3,
                                          edge_size=config['edge_mesh']*1e-3,
                                          growth_rate=1.5)
    model.generate_mesh()

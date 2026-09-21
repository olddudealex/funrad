"""Regression against saved experimental evidence; never reruns the EM solve.

Default: rebuild all 58 planar layouts and three representative 3-D domains.
With --mesh: also mesh R058 and compare node/tetrahedron counts.
"""
import argparse
import json
from pathlib import Path

import emerge as em
import gmsh
import numpy as np

from simulation.geometry import build_paths, outline, install_polygon_dedupe
from simulation.domain import create_simulation, build_domain
from simulation.mesh import generate_mesh

ROOT = Path(__file__).resolve().parents[1]


def verify(check_mesh=False):
    records = []
    domains = []
    mesh_check = None
    for saved in sorted((ROOT / 'results_redesign').glob('*/layout.json')):
        folder = saved.parent
        config = json.loads((folder / 'config.json').read_text())
        expected = json.loads(saved.read_text())
        em.cleanup()
        install_polygon_dedupe()
        model, layouter, copper = create_simulation(config, 'refactor_check')
        info, names = build_paths(layouter, config)
        polygons = [outline(path) for path in layouter.paths]
        assert len(polygons) == len(expected['polygons']), folder.name
        error = 0.0
        for actual, reference in zip(polygons, expected['polygons']):
            assert np.shape(actual) == np.shape(reference), folder.name
            error = max(error, float(np.max(np.abs(np.array(actual) - reference))))
        assert error < 1e-12, (folder.name, error)
        assert abs(info['total_x'] - expected['info']['total_x']) < 1e-12
        records.append({'name': config['name'], 'max_vertex_error_mm': error})

        if config['name'] not in ('final51_copper9', 'relief_refined', 'core_refined_control'):
            continue
        ports, metal, ground = build_domain(layouter, config, copper, polygons, names)
        gmsh.model.occ.synchronize()
        bounds = dict(ground=[gmsh.model.getBoundingBox(*dt) for dt in ground.dimtags],
                      traces=[gmsh.model.getBoundingBox(*dt) for dt in metal.dimtags])
        reference = json.loads((folder / 'geometry_bounds.json').read_text())
        for key in bounds:
            np.testing.assert_allclose(bounds[key], reference[key], rtol=0, atol=1e-12)
        domains.append(config['name'])
        if check_mesh and config['name'] == 'final51_copper9':
            model.commit_geometry()
            generate_mesh(model, metal, ports, config)
            counts = dict(nodes=int(gmsh.model.mesh.getNodes()[0].size),
                          volume_elements=sum(len(tags) for tags in gmsh.model.mesh.getElements(3)[1]))
            reference = json.loads((folder / 'mesh.json').read_text())
            assert all(counts[k] == reference[k] for k in counts), (counts, reference)
            mesh_check = counts
    assert len(records) == 58
    report = dict(scope='Geometry and mesh regression only; no new S-parameter solve',
                  layouts=records, checked_domains=domains, R058_mesh=mesh_check)
    (ROOT / 'catalogue/refactor_verification.json').write_text(json.dumps(report, indent=2)+'\n')
    print(f'PASS: {len(records)} saved layouts; {len(domains)} domain comparisons; R058 mesh {mesh_check}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mesh', action='store_true')
    verify(parser.parse_args().mesh)

"""Extract the fabricated coupon's copper with KiCad's own polygon engine.

Run with KiCad 10's Python. No PCB files are modified or zone fills rebuilt.
"""
from pathlib import Path
import argparse
import hashlib
import json
import pcbnew as pcb

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BOARD = ROOT / 'Frontend/kicad/FrontendPCBCoupon/FrontendPCBCoupon.kicad_pcb'
# Coupon D bounds, from the submitted panel's board-edge coordinates.
BOUNDS = (47.460, 112.000, 67.620, 128.000)
LAYERS = [('F.Cu', pcb.F_Cu, 0.0, .035),
          ('In1.Cu', pcb.In1_Cu, -.2104, .0152),
          ('In2.Cu', pcb.In2_Cu, -1.2906, .0152),
          ('B.Cu', pcb.B_Cu, -1.5162, .035)]


def inside(position):
    x, y = pcb.ToMM(position.x), pcb.ToMM(position.y)
    return BOUNDS[0] <= x <= BOUNDS[2] and BOUNDS[1] <= y <= BOUNDS[3]


def xy(position):
    return [pcb.ToMM(position.x) - BOUNDS[0], 120.0 - pcb.ToMM(position.y)]


def chain_points(chain):
    return [xy(chain.CPoint(i)) for i in range(chain.PointCount())]


def extract(board_path=BOARD,out=HERE/'pcb_geometry.json'):
    board_path=Path(board_path).resolve();out=Path(out).resolve()
    digest=hashlib.sha256(board_path.read_bytes()).hexdigest()
    if out.exists() and json.loads(out.read_text(encoding='utf-8')).get('board_sha256')!=digest:
        raise ValueError('This output contains frozen geometry from a different PCB revision. '
                         'Use the original revision A board, or --output with a new filename.')
    board = pcb.LoadBoard(str(board_path))
    clip = pcb.SHAPE_POLY_SET()
    contour = pcb.SHAPE_LINE_CHAIN()
    for x, y in [(BOUNDS[0], BOUNDS[1]), (BOUNDS[2], BOUNDS[1]),
                 (BOUNDS[2], BOUNDS[3]), (BOUNDS[0], BOUNDS[3])]:
        contour.Append(pcb.FromMM(x), pcb.FromMM(y))
    contour.SetClosed(True)
    clip.AddOutline(contour)
    grouped = {}
    footprints = [fp for fp in board.GetFootprints() if fp.GetReference() in ('J1', 'J2')]
    assert len(footprints) == 2 and all(inside(fp.GetPosition()) for fp in footprints)
    tracks = [t for t in board.GetTracks() if inside(t.GetPosition())]
    pads = [pad for fp in footprints for pad in fp.Pads()]
    result = dict(board=str(board_path.relative_to(ROOT)) if board_path.is_relative_to(ROOT) else str(board_path),
                  board_sha256=digest,
                  source_bounds_mm=BOUNDS, board_size_mm=[20.16, 16.0],
                  coordinate_transform='x = pcb_x - 47.460; y = 120.000 - pcb_y',
                  top_to_l2_dielectric_mm=.2104, nominal_er=4.5,
                  layers=[], pads=[], vias=[], tracks=[], source_notes=[])
    for name, layer, z, thickness in LAYERS:
        for item in pads + tracks:
            if not item.IsOnLayer(layer):
                continue
            poly = pcb.SHAPE_POLY_SET()
            item.TransformShapeToPolygon(poly, layer, 0, pcb.FromMM(.005), pcb.ERROR_INSIDE)
            key = (name, item.GetNetname())
            grouped.setdefault(key, pcb.SHAPE_POLY_SET()).BooleanAdd(poly)
        for zone in board.Zones():
            if not zone.IsOnLayer(layer) or not zone.HasFilledPolysForLayer(layer):
                continue
            poly = pcb.SHAPE_POLY_SET(zone.GetFilledPolysList(layer))
            poly.BooleanIntersection(clip)
            if poly.OutlineCount():
                key = (name, zone.GetNetname())
                grouped.setdefault(key, pcb.SHAPE_POLY_SET()).BooleanAdd(poly)
        copper = []
        for (lname, net), poly in grouped.items():
            if lname != name:
                continue
            poly.BooleanIntersection(clip)
            for i in range(poly.OutlineCount()):
                copper.append(dict(net=net, outer=chain_points(poly.COutline(i)),
                                   holes=[chain_points(poly.CHole(i, j)) for j in range(poly.HoleCount(i))]))
        result['layers'].append(dict(name=name, z_mm=z, thickness_mm=thickness, copper=copper))
    for pad in pads:
        result['pads'].append(dict(number=pad.GetNumber(), net=pad.GetNetname(),
                                  xy_mm=xy(pad.GetPosition()),
                                  size_mm=[pcb.ToMM(pad.GetSize().x), pcb.ToMM(pad.GetSize().y)]))
        if pad.GetDrillSize().x > 0:
            result['vias'].append(dict(xy_mm=xy(pad.GetPosition()),
                                       drill_mm=pcb.ToMM(pad.GetDrillSize().x),
                                       outside_mm=pcb.ToMM(pad.GetSize().x), source='connector ground pad'))
    for track in tracks:
        if isinstance(track, pcb.PCB_VIA):
            result['vias'].append(dict(xy_mm=xy(track.GetPosition()),
                                       drill_mm=pcb.ToMM(track.GetDrillValue()),
                                       outside_mm=pcb.ToMM(track.GetWidth()), source='PCB via'))
        else:
            result['tracks'].append(dict(start=xy(track.GetStart()), stop=xy(track.GetEnd()),
                                          width_mm=pcb.ToMM(track.GetWidth()), net=track.GetNetname()))
    result['source_notes'] = [
        'Includes saved filled copper zones: connector tapers/teardrops and ground clearances are not redrawn.',
        'Each copper layer uses its nominal upper surface as a thin-sheet reference plane.',
        'No connector bodies, pin overhang, solder fillets, or panel mouse-bite remnants.',
        'No soldermask in this initial electrical model; the bare signal path is the target.',
        'CAD dielectric constant is 4.5; previous coupler studies used 4.4. Both must remain explicit.',
    ]
    out.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(f'{out}: {[(x["name"], len(x["copper"])) for x in result["layers"]]}, {len(result["vias"])} ground vias')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--board',type=Path,default=BOARD)
    parser.add_argument('--output',type=Path,default=HERE/'pcb_geometry.json')
    args=parser.parse_args()
    extract(args.board,args.output)

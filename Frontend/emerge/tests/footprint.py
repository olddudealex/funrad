"""Run with KiCad's bundled Python; load, verify polygons, and create a DRC fixture."""
from pathlib import Path
import json
import pcbnew as pcb

ROOT=Path(__file__).resolve().parents[2]
LIB=ROOT/'kicad/FunRad_RF.pretty'
NAME='FunRad_Coupler_5GHz8_Symmetric_15dB'
fp=pcb.FootprintLoad(str(LIB),NAME)
assert fp is not None and fp.GetPadCount()==4 and fp.IsNetTie()
layout=json.loads((ROOT/'emerge/results_redesign/final51_3857a21020/layout.json').read_text())
def area(p):return abs(sum(x*v-u*y for (x,y),(u,v) in zip(p,p[1:]+p[:1])))/2
checks=[]
for number,parity in [('1',0),('3',1)]:
    pad=next(p for p in fp.Pads() if p.GetNumber()==number)
    poly=pad.GetCustomShapeAsPolygon()
    source=pcb.SHAPE_POLY_SET();anchor=pad.GetPosition();length=layout['info']['total_x']
    for points in layout['polygons'][parity::2]:
        part=pcb.SHAPE_POLY_SET();part.NewOutline()
        for x,y in points:part.Append(round((x-length/2)*1e6)-anchor.x,round(-y*1e6)-anchor.y)
        source.BooleanAdd(part)
    expected=abs(source.Area())/1e12
    actual=abs(poly.Area())/1e12
    assert poly.OutlineCount()==1 and abs(actual-expected)<1e-5,(number,actual,expected)
    difference=pcb.SHAPE_POLY_SET(source);difference.BooleanXor(poly)
    assert abs(difference.Area())/1e12<1e-5
    checks.append(dict(pad=number,connected_outlines=poly.OutlineCount(),source_area_mm2=expected,exported_area_mm2=actual,error_mm2=actual-expected))
board=pcb.BOARD();board.SetCopperLayerCount(4);board.Add(fp);fp.SetPosition(pcb.VECTOR2I(pcb.FromMM(25),pcb.FromMM(25)))
for p in fp.Pads():
    n=pcb.NETINFO_ITEM(board,'PORT_'+p.GetNumber());board.Add(n);p.SetNet(n)
for a,b in [((14,20),(36,20)),((36,20),(36,30)),((36,30),(14,30)),((14,30),(14,20))]:
    line=pcb.PCB_SHAPE();line.SetShape(pcb.SHAPE_T_SEGMENT);line.SetLayer(pcb.Edge_Cuts)
    line.SetStart(pcb.VECTOR2I(*[pcb.FromMM(v) for v in a]));line.SetEnd(pcb.VECTOR2I(*[pcb.FromMM(v) for v in b]));line.SetWidth(pcb.FromMM(.05));board.Add(line)
out=ROOT/'kicad/validation';out.mkdir(exist_ok=True)
pcb.SaveBoard(str(out/'coupler_import_check.kicad_pcb'),board)
result=dict(kicad=pcb.GetBuildVersion(),pad_count=fp.GetPadCount(),net_tie_groups=['1,2','3,4'],copper_checks=checks,fixture='Import/DRC fixture only; not a fabrication board')
(out/'geometry_check.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))

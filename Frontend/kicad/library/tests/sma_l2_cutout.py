"""KiCad-native pad and zone-fill checks; run with KiCad's bundled Python."""
from pathlib import Path
import json
import math
import pcbnew as pcb

LIB=Path(__file__).resolve().parents[1]/'FunRad.pretty'
NAME='SMA_BWSMA-KE-P001_EdgeMount_L2Cutout_2.8x4.8mm'
OUT=LIB.parents[1]/'validation/sma_l2_cutout'


def point(x,y):
    return pcb.VECTOR2I(pcb.FromMM(x),pcb.FromMM(y))


def pad_geometry(fp):
    return sorted((p.GetNumber(),p.GetPosition().x,p.GetPosition().y,
                   p.GetSize().x,p.GetSize().y,p.GetDrillSize().x,p.GetDrillSize().y,
                   int(p.GetShape()),tuple(p.GetLayerSet().Seq())) for p in fp.Pads())


def main():
    original=pcb.FootprintLoad(str(LIB),'SMA_BWSMA-KE-P001_EdgeMount')
    revised=pcb.FootprintLoad(str(LIB),NAME)
    assert original is not None and revised is not None
    assert pad_geometry(original)==pad_geometry(revised),'Connector pads changed'
    assert revised.GetPadCount()==11
    rules=list(revised.Zones());assert len(rules)==1
    rule=rules[0]
    assert rule.GetIsRuleArea() and list(rule.GetLayerSet().Seq())==[pcb.In1_Cu]
    outline=rule.Outline()
    assert abs(abs(outline.Area())/1e12-4.8*2.8)<1e-9
    board=pcb.BOARD();board.SetCopperLayerCount(4)
    ground=pcb.NETINFO_ITEM(board,'GND');board.Add(ground)
    placements=[]
    for angle,xy in zip((0,90,180,270),((20,20),(40,20),(20,40),(40,40))):
        fp=pcb.FootprintLoad(str(LIB),NAME);board.Add(fp)
        fp.SetPosition(point(*xy));fp.SetOrientationDegrees(angle)
        signal=pcb.NETINFO_ITEM(board,f'SIGNAL_{angle}');board.Add(signal)
        for pad in fp.Pads():pad.SetNet(signal if pad.GetNumber()=='1' else ground)
        placements.append((fp,angle,xy))
    for a,b in (((0,0),(60,0)),((60,0),(60,60)),((60,60),(0,60)),((0,60),(0,0))):
        line=pcb.PCB_SHAPE();line.SetShape(pcb.SHAPE_T_SEGMENT);line.SetLayer(pcb.Edge_Cuts)
        line.SetStart(point(*a));line.SetEnd(point(*b));line.SetWidth(pcb.FromMM(.05));board.Add(line)
    pours={}
    for layer in (pcb.In1_Cu,pcb.In2_Cu,pcb.B_Cu):
        zone=pcb.ZONE(board);zone.SetLayer(layer);zone.SetNet(ground)
        zone.SetLocalClearance(pcb.FromMM(.2));zone.SetMinThickness(pcb.FromMM(.25))
        zone.SetPadConnection(pcb.ZONE_CONNECTION_FULL)
        poly=zone.Outline();poly.NewOutline()
        for xy in ((1,1),(59,1),(59,59),(1,59)):poly.Append(point(*xy))
        board.Add(zone);pours[layer]=zone
    assert pcb.ZONE_FILLER(board).Fill(board.Zones()),'Zone fill failed'
    checks=[]
    for fp,angle,(cx,cy) in placements:
        def placed(x,y):
            # KiCad's positive footprint angle rotates counter-clockwise on screen.
            t=math.radians(angle)
            return point(cx+x*math.cos(t)+y*math.sin(t),cy-x*math.sin(t)+y*math.cos(t))
        for xy in ((0,0),(2.39,0),(-2.39,0),(0,1.39),(0,-1.39),(2.35,1.35),(-2.35,-1.35)):
            probe=placed(*xy)
            assert not pours[pcb.In1_Cu].HitTestFilledArea(pcb.In1_Cu,probe),(angle,xy,'L2 not cleared')
            for layer in (pcb.In2_Cu,pcb.B_Cu):
                assert pours[layer].HitTestFilledArea(layer,probe),(angle,xy,'Lower ground removed')
        for xy in ((2.45,0),(-2.45,0),(0,1.45),(0,-1.45)):
            assert pours[pcb.In1_Cu].HitTestFilledArea(pcb.In1_Cu,placed(*xy)),(angle,xy,'L2 relief too large')
        checks.append(dict(rotation_degrees=angle,L2_window_empty=True,L3_and_Bottom_present=True,
                           L2_present_50um_beyond_edges=True))
    OUT.mkdir(parents=True,exist_ok=True)
    pcb.SaveBoard(str(OUT/'zone_fill_check.kicad_pcb'),board)
    report=dict(kicad=pcb.GetBuildVersion(),footprint=NAME,pads_unchanged=11,
                layer='In1.Cu (L2)',window_mm=[4.8,2.8],rotation_checks=checks,
                fixture='Zone-fill validation only; not a fabrication board')
    (OUT/'checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()

"""Export saved solver polygons, without rebuilding the geometry. Standard Python."""
from pathlib import Path
import json
import hashlib

HERE=Path(__file__).resolve().parents[1]
SOURCE=HERE/'results_redesign/final51_3857a21020'
OUT=HERE.parent/'kicad/library/FunRad.pretty'
NAME='FunRad_Coupler_5GHz8_Symmetric_15dB'

def export():
    OUT.mkdir(parents=True,exist_ok=True)
    layout=json.loads((SOURCE/'layout.json').read_text())
    c=json.loads((SOURCE/'config.json').read_text())
    polys=layout['polygons'];length=layout['info']['total_x']
    ymax=max(y for p in polys for x,y in p)
    # KiCad y points down; preserve the top/bottom port assignment seen in EM plots.
    def xy(x,y):return x-length/2,-y
    def pts(poly,anchor=(0,0)):
        return ' '.join(f'(xy {xy(x,y)[0]-anchor[0]:.6f} {xy(x,y)[1]-anchor[1]:.6f})' for x,y in poly)
    ports={}
    for i in (0,1):
        p=polys[i];ys=[y for x,y in p if abs(x)<1e-8]
        y=(min(ys)+max(ys))/2
        ports[1 if i==0 else 3]=xy(c['feed_w']/2,y)
        ports[2 if i==0 else 4]=xy(length-c['feed_w']/2,y)
    lines=[f'(footprint "{NAME}" (version 20240108) (generator "funrad_export")',
           '(layer "F.Cu")',
           '(descr "Prototype; exact final51 EM copper. L2 intact ground at h=0.2104 mm; er=4.4; top copper 35um. No soldermask over RF region.")',
           '(tags "RF directional coupler 5.8GHz 15dB net-tie prototype")',
           '(attr smd exclude_from_pos_files exclude_from_bom)',
           '(net_tie_pad_groups "1,2" "3,4")',
           '(clearance 0.09) (zone_connect 0)',
           f'(fp_text reference "REF**" (at 0 {-ymax-2.6:.6f}) (layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.12))))',
           f'(fp_text value "{NAME}" (at 0 {ymax+2.6:.6f}) (layer "F.Fab") (effects (font (size 0.65 0.65) (thickness 0.10))))']
    for num in (1,3):
        anchor=ports[num];parity=0 if num==1 else 1
        lines.append(f'(pad "{num}" smd custom (at {anchor[0]:.6f} {anchor[1]:.6f}) (size {c["feed_w"]:.6f} {c["feed_w"]:.6f}) (layers "F.Cu") (options (clearance outline) (anchor rect)) (primitives')
        for poly in polys[parity::2]:lines.append(f'(gr_poly (pts {pts(poly,anchor)}) (width 0) (fill yes))')
        lines.append('))')
    for num in (2,4):
        a=ports[num]
        lines.append(f'(pad "{num}" smd rect (at {a[0]:.6f} {a[1]:.6f}) (size {c["feed_w"]:.6f} {c["feed_w"]:.6f}) (layers "F.Cu"))')
    # One mask aperture also exposes the gaps; individual pad openings leave mask loading.
    for layer,margin,width,fill in [('F.Mask',.25,0,'solid'),('F.CrtYd',2,.05,'none'),('F.Fab',.10,.05,'none')]:
        lines.append(f'(fp_rect (start {-length/2-margin:.6f} {-ymax-margin:.6f}) (end {length/2+margin:.6f} {ymax+margin:.6f}) (stroke (width {width}) (type default)) (fill {fill}) (layer "{layer}"))')
    for num,a in ports.items():
        lines.append(f'(fp_text user "P{num}" (at {a[0]:.6f} {a[1]+(-.55 if a[1]<0 else .55):.6f}) (layer "F.Fab") (effects (font (size 0.5 0.5) (thickness 0.08))))')
    # Only F.Cu zone fills prohibited. Never remove the underlying L2 return plane.
    x0,x1=-length/2-.25,length/2+.25;y0,y1=-ymax-2,ymax+2
    lines.append(f'(zone (net 0) (net_name "") (layer "F.Cu") (hatch edge 0.5) (connect_pads (clearance 0)) (min_thickness 0.25) (keepout (tracks allowed) (vias not_allowed) (pads allowed) (copperpour not_allowed) (footprints allowed)) (fill (thermal_gap 0.3) (thermal_bridge_width 0.3)) (polygon (pts (xy {x0:.6f} {y0:.6f}) (xy {x1:.6f} {y0:.6f}) (xy {x1:.6f} {y1:.6f}) (xy {x0:.6f} {y1:.6f}))))')
    lines.append(')')
    path=OUT/(NAME+'.kicad_mod');path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    manifest=dict(source=str(SOURCE.relative_to(HERE)),layout_sha256=hashlib.sha256((SOURCE/'layout.json').read_bytes()).hexdigest(),
                  footprint=path.name,coordinate_transform='x_kicad=x_em-total_x/2; y_kicad=-y_em',
                  coordinate_rounding_mm=0.000001,ports_mm=ports,net_ties=[[1,2],[3,4]],copper_layers=['F.Cu'],paste=False,
                  ground='Continuous board L2, not embedded in footprint',production_ready=False)
    (OUT.parent/'coupler_export.json').write_text(json.dumps(manifest,indent=2))
    print(path)

if __name__=='__main__':export()

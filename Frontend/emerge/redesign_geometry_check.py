"""Planar opposite-net clearance check on the actual saved trace outlines."""
import json
from pathlib import Path
import numpy as np

def segments(poly):
    p=np.asarray(poly,float)
    return list(zip(p,np.roll(p,-1,axis=0)))

def point_segment(p,a,b):
    delta=b-a
    t=np.clip(np.dot(p-a,delta)/max(np.dot(delta,delta),1e-30),0,1)
    return np.linalg.norm(p-a-t*delta)

def cross(a,b):return a[0]*b[1]-a[1]*b[0]

def distance(a,b,c,d):
    u,v=b-a,d-c
    det=cross(u,v)
    if abs(det)>1e-15:
        t=cross(c-a,v)/det; s=cross(c-a,u)/det
        if 0<=t<=1 and 0<=s<=1:return 0.
    return min(point_segment(a,c,d),point_segment(b,c,d),point_segment(c,a,b),point_segment(d,a,b))

if __name__=='__main__':
    root=Path(__file__).resolve().parent/'results_redesign'
    for p in root.glob('*/layout.json'):
        config=json.loads((p.parent/'config.json').read_text())
        if config['straight']:continue
        polys=json.loads(p.read_text())['polygons']
        a=[poly for i,poly in enumerate(polys) if i%2==0]
        b=[poly for i,poly in enumerate(polys) if i%2==1]
        minimum=min(distance(*s,*t) for pa in a for pb in b for s in segments(pa) for t in segments(pb))
        result=dict(minimum_opposite_net_edge_clearance_mm=float(minimum),
                    passes_0p10mm=bool(minimum>=.1-1e-8),
                    scope='Opposite-net outline edge clearance only; not a full fabrication DRC')
        (p.parent/'clearance.json').write_text(json.dumps(result,indent=2))
        print(config['name'],result)

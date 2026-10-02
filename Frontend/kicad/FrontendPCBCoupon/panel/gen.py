from collections import defaultdict
S=2.0; R=1.0; TAB=3.0
PANEL=(43.230,17.000,183.230,133.000)
BOARDS={                         # new staircase: 90mm, coupler, 40, 40, 10
 "A_90mm_h":(47.460, 22.000,147.620, 38.000),
 "E_coup1" :(47.460, 40.000,110.790, 74.000),
 "B_40mm"  :(47.460, 76.000, 97.620, 92.000),
 "C_40mm"  :(47.460, 94.000, 97.620,110.000),
 "D_10mm"  :(47.460,112.000, 67.620,128.000),
 "F_coup2" :(127.000,61.210,161.000,124.540),   # bottom aligned with G
 "G_90mm_v":(163.000,24.380,179.000,124.540),
}
GAPS=[(47.460, 38.000,110.790, 40.000),   # A|E
      (47.460, 74.000, 97.620, 76.000),   # E|B
      (47.460, 92.000, 97.620, 94.000),   # B|C
      (47.460,110.000, 67.620,112.000),   # C|D
      (161.000,61.210,163.000,124.540)]   # F|G
def hx(x,y1,y2): return (x-TAB/2,y1,x+TAB/2,y2)
def vy(y,x1,x2): return (x1,y-TAB/2,x2,y+TAB/2)
TABS=[hx(80.85,20,22), hx(114.23,20,22),          # A top
      hx(125.00,38,40), hx(140.00,38,40),         # A bottom, right of E
      hx(104.00,74,76),                           # E bottom, right of B
      hx(82.00,110,112),                          # C bottom, right of D
      hx(52.00,128,130), hx(63.00,128,130),       # D bottom
      vy(80.00,125,127), vy(105.00,125,127),      # F left
      vy(35.00,161,163), vy(50.00,161,163),       # G left, above F
      vy(57.80,179,181), vy(91.10,179,181)]       # G right
# slot ring = every board dilated by S
V=[(x0-S,y0-S,x1+S,y1+S) for (x0,y0,x1,y1) in BOARDS.values()]
def cells(rects, minus):
    xs=sorted({v for r in rects+minus for v in (r[0],r[2])})
    ys=sorted({v for r in rects+minus for v in (r[1],r[3])})
    def cover(rs,i,j):
        cx=(xs[i]+xs[i+1])/2; cy=(ys[j]+ys[j+1])/2
        return any(r[0]<cx<r[2] and r[1]<cy<r[3] for r in rs)
    grid=set()
    for i in range(len(xs)-1):
        for j in range(len(ys)-1):
            if cover(rects,i,j) and not cover(minus,i,j): grid.add((i,j))
    return xs,ys,grid
xs,ys,grid=cells(V, list(BOARDS.values())+GAPS+TABS)
E=defaultdict(int)
for i,j in grid:
    for a,b in (((xs[i],ys[j]),(xs[i+1],ys[j])),((xs[i+1],ys[j]),(xs[i+1],ys[j+1])),
                ((xs[i+1],ys[j+1]),(xs[i],ys[j+1])),((xs[i],ys[j+1]),(xs[i],ys[j]))):
        E[(a,b)]+=1
edges={e for e in E if (e[1],e[0]) not in E}
succ=defaultdict(list)
for a,b in edges: succ[a].append(b)
loops=[];rem=set(edges)
while rem:
    a,b=next(iter(rem)); rem.discard((a,b)); loop=[a,b]
    while b!=a:
        nxt=[p for p in succ[b] if (b,p) in rem]
        if not nxt: break
        d=(loop[-1][0]-loop[-2][0], loop[-1][1]-loop[-2][1])
        nxt.sort(key=lambda p: 0 if (p[0]-b[0],p[1]-b[1])==d else 1)
        p=nxt[0]; rem.discard((b,p)); loop.append(p); b=p
    loops.append(loop[:-1] if loop[0]==loop[-1] else loop)
def dedup(pts):
    out=[]
    for p in pts:
        if len(out)>=2:
            (x0,y0),(x1,y1)=out[-2],out[-1]
            if (x1-x0)*(p[1]-y1)==(y1-y0)*(p[0]-x1): out.pop()
        out.append(p)
    return out
loops=[dedup(l) for l in loops]
print(f"panel {PANEL[2]-PANEL[0]:.2f} x {PANEL[3]-PANEL[1]:.2f}")
print(f"{len(loops)} void loops, vertices {[len(l) for l in loops]}, {len(TABS)} tabs")
import json
json.dump({"panel":PANEL,"boards":BOARDS,"gaps":GAPS,"loops":loops,"tabs":TABS,"R":R},open("panel3.json","w"))

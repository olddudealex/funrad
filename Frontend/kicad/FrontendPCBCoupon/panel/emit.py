import json, math, uuid
d=json.load(open('panel3.json'))
P=d['panel']; loops=[[tuple(p) for p in l] for l in d['loops']]; T=[tuple(t) for t in d['tabs']]
R=1.0
u=lambda: str(uuid.uuid4())
def f(v): return f"{v:.6f}".rstrip('0').rstrip('.') if v==v else "0"

out=[]
def line(a,b):
    if abs(a[0]-b[0])<1e-9 and abs(a[1]-b[1])<1e-9: return
    out.append(f'\n\t(gr_line\n\t\t(start {f(a[0])} {f(a[1])})\n\t\t(end {f(b[0])} {f(b[1])})'
               f'\n\t\t(stroke\n\t\t\t(width 0.05)\n\t\t\t(type default)\n\t\t)'
               f'\n\t\t(layer "Edge.Cuts")\n\t\t(uuid "{u()}")\n\t)')
def arc(a,m,b):
    out.append(f'\n\t(gr_arc\n\t\t(start {f(a[0])} {f(a[1])})\n\t\t(mid {f(m[0])} {f(m[1])})'
               f'\n\t\t(end {f(b[0])} {f(b[1])})'
               f'\n\t\t(stroke\n\t\t\t(width 0.05)\n\t\t\t(type default)\n\t\t)'
               f'\n\t\t(layer "Edge.Cuts")\n\t\t(uuid "{u()}")\n\t)')

# panel outline, sharp corners
p=[(P[0],P[1]),(P[2],P[1]),(P[2],P[3]),(P[0],P[3])]
for i in range(4): line(p[i],p[(i+1)%4])

def area(poly):
    return sum(poly[i][0]*poly[(i+1)%len(poly)][1]-poly[(i+1)%len(poly)][0]*poly[i][1]
               for i in range(len(poly)))/2
nrounded=0; warn=[]
for poly in loops:
    n=len(poly); A=area(poly); sgn=1 if A>0 else -1
    # classify each vertex
    conv=[]
    for i in range(n):
        a,v,b=poly[i-1],poly[i],poly[(i+1)%n]
        ux,uy=v[0]-a[0],v[1]-a[1]; wx,wy=b[0]-v[0],b[1]-v[1]
        cr=ux*wy-uy*wx
        conv.append(cr*sgn>0)
    # per-vertex cutback, limited by adjacent edge lengths
    cut=[R if c else 0.0 for c in conv]
    for i in range(n):
        j=(i+1)%n
        L=math.dist(poly[i],poly[j])
        if cut[i]+cut[j]>L+1e-9:
            s=L/(cut[i]+cut[j]); cut[i]*=s; cut[j]*=s
            if L< 2*R-1e-9: warn.append((poly[i],poly[j],round(L,3)))
    # emit
    pts=[]
    for i in range(n):
        a,v,b=poly[i-1],poly[i],poly[(i+1)%n]
        ui=((v[0]-a[0]),(v[1]-a[1])); li=math.hypot(*ui); ui=(ui[0]/li,ui[1]/li)
        uo=((b[0]-v[0]),(b[1]-v[1])); lo=math.hypot(*uo); uo=(uo[0]/lo,uo[1]/lo)
        c=cut[i]
        if c<1e-9: pts.append((v,None,v))
        else:
            p1=(v[0]-c*ui[0], v[1]-c*ui[1]); p2=(v[0]+c*uo[0], v[1]+c*uo[1])
            C=(p1[0]+c*uo[0], p1[1]+c*uo[1])
            mx,my=(p1[0]-C[0])+(p2[0]-C[0]), (p1[1]-C[1])+(p2[1]-C[1])
            ml=math.hypot(mx,my); M=(C[0]+c*mx/ml, C[1]+c*my/ml)
            pts.append((p1,M,p2)); nrounded+=1
    for i in range(n):
        p1,M,p2=pts[i]
        if M is not None: arc(p1,M,p2)
        line(p2, pts[(i+1)%n][0])

# mouse-bite footprints on the 18 tabs
mod=open('/dev/null').read()
fps=[]
for (x1,y1,x2,y2) in T:
    cx,cy=(x1+x2)/2,(y1+y2)/2
    rot = 0 if (x2-x1)>(y2-y1) else 90   # holes run along the slot
    fps.append((round(cx,3),round(cy,3),rot))
json.dump({"edgecuts":"".join(out),"fps":fps}, open('emit3.json','w'))
print(f"emitted: {out.__len__()} Edge.Cuts items, {nrounded} rounded corners, {len(fps)} tab footprints")
if warn: print("WARN short edges:", warn[:5])
else: print("no edges too short for R=1.0")

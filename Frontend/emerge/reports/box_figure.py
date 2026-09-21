"""Illustrate R058 domain from saved outlines and the archived driver settings."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

HERE=Path(__file__).resolve().parents[1]
run=HERE/'results_redesign/final51_copper9_e61849bc8c'
layout=json.loads((run/'layout.json').read_text())
c=json.loads((run/'config.json').read_text())
snapshot=(run/'driver_snapshot.py').read_text()
assert 'lo.generate_air(2.5)' in snapshot
assert 'leftmargin=0, rightmargin=0, topmargin=2, bottommargin=2' in snapshot
points=[p for poly in layout['polygons'] for p in poly]
x0=min(x for x,y in points);x1=max(x for x,y in points)
cy=max(abs(y) for x,y in points);wall=cy+2
roof=2.5
fig,(ax,side)=plt.subplots(2,1,figsize=(12,9),gridspec_kw={'height_ratios':[1.5,1]})
for poly in layout['polygons']:
    ax.fill([p[0] for p in poly],[p[1] for p in poly],fc='#bd7138',ec='#774319',lw=.6)
ax.add_patch(Rectangle((x0,-wall),x1-x0,2*wall,fill=False,ec='#244b63',lw=2.5))
for x in (x0,x1):
    for y in (-1.25,1.25):
        ax.plot([x,x],[y-c['port_width']/2,y+c['port_width']/2],color='#21a3b8',lw=6)
def dim(a,p,q,label,offset=(0,0)):
    a.annotate('',xy=p,xytext=q,arrowprops=dict(arrowstyle='<->',lw=1.4,color='#244b63'))
    a.text((p[0]+q[0])/2+offset[0],(p[1]+q[1])/2+offset[1],label,ha='center',va='center',fontsize=10,bbox=dict(fc='white',ec='none',pad=2))
dim(ax,(x0,wall+.65),(x1,wall+.65),f'{x1-x0:.3f} mm',offset=(0,.20))
dim(ax,(x1+.8,-wall),(x1+.8,wall),f'{2*wall:.3f} mm',offset=(.4,0))
dim(ax,(x1/2,cy),(x1/2,wall),'2.000 mm',offset=(1,0))
ax.text(x1/2,-wall-.5,'Blue ends: modal-port apertures, not a model of physical shield feedthroughs',ha='center',fontsize=10,color='#16758c')
ax.set(xlim=(-.8,x1+2),ylim=(-wall-.9,wall+1.1),aspect='equal',title='Top view — actual copper outline and box boundary')
ax.axis('off')
side.add_patch(Rectangle((-wall,-c['h']),2*wall,c['h'],fc='#e8d8a9',ec='none'))
side.add_patch(Rectangle((-wall,-c['h']-c['t']),2*wall,c['t'],fc='#bd7138'))
for y in (-.25,.25):side.add_patch(Rectangle((y-c['w']/2,0),c['w'],c['t'],fc='#bd7138'))
side.plot([-wall,-wall,wall,wall],[0,roof,roof,0],color='#244b63',lw=2.5)
dim(side,(-wall+.6,0),(-wall+.6,roof),'2.500 mm',offset=(.9,0))
side.text(0,roof+.15,'PEC roof',ha='center',color='#244b63',fontsize=11)
side.text(0,.45,'Roof clearance above copper: 2.465 mm',ha='center',fontsize=11)
side.text(0,-.65,'Substrate surface z = 0; copper top z = +0.035 mm\nL2 ground top z = −0.2104 mm',ha='center',va='top',fontsize=10)
side.set(xlim=(-wall-.4,wall+.4),ylim=(-1.3,roof+.45),aspect='equal',title='Cross-section through coupled lines — dimensions in mm')
side.axis('off')
fig.suptitle('R058 simulation enclosure: 13.113 × 6.870 × 2.500 mm above substrate',fontsize=15)
fig.text(.5,.02,'PEC = ideal electric conductor. No enclosure-size sweep has been performed. Dimensions are internal model boundaries, not cap outside dimensions.',ha='center',fontsize=9)
fig.tight_layout(rect=(0,.05,1,.96))
out=HERE.parents[1]/'Notes/FunRad/images/coupler'
for ext in ('png','svg'):fig.savefig(out/f'simulation_box_R058.{ext}',dpi=170)
print(f'Copper extent: {x1-x0:.9f} x {2*cy:.6f} mm; box: {x1-x0:.9f} x {2*wall:.6f} mm; roof {roof} mm')

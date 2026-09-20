"""Publication-style figures from saved data, never synthetic EM curves."""
from pathlib import Path
import json
import csv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

HERE=Path(__file__).resolve().parent
IMG=HERE.parents[1]/'Notes'/'FunRad'/'images'/'redesign'
IMG.mkdir(parents=True,exist_ok=True)
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,
                     'figure.facecolor':'white','axes.grid':True,'grid.alpha':.20})
COLORS=['#176b9b','#da7634','#39834a','#9955a2','#ba3949']

def save(fig,name):
    fig.tight_layout(); fig.savefig(IMG/name,dpi=180,bbox_inches='tight'); plt.close(fig)

def reference():
    fig,axes=plt.subplots(1,2,figsize=(12,4.5))
    r=np.linspace(40,60,1001)
    for z,color in [(48,COLORS[0]),(50,COLORS[1])]:
        gamma=np.abs((r-z)/(r+z))
        axes[0].plot(r,20*np.log10(np.maximum(gamma,1e-5)),color=color,label=f'{z} Ω reference')
    axes[0].set(xlabel='Resistive one-port load (Ω)',ylabel='S11 (dB)',ylim=(-65,-15),title='A match is always relative to a reference')
    axes[0].scatter([48],[-33.804],color=COLORS[1],zorder=5)
    axes[0].annotate('48 Ω load in a 50 Ω system: −33.8 dB',(48,-33.804),xytext=(41,-23),arrowprops={'arrowstyle':'->'})
    axes[0].legend(loc='lower right')
    names=['Compact asymmetric','Symmetric 90°']
    for i,(file,name) in enumerate(zip(['sparams_opt_comb3_w0.38s0.11o0.27y1j0.9.npz','sparams_opt_comb3_sym_w0.38s0.11o0.27y1.4j0.9b90.npz'],names)):
        d=np.load(HERE/'results'/file); f=d['f']/1e9
        mask=(f>=5.7)&(f<=5.9)
        for key,ls,ref in [('Smat','--','modal reference'),('Smat50','-','50 Ω')]:
            s=d[key]; direct=20*np.log10(abs(s[:,2,0])/abs(s[:,3,0]))
            axes[1].plot(f[mask],direct[mask],ls,color=COLORS[i],label=f'{name}, {ref}')
    axes[1].set(xlabel='Frequency (GHz)',ylabel='Directivity (dB)',title='Same saved networks; different matched terminations')
    axes[1].legend(fontsize=8)
    save(fig,'01_reference.png')

def all_runs():
    out=[]
    for p in (HERE/'results_redesign').glob('*/raw.npz'):
        c=json.loads((p.parent/'config.json').read_text()); d=np.load(p)
        out.append((c,d,p.parent))
    return out

def progress():
    runs=[x for x in all_runs() if not x[0]['straight']]
    if not runs:return
    fig,ax=plt.subplots(figsize=(11,5.5))
    rows=[]
    selection=HERE/'redesign_configs'/'selection.json'
    selected_name=json.loads(selection.read_text()).get('final') if selection.exists() else ''
    for c,d,p in runs:
        s=d['Smat50']; f=d['f']; mask=(f>=5.7e9)&(f<=5.9e9)
        db=20*np.log10(np.maximum(abs(s),1e-30)); i=abs(f-5.8e9).argmin()
        dv=(db[:,2,0]-db[:,3,0])[mask].min()
        coupling=db[i,2,0]
        ax.scatter(coupling,dv,s=85 if c['name']==selected_name else 30,
                   marker='D' if mask.sum()==1 else 'o',
                   color=COLORS[1] if c['name']==selected_name else COLORS[0],alpha=.8)
        if c['name'] in ['s45_initial','a90_n3','s90_n3','s45_core_control','s45_core_relief',selected_name]:
            ax.annotate(c['name'],(coupling,dv),xytext=(4,4),textcoords='offset points',fontsize=8)
        rows.append(dict(name=c['name'],path=str(p),band_samples=int(mask.sum()),edge_mesh_mm=c['edge_mesh'],coupling_center=coupling,
                         coupling_min=db[mask,2,0].min(),coupling_max=db[mask,2,0].max(),
                         directivity_min=dv,RL_min=-db[mask,0,0].max(),through_center=db[i,1,0]))
    ax.axvspan(-15.3,-14.7,color='#63b56d',alpha=.12,label='Centre coupling target')
    ax.set(xlabel='Coupling at 5.8 GHz (dB)',ylabel='Minimum sampled in-band directivity (dB)',title='Search history, mixed meshes: circles = band sweeps; diamonds = one frequency')
    ax.legend(loc='lower left'); save(fig,'03_search.png')
    with (HERE/'results_redesign'/'summary.csv').open('w',newline='') as fp:
        w=csv.DictWriter(fp,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def selected():
    selection=HERE/'redesign_configs'/'selection.json'
    if not selection.exists():return
    spec=json.loads(selection.read_text())
    runs={c['name']:(c,d,p) for c,d,p in all_runs()}
    final=spec['final']
    if final not in runs:final=final.replace('_dense','')
    if final not in runs:return
    c,d,p=runs[final]
    poly=json.loads((p/'layout.json').read_text())['polygons']
    fig,axes=plt.subplots(2,1,figsize=(12,7),gridspec_kw={'height_ratios':[1,1.6]})
    for ax in axes:
        for points in poly:
            a=np.array(points);ax.fill(a[:,0],a[:,1],color='#bf773f',ec='none')
        ax.set_aspect('equal');ax.set(xlabel='x (mm)',ylabel='y (mm)')
    axes[0].set_title('Proposed copper outline — actual geometry used by the solver')
    total=json.loads((p/'layout.json').read_text())['info']['total_x']
    for x,y,label in [(0,1.58,'P1 · PA'),(total,1.58,'P2 · antenna'),
                       (0,-1.65,'P3 · coupled'),(total,-1.65,'P4 · terminated')]:
        axes[0].text(x,y,label,ha='left' if x==0 else 'right',fontsize=9)
    axes[0].set_ylim(-1.85,1.85)
    comb=np.vstack(poly[2:2+2*c['fingers']])
    xmin,xmax=comb[:,0].min(),comb[:,0].max()
    ymin,ymax=comb[:,1].min(),comb[:,1].max()
    axes[1].set(xlim=(xmin-.5,xmax+.7),ylim=(ymin-.3,ymax+.3),title=f"Comb detail: {c['fw']:.2f} mm fingers / {c['fg']:.2f} mm slots / {c['overlap']:.2f} mm overlap")
    root=c['y']/2-c['feed_w']/2 if c['symmetric'] else -c['feed_w']/2
    finger=(c['y']-c['feed_w']+c['overlap'])/2
    axes[1].annotate('',(xmin-.15,root),(xmin-.15,root-finger),arrowprops={'arrowstyle':'<->','color':'#24577b'})
    axes[1].text(xmin-.18,root-finger/2,f'{finger:.3f} mm',rotation=90,ha='right',va='center',color='#24577b')
    axes[1].annotate(f"Coupled gap\n{c['gap']:.2f} mm",(xmax+.5,0),
                     xytext=(xmax+.22,ymax+.15),fontsize=9,
                     bbox={'facecolor':'white','edgecolor':'none','alpha':.9,'pad':2},
                     arrowprops={'arrowstyle':'->','color':'#24577b'})
    if c.get('relief',0):
        axes[1].add_patch(Rectangle((xmin-.05,-c['relief']/2),xmax-xmin+.1,c['relief'],facecolor='#53b4ce',alpha=.25,edgecolor='#17718a',linestyle='--',label='L2 ground opening'))
        axes[1].legend()
    save(fig,'02_geometry.png')
    fig,axes=plt.subplots(2,2,figsize=(12,8))
    for n,name in enumerate(spec['compare']):
        if name not in runs:continue
        cc,dd,_=runs[name];ss=dd['Smat50'];ff=dd['f']/1e9
        db=20*np.log10(np.maximum(abs(ss),1e-30))
        values=[db[:,2,0],db[:,2,0]-db[:,3,0],-db[:,0,0],-db[:,1,0]]
        for ax,val in zip(axes.flat,values):ax.plot(ff,val,'o-',ms=3,lw=1.5,color=COLORS[n%len(COLORS)],label=name)
    for ax,title,ylabel in zip(axes.flat,['Coupling','Directivity','Input return loss','Through insertion loss'],['S31 (dB)','S31 − S41 (dB)','−S11 (dB)','−S21 (dB)']):
        ax.set(title=title,xlabel='Frequency (GHz)',ylabel=ylabel)
    axes[0,0].axhspan(-15.3,-14.7,color='#63b56d',alpha=.12)
    axes[0,1].axhline(20,color='gray',ls=':',lw=1)
    axes[0,0].legend(fontsize=8)
    fig.suptitle('50 Ω results — markers are directly solved frequencies',fontsize=14)
    save(fig,'04_results.png')
    if spec.get('sensitivity'):
        fig,axes=plt.subplots(1,2,figsize=(12,4.5))
        labels=[]
        for n,name in enumerate([spec['final']]+spec['sensitivity']):
            if name not in runs:continue
            cc,dd,_=runs[name];ss=dd['Smat50'];ff=dd['f']/1e9
            db=20*np.log10(np.maximum(abs(ss),1e-30))
            i=abs(ff-5.8).argmin()
            label=name.replace('final51','Nominal').replace('Nominal_','').replace('er42','εr 4.2').replace('er46','εr 4.6')
            labels.append(label)
            axes[0].scatter([n],[db[i,2,0]],s=65,color=COLORS[n%len(COLORS)])
            axes[1].scatter([n],[db[i,2,0]-db[i,3,0]],s=65,color=COLORS[n%len(COLORS)])
            for ax in axes:
                ax.set_xticks(range(len([spec['final']]+spec['sensitivity'])))
        for ax in axes:
            ax.set_xticks(range(len(labels)),labels,rotation=25)
        axes[0].set(ylabel='Coupling (dB)',title='Sensitivity of coupling at 5.8 GHz')
        axes[1].set(ylabel='Directivity (dB)',title='Sensitivity of cancellation at 5.8 GHz')
        axes[0].axhspan(-15.3,-14.7,color='#63b56d',alpha=.12)
        save(fig,'05_sensitivity.png')

def controls():
    runs={c['name']:(c,d,p) for c,d,p in all_runs()}
    groups=[('06_convergence.png','Same geometry, different numerical settings',
             ['s45_check_coarse','s45_check_medium','s45_check_fine']),
            ('08_proposal_mesh.png','Earlier candidate: edge refinement exposes a false optimum',
             ['proposal','proposal_edges','proposal_edges_finer']),
            ('07_ground.png','Ground opening: matched lower-stack models',
             ['s45_core_control','s45_core_relief','core_refined_control','relief_refined'])]
    for file,title,names in groups:
        fig,axes=plt.subplots(1,2,figsize=(12,4.5))
        for i,name in enumerate(names):
            if name not in runs:continue
            c,d,p=runs[name];s=d['Smat50'];db=20*np.log10(np.maximum(abs(s),1e-30))
            axes[0].plot(d['f']/1e9,db[:,2,0],'o-',ms=4,color=COLORS[i],label=name)
            axes[1].plot(d['f']/1e9,db[:,2,0]-db[:,3,0],'o-',ms=4,color=COLORS[i],label=name)
        axes[0].set(xlabel='Frequency (GHz)',ylabel='Coupling (dB)')
        axes[1].set(xlabel='Frequency (GHz)',ylabel='Directivity (dB)')
        axes[0].legend(fontsize=8);fig.suptitle(title)
        save(fig,file)

def ground_layout():
    runs={c['name']:(c,d,p) for c,d,p in all_runs()}
    if 's45_core_relief' not in runs:return
    c,d,p=runs['s45_core_relief']
    polys=json.loads((p/'layout.json').read_text())['polygons']
    fingers=np.vstack(polys[2:2+2*c['fingers']])
    xl,xr=fingers[:,0].min()-.05,fingers[:,0].max()+.05
    fig,axes=plt.subplots(1,2,figsize=(12,4.5))
    for points in polys:
        a=np.array(points);axes[0].fill(a[:,0],a[:,1],color='#bf773f',ec='none')
    axes[0].add_patch(Rectangle((xl,-.25),xr-xl,.5,fc='#57b5cc',ec='#176c84',ls='--',alpha=.5))
    axes[0].set(xlim=(xl-.3,xr+.5),ylim=(-.75,.75),aspect='equal',xlabel='x (mm)',ylabel='y (mm)',title='Top view: blue region is removed from L2')
    h=.2104;t=.0152;bottom=-h-t-1.065
    axes[1].add_patch(Rectangle((-1.1,-h),2.2,h,fc='#d9e5b3'))
    axes[1].add_patch(Rectangle((-1.1,bottom),2.2,h*-1-bottom,fc='#efe4c5'))
    for y in [-.5,.5]:axes[1].add_patch(Rectangle((y-.185,0),.37,.035,fc='#bf773f'))
    for y,width in [(-1.1,.85),(.25,.85)]:axes[1].add_patch(Rectangle((y,-h-t),width,t,fc='#777777'))
    axes[1].add_patch(Rectangle((-1.1,bottom-t),2.2,t,fc='#777777'))
    axes[1].text(0,-h/2,'7628: 0.2104 mm',ha='center',va='center',fontsize=9)
    axes[1].text(0,(bottom-h)/2,'Core: 1.065 mm\nεr = 4.6',ha='center',va='center')
    axes[1].annotate('L2 aperture',(0,-h),xytext=(.65,-.42),arrowprops={'arrowstyle':'->'},fontsize=9)
    axes[1].text(0,bottom-.09,'Intact grounded L3 (assumed)',ha='center',fontsize=9)
    axes[1].set(xlim=(-1.2,1.2),ylim=(bottom-.16,.14),xlabel='Lateral position y (mm)',ylabel='Height z (mm)',title='Stack schematic; comb fingers omitted')
    save(fig,'09_ground_layout.png')

if __name__=='__main__':
    reference();progress();selected();controls();ground_layout()

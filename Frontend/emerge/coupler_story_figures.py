"""Figures for the consolidated design note; only saved EM data and explicit circuit calculations."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle
HERE=Path(__file__).resolve().parent
OUT=HERE.parents[1]/'Notes/FunRad/images/coupler'
OUT.mkdir(exist_ok=True)
plt.rcParams.update({'font.size':11,'axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.alpha':.2})
def load(name):
    for p in (HERE/'results_redesign').glob('*/config.json'):
        if json.loads(p.read_text())['name']==name:return np.load(p.parent/'raw.npz')
    raise KeyError(name)
def save(fig,n):fig.tight_layout();fig.savefig(OUT/n,dpi=170,bbox_inches='tight');plt.close(fig)

fig,axs=plt.subplots(2,2,figsize=(11,7))
for name,label,color in [('final51_bare','No comb, PEC','#7c8792'),('final51','Selected geometry, PEC','#23816b'),('final51_copper9','Selected geometry, finite copper','#ca7033')]:
    d=load(name);s=d['Smat50'];db=20*np.log10(abs(s));f=d['f']/1e9
    for ax,y in zip(axs.flat,[db[:,2,0],db[:,2,0]-db[:,3,0],-db[:,0,0],-db[:,1,0]]):ax.plot(f,y,'o-',label=label,color=color)
for ax,title,ylabel in zip(axs.flat,['Coupling','Directivity','Input return loss','Through insertion loss'],['S31 (dB)','S31 − S41 (dB)','−S11 (dB)','−S21 (dB)']):ax.set(title=title,xlabel='GHz',ylabel=ylabel)
axs[0,0].axhspan(-15.3,-14.7,color='#bde3c7',alpha=.35);axs[0,0].legend(fontsize=9)
fig.suptitle('Final symmetric geometry: directly solved points, 50 Ω, same edge refinement')
save(fig,'final_response.png')

# Historical truncated network: capacitance optimization is circuit algebra, not new EM.
d=np.load(HERE/'results/sparams_opt_nocomb_atcomb.npz');f=d['f'];s=d['Smat50'];I=np.eye(4)
y=np.linalg.solve(I+s,I-s)/50
stamp=np.zeros((4,4))
for a,b in [(0,2),(1,3)]:stamp[a,a]+=1;stamp[b,b]+=1;stamp[a,b]-=1;stamp[b,a]-=1
caps=np.arange(0,150.01,.5);mask=(f>=5.7e9)&(f<=5.9e9);direct=[];dcurves=[]
def response(cap):
    yy=y+1j*2*np.pi*f[:,None,None]*cap*1e-15*stamp
    return np.linalg.solve(I+50*yy,I-50*yy)
for cap in caps:
    ss=response(cap);curve=20*np.log10(abs(ss[mask,2,0])/abs(ss[mask,3,0]));direct.append(float(np.min(curve)));dcurves.append(curve)
best=float(caps[np.argmax(direct)])
fig,axs=plt.subplots(2,2,figsize=(12,9))
for cap,label,color in [(0,'No capacitor','#748493'),(40,'40 fF: under-compensated','#d99225'),(best,f'{best:g} fF: best worst-band D','#208b75'),(120,'120 fF: over-compensated','#c24d48')]:
    ss=response(cap);axs[0,0].plot(f[mask]/1e9,20*np.log10(abs(ss[mask,3,0])),label=label,color=color,lw=2)
    axs[1,0].plot(f[mask]/1e9,20*np.log10(abs(ss[mask,2,0])),color=color,lw=2)
axs[0,0].set(xlabel='Frequency (GHz)',ylabel='Isolation S41 (dB)',title='1 · Add the two capacitors outside the EM block');axs[0,0].legend(fontsize=9)
ok=caps[np.array(direct)>=20]
axs[0,1].axvspan(ok.min(),ok.max(),color='#d7eee4');axs[0,1].axhline(20,color='#6d7b83',ls='--',lw=1)
axs[0,1].plot(caps,direct,color='#285d89',lw=2);axs[0,1].scatter([best],[max(direct)],color='#cf622f',marker='*',s=170,zorder=3)
axs[0,1].annotate(f'{best:g} fF → {max(direct):.2f} dB\nMaximize the worst band point',(best,max(direct)),xytext=(7,27),fontsize=10,arrowprops=dict(arrowstyle='->',lw=1.7))
axs[0,1].text(4,2,f'D ≥ 20 dB: {ok.min():g}–{ok.max():g} fF per end',fontsize=10)
axs[0,1].set(xlabel='Each capacitor C (fF)',ylabel='Minimum fitted-band directivity (dB)',ylim=(-2,33),title='2 · Sweep one shared value for both capacitors')
axs[1,0].set(xlabel='Frequency (GHz)',ylabel='Coupling S31 (dB)',title='3 · Check the coupling penalty')
mesh=axs[1,1].pcolormesh(f[mask]/1e9,caps,np.array(dcurves),shading='auto',cmap='viridis',vmin=0,vmax=35)
axs[1,1].axhline(best,color='white',ls='--',lw=1.8);axs[1,1].text(5.705,best+4,f'Selected {best:g} fF',color='white',fontsize=10)
axs[1,1].set(xlabel='Frequency (GHz)',ylabel='Each capacitor C (fF)',title='4 · Follow the null across the band')
fig.colorbar(mesh,ax=axs[1,1],label='Directivity (dB)')
fig.suptitle('Saved bare EM network + two ideal lumped capacitors · historical geometry · 50 Ω',fontsize=14)
save(fig,'lumped_cap_method.png')
(HERE/'catalogue/lumped_cap_check.json').write_text(json.dumps(dict(cap_fF=best,d_min_db=max(direct),reference_ohm=50,source='results/sparams_opt_nocomb_atcomb.npz',sampling='legacy fitted S-matrix + circuit calculation'),indent=2))
print('Historical 50-ohm cap optimum',best,max(direct))

# Touchstone four-port matrix is row-major (unlike the special two-port ordering).
qucs=HERE/'catalogue/qucs';qucs.mkdir(exist_ok=True)
with (qucs/'historical_bare_at_comb_50ohm.s4p').open('w') as fp:
    fp.write('! Historical bare coupler, fitted EM network; reference planes at comb connections.\n! No capacitors included. Port order 1 input, 2 through, 3 coupled, 4 isolated.\n# Hz S RI R 50\n')
    for freq,smat in zip(f,s):
        for i,row in enumerate(smat):fp.write((f'{freq:.12g} ' if i==0 else '  ')+' '.join(f'{v.real:.16g} {v.imag:.16g}' for v in row)+'\n')
(qucs/'README.md').write_text('''# EM network + lumped capacitors in QUCS

Import `historical_bare_at_comb_50ohm.s4p` into a four-port S-parameter-file component in QUCS (Qucsator S-parameter analysis). The file contains the historical bare network, including its EM parasitics, at the comb connection reference planes. It is fitted saved EM data, not new direct samples of the final symmetric geometry.

Connect Cleft from terminal 1 to 3 and Cright from 2 to 4. Assign both the same parameter C. Attach four 50-ohm RF ports; ground the file component's additional reference pin if exposed by that component. Sweep S parameters over 5.7–5.9 GHz; sweep C from 0 to 150 fF (0.5 fF in the supplied Python calculation). C=0 means omit both capacitors. Plot S31 and S41 in dB, and D=S31_dB−S41_dB; maximize minimum D over the band.

The shipped plot is computed by S→Y, stamping the two capacitor admittances, and Y→S. This is the same linear circuit problem as the diagram, but QUCS itself was not run to generate those curves. Its result should reproduce the 85 fF / 25.78 dB optimum subject to interpolation and sweep spacing. Capacitors are bridge components between signal lines, not capacitors to ground; 2C is only the odd-mode half-circuit equivalent.

The final etched comb is a distributed geometry, not two imposed 85 fF parts. Never attach the caps at external board ports and interpret that answer as the required comb capacitance.
''',encoding='utf-8')
fig,ax=plt.subplots(figsize=(12,6));ax.set(xlim=(0,10),ylim=(-.5,4.6));ax.axis('off')
ax.add_patch(Rectangle((3,1),4,2.5,fc='#e8f0f6',ec='#49687c',lw=2))
ax.text(5,2.6,'4-port S-parameter file',ha='center',fontsize=15,fontweight='bold')
ax.text(5,2,'Bare EM coupler\nNo combs / no lumped capacitors inside',ha='center',va='center',fontsize=12)
for x,edge,outer,nums in [(2,3,.7,[1,3]),(8,7,9.3,[2,4])]:
    for yy,num in zip([3.15,1.35],nums):
        ax.plot([outer,edge],[yy,yy],color='#334d60',lw=2);ax.scatter([x],[yy],s=22,color='#334d60')
        ax.add_patch(Circle((outer,yy),.16,fc='white',ec='#334d60',lw=1.7))
        ax.text(outer,yy+.28,f'P{num} · 50 Ω',ha='center',fontsize=10)
        ax.text(edge+(.15 if edge==3 else -.15),yy,str(num),ha='center',va='bottom',fontsize=11)
    ax.plot([x,x],[1.35,2.13],color='#cf713c',lw=2);ax.plot([x,x],[2.37,3.15],color='#cf713c',lw=2)
    ax.plot([x-.28,x+.28],[2.13,2.13],color='#cf713c',lw=2.8);ax.plot([x-.28,x+.28],[2.37,2.37],color='#cf713c',lw=2.8)
    ax.text(x+(-.4 if x==2 else .4),2.25,'Cleft = C' if x==2 else 'Cright = C',ha='right' if x==2 else 'left',va='center',fontsize=12,color='#a65224')
ax.text(5,.75,'Reference planes are at the physical comb connection points',ha='center',fontsize=10,color='#49687c')
ax.text(5,.13,'Solve bare EM once  →  export .s4p  →  vary two external caps in QUCS',ha='center',fontsize=13,fontweight='bold')
ax.text(5,-.22,'No remeshing or repeated 3-D solve is needed for the capacitor sweep.',ha='center',fontsize=11)
ax.set_title('What the lumped-capacitor search actually does',fontsize=16)
save(fig,'qucs_cap_workflow.png')

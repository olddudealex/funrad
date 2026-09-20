"""Selected decision branches; relations are explicit, not inferred from ID order."""
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch
from matplotlib.path import Path

RELATIONS=[('R043','R046','mesh comparison','Same geometry; different surface mesh. Neither has an edge-refined validation.'),
 ('R044','R045','edge check','Same geometry, explicit 0.04 mm edge refinement; high-D result rejected.'),
 ('R045','R048','retune','Increase overlap 0.41 to 0.48 mm and comb spacing 1.00 to 1.05 mm.'),
 ('R048','R049','branch','Increase overlap to 0.60 mm and spacing to 1.20 mm; reject this tested variant.'),
 ('R048','R050','shorten','Shorten coupled section 5.6 to 5.3 mm at the same edge settings.'),
 ('R050','R052','band validation','Shorten to 5.1 mm and solve five band frequencies; selected geometry.'),
 ('R052','R057','bare control','Remove combs; check the compensation contribution after selection.')]

# Retrospective comparison baselines, not an invented chronological optimizer log.
GROUPS = [
 ('Port and ground controls', 'Check the numerical setup before interpreting a coupler optimum.', [(1,None),(2,1),(4,2),(5,4)]),
 ('Initial compensation grid', 'Explore overlap and gap together; all of these runs use the exploratory mesh.', [(3,None),(6,3),(7,6),(8,6),(9,6),(10,9),(11,9)]),
 ('Topology and longer fingers', 'Compare routing, finger count and stronger comb loading.', [(12,9),(13,6),(14,9),(15,13),(16,15),(17,15),(18,15),(19,18),(20,18)]),
 ('Width and surface-mesh checks', 'Tune width, then test whether the apparent response survives finer surfaces.', [(21,9),(22,21),(23,21),(24,21),(26,22),(27,26),(38,26)]),
 ('Length and local compensation', 'Explore a shorter section and nearby comb/width combinations.', [(29,21),(30,29),(31,30),(32,21),(33,23),(34,26),(35,34),(36,35),(37,36)]),
 ('Ground-opening branch', 'Compare intact ground and an aperture at matching mesh settings; this is a separate branch.', [(25,22),(28,25),(47,28),(51,25)]),
 ('Short candidates and the edge test', 'Surface-mesh peaks are provisional; R044 fails its explicit edge-refinement check.', [(39,29),(40,39),(41,37),(42,40),(43,39),(44,42),(45,44),(46,43)]),
 ('Edge retuning and selected geometry', 'Retune compensation with edge refinement enabled, then shorten and validate across the band.', [(48,45),(49,48),(50,48),(52,50)]),
 ('Sensitivity and physical-model checks', 'Keep the selected outline as baseline; probe tolerances, remove combs, and include copper loss.', [(53,52),(54,52),(55,52),(56,52),(57,52),(58,52)]),
]
_known={(a,b) for a,b,_,_ in RELATIONS}
for _,purpose,entries in GROUPS:
    for child,parent in entries:
        if parent is not None and (f'R{parent:03}',f'R{child:03}') not in _known and child != 58:
            RELATIONS.append((f'R{parent:03}',f'R{child:03}','comparison baseline',purpose+' Retrospective reference, not proof of chronological ancestry.'))
RELATIONS.append(('R051','R047','ground comparison','Matched refined-mesh intact-ground versus aperture comparison; reference direction is not chronology.'))

def change_codes(before,after):
    """Qualitative deltas from saved configurations; no optimization inference."""
    codes=[]
    for key,label in [('length','L'),('w','W'),('gap','g'),('y','Y'),('overlap','O'),('fingers','N'),('jog','J'),('er','εr')]:
        a,b=before.get(key,0),after.get(key,0)
        if abs(b-a)>1e-9: codes.append(label+('↑' if b>a else '↓'))
    if any(before.get(k)!=after.get(k) for k in ('fw','fg')):codes.append('etch')
    if before.get('bend')!=after.get('bend'):codes.append('bend')
    if before.get('symmetric')!=after.get('symmetric'):codes.append('sym' if after.get('symmetric') else 'asym')
    for key,label in [('legacy_ground','GND fix'),('lower_stack','stack'),('relief','GND cut'),('copper_loss','Cu loss')]:
        if before.get(key,0)!=after.get(key,0):codes.append(label)
    mesh=[after.get(k,0)-before.get(k,0) for k in ('trace_mesh','port_mesh','resolution')]
    if any(v < -1e-9 for v in mesh):codes.append('M+')
    if any(v > 1e-9 for v in mesh):codes.append('M−')
    if after.get('edge_mesh',0)!=before.get('edge_mesh',0):codes.append('E+')
    if after.get('nf')!=before.get('nf'):codes.append('F↑' if after['nf']>before['nf'] else 'F↓')
    return codes or ['setup']

def render(runs,out):
    import textwrap
    byid={r['id']:r for r in runs}
    covered=[f'R{n:03}' for _,_,entries in GROUPS for n,_ in entries]
    expected={r['id'] for r in runs if r['source']=='redesign'}
    assert len(covered)==len(set(covered)) and set(covered)==expected, 'Decision tree must cover every redesign attempt exactly once'
    # One connected overview; arrows summarize changes relative to each reference.
    children={n:[] for _,_,entries in GROUPS for n,_ in entries}
    roots=[]
    for _,_,entries in GROUPS:
        for n,p in entries:
            if p is None: roots.append(n)
            else: children[p].append(n)
    positions={};leaf=[0]
    def place(n,depth):
        ys=[place(child,depth+1) for child in children[n]]
        if ys: y=sum(ys)/len(ys)
        else: y=leaf[0];leaf[0]+=1
        positions[n]=(depth,y)
        return y
    for root in roots:place(root,0);leaf[0]+=1
    fig,ax=plt.subplots(figsize=(32,21));ax.axis('off')
    for _,_,entries in GROUPS:
        for n,p in entries:
            if p is None:continue
            x,y=positions[p];xx,yy=positions[n]
            solid=(f'R{p:03}',f'R{n:03}') in _known
            path=Path([(x+.20,-y),(xx-.70,-yy),(xx-.20,-yy)], [Path.MOVETO,Path.LINETO,Path.LINETO])
            ax.add_patch(FancyArrowPatch(path=path,arrowstyle='-|>',mutation_scale=13,lw=1.5,color='#57788b',linestyle='-' if solid else '--'))
            codes=change_codes(byid[f'R{p:03}']['config'],byid[f'R{n:03}']['config'])
            label='\n'.join(textwrap.wrap(' '.join(codes),14,break_long_words=False))
            # Labels near the destination keep siblings separated at a fork.
            ax.text(xx-.46,-yy+.16,label,ha='center',va='bottom',fontsize=9,color='#244b63',bbox=dict(fc='white',ec='none',pad=.9,alpha=.96),zorder=4)
    for n,(x,y) in positions.items():
        m=byid[f'R{n:03}']['metrics'];count=m.get('band_samples',0)
        metric=(f"D{'min' if count>1 else '@5.8'} {m['d_min']:.1f}" if 'd_min' in m else 'control')
        color='#d5eee1' if n==52 else '#fff0cf' if n in (43,46,58) else '#ffe0db' if n in (5,45,49) else '#e7f0f7'
        ax.text(x,-y,f'R{n:03}\n{metric}',ha='center',va='center',fontsize=11,bbox=dict(boxstyle='round,pad=.35',fc=color,ec='#849ba7'),zorder=5)
    ax.set_xlim(-.5,max(x for x,y in positions.values())+.5);ax.set_ylim(-leaf[0],1)
    fig.suptitle('Complete coupler exploration — 54 four-port runs and 4 numerical controls',fontsize=21,y=.98)
    fig.text(.5,.949,'↑ increase / ↓ decrease relative to predecessor     |     L length · W width · g line gap · Y comb spacing · O overlap · N fingers · J jog · εr dielectric\nM+ finer mesh / M− coarser mesh · E+ edge refinement · F↑/F↓ frequency samples · etch correlated finger width/gap change\nDashed = comparison baseline; solid = documented follow-up. D in dB; @5.8 = one frequency.\nGreen = selected geometry; amber = unresolved or target miss; red = rejected result; blue = explored.',ha='center',va='top',fontsize=13,linespacing=1.6)
    fig.subplots_adjust(top=.86,bottom=.02,left=.02,right=.98)
    for extension in ('png','svg'):fig.savefig(out/f'solution_tree_full.{extension}',dpi=160)
    plt.close(fig)

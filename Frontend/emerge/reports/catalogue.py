"""Rebuild the SQLite catalogue and visual history from immutable saved results.

Uses numpy/matplotlib/Pillow in the EMerge venv. Does not run EM simulations.
R IDs retain order using catalogue_ids.json; filename aliases remain searchable.
"""
from pathlib import Path
import json, sqlite3, hashlib, re, html, io
from datetime import datetime, timezone
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image

HERE=Path(__file__).resolve().parents[1]
OUT=HERE/'catalogue';OUT.mkdir(exist_ok=True)
IMG=HERE.parents[1]/'Notes/FunRad/images/coupler';IMG.mkdir(parents=True,exist_ok=True)
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'white'})
STAGES={
 'controls':('Numerical controls','Separate ground placement and port-discretization effects from geometric tuning.'),
 'comb':('Compensation scan','Change finger count, overlap and main gap to find useful compensation and coupling.'),
 'topology':('Topology comparison','Compare symmetric 45°, symmetric 90° and asymmetric routes; do not assume symmetry alone guarantees improvement.'),
 'width':('Width scan','Recover coupling and match after increasing comb loading.'),
 'ground':('Ground opening','Test an L2 aperture against an intact ground with the same lower stack and mesh.'),
 'surface':('Surface mesh check','Repeat identical geometry with finer trace/port settings; test numerical stability.'),
 'length':('Length and local tuning','Shorten the loaded coupled section; then adjust gap, width and overlap together.'),
 'edge':('Edge refinement / retune','Reject the surface-mesh peak, increase overlap and retune length using explicit edge refinement.'),
 'final':('Nominal band validation','Solve five frequencies on the selected edge-refined geometry.'),
 'sensitivity':('Sensitivity checks','Perturb dielectric constant or correlated widths/spaces at 5.8 GHz only.'),
 'baseline':('Final bare control','Remove combs from the final geometry; retain other nominal settings.'),
 'legacy':('Historical studies','Imported fitted legacy data. Geometry fields not encoded in the filename remain unknown.')}

def stage(n,c):
    if c.get('straight'):return 'controls'
    if n=='final51_bare':return 'baseline'
    if n in ('final51','final51_copper9'):return 'final'
    if n.startswith('final51_'):return 'sensitivity'
    if c.get('edge_mesh'):return 'edge'
    if c.get('lower_stack'):return 'ground'
    if n.startswith('s45_check'):return 'surface'
    if n in ('a90_n3','s90_n3'):return 'topology'
    if n.startswith('s45_trim'):return 'width'
    if n.startswith(('short','refine','candidate','proposal','s45_L','s45_short')):return 'length'
    return 'comb'

SPECIAL={'final51':'Selected symmetric prototype','final51_bare':'Selected geometry without combs',
 'final51_copper9':'Selected geometry · finite copper · nine band points',
 'proposal':'Earlier apparent optimum · surface mesh','proposal_edges':'Same earlier geometry · edge refinement',
 'final51_er42':'Selected geometry · dielectric εr 4.2','final51_er46':'Selected geometry · dielectric εr 4.6',
 'final51_narrow':'Selected geometry · widths −10 µm / gaps +10 µm',
 'final51_wide':'Selected geometry · widths +10 µm / gaps −10 µm',
 'edge_short53':'Edge-refined candidate · 5.3 mm section',
 'edge_tune_o48':'Edge retune · 0.48 mm overlap','edge_tune_o60':'Edge retune · 0.60 mm overlap'}

def label(n,c):
    if n in SPECIAL:return SPECIAL[n]
    if c.get('straight'):return f"Straight-line control · port mesh {c['port_mesh']:.2f} mm"+(' · old ground' if c.get('legacy_ground') else '')
    topo=('Symmetric' if c.get('symmetric') else 'Asymmetric')+f" {c['bend']:g}°"
    return f"{topo} · L {c['length']:g} / W {c['w']:g} / gap {c['gap']:g} · {c['fingers']} fingers / overlap {c['overlap']:g}"

def metric(d):
    if 'Smat50' not in d:return {}
    s=d['Smat50'];f=d['f'];band=(f>=5.7e9)&(f<=5.9e9);i=abs(f-5.8e9).argmin()
    if not band.any():return {}
    db=20*np.log10(np.maximum(abs(s),1e-30))
    m=dict(ports=s.shape[1],samples=len(f),band_samples=int(band.sum()),rl_min=float(-db[band,0,0].max()),il_center=float(-db[i,1,0]))
    if s.shape[1]==4:m.update(coupling_center=float(db[i,2,0]),coupling_min=float(db[band,2,0].min()),coupling_max=float(db[band,2,0].max()),d_min=float((db[band,2,0]-db[band,3,0]).min()),d_center=float(db[i,2,0]-db[i,3,0]))
    return m

def collect():
    registry=OUT/'catalogue_ids.json';ids=json.loads(registry.read_text()) if registry.exists() else {}
    timestamp_file=OUT/'run_timestamps.json'
    timestamps=json.loads(timestamp_file.read_text()) if timestamp_file.exists() else {}
    runs=[]
    paths=sorted((HERE/'results_redesign').glob('*/config.json'),key=lambda p:p.stat().st_mtime)
    for p in paths:
        c=json.loads(p.read_text());key=p.parent.name
        timestamps.setdefault(key,datetime.fromtimestamp(p.stat().st_mtime,timezone.utc).isoformat())
        if key not in ids:ids[key]=f'R{1+max([int(v[1:]) for v in ids.values() if v.startswith("R")],default=0):03d}'
        raw=p.parent/'raw.npz';invalid=p.parent/'invalid_port_result.npz'
        status='completed' if raw.exists() else ('invalid_port' if invalid.exists() else 'incomplete')
        d=np.load(raw) if raw.exists() else None
        runs.append(dict(id=ids[key],name=c['name'],label=label(c['name'],c),stage=stage(c['name'],c),config=c,
                         status=status,source='redesign',geometry_source='saved config and actual polygons',
                         sampling='direct',path=p.parent,data=d,metrics=metric(d) if d is not None else {},
                         timestamp=timestamps[key]))
    # Git checkout timestamps are not experiment order. Persist both chronology and IDs.
    runs.sort(key=lambda r:int(r['id'][1:]))
    for p in sorted((HERE/'results').glob('*.npz')):
        key='legacy/'+p.name
        if key not in ids:ids[key]=f'L{1+max([int(v[1:]) for v in ids.values() if v.startswith("L")],default=0):03d}'
        d=np.load(p);c={}
        # Parse explicit labels only. Never manufacture missing historical defaults.
        tail=p.stem.split('_comb')[-1] if '_comb' in p.stem else p.stem.split('_nocomb')[-1]
        for tag,key2 in [('w','w'),('s','gap'),('o','overlap'),('y','y'),('j','jog'),('b','bend')]:
            m=re.search(tag+r'(\d+(?:\.\d+)?)',tail)
            if m:c[key2]=float(m[1])
        m=re.search(r'_comb(\d+)',p.stem)
        if m:c['fingers']=int(m[1])
        elif '_nocomb' in p.stem:c['fingers']=0
        c['symmetric']='_sym_' in p.stem
        runs.append(dict(id=ids[key],name=p.stem,label=('Historical symmetric' if c['symmetric'] else 'Historical asymmetric/default')+(' · bare' if c.get('fingers')==0 else ' · comb'),stage='legacy',config=c,
                         status='completed' if 'Smat50' in d else 'partial_matrix',source='legacy',geometry_source='partial filename only; missing values are NULL',sampling='fitted',path=p,data=d,metrics=metric(d),timestamp=None))
    registry.write_text(json.dumps(ids,indent=2))
    timestamp_file.write_text(json.dumps(timestamps,indent=2)+'\n');return runs

def database(runs):
    db=sqlite3.connect(OUT/'coupler_simulations.sqlite');db.execute('PRAGMA foreign_keys=ON')
    db.executescript('''DROP VIEW IF EXISTS comparison; DROP TABLE IF EXISTS decision_relations; DROP TABLE IF EXISTS samples; DROP TABLE IF EXISTS port_references; DROP TABLE IF EXISTS artifacts; DROP TABLE IF EXISTS simulations; DROP TABLE IF EXISTS cross_section_checks; DROP TABLE IF EXISTS circuit_checks;
    CREATE TABLE simulations(id TEXT PRIMARY KEY, alias TEXT, label TEXT, source TEXT, status TEXT, stage TEXT, rationale TEXT, symmetry TEXT, sampling TEXT, timestamp_utc TEXT, geometry_source TEXT,
      length_mm REAL,width_mm REAL,feed_width_mm REAL,gap_mm REAL,fingers INTEGER,finger_width_mm REAL,finger_gap_mm REAL,overlap_mm REAL,comb_spacing_mm REAL,jog_mm REAL,bend_deg REAL,er REAL,height_mm REAL,copper_mm REAL,relief_mm REAL,
      edge_mesh_mm REAL,trace_mesh_mm REAL,port_mesh_mm REAL,config_json TEXT,ports INTEGER,samples INTEGER,band_samples INTEGER,coupling_center_db REAL,coupling_min_db REAL,coupling_max_db REAL,d_min_db REAL,d_center_db REAL,rl_min_db REAL,il_center_db REAL,raw_path TEXT);
    CREATE TABLE samples(simulation_id TEXT REFERENCES simulations(id),frequency_hz REAL,reference TEXT,output_port INTEGER,input_port INTEGER,real REAL,imag REAL,PRIMARY KEY(simulation_id,frequency_hz,reference,output_port,input_port));
    CREATE TABLE port_references(simulation_id TEXT REFERENCES simulations(id),frequency_hz REAL,port INTEGER,real_ohm REAL,imag_ohm REAL,PRIMARY KEY(simulation_id,frequency_hz,port));
    CREATE TABLE artifacts(simulation_id TEXT REFERENCES simulations(id),kind TEXT,path TEXT,sha256 TEXT,PRIMARY KEY(simulation_id,kind));
    CREATE TABLE cross_section_checks(grid_um REAL PRIMARY KEY,width_mm REAL,gap_mm REAL,length_mm REAL,even_ohm REAL,odd_ohm REAL,eps_even REAL,eps_odd REAL,delta_theta_deg REAL,purpose TEXT);
    CREATE TABLE circuit_checks(source TEXT PRIMARY KEY,reference_ohm REAL,optimum_cap_fF REAL,d_min_db REAL,sampling TEXT);
    CREATE TABLE decision_relations(from_id TEXT REFERENCES simulations(id),to_id TEXT REFERENCES simulations(id),kind TEXT,reason TEXT,PRIMARY KEY(from_id,to_id));
    CREATE VIEW comparison AS SELECT id,label,stage,symmetry,length_mm,width_mm,gap_mm,fingers,overlap_mm,edge_mesh_mm,band_samples,coupling_center_db,d_min_db,rl_min_db,sampling,status FROM simulations;
    ''')
    keys=['length','w','feed_w','gap','fingers','fw','fg','overlap','y','jog','bend','er','h','t','relief','edge_mesh','trace_mesh','port_mesh']
    for r in runs:
        c=r['config'];m=r['metrics'];p=r['path'];d=r['data']
        sym='straight' if c.get('straight') else ('symmetric' if c.get('symmetric') else 'asymmetric')
        raw=p/'raw.npz' if p.is_dir() else p
        values=[r['id'],r['name'],r['label'],r['source'],r['status'],r['stage'],STAGES[r['stage']][1],sym,r['sampling'],r['timestamp'],r['geometry_source']]+[c.get(k) for k in keys]+[json.dumps(c)]+[m.get(k) for k in ['ports','samples','band_samples','coupling_center','coupling_min','coupling_max','d_min','d_center','rl_min','il_center']]+[str(raw.relative_to(HERE)).replace('\\','/')]
        db.execute('INSERT INTO simulations VALUES ('+','.join('?' for _ in values)+')',values)
        artifacts={'raw':raw} if raw.exists() else {}
        if p.is_dir():
            artifacts.update({k:p/(k+ext) for k,ext in [('config','.json'),('layout','.json'),('mesh','.json'),('driver_snapshot','.py')] if (p/(k+ext)).exists()})
            if (p/'layout.png').exists():artifacts['preview']=p/'layout.png'
        for kind,file in artifacts.items():db.execute('INSERT INTO artifacts VALUES (?,?,?,?)',(r['id'],kind,str(file.relative_to(HERE)).replace('\\','/'),hashlib.sha256(file.read_bytes()).hexdigest()))
        if d is None:continue
        for key,ref in [('Smat','modal'),('Smat50','50ohm')]:
            if key not in d:continue
            rows=((r['id'],float(f),ref,i+1,j+1,float(s[i,j].real),float(s[i,j].imag)) for f,s in zip(d['f'],d[key]) for i in range(s.shape[0]) for j in range(s.shape[1]))
            db.executemany('INSERT INTO samples VALUES (?,?,?,?,?,?,?)',rows)
        if 'Z0' in d:
            z=np.asarray(d['Z0']);z=np.broadcast_to(z,(len(d['f']),m.get('ports',4)))
            db.executemany('INSERT INTO port_references VALUES (?,?,?,?,?)',((r['id'],float(f),i+1,float(v.real),float(v.imag)) for f,zs in zip(d['f'],z) for i,v in enumerate(zs)))
    check=OUT/'final_cross_section.json'
    from reports.decision_tree import RELATIONS
    present={r['id'] for r in runs}
    relations=RELATIONS+[('R052','R058','model check','Same geometry, finite copper conductivity and nine directly solved band frequencies.')]
    db.executemany('INSERT INTO decision_relations VALUES (?,?,?,?)',[row for row in relations if row[0] in present and row[1] in present])
    if check.exists():
        x=json.loads(check.read_text())
        for r in x['rows']:db.execute('INSERT INTO cross_section_checks VALUES (?,?,?,?,?,?,?,?,?,?)',(r['grid_um'],x['width_mm'],x['gap_mm'],x['length_mm'],r['even_ohm'],r['odd_ohm'],r['eps_even'],r['eps_odd'],r['delta_theta_deg'],x['purpose']))
    check=OUT/'lumped_cap_check.json'
    if check.exists():
        x=json.loads(check.read_text());db.execute('INSERT INTO circuit_checks VALUES (?,?,?,?,?)',(x['source'],x['reference_ohm'],x['cap_fF'],x['d_min_db'],x['sampling']))
    db.commit();assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok';db.close()

def draw_layout(ax,r):
    p=r['path']/'layout.json'
    if not p.exists():ax.text(.5,.5,'No saved geometry',ha='center');return
    layout=json.loads(p.read_text())
    for poly in layout['polygons']:
        a=np.asarray(poly);ax.fill(a[:,0],a[:,1],color='#b87333',ec='none')
    ax.set_aspect('equal');ax.set_xlabel('x (mm)',fontsize=8);ax.set_ylabel('y (mm)',fontsize=8);ax.tick_params(labelsize=7)
    if r['config'].get('relief'):
        c=r['config']
        for side in (0,1):
            a=np.vstack(layout['polygons'][2+side*2*c['fingers']:2+(side+1)*2*c['fingers']])
            ax.add_patch(plt.Rectangle((a[:,0].min()-.05,-c['relief']/2),np.ptp(a[:,0])+.1,c['relief'],fc='#52b8d1',alpha=.5))

def visuals(runs):
    new=[r for r in runs if r['source']=='redesign']
    good=[r for r in new if r['metrics'].get('ports')==4]
    for start in range(0,len(new),9):
        fig,axes=plt.subplots(3,3,figsize=(16,10))
        for ax,r in zip(axes.flat,new[start:start+9]):
            draw_layout(ax,r);c=r['config'];m=r['metrics']
            title=f"{r['id']} · {STAGES[r['stage']][0]}\nL={c['length']:g}, W={c['w']:g}, gap={c['gap']:g}, N={c['fingers']}, overlap={c['overlap']:g} mm\n"
            title+=f"Y={c['y']:g}, J={c['jog']:g}, finger/slot={c['fw']:g}/{c['fg']:g} mm; εr={c['er']:g}\n"
            title+=(f"C={m['coupling_center']:.2f} dB | Dmin={m['d_min']:.1f} dB | {m['band_samples']} points" if 'd_min' in m else r['status']+' · straight control')
            title+=f"\nmesh: edge {c['edge_mesh']:g} / surface {c['trace_mesh']:g} / port {c['port_mesh']:g} mm; "+('finite Cu' if c.get('copper_loss') else 'PEC')
            ax.set_title(title,fontsize=8)
        for ax in list(axes.flat)[len(new[start:start+9]):]:ax.axis('off')
        fig.suptitle(f'Variant matrix {start//9+1} — all redesign runs; nominal and numerical variants',fontsize=15)
        fig.tight_layout();fig.savefig(IMG/f'variants_{start//9+1:02d}.png',dpi=130);plt.close(fig)
    frames=[]
    for i,r in enumerate(good):
        fig,axes=plt.subplots(1,2,figsize=(12,5),gridspec_kw={'width_ratios':[1.1,1]})
        draw_layout(axes[0],r);c=r['config'];m=r['metrics']
        axes[0].set_title(f"{r['id']} · {STAGES[r['stage']][0]}\nL={c['length']:g}, W={c['w']:g}, gap={c['gap']:g} mm\n{c['fingers']} fingers, overlap {c['overlap']:g}, comb spacing {c['y']:g} mm\nfinger/slot {c['fw']:g}/{c['fg']:g} mm; εr={c['er']:g}",fontsize=10)
        ax=axes[1];ax.axvspan(-15.3,-14.7,color='#bce2c6',alpha=.4)
        for v in good[:i+1]:
            mm=v['metrics'];col='#854ea5' if v['config']['edge_mesh'] else '#5d91b3'
            ax.scatter(mm['coupling_center'],mm['d_min'],color=col,marker='D' if mm['band_samples']==1 else 'o',s=30,alpha=.6)
        ax.scatter(m['coupling_center'],m['d_min'],s=155,facecolors='none',edgecolors='#dc5a22',lw=2)
        ax.set(xlim=(min(v['metrics']['coupling_center'] for v in good)-.5,max(v['metrics']['coupling_center'] for v in good)+.5),ylim=(0,42),xlabel='Coupling at 5.8 GHz (dB)',ylabel='Minimum sampled directivity (dB)',title=f"{i+1}/{len(good)}: C={m['coupling_center']:.2f}, D={m['d_min']:.1f} dB; {m['band_samples']} freq.")
        ax.grid(alpha=.2)
        fig.suptitle('Search history · chronological saved configurations',fontsize=14)
        fig.text(.5,.025,'Mixed meshes: blue = surface only; purple = edge refined. Diamonds = one frequency. No gradient algorithm.',ha='center',fontsize=9)
        fig.tight_layout(rect=(0,.05,1,.95));buf=io.BytesIO();fig.savefig(buf,format='png',dpi=105);plt.close(fig);buf.seek(0)
        frames.append(Image.open(buf).convert('RGB').quantize(colors=128))
    frames[0].save(IMG/'search_history.gif',save_all=True,append_images=frames[1:],duration=[850]*(len(frames)-1)+[3000],loop=0,optimize=False)
    # A compact visual decision log: decisions, not a fictitious optimization trajectory.
    decisions=[('1 · Analytic starting point','−15 dB → even/odd impedances\nTranscalc: W .38 / gap .15 / L 7.14'),
      ('2 · Manufacturable compensation','Clean symmetric 45° fan-outs\n0.10 mm fingers and slots; scan N, overlap, gap'),
      ('3 · Match / coupling recovery','Scan width; test ground aperture\nChange one group at a time, compare sampled D'),
      ('4 · Shorten the loaded structure','L 7.15 → 6 → 5.5–5.6 mm\nRetune gap and overlap; apparent D >34 dB'),
      ('5 · Reject a numerical optimum','Same geometry: add 0.04 mm edge refinement\nDmin 34.1 → 19.7 dB'),
      ('6 · Retune on the finer mesh','Overlap .41 → .48; comb spacing 1 → 1.05\nL 5.6 → 5.3 → 5.1 mm'),
      ('7 · Validate / challenge','PEC: five points, Dmin 32.2 dB\nFinite Cu: nine points, Dmin 30.5 dB'),
      ('8 · Prototype decision','Keep intact L2; export exact copper\nFinite Cu misses coupling target by 0.12 dB at 5.9 GHz')]
    fig,ax=plt.subplots(figsize=(12,8));ax.set(xlim=(0,2),ylim=(0,4));ax.axis('off')
    for i,(title,body) in enumerate(decisions):
        col=i%2;row=3-i//2;x=col+.5;y=row+.54
        ax.text(x,y,title+'\n\n'+body,ha='center',va='center',fontsize=10,bbox=dict(boxstyle='round,pad=.8',fc='#e9f1f5' if i!=4 else '#ffe4dc',ec='#a1b7c5'))
        if i%2==0:ax.annotate('',(1.10,y),(.90,y),arrowprops=dict(arrowstyle='-|>',mutation_scale=26,lw=3,color='#385c74'))
        if i%2==1 and i<7:
            ax.annotate('',(.5,y-.65),(1.5,y-.32),arrowprops=dict(arrowstyle='-|>',mutation_scale=24,lw=2.5,color='#385c74',connectionstyle='angle,angleA=-90,angleB=0,rad=12'))
    fig.suptitle('Physics-guided parameter sweeps and refinement checks — not gradient descent',fontsize=15)
    fig.tight_layout();fig.savefig(IMG/'decision_path.png',dpi=160);plt.close(fig)
    from reports.decision_tree import render
    render(runs,IMG)
    return new,good

def documents(runs,new):
    note=HERE.parents[1]/'Notes/FunRad/Frontend/Coupler/Coupler Simulation Catalogue.md'
    lines=['---','permalink: Coupler-Simulation-Catalogue','---','','# Coupler simulation catalogue','',
      'The design argument is in [[TX Coupler EM Method]]. This page is the complete redesign variant matrix; the database also retains the older fitted studies. IDs are stable; original filenames remain searchable aliases.', '',
      '[SQLite database](../../../../Frontend/emerge/catalogue/coupler_simulations.sqlite) · [Searchable local table](../../../../Frontend/emerge/catalogue/index.html) · [Database schema and queries](../../../../Frontend/emerge/catalogue/README.md)','',
      '**Reading the data:** all reported metrics use 50 Ω. One-point experiments do not establish a band minimum. Exploration, surface-refined and edge-refined runs are different fidelity levels. Historical fitted curves are not independent EM samples. Chronology uses saved configuration timestamps; stage/rationale labels are a retrospective reconstruction of the actual search, not an optimizer log.','',
      '## Decision tree','',
      '![Complete exploration tree: every redesign attempt](../../images/coupler/solution_tree_full.png)','','[Open the full tree as a zoomable SVG](../../images/coupler/solution_tree_full.svg)','',
      '**54 coupler runs + 4 numerical controls.** Arrow labels summarize changes relative to the preceding node; ↑ / ↓ mean increase / decrease. L = coupled length, W = trace width, g = line gap, Y = comb spacing, O = overlap, N = finger count, J = jog. M+ / M− = finer / coarser surface or port mesh; E+ = explicit edge refinement; F↑ / F↓ = more / fewer frequency samples. Other changes are named directly. Exact values remain in the table and database.','',
      'Solid arrows are documented follow-ups; dashed arrows are retrospective comparison baselines, not a claimed chronological ancestry. Dmin is the minimum over sampled frequencies; D@5.8 is a single-frequency result. Green marks the selected geometry, amber unresolved checks or a target miss, and red rejected results.','',
      'The selected path is **R044 → R045 (reject the apparent peak) → R048 → R050 → R052**. R043/R046 remain without edge validation. R058 adds copper loss and denser sampling, exposing a small coupling-target miss. The ground branch compares R051 (intact) with R047 (aperture) at matching refinement.','']
    lines += ['## Animated search and geometry matrix','','![Geometry and accumulating search results](../../images/coupler/search_history.gif)','']
    for p in sorted(IMG.glob('variants_*.png')):lines+= [f'![Variant matrix {p.stem}](../../images/coupler/{p.name})','']
    lines+=['| ID | Description | Original alias | Samples | Coupling at 5.8 (dB) | Min sampled D (dB) |','|---|---|---|---:|---:|---:|']
    for r in new:
        m=r['metrics'];lines.append(f"| {r['id']} | {r['label']} | `{r['name']}` | {m.get('band_samples','—')} | {m.get('coupling_center',float('nan')):.2f} | {m.get('d_min',float('nan')):.2f} |".replace('nan','—'))
    note.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    rows=[]
    for r in runs:
        c=r['config'];m=r['metrics'];thumb=''
        p=r['path']/'layout.png' if r['path'].is_dir() else None
        if p and p.exists():thumb=f'<img loading="lazy" width="260" src="../{p.relative_to(HERE).as_posix()}" alt="{r["id"]} saved outline">'
        rows.append('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in [r['id'],r['label'],r['name'],STAGES[r['stage']][0],r['status'],r['sampling'],c.get('length','?'),c.get('w','?'),c.get('gap','?'),c.get('overlap','?'),c.get('edge_mesh','?'),m.get('band_samples','?'),round(m['coupling_center'],3) if 'coupling_center' in m else '—',round(m['d_min'],2) if 'd_min' in m else '—'])+'<td>'+thumb+'</td></tr>')
    (OUT/'index.html').write_text('''<!doctype html><meta charset="utf-8"><title>FunRad coupler simulations</title><style>body{font:14px system-ui;margin:24px;color:#183244}input{padding:10px;width:500px}table{border-collapse:collapse}th{position:sticky;top:0;background:#dceaf3}td,th{padding:8px;border-bottom:1px solid #ddd;text-align:left}tr:nth-child(even){background:#f6f9fb}img{max-width:260px} </style><h1>FunRad coupler simulation catalogue</h1><p>50 Ω results. Mixed meshes; one frequency is not a band result. Historical data are fitted. Unknown geometry is shown as ?.</p><input id="q" placeholder="Filter ID, geometry, alias or stage…"><span id="count"></span><table><thead><tr>'''+''.join('<th>'+x+'</th>' for x in ['ID','Description','Alias','Stage','Status','Sampling','L mm','W mm','gap mm','overlap mm','edge mm','band samples','S31 dB','Dmin dB','Geometry'])+'</tr></thead><tbody>'+''.join(rows)+'''</tbody></table><script>const q=document.querySelector('#q'), rows=[...document.querySelectorAll('tbody tr')];function filter(){let n=0;for(const r of rows){r.hidden=!r.textContent.toLowerCase().includes(q.value.toLowerCase());if(!r.hidden)n++}document.querySelector('#count').textContent=' '+n+' / '+rows.length+' records'}q.addEventListener('input',filter);filter()</script>''',encoding='utf-8')
    (OUT/'README.md').write_text('''# Simulation database

Rebuild with `python -m reports.catalogue` from the EMerge directory. No EM runs are performed. The generated SQLite file is excluded from Git; all source matrices are committed. `catalogue_ids.json` preserves IDs and `run_timestamps.json` preserves original configuration timestamps across checkouts. The DB contains redesign attempts (including the incomplete port-mode run), straight controls, all legacy NPZ files, complete complex S matrices where present, port impedances, parameters and source hashes. Paths are relative to `Frontend/emerge`.

`simulations`: geometry in mm, status, sampling provenance, mesh sizes and scalar metrics. `config_json` retains every original parameter including lower-stack and solver settings. Historical parameters are parsed only when encoded explicitly; unknown values are NULL. `samples`: complex S entries, frequency in Hz, 1-based ports, modal or 50-ohm reference. `port_references`: complex modal impedances. `artifacts`: file provenance and SHA-256. `comparison`: convenient view.

All scalar results use 50 ohm and 5.7–5.9 GHz; centre is the stored sample nearest 5.8 GHz. One-sample Dmin is not broadband. Fitted legacy curves must not be ranked as equally validated against direct new samples. Stages explain groups of experiments; they do not imply a deterministic parent-child optimization or measured gradients.

```sql
SELECT * FROM comparison WHERE stage = 'final';
SELECT id,label,length_mm,gap_mm,d_min_db FROM comparison
WHERE status='completed' AND sampling='direct'
  AND edge_mesh_mm=0.04 AND band_samples>=3 ORDER BY d_min_db DESC;
SELECT frequency_hz,real,imag FROM samples
WHERE simulation_id=(SELECT id FROM simulations WHERE alias='final51')
  AND reference='50ohm' AND output_port=4 AND input_port=1
ORDER BY frequency_hz;
SELECT id,alias,config_json FROM simulations WHERE symmetry='symmetric';
```
''',encoding='utf-8')

if __name__=='__main__':
    runs=collect();database(runs);new,good=visuals(runs);documents(runs,new)
    print(f'{len(runs)} database records; {len(new)} redesign attempts; {len(good)} four-port frames')

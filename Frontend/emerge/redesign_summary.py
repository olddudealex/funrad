import json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parent/'results_redesign'
for p in sorted(ROOT.glob('*/raw.npz')):
    c=json.loads((p.parent/'config.json').read_text())
    d=np.load(p); s=d['Smat50']; db=20*np.log10(np.maximum(abs(s),1e-30))
    band=(d['f']>=5.7e9)&(d['f']<=5.9e9)
    line=f"{c['name']:27s} Z={d['Z0'].real.mean():.2f} RL={-db[band,0,0].max():.1f}"
    if s.shape[1]==4:
        line+=f" C={db[band,2,0].min():.2f}..{db[band,2,0].max():.2f} D={np.min(db[band,2,0]-db[band,3,0]):.2f}"
    print(line)

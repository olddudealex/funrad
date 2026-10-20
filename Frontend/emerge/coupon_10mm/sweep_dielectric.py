"""Sequential, resumable epsilon-r sensitivity sweeps on the saved finer mesh."""
import json
import subprocess
import sys
import numpy as np
from .model import HERE

OUT=HERE/'dielectric_sensitivity'
BASE='result_coax_open_2.8x4.8mm_5p3to6p3GHz_mesh_finer'
CORNERS=(4.2,4.8)


def main():
    OUT.mkdir(exist_ok=True)
    progress=dict(status='running',nominal_er=4.5,corners=list(CORNERS),completed=[])
    for er in CORNERS:
        stem=BASE+'_er'+f'{er:g}'.replace('.','p')
        path=HERE/f'{stem}.json'
        completed=False
        if path.exists() and (HERE/f'{stem}.npz').exists():
            meta=json.loads(path.read_text(encoding='utf-8'))
            completed=(meta['status']=='completed' and meta['pcb_er']==er and
                       np.allclose(meta['frequencies_GHz'],np.linspace(5.3,6.3,11)))
        if not completed:
            command=[sys.executable,'-m','coupon_10mm.connector_model','--l2-opening','2.8','4.8',
                     '--frequency-grid','flatness','--mesh-profile','finer','--reuse-mesh',
                     '--pcb-er',str(er),'--solve']
            progress['current_er']=er
            (OUT/'progress.json').write_text(json.dumps(progress,indent=2)+'\n',encoding='utf-8')
            print(f'Running epsilon-r={er:g} on the saved finer mesh',flush=True)
            with (OUT/f'er{er:g}.log').open('w',encoding='utf-8') as logfile:
                result=subprocess.run(command,cwd=HERE.parent,stdout=logfile,stderr=subprocess.STDOUT)
            if result.returncode:
                progress.update(status='failed',returncode=result.returncode)
                (OUT/'progress.json').write_text(json.dumps(progress,indent=2)+'\n',encoding='utf-8')
                raise RuntimeError(f'epsilon-r={er:g} failed; see {logfile.name}')
        progress['completed'].append(er)
        (OUT/'progress.json').write_text(json.dumps(progress,indent=2)+'\n',encoding='utf-8')
    progress.update(status='completed',current_er=None)
    (OUT/'progress.json').write_text(json.dumps(progress,indent=2)+'\n',encoding='utf-8')
    subprocess.run([sys.executable,'-m','coupon_10mm.report_dielectric'],cwd=HERE.parent,check=True)


if __name__=='__main__':main()

"""Six L2-window geometries, 11 frequencies each; sequential, resumable jobs.

Run from Frontend/emerge: python -m coupon_10mm.sweep_flatness
Each geometry invokes one EMerge run_sweep, not separate single-frequency jobs.
"""
import json
import subprocess
import sys
from datetime import datetime,timezone
from .model import HERE
from .connector_model import variant_paths,FLATNESS_FREQUENCIES_GHZ

OUT=HERE/'sweep_flatness_5p3to6p3'
CASES=[dict(id=f'F{k+1:02d}',width_mm=w,length_mm=l)
       for k,(w,l) in enumerate((w,l) for w in (2.8,3.5,4.2) for l in (4.2,4.8))]


def run_cases(cases,out,report_module):
    """Common sequential/resumable driver for controlled geometry studies."""
    out.mkdir(exist_ok=True)
    cases=[dict(case) for case in cases]
    status=dict(state='running',frequencies_GHz=FLATNESS_FREQUENCIES_GHZ,cases=cases)
    def save():
        status['updated_utc']=datetime.now(timezone.utc).isoformat()
        (out/'progress.json').write_text(json.dumps(status,indent=2)+'\n',encoding='utf-8')
    save()
    for case in cases:
        opening=[case['width_mm'],case['length_mm']]
        preview,base=variant_paths(opening)
        stem=base+'_5p3to6p3GHz'
        case.update(result_stem=stem,state='running')
        path=HERE/f'{stem}.json'
        if path.exists() and (HERE/f'{stem}.npz').exists():
            saved=json.loads(path.read_text(encoding='utf-8'))
            if saved.get('status')=='completed' and saved['frequencies_GHz']==FLATNESS_FREQUENCIES_GHZ:
                case['state']='completed';save();continue
        command=[sys.executable,'-m','coupon_10mm.connector_model','--l2-opening',
                 str(opening[0]),str(opening[1]),'--frequency-grid','flatness','--solve']
        # A mesh depends on geometry, not which frequencies we choose to solve.
        if (preview/'coupon_coax.msh').exists() and (preview/'mesh.json').exists():
            command.append('--reuse-mesh')
        case['command']=command;save()
        print(f'{case["id"]}: width {opening[0]:g}, length {opening[1]:g} mm',flush=True)
        with (out/f'{case["id"]}.log').open('w',encoding='utf-8') as log:
            process=subprocess.run(command,cwd=HERE.parent,stdout=log,stderr=subprocess.STDOUT)
        if process.returncode:
            case.update(state='failed',exit_code=process.returncode);status['state']='failed';save()
            raise SystemExit(f'{case["id"]} failed; see {out/case["id"]}.log')
        case['state']='completed';save()
    status['state']='completed';save()
    subprocess.run([sys.executable,'-m',report_module],cwd=HERE.parent,check=True)


def main():
    run_cases(CASES,OUT,'coupon_10mm.report_flatness')


if __name__=='__main__':main()

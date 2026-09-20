"""Sequential worker for the active investigation; exits when queue is empty."""
import json
import subprocess
import sys
from pathlib import Path

here=Path(__file__).resolve().parent
queue=here/'redesign_configs'/'queue.json'
done=set()
while True:
    pending=[x for x in json.loads(queue.read_text()) if x not in done]
    if not pending:
        break
    config=pending[0]
    log=here/'results_redesign'/f'{Path(config).stem}.log'
    log.parent.mkdir(exist_ok=True)
    with log.open('w',encoding='utf-8') as stream:
        result=subprocess.run([sys.executable,str(here/'redesign.py'),config],
                              cwd=here,stdout=stream,stderr=subprocess.STDOUT)
    print(config,'exit',result.returncode,flush=True)
    done.add(config)

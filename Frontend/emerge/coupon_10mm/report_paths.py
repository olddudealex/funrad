"""Publish coupon reports and their figures into the FunRad Obsidian vault.

Simulation inputs, mesh metadata and compact numerical results stay beside
the Python modules. Numbered Markdown reports have one home in Notes.
"""
from pathlib import Path
import re
import shutil
from urllib.parse import unquote

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
REPORTS=ROOT/'Notes/FunRad/Frontend/Coupon'
MEASUREMENTS=REPORTS/'measurements'
REPORT_NAMES={
    '01_PCB_ONLY_RESULTS.md','02_MODAL_PORT_CHECK.md','03_CONNECTOR_GEOMETRY.md',
    '04_COAX_RESULTS.md','05_L2_CUTOUT_RESULTS.md','06_L2_CUTOUT_FLATNESS_SWEEP.md',
    '07_BROADBAND_CHECK.md','08_MESH_REFINEMENT.md','09_L3_CUTOUT_RESULTS.md',
    '10_DIELECTRIC_SENSITIVITY.md',
}


def write_report(path,text):
    """Resolve legacy figure links, copy plots into the vault, and save a report.

    Repeated publication preserves already-published asset links and appended
    study sections. Variant-specific diagnostic reports outside REPORTS retain
    their existing local paths.
    """
    path=Path(path)
    if path.parent.resolve()!=REPORTS.resolve():
        path.write_text(text,encoding='utf-8')
        return
    REPORTS.mkdir(parents=True,exist_ok=True)

    def link(match):
        url=match.group(1)
        if re.match(r'^[a-z][\w+.-]*:',url,re.I) or url.startswith(('/', '#')):
            return match.group(0)
        raw,separator,fragment=url.partition('#')
        raw=unquote(raw)
        tail=separator+fragment
        if raw=='README.md':return '](index.md'+tail+')'
        if raw in REPORT_NAMES or raw.startswith(('assets/','measurements/')):
            return ']('+raw.replace(' ','%20')+tail+')'
        source=(HERE/raw).resolve()
        if source.suffix.lower() in ('.png','.svg','.gif','.jpg','.jpeg'):
            relative=source.relative_to(HERE)
            dest=REPORTS/'assets'/relative
            if source.exists():
                dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(source,dest)
            if not dest.exists():raise FileNotFoundError(f'Missing report figure: {source}')
            return '](assets/'+relative.as_posix().replace(' ','%20')+tail+')'
        # Link source files outside the vault to their repository location.
        if source.is_file() and source.is_relative_to(ROOT):
            relative=source.relative_to(ROOT).as_posix().replace(' ','%20')
            return '](https://github.com/olddudealex/funrad/blob/main/'+relative+tail+')'
        return match.group(0)

    text=re.sub(r'\]\(([^\n)]+)\)',link,text)
    path.write_text(text,encoding='utf-8')

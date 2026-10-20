"""Extend the selected 2.8 mm-wide L2 windows beneath the original tapers."""
from .model import HERE
from .sweep_flatness import run_cases

OUT=HERE/'sweep_taper_cutout_5p3to6p3'
CASES=[dict(id=f'T{k+1:02d}',width_mm=2.8,length_mm=length)
       for k,length in enumerate((5.2,5.6,6.0,5.0))]


if __name__=='__main__':run_cases(CASES,OUT,'coupon_10mm.report_taper_cutout')

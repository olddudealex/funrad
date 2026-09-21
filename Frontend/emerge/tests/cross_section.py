"""Post-design cross-section check; this did not drive the September 18 tuning."""
from pathlib import Path
import json
import numpy as np
from simulation.coupled_2d import modes

rows=[]
for d in [10.,5.]:
    ze,zo,ee,eo=modes(370.,130.,d_um=d)
    omega=2*np.pi*5.8e9
    delta=omega/299792458*(np.sqrt(ee)-np.sqrt(eo))*.0051
    rows.append(dict(grid_um=d,even_ohm=ze,odd_ohm=zo,eps_even=ee,eps_odd=eo,
                     geometric_mean_ohm=np.sqrt(ze*zo),delta_theta_deg=float(np.degrees(delta)),
                     quarter_wave_estimate_fF=delta/(2*omega*zo)*1e15))
    print(rows[-1],flush=True)
out=Path(__file__).resolve().parents[1]/'catalogue/final_cross_section.json'
out.write_text(json.dumps(dict(purpose='Post-design diagnostic, not synthesis of the final comb',width_mm=.37,gap_mm=.13,length_mm=5.1,rows=rows),indent=2))

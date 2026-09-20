# Quasi-static 2-D Solver

`Frontend/emerge/coupled_2d.py` solves the uniform microstrip cross-section. It estimates even/odd impedances and effective permittivities; the complete design is in [[TX Coupler EM Method]].

**Did it produce the final geometry? No.** It informed earlier line-width and compensation estimates. The final 0.37 mm width, 0.13 mm gap, 5.10 mm length and comb were selected by 3-D sweeps. This solver checked the final cross-section **after selection**, on 2026-09-20. That check is a diagnostic, not a retroactive account of how the optimum was found.

## Physics

For nonmagnetic materials under the quasi-TEM approximation, solve the same cross-section with the actual dielectric and then with air. The capacitances per unit length are $C$ and $C_a$. Since the air-filled line propagates at $c$:

$$L'\simeq\frac{1}{c^2C_a},\qquad Z_0\simeq\frac{1}{c\sqrt{CC_a}},\qquad\varepsilon_{\mathrm{eff}}\simeq\frac{C}{C_a}.$$

| Excitation | Strip voltages | Extracted quantities |
|---|---|---|
| Even | $+1,+1$ V | $C_e,C_{ae}\rightarrow Z_{0e},\varepsilon_e$ |
| Odd | $+1,-1$ V | $C_o,C_{ao}\rightarrow Z_{0o},\varepsilon_o$ |

Charge is integrated on one strip; capacitances are per line, with each strip at unit voltage relative to the modal symmetry reference.

## Numerical method

$$\nabla\cdot(\varepsilon\nabla V)=0,\qquad\sum_{n\in\{E,W,N,S\}}\varepsilon_{0n}(V_n-V_0)=0.$$

The code uses a uniform finite-difference grid, fixed strip potentials and grounded outer boundaries. Copper has finite cross-sectional thickness. Sparse linear solves give potentials, then flux integration gives charge. The implemented interface averaging is a discretization approximation, not proof of exact interface-flux treatment or grid convergence.

![Historical domain illustration](images/20_2D_Solver_Domain.png)

![Historical even/odd field illustration](images/21_2D_Solver_Fields.png)

These illustrations show the earlier example, not new field maps of the final 0.13 mm gap.

## Final cross-section: new diagnostic

$W=370$ µm, $S=130$ µm, $t=35$ µm, $h=210.4$ µm, $\varepsilon_r=4.4$. Grounded lid at 2.5 mm and lateral padding 1.5 mm. The grid snaps dimensions; even 5 µm does not exactly represent the 210.4 µm substrate.

| Grid, µm | $Z_{0e}$, Ω | $Z_{0o}$, Ω | $\varepsilon_e$ | $\varepsilon_o$ | $\sqrt{Z_{0e}Z_{0o}}$, Ω |
|---|---:|---:|---:|---:|---:|
| 10 | 58.112 | 37.804 | 3.4345 | 2.6963 | 46.871 |
| 5 | 58.425 | 38.448 | 3.4369 | 2.7163 | 47.396 |

For $L=5.10$ mm at 5.8 GHz, the 5 µm result gives

$$\Delta\theta=\frac{\omega L}{c}(\sqrt{\varepsilon_e}-\sqrt{\varepsilon_o})=7.309^\circ.$$

The velocity split remains: route symmetry does not eliminate microstrip inhomogeneity. Grid refinement moves odd-mode impedance by 0.64 Ω. These two points are not a rigorous uncertainty interval or asymptotic convergence study.

Putting these numbers into the **quarter-wave** capacitor estimate gives 45.5 fF/end. The final section is shorter than a quarter wave and includes distributed loading: **45.5 fF is not the extracted capacitance of the final comb** and was not used to size it.

## Scope and validation

| Useful for | Not represented |
|---|---|
| Single-line starting width | Finite-length bends and transitions |
| Even/odd velocity split | Finger inductance, end fringing and comb placement |
| Thickness and gap trends | Full four-port cancellation and broadband match |
| Cross-section checks | Real enclosure, launches and detector/termination loads |

The historical 0.37 mm single-line result was about 49.7 Ω versus about 49.9 Ω from a closed-form calculator. EMerge port results moved from about 47.9 to 48.75 Ω with refinement, then about 49.1 Ω in the edge-refined final model. Agreement between approximations is useful evidence, not an absolute calibration.

Transcalc and this solver disagree on the coupled-line effective permittivities. Finite thickness and narrow gaps are plausible contributors, but the old claim that one particular thickness correction was decisively proved wrong exceeded the evidence. Both models need their assumptions and numerical limits stated.

The condition $\sqrt{Z_{0e}Z_{0o}}=50\ \Omega$ belongs to ideal uniform coupled-line synthesis. It does not require the same geometric-mean impedance in a structure loaded with combs and transitions. Optimize the complete 3-D network against the system objectives.

## Reproduce

```python
from coupled_2d import modes
ze, zo, ee, eo = modes(370.0, 130.0, t_um=35.0,
                       er=4.4, h_um=210.4, d_um=5.0)
```

Run `python final_cross_section_check.py` in `Frontend/emerge` for both rows. [Saved parameters and results](../../Frontend/emerge/catalogue/final_cross_section.json). The original `coupled_2d.py` demonstration uses historical geometries, not the final configuration.

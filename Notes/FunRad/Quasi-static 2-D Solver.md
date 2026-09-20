# Quasi-static 2-D Solver

A small electrostatic solver — `Frontend/emerge/coupled_2d.py` — that gives $Z_0$ and $\varepsilon_{\text{eff}}$ for a single microstrip and for a coupled pair on our stack. It exists because the two references we had disagreed with each other, and it turned out both were wrong in ways that mattered. Used by [[TX Coupler EM Method]].

**Why a third opinion was needed:**

| source | $Z_0$, single 0.37 mm line | verdict |
|---|---|---|
| Closed-form calculator | 49.9 ohm | fine for a single line |
| EMerge port extraction | 47.9 ohm | not converged, reads 2-3 ohm low |
| **this solver** | **49.7 ohm** | agrees with the calculator |

For the *coupled* case the disagreement is much worse, and that is the interesting part — see *Where Transcalc goes wrong* below.


## What it actually computes

Everything rests on one fact: **a TEM line's inductance does not care about the dielectric.** Magnetic permeability is $\mu_0$ everywhere, substrate or not. So if you solve the same cross-section twice — once with the real substrate, once with everything replaced by air — the inductance is identical and can be eliminated.

Solve electrostatics twice and get two capacitances per unit length, $C$ (real) and $C_{\text{air}}$. In the air case the line must propagate at $c$, so

$$v_{\text{air}} = \frac{1}{\sqrt{L C_{\text{air}}}} = c \qquad\Longrightarrow\qquad L = \frac{1}{c^2 C_{\text{air}}}$$

Substitute that $L$ into the two standard line formulas:

$$Z_0 = \sqrt{\frac{L}{C}} = \frac{1}{c\sqrt{C\,C_{\text{air}}}} \qquad\qquad \varepsilon_{\text{eff}} = \left(\frac{c}{v}\right)^2 = \frac{C}{C_{\text{air}}}$$

So two electrostatic solves give both numbers. No magnetics, no frequency, no meshing of a 3-D volume. The price is the quasi-TEM assumption — fine at 5.8 GHz on a 0.21 mm substrate, where the cross-section is a tiny fraction of a wavelength.

For a **coupled pair** the same thing is done twice more, under two excitations:

- **even**: both strips at $+1$ V → $C_e$, giving $Z_{0e}$ and $\varepsilon_{\text{eff},e}$
- **odd**: strips at $+1$ and $-1$ V → $C_o$, giving $Z_{0o}$ and $\varepsilon_{\text{eff},o}$

Charge is integrated on **one** strip only, so the capacitances are per line.


## The numerical method

### The equation

With a position-dependent permittivity the electrostatic problem is not Laplace but

$$\nabla \cdot \big(\varepsilon(x,y)\, \nabla V \big) = 0$$

Discretised on a uniform grid with spacing $d$, the five-point stencil weights each neighbour by the permittivity *on the face between* the two nodes:

$$\sum_{n \in \{E,W,N,S\}} \varepsilon_n \left( V_n - V_0 \right) = 0$$

Using face-averaged $\varepsilon$ rather than node values is what makes the dielectric interface come out right without any special-case code: at the substrate surface the face value is the average of 4.4 and 1, which is exactly the flux-continuity condition $\varepsilon_1 E_{1,\perp} = \varepsilon_2 E_{2,\perp}$ in discrete form.

### The domain

![[20_2D_Solver_Domain.png]]

- **Dirichlet everywhere on the outside**: the ground plane along the bottom, and the side walls and lid at 0 V. This deliberately matches the PEC air box in the 3-D EMerge model rather than an open half-space.
- **Dirichlet on the strips**, which are drawn with their real 35 um thickness — they are blocks, not zero-thickness lines. This matters more than it sounds; see below.
- Everything else is unknown. The system is assembled as a sparse matrix and solved directly with `spsolve`.

### Getting the charge out

Once $V$ is known, Gauss's law gives the charge on a strip by summing the flux leaving its surface. In discrete form that is the same stencil, evaluated only on the strip's boundary nodes and only over the faces pointing away from the conductor:

$$Q = -\varepsilon_0 \sum_{\text{surface}} \varepsilon_n \left( V_n - V_{\text{strip}} \right)$$

With $V_{\text{strip}} = 1$ V, $C = Q$ numerically.


## What the two modes look like

![[21_2D_Solver_Fields.png]]

This picture is the whole coupler design in one image. The even mode's field spreads down into the substrate and out to the ground plane; very little of it is in the air gap. The odd mode has to get from $+1$ to $-1$ across 0.1 mm of gap, so a large share of its energy sits **in the air between the strips**, where $\varepsilon_r = 1$.

More field in air → lower effective permittivity → **the odd mode travels faster**. That velocity split is what ruins the isolated port and forces the compensation comb in [[TX Coupler EM Method]].


## Convergence

![[22_2D_Solver_Convergence.png]]

Neither the grid nor the box moves the answer much — both stay within about an ohm — but the grid plot is not smooth, and the reason is worth knowing.

**The scatter is dimension snapping, not discretisation error.** Every length is rounded to a whole number of cells, so a grid step that does not divide the geometry silently models a *different coupler*:

| $d$, um | h = 210.4 becomes | W = 370 becomes | S = 100 becomes | worst error |
|---|---|---|---|---|
| 20 | **220.0** | **380.0** | 100.0 | 4.6 % |
| 15 | 210.0 | **375.0** | **105.0** | 5.0 % |
| **10** | 210.0 | 370.0 | 100.0 | 0.2 % |
| 7.5 | 210.0 | **367.5** | **97.5** | 2.5 % |
| **5** | 210.0 | 370.0 | 100.0 | 0.2 % |

At $d$ = 15 um the gap is modelled 5 % too wide; at $d$ = 20 the substrate is 4.6 % too thick. Those are the outlying points, and they are the solver being asked the wrong question rather than answering badly.

**So: pick a grid step that divides your dimensions.** Here 10 and 5 um both do, and they agree to about 0.5 ohm — that residual is the genuine discretisation error.

**Box size barely matters.** Opening the side walls from 0.7 to 4 mm moves $Z_{0e}$ by well under an ohm and $Z_{0o}$ almost not at all: the odd mode's field is trapped in the gap and never reaches the walls. This also justifies the PEC lid in the 3-D model — at 2.5 mm it is electrically invisible.

**Overall uncertainty: about ±1 ohm.** Worth remembering whenever a conclusion rests on a couple of ohms.


## Validation

Three independent checks, in increasing order of how much they prove:

1. **Single line against a closed-form calculator.** 49.7 ohm against 49.9 for a 0.37 mm strip — 0.2 ohm apart.
2. **Wide-gap limit.** Push the pair apart to S = 3 mm and the two modes must converge on the single-line value. They do: $Z_{0e}$ = 49.71, $Z_{0o}$ = 49.41. This tests the coupled machinery against the single-line case it must reduce to.
3. **Against the 3-D EM model.** This is the real test, because it is a different method entirely. Run the solver on the coupler's actual cross-section, push the result through closed-form coupled-line theory, and compare with the full 3-D EMerge sweep:

| on the adopted 0.37 / 0.10 / 7.39 section | this solver | 3-D EM |
|---|---|---|
| $S_{41}$ | -20.47 dB | -20.48 dB |
| required compensation C | 75.5 fF | 76 fF (measured) |
| $S_{31}$ | -12.43 dB | -11.66 dB |

0.01 dB on the isolated port and 0.7 % on the capacitance — far closer than
either method claims on its own. $S_{31}$ is the one that parts company, by
0.8 dB, which is expected: the bends and width transitions either side of the
coupled run are part of the 3-D structure and simply do not exist in a
cross-section.


## Design curves

![[23_2D_Solver_Design_Curves.png]]

The two questions this solver was built to answer.

### Proper width for a single 50 ohm microstrip

On this stack (FR-4, $\varepsilon_r$ 4.4, h = 0.2104 mm, 35 um copper) the 50 ohm crossing is at **0.366 mm**. The design uses **0.37 mm**, which this solver puts at 49.7 ohm and an external closed-form calculator at 49.9 ohm.

The 4 um difference is inside the solver's own ±1 ohm uncertainty, so there is nothing to choose between them and `W_50` = 0.37 stands - and it is on the 0.01 mm drawing grid, which 0.366 is not. For a single line this is the easy case — **width sets impedance and nothing else**, one answer, no trade-off.

### Proper widths for a -15 dB coupled pair

Here there are two dimensions and they do nearly independent jobs:

| | set by | condition |
|---|---|---|
| match | **W** | $\sqrt{Z_{0e}Z_{0o}} = Z_0$ |
| coupling | **S** | ratio $Z_{0e}/Z_{0o}$ |

The sensitivity on this stack is about **-75 ohm per mm of W**, so a 25 um width error costs ~2 ohm of match.

For the coupler as built (S = 0.10 mm, chosen over-coupled for reasons in
[[TX Coupler EM Method]]), the 50 ohm crossing is at **W = 0.32 mm**.

### ...and why that is the wrong answer here

**Do not take the 50 ohm crossing as the coupled width unless the coupler is
operating at its design coupling.** $\sqrt{Z_{0e}Z_{0o}} = Z_0$ is derived for a
matched coupler delivering its nameplate coupling. The TX coupler's section is
deliberately over-coupled, then loaded by a compensation comb, and entered
through a width step from the feed. None of those three things is in this
solver, and together they dominate.

Measured in 3-D with the comb present:

| `W_C` | what this solver says | D worst, measured |
|---|---|---|
| 0.32 | $\sqrt{Z_{0e}Z_{0o}}$ = 50 ohm, "correct" | 15.6 dB |
| **0.37** | 46.5 ohm, 7 % low | **20.4 dB** |

The width this solver calls correct measures **4.8 dB worse** than the one that
was adopted. Worse, the uncompensated 3-D model agrees with the solver and is
equally wrong - it ranks 0.32 above 0.37 too. Only the compensated structure
tells the truth.

So the honest scope of this page: the solver tells you what a **cross-section**
does, exactly and cheaply, and that is genuinely valuable - it is how the
velocity split was pinned down and how the compensation capacitance was sized,
both confirmed against 3-D to within a couple of percent. It does not tell you
what a **structure** does. For that there is no substitute for the 3-D model.

## Where Transcalc goes wrong

Qucs Transcalc is fine for a single line and **not reliable for a coupled pair on this stack**:

| | Transcalc | this solver | 3-D EM |
|---|---|---|---|
| $Z_{0e}$ | 59.85 | 56.4 | |
| $Z_{0o}$ | 41.77 | 38.9 | |
| $\varepsilon_{\text{eff},e}$ | 3.549 | 3.45 | |
| $\varepsilon_{\text{eff},o}$ | **3.029** | **2.76** | |
| implied compensation C | 42 fF | 73 fF | **72 fF** |

The EM model sides with the solver, decisively — a factor of 1.75 on the quantity the whole compensation design depends on.

**The failure is in $\varepsilon_{\text{eff},o}$, and the reason is geometric.** The odd mode lives in the gap between the strips, so it is the mode most sensitive to what that gap actually looks like. Three things about this stack push it outside where closed-form fits were built:

- the substrate is thin, 0.21 mm;
- the copper is 35 um — **17 % of the substrate height**, so the strips are blocks, not lines, and the gap is a parallel-plate capacitor between their 35 um sidewalls;
- the gap is 0.10-0.15 mm, comparable to the substrate height.

Closed-form coupled-microstrip models carry a thickness correction, but it is a perturbation fitted for thin conductors. Here the sidewall-to-sidewall capacitance is a leading term, not a correction, and it lands almost entirely on the odd mode. Transcalc therefore under-estimates $C_o$, over-estimates $\varepsilon_{\text{eff},o}$, and reports a velocity split 37 % smaller than the real one.

**Practical rule:** use Transcalc to get into the right neighbourhood for W, S and L — it is good at that — but do not take its $\varepsilon_{\text{eff}}$ values into a compensation calculation on a stack like this one. Solve the cross-section instead.


## Running it

```
python coupled_2d.py          # validation table + the design's own numbers
python figs_2d.py             # every figure on this page
```

```python
from coupled_2d import modes, single, coupling_db
Z0e, Z0o, eps_e, eps_o = modes(W_um=320.0, S_um=100.0, d_um=5.0)
coupling, z_match = coupling_db(Z0e, Z0o)
```

Defaults are this project's stack: `er` 4.4, `h_um` 210.4, `t_um` 35, lid 2.5 mm, box half-width 1.5 mm. A single solve at $d$ = 5 um is a few hundred thousand unknowns and takes a couple of minutes; `modes()` does four of them, so expect ~10 minutes per point at production resolution and use `d_um=10` for scans.

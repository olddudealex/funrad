# TX Coupler EM Method

How the 5.8 GHz TX tap in [[RF Architecture]] got its geometry. Self-contained: every number it leans on is quoted here.

**Target:** -15 dB coupling, high directivity, good return loss, over 5.7-5.9 GHz.
**Model:** `Frontend/emerge/coupler_sim.py` (EMerge 2.8.9 + gmsh), 35 um copper etched on FR-4, ground plane, air box. Copper is PEC — no conductor loss.

![[11_Coupler_Mesh.png|560]]


## Result

| | uncompensated | with comb |
|---|---|---|
| Coupling $S_{31}$ | -11.96 dB | **-15.00 dB** |
| Isolation $S_{41}$ | -19.57 dB | -35.99 dB |
| Through $S_{21}$ | -0.815 dB | -0.588 dB |
| Return loss | 21.3 dB | 28.6 dB |
| **Directivity, worst in band** | **7.4 dB** | **20.35 dB** |

Final geometry, mm:

| | value |
|---|---|
| `W_50` feed width | 0.37 |
| `W_C` coupled width | 0.37 — *the same*, so there is no width step |
| `S_GAP` coupled gap | 0.10 |
| `L_C` coupled length | 7.39 |
| comb | 3 fingers/side, 0.08 wide, 0.06 gap, 0.27 overlap (0.60 finger) |

All bends are 90 degree mitred, no diagonals, and **every dimension sits on a 0.01 mm drawing grid** — including the derived ones: clearance = `Y_COMB` - `W_50` = 0.93, so an overlap of 0.27 puts the comb finger at exactly 0.60.

Micron-resolution widths were false precision. Rounding the old 0.371 to 0.37 moves the line by 0.08 ohm, against a fab etch tolerance near 0.02 mm — a design that cannot survive 5 um of rounding cannot be built. Measured, the rounded geometry came out *better*, so it costs nothing.

Only the stack-up keeps more digits, because it is specified by the fab rather than drawn by us: $\varepsilon_r$ 4.4, h = 0.2104 mm prepreg, 35 um copper.

![[12_Coupler_Layout.png]]


## The idea

Every number in this section comes out of `coupled_theory.py`; run it to reproduce them.

### What a -15 dB coupler requires

The nameplate coupling is the voltage coupling coefficient $k$, and a matched backward-wave coupler must also satisfy $Z_{0e} Z_{0o} = Z_0^2$. Those two conditions fix both mode impedances outright:

$$k = 10^{-15/20} = 0.1778 \qquad Z_{0e} = Z_0\sqrt{\frac{1+k}{1-k}} \qquad Z_{0o} = Z_0\sqrt{\frac{1-k}{1+k}}$$

$$Z_{0e} = 59.85\ \Omega \qquad Z_{0o} = 41.77\ \Omega$$

That is the whole specification. Everything physical follows from those two impedances plus a quarter wave of length.

### What Transcalc makes of them

Feeding those two impedances at 5.8 GHz into Qucs Transcalc, for this substrate:

![[19_Coupler_Transcalc_Synthesis.png]]

Rounded to the drawing grid, that synthesis is **W = 0.38, S = 0.15, L = 7.14 mm**, with

$$\varepsilon_{\text{eff},e} = 3.549 \qquad \varepsilon_{\text{eff},o} = 3.029$$

The last pair is what matters, and it is the reason this page exists.

### Why unequal mode velocities break the isolated port

Solve the coupled pair by even/odd decomposition. Exciting ports 1 and 3 in phase sees one line of impedance $Z_{0e}$ and electrical length $\theta_e$; out of phase sees $Z_{0o}$ and $\theta_o$. The four-port then follows from the reflection and transmission of those two lines:

$$S_{31} = \tfrac{1}{2}(\Gamma_e - \Gamma_o) \qquad S_{41} = \tfrac{1}{2}(T_e - T_o)$$

**This is Pozar's derivation, and the effect is absent there by assumption.** Pozar works in a homogeneous medium — stripline — where both modes see the same permittivity. Then $\theta_e = \theta_o$, the two transmissions are identical, $S_{41}$ vanishes *identically*, and the isolated port is perfectly isolated. Directivity never appears as a design problem because it is infinite.

Microstrip is not homogeneous. The even mode keeps most of its field in the substrate; the odd mode puts a large share in the air gap between the strips, where $\varepsilon$ = 1. So $\varepsilon_{\text{eff},e} > \varepsilon_{\text{eff},o}$, the odd mode runs faster, and at 5.8 GHz the two electrical lengths are **7.13 deg apart** even though their mean is the 90 deg that was asked for. $T_e$ and $T_o$ no longer cancel and the isolated port comes alive.

Force $\varepsilon_{\text{eff},o} := \varepsilon_{\text{eff},e}$ in the same calculation and $S_{41}$ drops to -319 dB, i.e. numerically zero. **The entire directivity limit is the velocity split.** It is a property of the medium, not of the layout, so no choice of W, S or L removes it — which is why the coupler needs something *added* rather than something adjusted.

### The fix

A capacitor bridging the two lines at each end. It is invisible to the even mode — both strips sit at the same potential, so there is no voltage across it and no current — and loads only the odd mode, slowing it until the two electrical lengths match.

**Where the formula comes from.** Four steps.

*1. What the bridging capacitor looks like to one line.* Under odd excitation the symmetry plane is a virtual ground. A capacitor $C$ from line 1 to line 2 is then two capacitors of $2C$ in series through that ground, so each line sees $2C$ to ground:

$$B = \omega \cdot 2C$$

*2. What a line section looks like as lumped elements.* A section of impedance $Z$ and electrical length $\theta$ has an exact equivalent $\pi$-network — series arm $jZ\sin\theta$, and a shunt arm at each end of

$$Y_{\text{shunt}} = \frac{j\tan(\theta/2)}{Z}$$

*3. Ask the loaded line to look longer.* Adding $B$ at each end should make the odd mode behave as a line of length $\theta_o + \Delta\theta$. Matching the shunt arms:

$$\frac{\tan\!\big((\theta_o+\Delta\theta)/2\big)}{Z_{0o}} = \frac{\tan(\theta_o/2)}{Z_{0o}} + B$$

For small $\Delta\theta$, differentiate the left side — $\frac{d}{d\theta}\frac{\tan(\theta/2)}{Z} = \frac{\sec^2(\theta/2)}{2Z}$ — which gives

$$\Delta\theta\,\frac{\sec^2(\theta_o/2)}{2 Z_{0o}} = 2\omega C$$

*4. Evaluate at the design point.* The section is a quarter wave, $\theta_o \approx 90^\circ$, so $\sec^2(45^\circ) = 2$ and the factor collapses:

$$\boxed{\;C = \frac{\theta_e - \theta_o}{2\,\omega\,Z_{0o}}\;}$$

with $\Delta\theta = \theta_e - \theta_o$ in radians, because that is exactly the length the odd mode is short by. On Transcalc's numbers this gives **40.9 fF**, and a numerical sweep of the same circuit agrees to 0.04 fF.

(Step 4's $\theta_o \approx 90^\circ$ is what produces the tidy factor of 2. Keeping $\sec^2(\theta_o/2)$ at the real 86.5 deg would say 38.5 fF instead. That is *not* more accurate — the derivation only matched the shunt arm and ignored what the capacitor does to the series arm, and the two approximations happen to cancel at $90^\circ$.)

There is no room for a discrete part at 5.8 GHz, so it is etched as an interdigital comb.

The rest of this page is the 3-D work: measure the real uncompensated coupler, find the capacitance *it* wants, then build that as a comb and tune it.


## Step 1 — the uncompensated baseline

```
python coupler_sim.py --no-comb --at-comb
```

`--at-comb` truncates both lines at the comb plane and puts the four ports there. This matters: in step 2 a lumped capacitor lands exactly on the port reference plane, so the ports must sit where the comb will actually go. Put them on the board edges instead and the capacitance that comes out is a different number, which the comb cannot be sized against.

![[13_Coupler_Geometry_at_Comb_Planes.png|560]]

| $S_{11}$ | $S_{31}$ | $S_{21}$ | $S_{41}$ | D worst |
|---|---|---|---|---|
| -24.83 | -11.66 | -0.621 | -20.48 | 8.59 dB |

![[14_Coupler_Sparams_Uncompensated.png]]

Two things to take from it.

**Coupling is deliberately 3.3 dB too strong, and the reason is not what it looks like.** Adding the comb takes $S_{31}$ from -11.66 to -15.00 dB, so the bare section has to start over-coupled. But that is *not* a property of compensation. A capacitor placed where the theory puts it — right at the ends of the coupled section — costs essentially no coupling. Out on the jog, 1 mm away, the comb is only partly a compensation element; the rest of it is plain shunt capacitance across the line pair, which de-couples them. **So `S_GAP` = 0.10 mm is a correction for where the comb had to go**, not a design value in its own right.

**Directivity is 8.6 dB and there is no isolation null anywhere in the sweep** — the signature of an uncompensated coupled-line coupler, and the reason the comb exists.


## Step 2 — find the capacitance

```
python cap_opt.py results/sparams_opt_nocomb_atcomb.npz
```

Adding lumped caps to a 4-port result is a circuit problem, so it needs no second EM run. `cap_opt.py` converts S to Y, adds $y = j\omega C$ across each end, converts back, and sweeps C. The same thing works by hand: drop the `_portref.s4p` file into a QUCS S-parameter block with a capacitor from port 1 to 3 and from port 2 to 4.

- **Optimum C = 76 fF per end, giving 37.6 dB.**
- 20 dB or better: 61 - 88 fF
- Past 114 fF, compensation is worse than none at all.

The capacitor pushes $S_{41}$ down across the whole band. Too little under-corrects, too much over-corrects straight past:

![[15_Coupler_Cap_Effect.png]]

![[16_Coupler_Cap_Window.png|640]]

### Why this is 76 fF when the closed form said 41

Three things change between the two numbers, and each is worth a row. Every capacitance in the first four rows comes from the same closed form,

$$C = \frac{\theta_e - \theta_o}{2\,\omega\,Z_{0o}} \qquad\text{with}\qquad \theta_e - \theta_o = k_0 \left(\sqrt{\varepsilon_{\text{eff},e}} - \sqrt{\varepsilon_{\text{eff},o}}\right) L$$

so the only thing differing between them is where $\varepsilon_{\text{eff}}$, $Z_{0o}$ and the dimensions came from:

| what changes | W / S / L, mm | $\varepsilon_{\text{eff},o}$ | $Z_{0o}$ | $\theta_e - \theta_o$ | C | how C was obtained |
|---|---|---|---|---|---|---|
| Transcalc's model on Transcalc's geometry | 0.38 / 0.15 / 7.14 | 3.029 | 41.77 | 7.13 deg | 40.9 fF | closed form |
| **same geometry, `coupled_2d` instead** | 0.38 / 0.15 / 7.14 | **2.754** | 39.09 | 9.76 deg | 59.8 fF | closed form |
| design width and gap | **0.37** / **0.10** / 7.14 | 2.663 | 36.29 | 11.05 deg | 72.9 fF | closed form |
| design length as well - the real section | 0.37 / 0.10 / **7.39** | 2.663 | 36.29 | 11.43 deg | **75.5 fF** | closed form |
| the same section, solved in 3-D | 0.37 / 0.10 / 7.39 | - | - | - | **76 fF** | 4-port EM + circuit sweep |

Reading down the rows: swapping the cross-section model is worth **x1.46**, the tighter gap and width **x1.22**, the slightly longer section **x1.04**.

The last row is a different kind of calculation entirely. There is no $\varepsilon_{\text{eff}}$ and no formula in it — it is the measured 4-port from step 1 with a capacitor swept across ports 1-3 and 2-4 in `cap_opt.py`, exactly as a circuit simulator would do it. It lands 0.7 % from the closed-form prediction, which is what makes the first four rows believable.

**The second row is the one worth knowing about.** Nothing about the geometry changed between rows one and two — only the source of $\varepsilon_{\text{eff},o}$ — and the answer moved by nearly half. Transcalc puts the odd mode at 3.029 where a direct solve of the same cross-section says 2.754, a 37 % larger velocity split. See [[Quasi-static 2-D Solver]] for why: the substrate is 0.21 mm, the copper is 17 % of that height, and the gap is 0.10-0.15 mm, so the strips are blocks whose 35 um sidewalls form a parallel-plate capacitor across the gap. For the odd mode that is a leading term, not the thin-conductor correction the closed forms assume.

So use Transcalc to put W, S and L in the right neighbourhood, but do not take its $\varepsilon_{\text{eff}}$ into a compensation calculation on a stack like this one.


## Step 3 — build the comb and tune it

```
python coupler_sim.py
```

![[17_Coupler_Geometry_with_Comb.png|560]]

**What was optimised:** `W_C`, `S_GAP` and the comb overlap, maximising worst-case in-band directivity subject to $|S_{31}|$ within 0.3 dB of -15 dB. `W_50` is fixed at 0.37 by the 50 ohm requirement and `L_C` at its analytic quarter wave.

### The coupled width, and a trap that cost real performance

`W_C` looks like it should follow from theory. A coupler is matched when $\sqrt{Z_{0e}Z_{0o}} = Z_0$, and [[Quasi-static 2-D Solver|the cross-section solver]] puts that crossing at **W = 0.32** for this gap. That is not the answer.

Measured in 3-D with the comb present and the coupling constraint enforced:

| `W_C` | `S_GAP` | $S_{11}$ | $S_{31}$ | $S_{41}$ | D worst | coupling in spec |
|---|---|---|---|---|---|---|
| 0.32 | 0.10 | -20.00 | -14.71 | -31.04 | 15.60 | yes |
| 0.35 | 0.10 | -24.22 | -15.04 | -34.02 | 18.25 | yes |
| **0.37** | **0.10** | **-28.56** | **-15.00** | **-35.99** | **20.35** | **yes** |
| 0.38 | 0.10 | -30.89 | -15.30 | -36.16 | 20.39 | borderline |
| 0.39 | 0.10 | -34.40 | -15.39 | -36.84 | 21.10 | no, under-coupled |
| 0.40 | 0.10 | -35.65 | -15.72 | -39.62 | 23.20 | no, under-coupled |
| 0.40 | 0.09 | -35.34 | -14.66 | -35.59 | 20.85 | no, over-coupled |
| 0.42 | 0.09 | -29.16 | -15.01 | -37.01 | 21.62 | yes |

The theoretical 0.32 is **4.8 dB worse** than the adopted 0.37. Two things to take away:

**Uncompensated directivity points the wrong way here.** Sweeping the same widths *without* the comb ranks them in the opposite order:

| `W_C` | 0.30 | 0.31 | 0.32 | 0.33 | 0.34 | 0.36 | 0.37 |
|---|---|---|---|---|---|---|---|
| D worst, no comb | 10.5 | 10.0 | 9.7 | 9.5 | 9.2 | 8.8 | **8.6** |

The width that looks worst bare (8.6 dB) is the best finished (20.4 dB); the one that looks best bare is 4.8 dB worse finished. Judge widths with the comb in place, or not at all.

**Wider is better up to the coupling constraint.** Directivity keeps climbing past 0.37 — 0.42 with a 0.09 gap reaches 21.6 dB and is still in spec — because a wider coupled run weakens coupling and deepens isolation together. It was not adopted because 0.09 mm is at the fab's minimum spacing, and spending the entire etch margin before the tolerance study has run is the wrong order. **This is a real remaining gain, gated on that study.**

`W_C` = 0.37 also happens to equal `W_50`, so the coupled section is the same width as the feed and there is no width step at either end. That is a genuine layout simplification, but it is not *why* it wins — the trend continues past it, where a step reappears with the opposite sign.

### The gap and the comb

With `W_C` settled, the other two knobs at the adopted width:

| varying | value | $S_{11}$ | $S_{31}$ | $S_{41}$ | D worst |
|---|---|---|---|---|---|
| `S_GAP` | 0.09 | -25.0 | -14.05 | -32.9 | 18.9 |
| | **0.10** | **-28.56** | **-15.00** | **-35.99** | **20.35** |
| | 0.11 | -21.6 | -16.05 | -33.0 | 16.9 |
| comb overlap | 0.25 | -30.31 | -14.69 | -33.91 | 18.96 |
| | **0.27** | **-28.56** | **-15.00** | **-35.99** | **20.35** |
| | 0.29 | -28.83 | -14.97 | -35.96 | 20.38 |

The comb sits on a plateau — 0.27 and 0.29 are indistinguishable, and only 0.25 falls off — which is the same flat optimum the capacitance sweep predicted in step 2.

**A consequence of the 0.01 mm grid worth knowing:** the gap now moves coupling by about 1 dB per step, against a spec window of ±0.3 dB. The gap alone can no longer trim coupling to target — it has to be chosen together with `W_C`. That was hidden when the dimensions carried micron resolution.

![[18_Coupler_Sparams_Final.png]]

The isolation null has appeared at 5.50 GHz where the uncompensated response had none, and coupling has come down to -15.00 dB, both as step 2 predicted.


## Three traps

- **Do not widen the line spacing.** `Y_COMB` = 1.3 mm looks like a free routing choice and is not — it sets how far the comb fingers reach. Widening it to 2.2 mm lengthens them from 0.60 to 1.05 mm, at which point they stop behaving as a lumped capacitor: measured, that costs about 6 dB of directivity and 8 dB of return loss, and retuning the comb does not get it back.
- **Do not judge the coupled width without the comb.** See above — the ranking inverts completely.
- **Do not size the comb from the formula.** The nominal $(2n-1) \times \text{overlap} \times C_m$ value is roughly half what step 2 actually wants. $C_m$ itself is right to 1 %; it is the edge-counting that is crude. Use the formula for a starting point and let the EM search finish.


## Why the comb only gets 20.4 dB when ideal caps get 37.6

This is the dominant limitation, and it *grew* when the coupled width improved:
the ideal-cap ceiling rose 9 dB while the realised comb captured only 2 dB of it.

**What the 17 dB is, precisely.** Step 2's 37.6 dB is an ideal lumped capacitor
placed *at the comb plane* - the `--at-comb` ports sit exactly where the comb
goes. Step 3's 20.4 dB is the real comb at that same plane. Both sides of the
comparison are in the same place, so this gap is **not** about where the comb
sits. About 1 dB of it is the feed lines, which the truncated model does not
have. The remaining ~16 dB is the comb failing to behave as a lumped capacitor.

**The likely mechanism is series inductance.** Current entering a finger runs
0.60 mm out and 0.60 mm back, around 15 degrees of line at 5.8 GHz, so the comb
is really C in series with L rather than a clean C. A series resonance limits
how deep the isolation null goes and how wide it stays. The one experiment that
bears on it agrees: widening `Y_COMB` from 1.3 to 2.2 mm stretched the fingers
from 0.60 to 1.05 mm and cost about 6 dB of directivity, which no amount of
re-tuning recovered.

**So the lever is a more compact comb, not a relocated one.** Shorter fingers
mean a smaller `Y_COMB`, or a capacitor topology with a shorter current path.

There is an awkward constraint in the way, and it is a modelling one rather than
a physical one: `Y_COMB` cannot shrink much below 1.3 mm because the step 1
ports are placed on the comb plane, and their faces would overlap. That is a
limit of how the baseline is measured, not of the board. Breaking it needs a
different step 1 - narrower port faces, or reference planes taken somewhere else
and de-embedded back.

### Where the comb sits, and what that separately costs

The offset is real even though it is not the 17 dB:

| | |
|---|---|
| comb centre | x = 2.57 mm |
| coupled section starts | x = 3.64 mm |
| offset | 1.07 mm, about 13 degrees of line |

The comb has to be there because the coupled section's own gap is 0.10 mm, with
no room for interdigital fingers between the lines; the jog opens them to
1.30 mm where a comb can be built. What that offset costs is **coupling, not
directivity**: out on the jog the comb is partly plain shunt capacitance across
the line pair, which de-couples them by 3.3 dB and is why `S_GAP` has to start
over-coupled (step 1). Moving the comb inward would let the gap open back up
toward the analytic 0.15 mm, which is worth having, but it is not where the
17 dB is hiding.

## Known limitations

- [ ] **The comb does not behave as a lumped capacitor** — see above. ~16 dB of headroom sits behind making it more compact (shorter fingers, less series inductance), which in turn needs a step 1 that does not force `Y_COMB` wide.
- [ ] **No conductor loss.** Copper is PEC, so $S_{21}$ = -0.588 dB is a lower bound; conductor loss (28.7 dB/m) should exceed dielectric loss (16.1 dB/m). `--cu-loss` exists but is unusable — it drops the extracted port impedance by ~5 ohm and corrupts the S-parameters with it.
- [ ] **Tolerance study outstanding** — permittivity, loss tangent, etch bias on width and gap. This is the fab-blocking item, and it also gates the wider-`W_C` gain above, which needs a 0.09 mm gap. The 0.01 mm rounding is one favourable data point on it, not a substitute.
- [ ] Port impedance is not converged: EMerge reports 47.9 ohm where two agreeing quasi-static methods give 49.6. S-parameters are quoted at the solver's own port reference, never renormalised to 50 ohm, so that error is not spread over all sixteen terms. It is not merely cosmetic — twice in this study the port reference made a comparison look more decisive than it was.


## Notes on running it

Solves take ~11 minutes on the fine mesh (the default; `--fast` mis-read directivity by 8 dB in both directions and is for flow checks only). **Run them one at a time** — two concurrent fine-mesh sweeps exhaust memory and SuperLU dies, sometimes as a confusing `gstrf was called with invalid arguments`.

Each run writes `sparams_<tag>.npz`, `.s4p` (50 ohm) and `_portref.s4p` (port reference — **use this one for circuit work**).

```
python coupler_sim.py --preview               # geometry then mesh, no solve
python coupler_sim.py --wc 0.40 --gap 0.09    # sweep a dimension, tagged output
python render_em.py comb                      # 3-D screenshots for this page
python figs.py                                # every figure on this page
```

Figures land in `Notes/FunRad/images/`, so re-running `figs.py` after a solve refreshes this page.

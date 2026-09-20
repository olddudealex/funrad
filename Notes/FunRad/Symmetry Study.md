# Symmetry Study (investigation — negative result)

The shipped coupler is not mirror-symmetric: line A runs dead straight while line B does all the bending. The compensation in [[TX Coupler EM Method]] is an **even/odd decomposition**, and that derivation assumes the structure *is* symmetric about the plane between the two lines. This page tested what that assumption is worth.

**Status: symmetry does not pay. Nothing merged.**

| | finger | $S_{11}$ | $S_{41}$ | **D worst** |
|---|---|---|---|---|
| shipped, asymmetric | 0.60 | -28.56 | -35.99 | 20.35 |
| **best asymmetric** ([[Comb Study]]) | 0.45 | **-35.79** | **-44.73** | **28.90** |
| best symmetric (90 deg, `Y_COMB` 1.40) | 0.65 | -30.45 | -43.82 | 26.37 |

The best symmetric layout loses to the best asymmetric one by **2.5 dB**, and it is not close at any other point in the space.

> **This page previously claimed the opposite.** An earlier version reported symmetry winning at 29.36 dB. That result was built on degenerate geometry — see *The mistake* at the bottom — and has been deleted rather than corrected in place. The [[Comb Study]] is unaffected and its +8.6 dB stands.


## Why symmetry should have helped

The derivation in [[TX Coupler EM Method]] rests on two things that both want a mirror plane:

1. **The even/odd decomposition itself.** Exciting the pair in phase and out of phase separates into two independent one-line problems only if the halves are mirror images.
2. **"A capacitor $C$ between the lines looks like $2C$ to a virtual ground."** That virtual ground *is* the symmetry plane under odd excitation. With line A straight and line B bent, there is no such plane at the comb — so the step is approximate exactly where the compensation is applied.

The expected payoff was less **mode conversion**: an asymmetric transition turns
even into odd and back, and whatever converts lands in the isolated port.


## What was measured

Both lines fan out from the coupled run by the same amount, mirroring about
$y = 0$. Every other dimension is held identical - `W_C` 0.38, `S_GAP` 0.11,
`L_C` 7.39, `JOG` 0.90, comb overlap 0.27 - so the only thing that differs is
the routing, and the comb finger length that the routing forces.

![[28_Symmetry_Layout.png]]

| | asymmetric | symmetric |
|---|---|---|
| `Y_COMB` | **1.00** | 1.40 (its floor is 1.33) |
| comb finger | **0.45 mm** | 0.65 mm |
| $S_{11}$ | **-35.79** | -30.45 |
| $S_{41}$ | **-44.73** | -43.82 |
| **D worst** | **28.90 dB** | **26.37 dB** |

Every symmetric variant tried is worse than the 28.90 dB the asymmetric layout reaches.


## Why it loses: the layout is boxed in

Symmetry is not free — it costs geometry, and the geometry costs more than the symmetry is worth.

In the symmetric layout each line travels **half** the level change, but a bend pair still consumes a fixed amount of vertical travel. That sets a floor on `Y_COMB`, and `Y_COMB` sets the comb finger length, which [[Comb Study]] showed is worth about 2 dB:

$$\text{90 deg: } \texttt{Y\_COMB} \ge \texttt{ctc} + 2\,\texttt{W\_50} \approx 1.33 \quad\Longrightarrow\quad \text{finger} \ge 0.61$$

The asymmetric layout runs 0.45 mm fingers. Symmetry cannot get there. And it is squeezed from the other side too: `FAR` $\ge$ `Y_COMB` $+\ 2\,$`W_50` caps `Y_COMB` at 1.76, which is why a 1.80 attempt refuses to build.

**Shallower corners do not rescue it.** Dropping the corner angle lowers the
`Y_COMB` floor and makes 0.45 mm fingers reachable, but isolation falls:

| corners | `Y_COMB` | finger | $S_{11}$ | $S_{41}$ | D worst |
|---|---|---|---|---|---|
| 90 deg | 1.40 | 0.65 | -30.45 | **-43.82** | **26.37** |
| 45 deg | 1.00 | 0.45 | **-37.63** | -38.07 | 22.89 |
| 45 deg | 0.80 | 0.40 | -35.61 | -32.48 | 17.73 (out of spec) |

The match improves and the isolation collapses. Since the compensation is what
produces isolation, the plausible reading is that gradual convergence along the
diagonals adds coupling ahead of the coupled section that the comb was never
sized to cancel. That is a hypothesis, not a measurement.

So there is no corner of the space where symmetry competes: right-angle corners
force long fingers, shallow corners cost isolation.

**Does symmetry help at all?** Probably, but it is swamped. The symmetric 90 deg / `Y_COMB` 1.40 point reaches -43.82 dB isolation with 0.65 mm fingers, while the asymmetric layout needs 0.45 mm fingers to reach -44.73. Like for like on finger length, symmetry is likely ahead — but it can never be compared like for like, because the geometry that makes it symmetric is the same geometry that lengthens the fingers.


## The mistake

Worth recording, because three separate numeric checks passed on geometry that was wrong, and the figure caught it in seconds.

**Defect 1 — the mitre over-cuts below 90 degrees.** EMerge sizes a chamfer as a fraction of the *corner diagonal*, which grows without bound as the angle gets shallow. At 45 degrees with the project's `dsratio` of 0.5 the cut is 0.370 mm and **the trace edge folds back on itself by a full line width**:

| corner type | dsratio | worst backward step at 45 deg |
|---|---|---|
| miter | 0.50 | **0.370 mm** |
| miter | 0.15 | 0.004 mm |
| **square** | - | **0.000 mm** |
| *miter at 90 deg (shipped)* | 0.50 | 0.000 mm |

Fixed: `build()` uses square corners for any angle other than 90 degrees.

**Defect 2 — the symmetric layout ran degenerate.** At `Y_COMB` 1.24 the level change is 0.375 mm and the 90 degree bend pair alone eats 0.370, leaving **5 um of straight** between the two corners. The chamfers merge into one facet, and the transition measures **45.0 degrees** despite being labelled 90. Every symmetric result in the earlier version of this page sat on that geometry, and the "90 vs 45" comparison it reported was really 45-chamfered against 45-square.

Fixed: `build()` refuses any level change leaving under 50 um of straight, and says why.

**What the checks missed.** Before the defects were found, three invariants passed:

- the path **centreline** landed within 1e-4 mm of prediction — true, but it is the *edges* that fold;
- the two lines' **min/max y** never overlapped — true, and a fold-back does not require them to;
- a **self-intersection** test returned zero — the fold stops just short of a strict crossing.

A fourth, minimum edge-to-edge distance, produced a **false positive** instead: it flagged every 90 degree design as "pinched" at 0.2616 mm, which is simply $W_{50}/\sqrt{2}$ — what a 90 degree mitre geometrically *is*.

What actually found both defects was plotting the outline as a traced path with vertices marked, and watching x run 3.30 -> 3.19 -> forward again.

**For geometry, look at the picture.** A numeric invariant only catches the failure it was written for.


## Where this leaves things

- **Do not pursue symmetry** with this routing. The finger-length penalty it forces is larger than the mode-conversion benefit it buys.
- **[[Comb Study]] is the live proposal** at 28.90 dB, +8.6 dB on the shipped design, and its geometry was never degenerate — 0.14 to 1.13 mm of straight throughout.
- **Worth keeping from this page:** the two geometry traps above, and the observation that isolation at matched finger length does favour symmetry. A routing that delivers symmetry *without* lengthening the fingers would be worth revisiting — putting the comb at the coupled-section end rather than on a jog is the obvious candidate.


## Reproducing

```
python coupler_sim.py --symmetric --bend 90 --ycomb 1.40 --wc 0.38 --jog 0.90 --gap 0.11 --overlap 0.27
python figs_comb.py sym
```

`--symmetric` mirrors both lines about y = 0. `--bend` sets the corner angle. Both refuse to build degenerate geometry rather than drawing something mislabelled.

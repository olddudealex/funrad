# Comb Study (investigation, not yet adopted)

An investigation into the biggest remaining shortfall in [[TX Coupler EM Method]]: an ideal lumped capacitor at the comb plane reaches 37.6 dB of directivity, while the etched comb reaches 20.4 dB. Where do the missing ~16 dB go, and can the comb be moved closer to the coupled section so the theory describes it better?

**Status: succeeded, not merged.** Nothing here has been applied to the shipped design. Every dimension is on the 0.01 mm grid, so it is directly adoptable.

| | shipped | **this study** |
|---|---|---|
| `W_C` / `Y_COMB` / `JOG` / `S_GAP` | 0.37 / 1.30 / 1.40 / 0.10 | **0.38 / 1.00 / 0.90 / 0.11** |
| Coupling $S_{31}$ | -15.00 | -15.24 |
| Isolation $S_{41}$ | -35.99 | **-44.73** |
| Through $S_{21}$ | -0.588 | **-0.550** |
| Return loss | 28.6 dB | **35.8 dB** |
| **Directivity, worst in band** | **20.35 dB** | **28.90 dB** |

**+8.6 dB directivity, +7.2 dB return loss, and a wider gap** — better performance *and* better fab margin.

Two changes, both visible in the layout: the comb walks 0.25 mm closer to the coupled section, and its fingers get shorter.

![[24_Comb_Study_Layout.png]]


## Two hypotheses, and the first one was wrong

The original note blamed the comb's distance from the coupled section, then its series inductance. Both were guesses. Here they are tested.

### Series inductance — refuted

Current entering a finger runs its length and back, so the comb is C in series with some L. Estimating L from the finger as a length of high-impedance line (0.08 mm wide, ~95 ohm, ~0.53 nH/mm):

| `Y_COMB` | finger | path out+back | L | self-resonance | $C_{\text{eff}}/C$ at 5.8 GHz |
|---|---|---|---|---|---|
| 1.00 | 0.45 | 0.90 mm | 0.48 nH | 26 GHz | 1.05 |
| 1.30 | 0.60 | 1.20 mm | 0.64 nH | 23 GHz | 1.07 |
| 1.60 | 0.75 | 1.50 mm | 0.80 nH | 20 GHz | 1.09 |

Self-resonance sits three to five times above the band and the effective capacitance shifts by under 10 % — inside the comb's own ±10 % tuning plateau. **Too weak to explain anything.**

### Capacitance to ground — supported

The theory in [[TX Coupler EM Method]] wants a capacitor *between the two lines* and nothing else. But every finger is also a plate of copper over the ground plane, and that capacitance is pure parasitic:

| `Y_COMB` | finger | $C$ to ground, 6 fingers | as % of the 76 fF target |
|---|---|---|---|
| 0.90 | 0.40 | 36 fF | 47 % |
| 1.00 | 0.45 | 40 fF | 53 % |
| 1.30 | 0.60 | **53 fF** | **70 %** |
| 1.60 | 0.75 | 67 fF | 88 % |
| 2.20 | 1.05 | 93 fF | 123 % |

Parallel-plate only, ignoring fringing, so these are lower bounds. At the shipped `Y_COMB` the comb throws away **70 % as much capacitance to ground as it delivers between the lines**. That is not a correction term; it is the same order as the design quantity.

**The test.** Hold the comb's capacitance fixed — the finger *overlap* sets the facing edge, hence C — and vary only `Y_COMB`, which changes the finger stem length and therefore the copper area over ground:

| `Y_COMB` | finger | $S_{11}$ | $S_{41}$ | D worst |
|---|---|---|---|---|
| 0.90 | 0.40 | **-36.34** | -35.20 | 20.03 |
| 1.00 | 0.45 | **-36.70** | -36.46 | **21.29** |
| 1.15 | 0.52 | -32.86 | -35.07 | 20.14 |
| 1.30 (shipped) | 0.60 | -28.56 | -35.99 | 20.35 |
| 1.60 | 0.75 | -24.84 | -33.64 | 17.91 |

**Return loss swings 12 dB, monotonically with finger length.** The inductance model predicts a few per cent; the ground-capacitance model predicts this ordering and roughly this size. That settles it.

![[25_Comb_Study_Parasitic.png]]

The measured $S_{11}$ and the predicted parasitic track each other almost line for line, and the parasitic climbs to within striking distance of the 76 fF the comb is supposed to be delivering.

It also explains the trap already recorded in the main note — widening `Y_COMB` to 2.2 mm cost ~6 dB and no re-tuning recovered it. At 2.2 mm the parasitic *exceeds* the useful capacitance.


## Moving the comb closer

The second question, and the one with the larger payoff. The comb sits on the jog because the coupled section's gap is 0.10 mm, with no room for fingers between the lines. Its offset is

$$\text{offset} = \frac{\texttt{JOG}}{2} + \texttt{W\_50}$$

so shortening `JOG` walks it inward. `JOG` cannot go below the comb's own span, 0.78 mm.

| `JOG` | offset | $S_{31}$ | $S_{41}$ | D worst | coupling |
|---|---|---|---|---|---|
| 1.40 (shipped) | 1.07 mm | -15.00 | -35.99 | 20.35 | in spec |
| 1.10 | 0.92 mm | -14.57 | -37.95 | 22.47 | over-coupled |
| 0.90 | 0.82 mm | -13.95 | -39.12 | 24.65 | over-coupled |
| 0.80 | 0.77 mm | -14.59 | -45.28 | 29.78 | over-coupled |

Directivity climbs steeply - but so does coupling, so none of those rows is creditable as it stands; coupling is put back on target in the next section.

![[26_Comb_Study_Offset.png]]

**Why does coupling rise when the comb moves in?** Not for the reason the finger-length section gives. Moving the comb does **not** change the fingers at all - same `Y_COMB`, same overlap, same length - so their capacitance to ground is identical in every row of that table. The ground parasitic explains the `Y_COMB` sweep and has nothing to say about this one.

Re-running the same `JOG` change with the comb deleted separates the causes:

| $S_{31}$ | JOG 1.40 | JOG 0.90 | change |
|---|---|---|---|
| no comb | -11.96 | -11.71 | +0.25 dB |
| with comb | -15.00 | -13.95 | **+1.05 dB** |

Shortening `JOG` also shortens the whole board by 1 mm and moves both lead-ins, and that routing change alone accounts for **23 %** of the shift. The remaining 0.80 dB needs the comb to be there.

**The surviving explanation is interference between two coupling paths.** The comb bridges line A to line B directly, so it is a second route to port 3 alongside the coupled section itself. The two contributions add with a relative phase set by the distance between them, and interference changes *magnitude* - which a pure phase shift could not. Moving the comb changes that distance, hence the coupling.

That also fits what the compensation is doing at port 4: the whole point of the capacitor is to add a second path that cancels there. It would be odd if it added nothing at port 3.

**This is a hypothesis with one supporting measurement, not a demonstrated mechanism.** What would settle it: sweep `JOG` finely enough to see the coupling oscillate with distance rather than drift monotonically, or extract the comb's own S-parameters and add them to the coupled section in a circuit model at varying separations.


## Putting it together

Each step inward has to be paid for by weakening coupling again. The gap does the coarse work and `W_C` the fine trim:

| configuration | $S_{11}$ | $S_{31}$ | $S_{21}$ | $S_{41}$ | D worst | spec |
|---|---|---|---|---|---|---|
| shipped: W 0.37, Y 1.30, J 1.40, gap 0.10 | -28.56 | -15.00 | -0.588 | -35.99 | 20.35 | in |
| move in: W 0.37, Y 1.30, J 0.90, gap 0.11 | -29.71 | -15.01 | -0.566 | -39.96 | 23.17 | in |
| + short fingers: W 0.37, Y 1.00, J 0.90, gap 0.11 | -36.16 | -14.81 | -0.564 | -40.18 | 25.22 | in |
| **+ W_C trim: W 0.38, Y 1.00, J 0.90, gap 0.11** | **-35.79** | **-15.24** | **-0.550** | **-44.73** | **28.90** | **in** |
| too far in: W 0.38, Y 1.00, J 0.80, gap 0.11 | -33.40 | -14.78 | -0.562 | -40.28 | 25.13 | in |
| wrong knob: W 0.37, Y 1.00, J 0.90, gap 0.10, overlap 0.25 | -34.23 | -13.83 | -0.607 | -33.66 | 19.81 | out |

Three things worth keeping.

**The gap gets wider, not narrower** — 0.10 to 0.11 mm. Every other improvement found in this project wanted a *tighter* gap and spent fab margin; the `W_C` 0.42 option needed 0.09 mm. This one hands margin back while improving performance, which matters because etch tolerance on the gap is the fab-blocking risk.

**Coupling must be restored with the gap and `W_C`, not the comb.** The last row weakens coupling by shrinking the comb instead — it loses 5.4 dB and misses spec anyway. Both knobs move $S_{31}$ but they are not interchangeable: the comb sets compensation, the gap sets coupling.

**`JOG` 0.80 is past the optimum.** It looked best of all when over-coupled, but once coupling is restored it falls to 25.13. The turnover is real, and `JOG` 0.90 is the place to be.


## The result is broadband, not a knife edge

Worth checking, because a 28.9 dB worst case could be a sharp null that a fab tolerance would walk straight off:

| f, GHz | shipped | this study |
|---|---|---|
| 5.60 | 22.0 | 28.8 |
| 5.70 | 21.5 | 29.4 |
| 5.80 | 21.0 | **29.5** |
| 5.90 | 20.4 | 28.9 |
| 6.00 | 19.6 | 27.7 |

It is **flatter than the shipped design** — 0.7 dB of spread across the band against 2.4 dB — and $S_{41}$ stays below -44 dB throughout. The isolation null is broad, not resonant.

![[27_Comb_Study_Sparams.png]]

The shipped design (dashed) puts its isolation null below the band and reaches only -36 dB; the study (solid) digs a deeper null and centres it, while $S_{31}$ stays on top of the original. Return loss improves across the whole band as well.

**This overturns a trap in the main note.** That note says *do not tune by putting the isolation null at 5.8 GHz*, because on the old geometry the best in-band worst case sat with the null near 5.0-5.5 GHz. Here the null is at 5.82 GHz, inside the band, and it is the best configuration found. The old advice was specific to a shallow null; with a deep broad one, centring it is correct. **If this study is merged, that trap has to be rewritten, not carried over.**


## Where this stands

- **Recommended:** `W_C` 0.38, `Y_COMB` 1.00, `JOG` 0.90, `S_GAP` 0.11, overlap 0.27. 28.90 dB worst-case directivity, -35.8 dB return loss, coupling -15.24 dB, all on the 0.01 mm grid.
- **Coupling sits 0.24 dB low** at band centre and reaches -15.61 at the top of the band. Inside the ±0.3 dB spec at 5.8 GHz as written, but with less margin than the shipped design. A 0.005 mm trim would centre it, which the drawing grid does not allow — so if tighter centring is wanted, it has to come from `L_C` or the comb.
- **Not attempted:** relieving the ground plane under the comb. That attacks the parasitic directly rather than working around it, and is the obvious next experiment.
- **The floor on `JOG`** is the comb's own 0.78 mm span. Going closer needs a different comb topology — fewer or wider-spaced fingers, or one sitting at the coupled-section end with line B flaring away after it.
- **Before merging:** this changes four dimensions at once against a design whose tolerance study has not been run. The 0.11 mm gap is more forgiving than 0.10, which helps, but the whole configuration should go through the tolerance study before it replaces a known-good design.


## Reproducing

```
python coupler_sim.py --wc 0.38 --ycomb 1.00 --jog 0.90 --gap 0.11 --overlap 0.27
```

`--ycomb` sets the line spacing at the comb; at fixed `--overlap` it changes only the finger length, hence the parasitic, not the capacitance. `--jog` sets the straight run carrying the comb, so it moves the comb's offset. Both write tagged result files and leave the shipped design untouched.

```
python figs_comb.py        # every figure on this page
```

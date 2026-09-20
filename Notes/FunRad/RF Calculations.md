# RF Calculations

This page explains the equations used by [[FunRad Stages Calculations.ods]]. [[RF Architecture]] stays short and describes the design; [[FunRad Rev.A Specification]] holds configuration decisions.

All logarithms are base 10. Voltages are RMS unless explicitly marked peak or peak-to-peak.

<span style="color:red">The simulator antenna and receiver-noise models were recently corrected. Recalculate and compare the workbook reference cases before treating the numerical SNR examples below as signed-off performance.</span>

## Symbols and constants

| Symbol | Meaning |
| --- | --- |
| $P$ | RF power |
| $V$ | RMS voltage |
| $G$ | power gain in dB; loss is negative gain |
| $G_v$ | voltage gain in dB |
| $NF$ | noise figure in dB |
| $F=10^{NF/10}$ | linear noise factor |
| $B$ | equivalent noise bandwidth in hertz |
| $R_0=50\ \Omega$ | RF reference impedance |
| $k=1.380649\times10^{-23}\ \mathrm{J/K}$ | Boltzmann constant, exact SI value |
| $T_0=290\ \mathrm{K}$ | standard noise reference temperature |
| $P_0=1\ \mathrm{mW}$ | dBm reference power |

## Where -174 dBm/Hz comes from

The available thermal-noise density of a matched source at $T_0$ is

$$
N_0=kT_0.
$$

Relative to 1 mW,

$$
N_{0,\mathrm{dBm/Hz}}
=10\log_{10}\left(\frac{kT_0}{P_0}\right)
=10\log_{10}\left(\frac{(1.380649\times10^{-23})(290)}{1\times10^{-3}}\right)
=-173.98\ \mathrm{dBm/Hz}.
$$

The workbook rounds this to $-174\ \mathrm{dBm/Hz}$. Integrated over an equivalent noise bandwidth $B$,

$$
P_{n,\mathrm{dBm}}=N_{0,\mathrm{dBm/Hz}}+10\log_{10}(B).
$$

## Cascaded signal levels and tolerances

For stage $n$,

$$
P_{out,n}=P_{out,n-1}+G_n.
$$

With gain/loss tolerance $\Delta G_n$,

$$
P_{min,n}=P_{min,n-1}+G_n-\Delta G_n,
$$

$$
P_{max,n}=P_{max,n-1}+G_n+\Delta G_n.
$$

This deliberately accumulates worst-case limits. Statistical RSS tolerancing would be a separate result and must be labelled as such.

### TX example

At the example attenuator setting,

$$
P_{TX,out}=2-3-16+19=2\ \mathrm{dBm}.
$$

Let the signed PE43711 entry be $g_A=-16\ \mathrm{dB}$. The workbook model for attenuation accuracy is

$$
\Delta A=-\left[(0.06\ \mathrm{dB/dB})g_A+0.25\ \mathrm{dB}\right].
$$

Therefore

$$
\Delta A=-\left[0.06(-16)+0.25\right]=0.71\ \mathrm{dB}.
$$

The coefficients are device-model inputs; they must remain visible beside the formula rather than being embedded as unexplained numbers.

### LO example

Before the four-way divider,

$$
P_{LO,prediv}=2-3-5+12=6\ \mathrm{dBm}.
$$

The ideal division loss of $N$ equal outputs is

$$
L_N=10\log_{10}(N).
$$

For $N=4$, $L_4=6.02\ \mathrm{dB}$, so the ideal nominal output is approximately

$$
P_{LO,out}=6-6.02=-0.02\ \mathrm{dBm}
$$

per mixer. PCB and excess divider loss must be added when known.

## Target received power

For a monostatic point target in free space,

$$
P_r=\frac{P_tG_tG_r\lambda^2\sigma}{(4\pi)^3R^4L},
$$

where $\lambda=c/f_c$, $\sigma$ is RCS in square metres, $R$ is range, and $L$ is the linear product of additional losses. In decibel form,

$$
P_{r,\mathrm{dBm}}=P_{t,\mathrm{dBm}}+G_{t,\mathrm{dBi}}+G_{r,\mathrm{dBi}}
+20\log_{10}(\lambda)+10\log_{10}(\sigma)
-30\log_{10}(4\pi)-40\log_{10}(R)-L_{\mathrm{dB}}.
$$

Each antenna gain must appear once. The propagation model must not apply $G_t$ or $G_r$ again if antenna blocks have already applied them.

For unchanged frequency, antennas, RCS, and losses, the difference between two cases is

$$
\Delta P_r=\Delta P_t+40\log_{10}\left(\frac{R_1}{R_2}\right)+\Delta\sigma_{\mathrm{dBsm}}.
$$

The workbook presently contains 1 m and 150 m cases. It also contains the inverse calculation: start with the ADC maximum and minimum useful voltages, refer them back through the RX gain, convert acceptable input power to distance, and repeat for TX attenuation and RCS. Those plots are useful dynamic-range views, but their limits inherit the ADC definitions still marked open.

The current RX worksheets use these signal levels as inputs to the receiver cascade:

| Case | TX amplifier output | TX antenna gain | Range | RCS | RX antenna output |
| --- | ---: | ---: | ---: | ---: | ---: |
| Far target | $2\ \mathrm{dBm}$ | $12\ \mathrm{dBi}$ | $150\ \mathrm{m}$ | $0\ \mathrm{dBsm}=1\ \mathrm{m^2}$ | $-95.60\ \mathrm{dBm}$ |
| Close target | $-15\ \mathrm{dBm}$ | $12\ \mathrm{dBi}$ | $1\ \mathrm{m}$ | $0\ \mathrm{dBsm}=1\ \mathrm{m^2}$ | $-25.50\ \mathrm{dBm}$ |

Their relative scaling follows the $R^{-4}$ law. With the other terms unchanged,

$$
\Delta P_r=(P_{t,close}-P_{t,far})
+40\log_{10}\left(\frac{R_{far}}{R_{close}}\right).
$$

Substitution gives

$$
\Delta P_r=(-15-2)+40\log_{10}\left(\frac{150}{1}\right)=70.04\ \mathrm{dB}.
$$

The two workbook inputs differ by

$$
-25.50-(-95.60)=70.10\ \mathrm{dB},
$$

which agrees within $0.06\ \mathrm{dB}$ of rounding. This relative check does not by itself validate the absolute received power; that is the comparison still required against the corrected simulator.

## LNA output signal and noise

The working values are

$$
G_{LNA}=17.9\ \mathrm{dB},\qquad NF_{LNA}=0.66\ \mathrm{dB},\qquad B_{RF}=150\ \mathrm{MHz}.
$$

The signal is

$$
P_{s,LNA}=P_r+G_{LNA}.
$$

For the far target,

$$
P_{s,LNA,far}=-95.60+17.9=-77.70\ \mathrm{dBm}.
$$

For the close target,

$$
P_{s,LNA,close}=-25.50+17.9=-7.60\ \mathrm{dBm}.
$$

If the matched source noise at $T_0$ is included at the LNA input, the total output noise is

$$
P_{n,LNA}=N_{0,\mathrm{dBm/Hz}}+10\log_{10}(B_{RF})+NF_{LNA}+G_{LNA}.
$$

Using the rounded thermal-noise density derived earlier,

$$
P_{n,LNA}
=-174+10\log_{10}(150\times10^6)+0.66+17.9
=-73.68\ \mathrm{dBm}.
$$

This expression already contains both the matched-source thermal noise and the LNA noise figure. It is the convenient workbook equation for total LNA output noise under the $T_0$ reference condition.

The simulator represents the same result in two pieces. Because it propagates source noise separately, it adds only the LNA's device contribution

$$
N_{add,in}=kT_0B_{RF}(F_{LNA}-1),
$$

then apply gain and combine uncorrelated powers. The two methods are equivalent when their reference conditions are the same; mixing them double-counts source noise.

## Conversion from dBm to dBV

At cells I9 and J9,

$$
V_{RMS}=\sqrt{R_0P_0\,10^{P_{dBm}/10}},
$$

and

$$
V_{dBV}=20\log_{10}\left(\frac{V_{RMS}}{1\ \mathrm{V}}\right).
$$

Combining the equations,

$$
V_{dBV}=P_{dBm}+10\log_{10}(R_0P_0).
$$

For $R_0=50\ \Omega$ and $P_0=1\ \mathrm{mW}$,

$$
10\log_{10}(50\times10^{-3})=-13.0103\ \mathrm{dB},
$$

so

$$
V_{dBV}=P_{dBm}-13.0103.
$$

The number $-13.0103$ is therefore not an arbitrary offset; it is the 50 Ω dBm-to-dBV conversion.

Applying it to the LNA outputs gives

$$
V_{n,LNA}=-73.68-13.0103=-86.69\ \mathrm{dBV},
$$

$$
V_{s,LNA,far}=-77.70-13.0103=-90.71\ \mathrm{dBV},
$$

$$
V_{s,LNA,close}=-7.60-13.0103=-20.61\ \mathrm{dBV}.
$$

From this point onward, the workbook propagates both signal and noise as RMS voltage quantities in dBV.

## ADL5380 output-referred added noise

The working values are $G_{v,mix}=5.8\ \mathrm{dB}$ and $NF_{mix}=15.5\ \mathrm{dB}$. Thermal-noise density in the same 50 Ω voltage reference is

$$
N_{0,dBV/Hz}=N_{0,dBm/Hz}+10\log_{10}(R_0P_0)\approx-186.99\ \mathrm{dBV/Hz}.
$$

The mixer noise factor is

$$
F_{mix}=10^{NF_{mix}/10}.
$$

Noise factor describes total output noise relative to an ideal noiseless device driven by a matched $T_0$ source. Its two parts are

$$
F=1+(F-1).
$$

The `1` is the source thermal noise propagated through an ideal device. The $(F-1)$ term is noise added by the real device, referred to its input. Because the workbook already propagates the LNA/input noise, the mixer-added term must use $F-1$:

$$
V_{n,add,mix}=N_{0,dBV/Hz}+10\log_{10}(B_{RF})
+10\log_{10}\left(10^{NF_{mix}/10}-1\right)+G_{v,mix}.
$$

Thus

$$
10\log_{10}\left(10^{NF/10}-1\right)=10\log_{10}(F-1)
$$

is simply the dB form of the device-added-noise multiplier. Using $F$ here would count the source-noise part twice. For an ideal device, $NF=0\ \mathrm{dB}$, $F=1$, and $F-1=0$, correctly giving zero added noise.

Input noise propagated through the mixer is

$$
V_{n,from\ input,mix}=V_{n,LNA}+G_{v,mix}.
$$

Independent noise terms add as mean-square voltages, which in dBV is

$$
V_{n,mix}=10\log_{10}\left(10^{V_{n,add,mix}/10}+10^{V_{n,from\ input,mix}/10}\right).
$$

The signal follows voltage gain:

$$
V_{s,mix}=V_{s,LNA}+G_{v,mix}.
$$

For example, the input noise propagated to the mixer output is

$$
V_{n,from\ input,mix}=-86.69+5.8=-80.89\ \mathrm{dBV}.
$$

The workbook results after combining that noise with the mixer-added term are:

| Quantity | Far target | Close target |
| --- | ---: | ---: |
| Mixer output-referred added noise | $-84.07\ \mathrm{dBV}$ | $-84.07\ \mathrm{dBV}$ |
| Input noise propagated to output | $-80.89\ \mathrm{dBV}$ | $-80.89\ \mathrm{dBV}$ |
| Total mixer output noise | $-79.19\ \mathrm{dBV}$ | $-79.19\ \mathrm{dBV}$ |
| Mixer output target signal | $-84.91\ \mathrm{dBV}$ | $-14.81\ \mathrm{dBV}$ |

The noise is identical in the two cases because the receiver settings and assumed noise environment are identical. Only target signal level changes.

## First IF filter

For insertion gain $G_{f1}=-1\ \mathrm{dB}$, input noise bandwidth $B_{RF}$, and output equivalent noise bandwidth $B_{IF}=1\ \mathrm{MHz}$,

$$
V_{s,f1}=V_{s,mix}+G_{f1},
$$

$$
V_{n,f1}=V_{n,mix}+G_{f1}+10\log_{10}\left(\frac{B_{IF}}{B_{RF}}\right).
$$

This bandwidth-ratio shortcut assumes a sufficiently flat input noise density and a filter whose effective noise bandwidth really is $B_{IF}$. Once the filter is designed, use its equivalent noise bandwidth

$$
B_{ENBW}=\frac{1}{|H(0)|^2}\int_0^\infty |H(f)|^2\,df
$$

instead of treating its corner frequency as automatically equal to noise bandwidth.

With the provisional $1\ \mathrm{MHz}$ bandwidth and $-1\ \mathrm{dB}$ insertion gain,

$$
V_{n,f1}=-79.19-1+10\log_{10}\left(\frac{1\times10^6}{150\times10^6}\right)
=-101.95\ \mathrm{dBV}.
$$

The target signals are

$$
V_{s,f1,far}=-84.91-1=-85.91\ \mathrm{dBV},
$$

$$
V_{s,f1,close}=-14.81-1=-15.81\ \mathrm{dBV}.
$$

## THS4551 fully differential amplifier

The provisional circuit uses

$$
R_F=1000\ \Omega,\quad R_G=100\ \Omega,\quad B_{IF}=1\ \mathrm{MHz},\quad T=300\ \mathrm{K}.
$$

The differential signal gain is

$$
A_v=\frac{R_F}{R_G}=10,\qquad G_{v,FDA}=20\log_{10}(A_v)=20\ \mathrm{dB}.
$$

The amplifier input-voltage noise follows noise gain, not signal gain:

$$
NG=1+\frac{R_F}{R_G}=11.
$$

Using the working datasheet densities

$$
e_n=3.3\ \mathrm{nV}/\sqrt{\mathrm{Hz}},\qquad i_n=0.5\ \mathrm{pA}/\sqrt{\mathrm{Hz}},
$$

the differential output-referred added-noise density is

$$
e_{o,FDA}=\sqrt{(e_nNG)^2+2(i_nR_F)^2+2(4kTR_FNG)}.
$$

The terms are respectively amplifier voltage noise, the two uncorrelated input-current-noise sources, and the two resistor networks.

For one side, the feedback resistor contributes

$$
e_{o,R_F}^2=4kTR_F,
$$

while the gain resistor contributes

$$
e_{o,R_G}^2=4kTR_G\left(\frac{R_F}{R_G}\right)^2
=4kT\frac{R_F^2}{R_G}.
$$

Together on one side,

$$
e_{o,R_F+R_G}^2=4kTR_F\left(1+\frac{R_F}{R_G}\right)=4kTR_FNG.
$$

The factor of two in the complete equation accounts for the two symmetric, uncorrelated sides. Substitution gives

$$
e_{o,FDA}=41.02\ \mathrm{nV}/\sqrt{\mathrm{Hz}}.
$$

After integration over equivalent noise bandwidth,

$$
V_{n,add,FDA}=e_{o,FDA}\sqrt{B_{IF}}
=41.02\times10^{-9}\sqrt{1\times10^6}
=41.02\ \mathrm{\mu V_{RMS}},
$$

or

$$
V_{n,add,FDA,dBV}=20\log_{10}\left(\frac{41.02\times10^{-6}}{1\ \mathrm{V}}\right)=-87.74\ \mathrm{dBV}.
$$

Noise already present at the FDA input is propagated with the signal gain:

$$
V_{n,from\ input,FDA}=V_{n,f1}+G_{v,FDA}.
$$

The output noise is

$$
V_{n,FDA}=10\log_{10}\left(10^{V_{n,add,FDA,dBV}/10}+10^{V_{n,from\ input,FDA}/10}\right),
$$

and the signal is

$$
V_{s,FDA}=V_{s,f1}+G_{v,FDA}.
$$

For the current workbook values, the input noise propagated through the FDA is

$$
V_{n,from\ input,FDA}=-101.95+20=-81.95\ \mathrm{dBV}.
$$

Combining it with the FDA-added noise gives

$$
V_{n,FDA}=10\log_{10}\left(10^{-87.74/10}+10^{-81.95/10}\right)
=-80.93\ \mathrm{dBV}.
$$

The target signals become

$$
V_{s,FDA,far}=-85.91+20=-65.91\ \mathrm{dBV},
$$

$$
V_{s,FDA,close}=-15.81+20=4.19\ \mathrm{dBV}.
$$

The resistor-noise result depends on where each equivalent source is placed. A resistor source placed in series with an amplifier input must receive the corresponding noise gain; a resistor source already referred to the output must not be amplified again. The equation above keeps every term explicitly output-referred before RSS combination.

<span style="color:red">Confirm the final resistor network, common-mode circuit, output load, stability network, output swing, and actual filter ENBW during schematic design.</span>

## Final anti-alias filter and output voltage

With $G_{f2}=-1\ \mathrm{dB}$ and no further bandwidth reduction in the current model,

$$
V_{n,out}=V_{n,FDA}+G_{f2},\qquad V_{s,out}=V_{s,FDA}+G_{f2}.
$$

Therefore,

$$
V_{n,out}=-80.93-1=-81.93\ \mathrm{dBV},
$$

$$
V_{s,out,far}=-65.91-1=-66.91\ \mathrm{dBV},
$$

$$
V_{s,out,close}=4.19-1=3.19\ \mathrm{dBV}.
$$

Any dBV value converts to RMS voltage as

$$
V_{RMS}=10^{V_{dBV}/20}\ \mathrm{V},
$$

or

$$
V_{RMS,mV}=1000\times10^{V_{dBV}/20}.
$$

The final far-target signal is

$$
V_{s,out,far}=1000\times10^{-66.91/20}=0.451\ \mathrm{mV_{RMS}},
$$

and the close-target signal is

$$
V_{s,out,close}=1000\times10^{3.19/20}=1444\ \mathrm{mV_{RMS}}.
$$

<span style="color:red">The close-target voltage must be checked against the THS4551 linear differential output swing, ADC full-scale convention, common-mode range, and required overload margin.</span>

When signal and noise use the same voltage reference,

$$
SNR_{dB}=V_{s,dBV}-V_{n,dBV}.
$$

Using the current final-stage workbook results,

$$
SNR_{far}=-66.91-(-81.93)=15.02\ \mathrm{dB},
$$

$$
SNR_{close}=3.19-(-81.93)=85.12\ \mathrm{dB}.
$$

These values describe analog signal and integrated analog noise at the final filter output. They do not yet include a signed-off ADC quantisation model, FFT-bin bandwidth, window correction, detection threshold, leakage, or compression.

## ADC input range and inverse range calculation

If the differential ADC span is confirmed as $V_{FS,pp}$ and the converter has $N$ bits, one ideal code step is

$$
\Delta V=\frac{V_{FS,pp}}{2^N}.
$$

For the provisional values,

$$
V_{FS,pp}=8.192\ \mathrm{V},\qquad N=14.
$$

The workbook's inverse calculation refers a chosen maximum and minimum useful ADC voltage back through the voltage gain:

$$
V_{in,dBV}=V_{ADC,dBV}-G_{v,total}.
$$

At the 50 Ω RF boundary,

$$
P_{in,dBm}=V_{in,dBV}-10\log_{10}(R_0P_0)
=V_{in,dBV}+13.0103.
$$

Solving the monostatic radar equation for range gives

$$
R=\left[\frac{P_tG_tG_r\lambda^2\sigma}{(4\pi)^3LP_r}\right]^{1/4}
$$

in linear units. Repeating this for ADC minimum and maximum, TX attenuation, and RCS produces the minimum/maximum distance curves.

<span style="color:red">Open definition: one LSB is a code step, not automatically the minimum detectable signal. The quantisation-noise, converter SINAD/ENOB, analog-noise, FFT-bin, and detection-threshold meanings must be chosen together before these limits are called usable range.</span>

## FFT calculations still to define

For $N_{used}$ real samples at sample rate $f_s$, the observation time is

$$
T_{obs}=\frac{N_{used}}{f_s}.
$$

For chirp slope $S=B/T_{ramp}$, an observation covering only $T_{obs}$ sees bandwidth

$$
B_{obs}=S T_{obs},
$$

and the physical range resolution is

$$
\Delta R=\frac{c}{2B_{obs}}=\frac{c}{2ST_{obs}}.
$$

For a window with equivalent noise bandwidth $K_w$ FFT bins,

$$
B_{bin}=K_w\frac{f_s}{N_{used}}.
$$

If analog noise $N_{total}$ is integrated over $B_n$, the corresponding noise per FFT bin is

$$
N_{bin}=N_{total}+10\log_{10}\left(\frac{B_{bin}}{B_n}\right).
$$

<span style="color:red">Open definition: choose $N_{used}$, acquisition interval, FFT length, window, coherent-gain correction, ENBW, and displayed spectral units. Zero padding must not be described as improved physical range resolution.</span>

## Calculations to add after the relevant circuits are defined

- sweep-slope error and chirp nonlinearity;
- PLL phase noise and reference spurs;
- TX-to-RX leakage and DC offset;
- compression, SFDR, and blocker margin;
- ADC clock-jitter SNR;
- I/Q amplitude/phase imbalance and image rejection;
- IF amplitude flatness, equivalent noise bandwidth, and group delay;
- component tolerances and temperature corners;
- detection probability and false-alarm assumptions.

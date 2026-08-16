# General
Here is the latest version of RF architecture of FunRad project:
![[FunRadBlockDiagram.excalidraw.svg|697]]

# TX Channel Calculation

| Stage             | Part#            | Gain/Loss (db) | Gain/Loss Tolerance (dB) | Typ Out (dBm) | Abs Min Out (dBm) | Abs Max Out (dBm) | P1dB (dBm) | Max RF Input (dBm) |
| ----------------- | ---------------- | -------------- | ------------------------ | ------------- | ----------------- | ----------------- | ---------- | ------------------ |
| VCO               | HMC431           | -              |                          | 2             | -1                | 3                 |            |                    |
| Wilkinson Divider | Planar Component | -3             |                          | -1            | -4                | 0                 |            |                    |
| Step Attennuator  | PE43711B-Z       | -16            | 0,71                     | -17           | -20,71            | -15,29            |            | 23                 |
| Amplifier         | Qorvo QPA9127    | 19             | 1                        | 2             | -2,71             | 4,71              | 17         |                    |
# LO Path Calculation
| Stage                 | Part#            | Gain/Loss (db) | Gain/Loss Tolerance (dB) | Typ Out (dBm) | Abs Min Out (dBm) | Abs Max Out (dBm) | P1dB (dBm) |
|-----------------------|------------------|----------------|--------------------------|---------------|-------------------|-------------------|------------|
| VCO                   | HMC431           | -              |                          | 2             | -1                | 3                 |            |
| Wilkinson Divider 1:2 | Planar Component | -3             |                          | -1            | -4                | 0                 |            |
| Attennuator           | Fixed            | -5             | 0,5                      | -6            | -9,5              | -4,5              |            |
| Amplifier             | GALI-84+         | 12             | 1                        | 6             | 1,5               | 8,5               | 15,5       |
| Wilkinson Divider 1:4 | Planar Component | -6             | 0,5                      | 0             | -5                | 3                 |

# RX Channel Calculation

The detailed calculations are maintained in [[FunRad Stages Calculations.ods]]. The equations below define the method used in the workbook. All logarithms are base 10.

## Symbols and reference quantities

| Symbol | Meaning |
| --- | --- |
| $P$ | RF power in dBm |
| $V$ | RMS voltage in volts unless stated otherwise |
| $G$ | stage gain in dB; a loss is entered as a negative gain |
| $G_v$ | voltage gain in dB |
| $NF$ | noise figure in dB |
| $F=10^{NF/10}$ | linear noise factor |
| $B$ | noise bandwidth in hertz |
| $R_0=50\ \Omega$ | RF reference impedance used for the dBm-to-voltage conversion |
| $k=1.380649\times10^{-23}\ \mathrm{J/K}$ | Boltzmann constant |
| $T_0=290\ \mathrm{K}$ | standard noise-temperature reference |
| $P_0=1\ \mathrm{mW}$ | dBm reference power |

### Origin of the thermal-noise density

The available thermal-noise power spectral density of a matched source at the standard temperature is

$$
N_0=kT_0
$$

Expressed in dBm/Hz:

$$
N_{0,\mathrm{dBm/Hz}}
=10\log_{10}\left(\frac{kT_0}{P_0}\right)
=10\log_{10}\left(\frac{(1.380649\times10^{-23})(290)}{1\times10^{-3}}\right)
\approx-173.98\ \mathrm{dBm/Hz}
$$

The workbook rounds this to $-174\ \mathrm{dBm/Hz}$.

## General cascaded signal-level calculation

For any stage $n$, the nominal output level is

$$
P_{\mathrm{out},n}=P_{\mathrm{out},n-1}+G_n
$$

When the stage gain/loss tolerance is $\Delta G_n$, the absolute limits are accumulated as

$$
P_{\min,n}=P_{\min,n-1}+G_n-\Delta G_n
$$

$$
P_{\max,n}=P_{\max,n-1}+G_n+\Delta G_n
$$

For a passive divider, attenuator, or filter, $G_n$ is negative. For an amplifier, $G_n$ is positive.

### TX path

The nominal cascade is

$$
2\ \mathrm{dBm}-3\ \mathrm{dB}-16\ \mathrm{dB}+19\ \mathrm{dB}=2\ \mathrm{dBm}
$$

Let $g_A$ be the signed gain/loss entry for the PE43711, so $g_A=-16\ \mathrm{dB}$ at the selected setting. The workbook's attenuation-accuracy model uses a slope coefficient of $0.06\ \mathrm{dB/dB}$ and an offset coefficient of $0.25\ \mathrm{dB}$. Its tolerance equation is

$$
\Delta A=-\left(0.06g_A+0.25\right)
$$

For $g_A=-16\ \mathrm{dB}$:

$$
\Delta A=-\left(0.06(-16)+0.25\right)=0.71\ \mathrm{dB}
$$

### LO distribution path

The nominal level before the 1:4 divider is

$$
2\ \mathrm{dBm}-3\ \mathrm{dB}-5\ \mathrm{dB}+12\ \mathrm{dB}=6\ \mathrm{dBm}
$$

The ideal 1:4 division loss is

$$
L_{1:4}=10\log_{10}(4)=6.02\ \mathrm{dB}
$$

Using the rounded $-6\ \mathrm{dB}$ workbook value, each nominal LO output is

$$
P_{\mathrm{LO,out}}=6\ \mathrm{dBm}-6\ \mathrm{dB}=0\ \mathrm{dBm}
$$

## Target signal at the receiver

For a monostatic radar and a point target in free space, the received power is calculated from

$$
P_r=\frac{P_tG_tG_r\lambda^2\sigma}{(4\pi)^3R^4L}
$$

where $P_t$ is transmitted power in watts, $G_t$ and $G_r$ are linear antenna gains, $\lambda=c/f_c$ is wavelength, $\sigma$ is radar cross section in square metres, $R$ is target range in metres, and $L$ is the linear product of additional system losses.

In decibel form:

$$
P_{r,\mathrm{dBm}}=P_{t,\mathrm{dBm}}+G_{t,\mathrm{dBi}}+G_{r,\mathrm{dBi}}+20\log_{10}(\lambda)+10\log_{10}(\sigma)-30\log_{10}(4\pi)-40\log_{10}(R)-L_{\mathrm{dB}}
$$

The workbook currently uses the following received-power scenario inputs:

| Case | TX amplifier output | TX antenna gain | Range | RCS | RX antenna output used by workbook |
| --- | ---: | ---: | ---: | ---: | ---: |
| Far target | $2\ \mathrm{dBm}$ | $12\ \mathrm{dBi}$ | $150\ \mathrm{m}$ | $0\ \mathrm{dBsm}=1\ \mathrm{m^2}$ | $-95.60\ \mathrm{dBm}$ |
| Close target | $-15\ \mathrm{dBm}$ | $12\ \mathrm{dBi}$ | $1\ \mathrm{m}$ | $0\ \mathrm{dBsm}=1\ \mathrm{m^2}$ | $-25.50\ \mathrm{dBm}$ |

These two received-power values are treated as inputs to the RX cascade for now.

Their relative scaling is consistent with the monostatic $R^{-4}$ law. For unchanged antenna gains, RCS, wavelength, and system loss, the expected difference is

$$
\Delta P_r=(P_{t,\mathrm{close}}-P_{t,\mathrm{far}})+40\log_{10}\left(\frac{R_{\mathrm{far}}}{R_{\mathrm{close}}}\right)
$$

$$
\Delta P_r=(-15-2)+40\log_{10}\left(\frac{150}{1}\right)=70.04\ \mathrm{dB}
$$

The workbook inputs differ by

$$
-25.50-(-95.60)=70.10\ \mathrm{dB}
$$

which agrees within $0.06\ \mathrm{dB}$ of rounding.

## LNA output: signal and noise in dBm

For the QPL9504, the workbook uses

$$
G_{\mathrm{LNA}}=17.9\ \mathrm{dB},\qquad NF_{\mathrm{LNA}}=0.66\ \mathrm{dB},\qquad B_{\mathrm{RF}}=150\ \mathrm{MHz}
$$

The target signal after the LNA is

$$
P_{s,\mathrm{LNA}}=P_{r}+G_{\mathrm{LNA}}
$$

Therefore:

$$
P_{s,\mathrm{LNA,far}}=-95.60+17.9=-77.70\ \mathrm{dBm}
$$

$$
P_{s,\mathrm{LNA,close}}=-25.50+17.9=-7.60\ \mathrm{dBm}
$$

The LNA output-noise power is

$$
P_{n,\mathrm{LNA}}=N_{0,\mathrm{dBm/Hz}}+10\log_{10}(B_{\mathrm{RF}})+NF_{\mathrm{LNA}}+G_{\mathrm{LNA}}
$$

$$
P_{n,\mathrm{LNA}}=-174+10\log_{10}(150\times10^6)+0.66+17.9=-73.68\ \mathrm{dBm}
$$

## RF power to baseband-voltage transition

The workbook makes the domain transition at cells I9 and J9. Power in a $50\ \Omega$ system is converted to RMS voltage using

$$
V_{\mathrm{RMS}}=\sqrt{R_0P_0\,10^{P_{\mathrm{dBm}}/10}}
$$

or, in millivolts,

$$
V_{\mathrm{RMS,mV}}=1000\sqrt{R_0P_0\,10^{P_{\mathrm{dBm}}/10}}
$$

The corresponding dBV value is

$$
V_{\mathrm{dBV}}=20\log_{10}\left(\frac{V_{\mathrm{RMS}}}{1\ \mathrm{V}}\right)
$$

Combining the equations gives the general conversion

$$
V_{\mathrm{dBV}}=P_{\mathrm{dBm}}+10\log_{10}(R_0P_0)
$$

and for $R_0=50\ \Omega$ and $P_0=1\ \mathrm{mW}$:

$$
V_{\mathrm{dBV}}=P_{\mathrm{dBm}}+10\log_{10}(50\times10^{-3})=P_{\mathrm{dBm}}-13.0103
$$

Thus, at I9 and J9:

$$
V_{n,\mathrm{LNA}}=-73.68-13.0103=-86.69\ \mathrm{dBV}
$$

$$
V_{s,\mathrm{LNA,far}}=-77.70-13.0103=-90.71\ \mathrm{dBV}
$$

$$
V_{s,\mathrm{LNA,close}}=-7.60-13.0103=-20.61\ \mathrm{dBV}
$$

From this point onward, signal and noise are propagated as baseband voltage in dBV.

## Demodulator output noise

For the ADL5380, the workbook uses voltage conversion gain $G_{v,\mathrm{mix}}=5.8\ \mathrm{dB}$, noise figure $NF_{\mathrm{mix}}=15.5\ \mathrm{dB}$, and RF bandwidth $B_{\mathrm{RF}}=150\ \mathrm{MHz}$.

The thermal-noise density expressed as dBV/Hz at the $50\ \Omega$ reference is

$$
N_{0,\mathrm{dBV/Hz}}=N_{0,\mathrm{dBm/Hz}}+10\log_{10}(R_0P_0)
$$

$$
N_{0,\mathrm{dBV/Hz}}=-173.98+10\log_{10}(50\times10^{-3})\approx-186.99\ \mathrm{dBV/Hz}
$$

The workbook uses the rounded value $-187.01\ \mathrm{dBV/Hz}$.

The demodulator's output-referred added noise is

$$
V_{n,\mathrm{add,mix}}=N_{0,\mathrm{dBV/Hz}}+10\log_{10}(B_{\mathrm{RF}})+10\log_{10}\left(10^{NF_{\mathrm{mix}}/10}-1\right)+G_{v,\mathrm{mix}}
$$

The noise figure is first converted from decibels to the linear noise factor

$$
F_{\mathrm{mix}}=10^{NF_{\mathrm{mix}}/10}
$$

By definition, a real device produces $F$ times the output noise that an ideal noiseless device would produce when both are driven by a matched source at $T_0$. That total consists of two parts:

$$
F=1+(F-1)
$$

The first term represents the source thermal noise propagated through the device. The second term, $F-1$, represents noise generated by the device itself, referred to its input. Therefore, the demodulator's input-referred added-noise density is

$$
N_{\mathrm{add,in}}=kT_0(F_{\mathrm{mix}}-1)
$$

Integrating this density over bandwidth $B_{\mathrm{RF}}$ and applying the demodulator gain gives the output-referred added noise. In logarithmic units, multiplication by $F_{\mathrm{mix}}-1$ becomes

$$
10\log_{10}(F_{\mathrm{mix}}-1)
=10\log_{10}\left(10^{NF_{\mathrm{mix}}/10}-1\right)
$$

The subtraction of one is important because the source noise is propagated separately in $V_{n,\mathrm{from\ input,mix}}$. Using $F$ instead of $F-1$ here would include the source thermal-noise contribution in the added-noise term and then count it again when the propagated input noise is combined below. For an ideal noiseless device, $NF=0\ \mathrm{dB}$, $F=1$, and $F-1=0$, correctly indicating that the device adds no noise.

The LNA noise propagated through the demodulator is

$$
V_{n,\mathrm{from\ input,mix}}=V_{n,\mathrm{LNA}}+G_{v,\mathrm{mix}}
$$

Uncorrelated noise voltages are added as powers:

$$
V_{n,\mathrm{mix}}=10\log_{10}\left(10^{V_{n,\mathrm{add,mix}}/10}+10^{V_{n,\mathrm{from\ input,mix}}/10}\right)
$$

The target signal is propagated with voltage gain:

$$
V_{s,\mathrm{mix}}=V_{s,\mathrm{LNA}}+G_{v,\mathrm{mix}}
$$

The workbook results are:

| Quantity | Far target | Close target |
| --- | ---: | ---: |
| Demodulator total noise | $-79.19\ \mathrm{dBV}$ | $-79.19\ \mathrm{dBV}$ |
| Demodulator target signal | $-84.91\ \mathrm{dBV}$ | $-14.81\ \mathrm{dBV}$ |

## First IF low-pass filter

The first filter has gain $G_{f1}=-1\ \mathrm{dB}$ and noise bandwidth $B_{\mathrm{IF}}=1\ \mathrm{MHz}$. It attenuates the signal by its insertion loss:

$$
V_{s,f1}=V_{s,\mathrm{mix}}+G_{f1}
$$

It also reduces the integrated noise from the demodulator bandwidth to the IF bandwidth:

$$
V_{n,f1}=V_{n,\mathrm{mix}}+G_{f1}+10\log_{10}\left(\frac{B_{\mathrm{IF}}}{B_{\mathrm{RF}}}\right)
$$

This gives $V_{n,f1}=-101.95\ \mathrm{dBV}$, $V_{s,f1}=-85.91\ \mathrm{dBV}$ for the far target, and $V_{s,f1}=-15.81\ \mathrm{dBV}$ for the close target.

## THS4551 fully differential amplifier

The IF amplifier is the THS4551, configured with equal feedback networks on both sides. The workbook uses

$$
R_F=1000\ \Omega,\qquad R_G=100\ \Omega,\qquad B_{\mathrm{IF}}=1\ \mathrm{MHz},\qquad T=300\ \mathrm{K}
$$

The differential signal gain is

$$
A_v=\frac{R_F}{R_G}=\frac{1000}{100}=10\ \mathrm{V/V}
$$

or

$$
G_{v,\mathrm{FDA}}=20\log_{10}(A_v)=20\ \mathrm{dB}
$$

The amplifier input-voltage noise does not follow the signal gain. It follows the noise gain

$$
NG=1+\frac{R_F}{R_G}=11
$$

The THS4551 noise-density inputs used by the workbook are

$$
e_n=3.3\ \mathrm{nV}/\sqrt{\mathrm{Hz}},\qquad i_n=0.5\ \mathrm{pA}/\sqrt{\mathrm{Hz}}
$$

The differential output-referred added-noise density is calculated by root-sum-square addition of the independent noise sources:

$$
e_{o,\mathrm{FDA}}=
\sqrt{
(e_nNG)^2
+2(i_nR_F)^2
+2(4kTR_FNG)
}
$$

The three terms represent:

1. THS4551 input-voltage noise amplified by the noise gain;
2. the two uncorrelated input-current-noise sources flowing through the two feedback resistors;
3. the thermal noise of the $R_F$ and $R_G$ networks on both sides of the FDA.

For one side, the feedback-resistor noise reaches the output with unity gain:

$$
e_{o,R_F}^2=4kTR_F
$$

The gain-resistor noise follows the signal gain $R_F/R_G$:

$$
e_{o,R_G}^2=4kTR_G\left(\frac{R_F}{R_G}\right)^2
=4kT\frac{R_F^2}{R_G}
$$

Combining these uncorrelated contributions on one side gives

$$
e_{o,R_F+R_G}^2
=4kTR_F+4kT\frac{R_F^2}{R_G}
=4kTR_F\left(1+\frac{R_F}{R_G}\right)
=4kTR_FNG
$$

The factor of two in the complete FDA equation accounts for the two symmetric, uncorrelated resistor networks.

Substituting the workbook values and $k=1.380649\times10^{-23}\ \mathrm{J/K}$ gives

$$
e_{o,\mathrm{FDA}}=41.02\ \mathrm{nV}/\sqrt{\mathrm{Hz}}
$$

Assuming an equivalent noise bandwidth of $1\ \mathrm{MHz}$, the integrated added-noise voltage is

$$
V_{n,\mathrm{add,FDA}}
=e_{o,\mathrm{FDA}}\sqrt{B_{\mathrm{IF}}}
$$

$$
V_{n,\mathrm{add,FDA}}
=41.02\times10^{-9}\sqrt{1\times10^6}
=41.02\ \mathrm{\mu V_{RMS}}
$$

Expressed in dBV:

$$
V_{n,\mathrm{add,FDA,dBV}}
=20\log_{10}\left(\frac{41.02\times10^{-6}}{1\ \mathrm{V}}
\right)
=-87.74\ \mathrm{dBV}
$$

The noise already present at the first IF-filter output is propagated through the FDA signal gain:

$$
V_{n,\mathrm{from\ input,FDA}}
=V_{n,f1}+G_{v,\mathrm{FDA}}
=-101.95+20
=-81.95\ \mathrm{dBV}
$$

The FDA-added noise and propagated input noise are uncorrelated and are combined as powers:

$$
V_{n,\mathrm{FDA}}
=10\log_{10}\left(
10^{V_{n,\mathrm{add,FDA,dBV}}/10}
+10^{V_{n,\mathrm{from\ input,FDA}}/10}
\right)
$$

$$
V_{n,\mathrm{FDA}}
=10\log_{10}\left(
10^{-87.74/10}+10^{-81.95/10}
\right)
=-80.93\ \mathrm{dBV}
$$

The target signal follows the FDA signal gain:

$$
V_{s,\mathrm{FDA}}=V_{s,f1}+G_{v,\mathrm{FDA}}
$$

This gives $V_{s,\mathrm{FDA,far}}=-65.91\ \mathrm{dBV}$ and $V_{s,\mathrm{FDA,close}}=4.19\ \mathrm{dBV}$.

## Final anti-alias filter

The final filter currently uses $G_{f2}=-1\ \mathrm{dB}$ and $B_{\mathrm{IF}}=1\ \mathrm{MHz}$. Because its bandwidth is the same as the preceding stage, no further bandwidth-ratio correction is applied:

$$
V_{n,\mathrm{out}}=V_{n,\mathrm{FDA}}+G_{f2}
$$

$$
V_{s,\mathrm{out}}=V_{s,\mathrm{FDA}}+G_{f2}
$$

The resulting values are $V_{n,\mathrm{out}}=-81.93\ \mathrm{dBV}$, $V_{s,\mathrm{out,far}}=-66.91\ \mathrm{dBV}$, and $V_{s,\mathrm{out,close}}=3.19\ \mathrm{dBV}$.

## Conversion from dBV to RMS voltage

Any baseband value in dBV is converted to RMS millivolts using

$$
V_{\mathrm{RMS,mV}}=1000\times10^{V_{\mathrm{dBV}}/20}
$$

For example, the final far-target signal is

$$
V_{s,\mathrm{out,far}}=1000\times10^{-66.91/20}=0.451\ \mathrm{mV_{RMS}}
$$

The close-target result is

$$
V_{s,\mathrm{out,close}}=1000\times10^{3.19/20}=1444\ \mathrm{mV_{RMS}}
$$

<span style="color:red">The close-target voltage must still be checked against the THS4551 linear differential output swing and the ADC's configured full-scale input.</span>

## Signal-to-noise ratio

When signal and noise use the same dB voltage reference, the SNR at any node is simply

$$
SNR_{\mathrm{dB}}=V_{s,\mathrm{dBV}}-V_{n,\mathrm{dBV}}
$$

Using the current final-stage results, the far-target SNR is

$$
SNR_{\mathrm{far}}=-66.91-(-81.93)=15.02\ \mathrm{dB}
$$

and the close-target SNR is

$$
SNR_{\mathrm{close}}=3.19-(-81.93)=85.12\ \mathrm{dB}
$$

## Far Target Case

### Sweep Slope Error

### Phase Noise

### SFDR

### SNR

### Clock jitter SNR

### Image Rejection Ration

### Amplitude Flatness

### Group Delay Variation

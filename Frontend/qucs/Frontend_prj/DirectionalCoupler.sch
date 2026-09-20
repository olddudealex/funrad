<Qucs Schematic 24.4.0>
<Properties>
  <View=-407,-331,2861,1482,0.683013,0,0>
  <Grid=10,10,1>
  <DataSet=DirectionalCoupler.dat>
  <DataDisplay=DirectionalCoupler.dpl>
  <OpenDisplay=0>
  <Script=DirectionalCoupler.m>
  <RunScript=0>
  <showFrame=0>
  <FrameText0=Title>
  <FrameText1=Drawn By:>
  <FrameText2=Date:>
  <FrameText3=Revision:>
</Properties>
<Symbol>
</Symbol>
<Components>
  <.SP SP1 1 330 540 0 68 0 0 "lin" 1 "4 GHz" 1 "8 GHz" 1 "200" 1 "no" 0 "1" 0 "2" 0 "no" 0 "no" 0>
  <SUBST FR4_7628 1 170 580 -30 24 0 0 "4.4" 1 "0.21 mm" 1 "35 um" 1 "0.02" 1 "0.022e-6" 1 "0" 1>
  <Eqn Eqn1 1 560 550 -28 18 0 0 "S11_dB=dB(S[1,1])" 1 "S21_dB=dB(S[2,1])" 1 "S31_dB=dB(S[3,1])" 1 "S41_dB=dB(S[4,1])" 1 "S23_dB=dB(S[2,3])" 1 "S24_dB=dB(S[2,4])" 1 "S34_dB=dB(S[3,4])" 1 "W=0.38m" 1 "L=4.9m" 1 "Gap=100u" 1 "yes" 0>
  <MMBEND MS3 1 160 240 -102 -26 0 2 "FR4_7628" 1 "0.38m" 1>
  <MMBEND MS4 1 740 240 -26 15 0 3 "FR4_7628" 1 "0.38m" 1>
  <MCOUPLED MS1 1 460 280 -26 37 0 0 "FR4_7628" 1 "W" 1 "L" 1 "Gap" 1 "Kirschning" 0 "Kirschning" 0 "26.85" 0>
  <MLIN MS8 1 740 170 15 -26 0 1 "FR4_7628" 1 "0.38m" 1 "5m" 1 "Hammerstad" 0 "Kirschning" 0 "26.85" 0>
  <MLIN MS9 1 160 170 15 -26 0 1 "FR4_7628" 1 "0.38m" 1 "5m" 1 "Hammerstad" 0 "Kirschning" 0 "26.85" 0>
  <Pac P3 1 10 90 -26 18 0 0 "3" 1 "50 Ohm" 1 "0 dBm" 0 "1 MHz" 0 "26.85" 0 "true" 0>
  <GND * 1 -40 90 0 0 0 3>
  <MMBEND MS12 1 160 90 15 -7 0 0 "FR4_7628" 1 "0.38m" 1>
  <MLIN MS13 1 80 90 -26 -79 0 2 "FR4_7628" 1 "0.38m" 1 "5m" 1 "Hammerstad" 0 "Kirschning" 0 "26.85" 0>
  <MMBEND MS14 1 740 90 -7 -63 0 1 "FR4_7628" 1 "0.38m" 1>
  <MLIN MS15 1 860 90 -26 -79 0 2 "FR4_7628" 1 "0.38m" 1 "5m" 1 "Hammerstad" 0 "Kirschning" 0 "26.85" 0>
  <Pac P4 1 970 90 -26 -66 0 2 "4" 1 "50 Ohm" 1 "0 dBm" 0 "1 MHz" 0 "26.85" 0 "true" 0>
  <GND * 1 1020 90 0 0 0 1>
  <GND * 1 -40 320 0 0 0 3>
  <Pac P1 1 10 320 -26 18 0 0 "1" 1 "50 Ohm" 1 "0 dBm" 0 "1 MHz" 0 "26.85" 0 "true" 0>
  <MLIN MS11 1 250 320 -26 -79 0 2 "FR4_7628" 1 "0.38m" 1 "5m" 1 "Hammerstad" 0 "Kirschning" 0 "26.85" 0>
  <Pac P2 1 970 320 -26 -66 0 2 "2" 1 "50 Ohm" 1 "0 dBm" 0 "1 MHz" 0 "26.85" 0 "true" 0>
  <GND * 1 1020 320 0 0 0 1>
  <MLIN MS17 1 870 320 -26 -79 0 2 "FR4_7628" 1 "0.38m" 1 "5m" 1 "Hammerstad" 0 "Kirschning" 0 "26.85" 0>
</Components>
<Wires>
  <490 310 490 320 "" 0 0 0 "">
  <490 240 710 240 "" 0 0 0 "">
  <490 240 490 250 "" 0 0 0 "">
  <190 240 430 240 "" 0 0 0 "">
  <430 240 430 250 "" 0 0 0 "">
  <740 200 740 210 "" 0 0 0 "">
  <160 200 160 210 "" 0 0 0 "">
  <-40 90 -20 90 "" 0 0 0 "">
  <160 120 160 140 "" 0 0 0 "">
  <40 90 50 90 "" 0 0 0 "">
  <110 90 130 90 "" 0 0 0 "">
  <740 120 740 140 "" 0 0 0 "">
  <1000 90 1020 90 "" 0 0 0 "">
  <770 90 830 90 "" 0 0 0 "">
  <890 90 940 90 "" 0 0 0 "">
  <-40 320 -20 320 "" 0 0 0 "">
  <40 320 220 320 "" 0 0 0 "">
  <430 310 430 320 "" 0 0 0 "">
  <280 320 430 320 "" 0 0 0 "">
  <1000 320 1020 320 "" 0 0 0 "">
  <900 320 940 320 "" 0 0 0 "">
  <490 320 840 320 "" 0 0 0 "">
</Wires>
<Diagrams>
  <Rect 1140 590 784 550 3 #c0c0c0 1 00 1 4e+09 5e+08 8e+09 1 -31.1486 5 2.55111 1 -1 0.2 1 315 0 225 1 0 0 "" "" "">
	<"S21_dB" #0000ff 0 3 0 0 0>
	  <Mkr 5.80905e+09 158 -475 3 0 0>
	<"S31_dB" #ff0000 0 3 0 0 0>
	  <Mkr 5.80905e+09 154 -366 3 0 0>
	<"S41_dB" #ff00ff 0 3 0 0 0>
	  <Mkr 5.80905e+09 156 -223 3 0 0>
	<"S11_dB" #00ff00 0 3 0 0 0>
  </Rect>
</Diagrams>
<Paintings>
</Paintings>

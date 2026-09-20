<Qucs Schematic 24.4.0>
<Properties>
  <View=-127,-197,1527,842,0.768844,0,0>
  <Grid=10,10,1>
  <DataSet=Wilkinson1_2.dat>
  <DataDisplay=Wilkinson1_2.dpl>
  <OpenDisplay=0>
  <Script=Wilkinson1_2.m>
  <RunScript=0>
  <showFrame=0>
  <FrameText0=Title>
  <FrameText1=Drawn By:>
  <FrameText2=Date:>
  <FrameText3=Revision:>
</Properties>
<Symbol>
  <.ID -20 44 SUB>
  <Line -20 -40 40 0 #000080 2 1>
  <Line 20 -40 0 80 #000080 2 1>
  <Line -20 40 40 0 #000080 2 1>
  <Line -20 -40 0 80 #000080 2 1>
  <Line 20 -30 30 0 #000080 2 1>
  <.PortSym -50 0 1 0 P1>
  <Line -50 0 30 0 #000080 2 1>
  <Line 20 30 30 0 #000080 2 1>
  <.PortSym 50 30 3 180 P3>
  <.PortSym 50 -30 2 180 P2>
  <Text -30 -20 9 #000000 0 "1">
  <Text 30 -50 9 #000000 0 "2">
  <Text 30 10 9 #000000 0 "3">
</Symbol>
<Components>
  <MLIN MS2 1 390 270 -26 15 0 0 "FR4_7628" 1 "W_50" 1 "2 mm" 1 "Hammerstad" 0 "Kirschning" 0 "26.85" 0>
  <MLIN MS12 1 620 470 -26 -79 0 2 "FR4_7628" 1 "W_70" 1 "L2" 1 "Hammerstad" 0 "Kirschning" 0 "26.85" 0>
  <MLIN MS3 1 490 130 15 -26 0 1 "FR4_7628" 1 "W_70" 1 "L1" 1 "Hammerstad" 0 "Kirschning" 0 "26.85" 0>
  <MLIN MS11 1 620 40 -26 -79 0 2 "FR4_7628" 1 "W_70" 1 "L2" 1 "Hammerstad" 0 "Kirschning" 0 "26.85" 0>
  <MLIN MS4 1 490 380 15 -26 0 1 "FR4_7628" 1 "W_70" 1 "L1" 1 "Hammerstad" 0 "Kirschning" 0 "26.85" 0>
  <MLIN MS10 1 710 380 15 -26 0 1 "FR4_7628" 1 "W_70" 1 "L3" 1 "Hammerstad" 0 "Kirschning" 0 "26.85" 0>
  <MMBEND MS18 1 710 40 15 -7 0 0 "FR4_7628" 1 "W_70" 1>
  <MMBEND MS19 1 710 470 -26 15 0 3 "FR4_7628" 1 "W_70" 1>
  <MMBEND MS20 1 490 470 -93 -26 0 2 "FR4_7628" 1 "W_70" 1>
  <MMBEND MS21 1 710 220 -93 -26 0 2 "FR4_7628" 1 "W_70" 1>
  <MMBEND MS22 1 710 310 -7 -63 0 1 "FR4_7628" 1 "W_70" 1>
  <R R1 1 960 260 15 -26 0 1 "100 Ohm" 1 "26.85" 0 "0.0" 0 "0.0" 0 "26.85" 0 "european" 0>
  <MLIN MS15 1 870 310 -26 -79 0 2 "FR4_7628" 1 "W_70" 1 "L4" 1 "Hammerstad" 0 "Kirschning" 0 "26.85" 0>
  <MLIN MS16 1 870 220 -26 -79 0 2 "FR4_7628" 1 "W_70" 1 "L4" 1 "Hammerstad" 0 "Kirschning" 0 "26.85" 0>
  <MLIN MS9 1 710 130 15 -26 0 1 "FR4_7628" 1 "W_70" 1 "L3" 1 "Hammerstad" 0 "Kirschning" 0 "26.85" 0>
  <MMBEND MS17 1 490 40 -7 -63 0 1 "FR4_7628" 1 "W_70" 1>
  <MTEE MS1 1 490 270 34 -45 0 3 "FR4_7628" 1 "W_70" 1 "W_70" 1 "W_50" 1 "Hammerstad" 0 "Kirschning" 0 "26.85" 0 "showNumbers" 0>
  <Port P1 1 340 270 -23 12 0 0 "1" 1 "analog" 0 "v" 0 "" 0>
  <Port P3 1 1050 310 4 -44 0 2 "3" 1 "analog" 0 "v" 0 "" 0>
  <Port P2 1 1050 220 4 -44 0 2 "2" 1 "analog" 0 "v" 0 "" 0>
  <SUBST FR4_7628 1 110 300 -30 24 0 0 "4.4" 1 "0.21 mm" 1 "35 um" 1 "0.020" 1 "0.022e-6" 1 "0.15e-6" 1>
  <Eqn Eqn1 1 130 0 -28 18 0 0 "S11_dB=dB(S[1,1])" 1 "S21_dB=dB(S[2,1])" 1 "S31_dB=dB(S[3,1])" 1 "S23_dB=dB(S[2,3])" 1 "W_50=0.00038" 1 "W_70=0.000195" 1 "Lsmd=0.00085" 1 "Lq=0.0071" 1 "L1=0.3*Lq" 1 "L2=Lq-(L1+L3+L4)" 1 "L3=L1-Lsmd/2" 1 "L4=0.0005" 1 "yes" 0>
</Components>
<Wires>
  <650 470 680 470 "" 0 0 0 "">
  <520 470 590 470 "" 0 0 0 "">
  <490 70 490 100 "" 0 0 0 "">
  <520 40 590 40 "" 0 0 0 "">
  <490 410 490 440 "" 0 0 0 "">
  <710 410 710 440 "" 0 0 0 "">
  <650 40 680 40 "" 0 0 0 "">
  <710 340 710 350 "" 0 0 0 "">
  <960 290 960 310 "" 0 0 0 "">
  <960 220 960 230 "" 0 0 0 "">
  <960 310 1050 310 "" 0 0 0 "">
  <960 220 1050 220 "" 0 0 0 "">
  <740 220 840 220 "" 0 0 0 "">
  <900 220 960 220 "" 0 0 0 "">
  <740 310 840 310 "" 0 0 0 "">
  <900 310 960 310 "" 0 0 0 "">
  <710 70 710 100 "" 0 0 0 "">
  <710 160 710 190 "" 0 0 0 "">
  <420 270 460 270 "" 0 0 0 "">
  <490 300 490 350 "" 0 0 0 "">
  <490 160 490 240 "" 0 0 0 "">
  <340 270 360 270 "" 0 0 0 "">
</Wires>
<Diagrams>
</Diagrams>
<Paintings>
</Paintings>

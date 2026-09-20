<Qucs Schematic 24.4.0>
<Properties>
  <View=-158,-104,1021,637,1.30557,110,43>
  <Grid=10,10,1>
  <DataSet=Wilkinson1_2_analysis.dat>
  <DataDisplay=Wilkinson1_2_analysis.dpl>
  <OpenDisplay=0>
  <Script=Wilkinson1_2_analysis.m>
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
  <.SP SP1 1 40 20 0 68 0 0 "lin" 1 "4 GHz" 1 "8 GHz" 1 "200" 1 "no" 0 "1" 0 "2" 0 "no" 0 "no" 0>
  <Pac P1 1 210 230 18 -26 0 1 "1" 1 "50 Ohm" 1 "0 dBm" 0 "1 MHz" 0 "26.85" 0 "true" 0>
  <GND * 1 210 260 0 0 0 0>
  <Pac P3 1 450 270 18 -26 0 1 "3" 1 "50 Ohm" 1 "0 dBm" 0 "1 MHz" 0 "26.85" 0 "true" 0>
  <GND * 1 450 300 0 0 0 0>
  <Pac P2 1 570 270 18 -26 0 1 "2" 1 "50 Ohm" 1 "0 dBm" 0 "1 MHz" 0 "26.85" 0 "true" 0>
  <GND * 1 570 300 0 0 0 0>
  <Eqn Eqn1 1 70 190 -28 18 0 0 "S11_dB=dB(S[1,1])" 1 "S21_dB=dB(S[2,1])" 1 "S31_dB=dB(S[3,1])" 1 "S23_dB=dB(S[2,3])" 1 "W_50=0.00038" 1 "W_70=0.000195" 1 "Lsmd=0.00085" 1 "Lq=0.0071" 1 "L1=0.3*Lq" 1 "L2=Lq-(L1+L3+L4)" 1 "L3=L1-Lsmd/2" 1 "L4=0.0005" 1 "yes" 0>
  <Sub SUB1 1 350 190 -26 48 0 0 "Wilkinson1_2.sch" 0>
</Components>
<Wires>
  <210 190 210 200 "" 0 0 0 "">
  <210 190 300 190 "" 0 0 0 "">
  <450 220 450 240 "" 0 0 0 "">
  <400 220 450 220 "" 0 0 0 "">
  <400 160 570 160 "" 0 0 0 "">
  <570 160 570 240 "" 0 0 0 "">
</Wires>
<Diagrams>
</Diagrams>
<Paintings>
</Paintings>

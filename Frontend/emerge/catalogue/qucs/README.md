# EM network + lumped capacitors in QUCS

Import `historical_bare_at_comb_50ohm.s4p` into a four-port S-parameter-file component in QUCS (Qucsator S-parameter analysis). The file contains the historical bare network, including its EM parasitics, at the comb connection reference planes. It is fitted saved EM data, not new direct samples of the final symmetric geometry.

Connect Cleft from terminal 1 to 3 and Cright from 2 to 4. Assign both the same parameter C. Attach four 50-ohm RF ports; ground the file component's additional reference pin if exposed by that component. Sweep S parameters over 5.7–5.9 GHz; sweep C from 0 to 150 fF (0.5 fF in the supplied Python calculation). C=0 means omit both capacitors. Plot S31 and S41 in dB, and D=S31_dB−S41_dB; maximize minimum D over the band.

The shipped plot is computed by S→Y, stamping the two capacitor admittances, and Y→S. This is the same linear circuit problem as the diagram, but QUCS itself was not run to generate those curves. Its result should reproduce the 85 fF / 25.78 dB optimum subject to interpolation and sweep spacing. Capacitors are bridge components between signal lines, not capacitors to ground; 2C is only the odd-mode half-circuit equivalent.

The final etched comb is a distributed geometry, not two imposed 85 fF parts. Never attach the caps at external board ports and interpret that answer as the required comb capacitance.

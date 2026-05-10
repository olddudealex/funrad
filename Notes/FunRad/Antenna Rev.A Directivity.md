# Measurement Process Description
The setup was designed to get the directivity measurements from the Antenna Array Rev.A:

![[05_20260321_235754.jpg]]

On the left side of the setup the rotational tower made out of Plexiglas and plastic standoffs is used for fixing the AUT (Antenna under Test). The tower rotation is performed by servo for RC models. The RC servo is controlled from PC via the STM32 NUCLEO-G474RE board. On the right side of setup the second AUT is fixed stationary.
![[06_20260322_203107.jpg|414]]

The list of used equipment:
1) LiteVNA64
2) 2xSMA Cables 2m (415-0033-M2.0)
3) RC Servo Miuzei MZ996
4) NUCLEO-G474RE board
5) 5V separate supply for servo
6) Breadboard + cables for commutation
7) PC

The utility for the taking the measurements was very simple and minimalistic:

![[07_ServoControlScreenshot.png|312]]

And as the results are saved in the database, I created another utility to explore the measurements easily:
![[08_AntennaPatternViewerScreenshot.png|697]]

The code for NUCLEO board, and PC software can be found here: https://github.com/olddudealex/antenna_measurements_tools

# Simulated vs measured results comparison
The figure below contains the comparison between the results of measurements and results of simulation in openEMS and emerge. The most interesting is the E-plane diagram, because in this plane the patches interfere with each other and form rather narrow beam. It's worth to mention that the measurements fit quite well in the range 0..90 degrees, and a little bit off in the range -90..0 degrees. It could be explained by the impact of the SMA-connector and RF-cable that are located from this side. The measured main beam amplitude is lower by 2dB than simulated - only 11.8dB instead of 13.8dB.

![[09_Directivity_Meas_vs_openEMS_vs_emerge.png]]

# Measured antenna beam squint/gain variation in the frequency range

The patch antennas with edge feed are very frequency sensitive and have very prominent resonance S-parameters. Due to this it's very hard to have a good wide bandwidth antenna out of these types of patches. It was especially interesting how the antenna will behave in the maximum bandwidth of ISM band: from 5.725GHz to 5.875GHz (150MHz band). Another problem is possible squint of antenna beam (rotation of beam direction due to changing of frequency). To answer to these two questions the following plot was drawn:
![[10_Gain_vs_Frequency.png]]

The beam squint looks insignificant in comparison to very poor gain on the lower frequencies. The gain difference between frequency band edges is 3.8dB! I believe that using another approach (aperture coupled feed) I can achieve much better results.
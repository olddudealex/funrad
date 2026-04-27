Small update regarding the 5.8GHz patch antenna array.

On first image you can see the differences between the measurements result made with professional ZNB20 VNA from R&S and LiteVNA toy. Surprisingly, it matches very well, of course if you calibrate LiteVNA right :) 
![[01_R&S_ZNB20_vs_LiteVNA_RevA.png]]

On second image the OpenEMS simulation results are plotted together with real measurements. You can see the shift of central frequency from 5.835GHz to 5.878GHz (43MHz difference). It's about 0.7% shift.
![[02_R&S_ZNB20_vs_OpenEMS_er=3.00.png]]

According to datasheet this Teflon dielectric has er=3.0±0.05. So I ran the simulation one more time with er=2.95 instead of 3.00 dielectric constant. And it matched very well to measurements data, see image below:
![[03_R&S_ZNB20_vs_OpenEMS_er=2.95.png]]

And on last image you can see comparison of emerge simulation results with the measurements. Yes, it's not that close as OpenEMS results, but after following advices given by .... it requires only 2 minutes on my PC instead of 30 minutes in OpenEMS!
![[04_R&S_ZNB20_vs_emerge_er=2.95.png]]

Based on the results above, I'm going to design soon new antenna with much higher bandwidth (looking to the slot-aperture patches right now) that will be tolerant to dielectric constant deviation. And I think that emerge will be a good fit in this task, making the optimization iterations very fast.

The code that was used for finding the correct phase and generation of these plots is here:
https://github.com/olddudealex/funrad/tree/main/Antenna/measurements

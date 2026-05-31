from .tx_path import PLLChirpBlock, DACIQBlock, AmplifierBlock
from .rx_path import LNABlock, MixerBlock, ADCBlock
from .passive import AntennaBlock, CouplerBlock, FilterBlock
from .target import TargetBlock
from .dsp import RangeFFTBlock
from graph.registry import register_block

for _cls in (PLLChirpBlock, DACIQBlock, AmplifierBlock,
             LNABlock, MixerBlock, ADCBlock,
             AntennaBlock, CouplerBlock, FilterBlock,
             TargetBlock, RangeFFTBlock):
    register_block(_cls)

ALL_BLOCKS = [
    PLLChirpBlock, DACIQBlock, AmplifierBlock,
    AntennaBlock, CouplerBlock, FilterBlock,
    TargetBlock,
    LNABlock, MixerBlock, ADCBlock,
    RangeFFTBlock,
]

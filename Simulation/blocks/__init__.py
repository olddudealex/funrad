from .tx_path import PLLChirpBlock, DACIQBlock, AmplifierBlock
from .rx_path import LNABlock, MixerBlock, ADCBlock, IQAmplifierBlock, IFFilterBlock
from .passive import AntennaBlock, CouplerBlock, FilterBlock, AttenuatorBlock, WilkinsonDividerBlock
from .target import TargetBlock
from .dsp import RangeFFTBlock
from graph.registry import register_block

for _cls in (PLLChirpBlock, DACIQBlock, AmplifierBlock,
             LNABlock, MixerBlock, IQAmplifierBlock, IFFilterBlock, ADCBlock,
             AntennaBlock, CouplerBlock, FilterBlock, AttenuatorBlock, WilkinsonDividerBlock,
             TargetBlock, RangeFFTBlock):
    register_block(_cls)

ALL_BLOCKS = [
    PLLChirpBlock, DACIQBlock, AmplifierBlock,
    AntennaBlock, CouplerBlock, FilterBlock, AttenuatorBlock, WilkinsonDividerBlock,
    TargetBlock,
    LNABlock, MixerBlock, IQAmplifierBlock, IFFilterBlock, ADCBlock,
    RangeFFTBlock,
]

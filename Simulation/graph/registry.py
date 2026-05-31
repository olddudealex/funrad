from __future__ import annotations
from blocks.base import Block

_BLOCK_REGISTRY: dict[str, type[Block]] = {}


def register_block(cls: type[Block]) -> type[Block]:
    _BLOCK_REGISTRY[cls.__name__] = cls
    return cls

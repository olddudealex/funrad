from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Connection:
    src_block_id: str
    src_port_name: str
    dst_block_id: str
    dst_port_name: str
    dpg_link_id: int = 0    # DPG node-editor link widget ID

    def to_dict(self) -> dict:
        return {
            "src_block": self.src_block_id,
            "src_port": self.src_port_name,
            "dst_block": self.dst_block_id,
            "dst_port": self.dst_port_name,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Connection:
        return cls(
            src_block_id=d["src_block"],
            src_port_name=d["src_port"],
            dst_block_id=d["dst_block"],
            dst_port_name=d["dst_port"],
        )

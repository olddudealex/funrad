from __future__ import annotations
from typing import Callable
import dearpygui.dearpygui as dpg
from blocks import ALL_BLOCKS
from blocks.base import Block


class Palette:
    """Left-side panel: lists available block types; click to add to canvas."""

    def __init__(self, on_add_block: Callable[[type[Block]], None]):
        self._on_add = on_add_block

    def build(self, parent: int | str):
        with dpg.child_window(parent=parent, width=148, border=True):
            dpg.add_text("Blocks", color=(200, 200, 200))
            dpg.add_separator()
            current_category = None
            for cls in ALL_BLOCKS:
                cat = getattr(cls, "category", "Other")
                if cat != current_category:
                    dpg.add_spacer(height=4)
                    dpg.add_text(f"[{cat}]", color=(120, 160, 200))
                    current_category = cat
                dpg.add_button(
                    label=cls.display_name,
                    width=-1,
                    callback=lambda s, a, u: self._on_add(u),
                    user_data=cls,
                )

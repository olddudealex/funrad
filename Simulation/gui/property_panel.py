from __future__ import annotations
from typing import Callable
import dearpygui.dearpygui as dpg
from blocks.base import Block

_LABEL_COL_W = 155   # px — wide enough for "Tx Antenna Gain Dbi"


class PropertyPanel:
    """Right-side panel: shows and edits parameters of the selected block."""

    def __init__(self, on_apply: Callable[[], None],
                 on_mirror: Callable[[str], None]):
        self._on_apply = on_apply
        self._on_mirror = on_mirror
        self._block: Block | None = None
        self._child_window_tag: int | str = 0
        self._param_tags: dict[str, int | str] = {}

    def build(self, parent: int | str):
        self._child_window_tag = dpg.add_child_window(
            parent=parent, width=-1, border=True, label="Properties"
        )
        with dpg.group(parent=self._child_window_tag):
            dpg.add_text("Select a block to edit its parameters.",
                         color=(160, 160, 160), wrap=-1)

    def show_block(self, block: Block | None, signal=None):
        self._block = block
        dpg.delete_item(self._child_window_tag, children_only=True)
        self._param_tags.clear()

        if block is None:
            with dpg.group(parent=self._child_window_tag):
                dpg.add_text("Select a block to edit its parameters.",
                             color=(160, 160, 160), wrap=-1)
            return

        with dpg.group(parent=self._child_window_tag):
            dpg.add_text(block.display_name, color=(100, 200, 255))
            dpg.add_text(f"Type: {type(block).__name__}", color=(140, 140, 140))
            dpg.add_separator()

            # Two-column table: fixed label column | stretching input column
            with dpg.table(header_row=False,
                           borders_innerV=False, borders_outerV=False,
                           borders_innerH=False, borders_outerH=False):
                dpg.add_table_column(width_fixed=True,
                                     init_width_or_weight=_LABEL_COL_W)
                dpg.add_table_column()   # stretches to fill panel width

                for key, val in block.params.items():
                    label = key.replace("_", " ").title()
                    with dpg.table_row():
                        dpg.add_text(label, color=(180, 180, 180))
                        if isinstance(val, bool):
                            tag = dpg.add_checkbox(
                                label=f"##{key}", default_value=val)
                        elif isinstance(val, float):
                            tag = dpg.add_input_float(
                                label=f"##{key}", default_value=val,
                                width=-1, step=0, format="%.4g",
                            )
                        elif isinstance(val, int):
                            tag = dpg.add_input_int(
                                label=f"##{key}", default_value=val, width=-1,
                            )
                        elif isinstance(val, str):
                            tag = dpg.add_input_text(
                                label=f"##{key}", default_value=val, width=-1,
                            )
                        else:
                            dpg.add_text(f"{val}", color=(140, 140, 140))
                            continue
                        self._param_tags[key] = tag

            dpg.add_spacer(height=8)
            with dpg.group(horizontal=True):
                dpg.add_button(label="Apply", width=160, callback=self._apply)
                mirror_label = "Un-mirror" if block.mirrored else "Mirror"
                dpg.add_button(label=mirror_label, width=160,
                               callback=self._mirror)

    def _apply(self):
        if self._block is None:
            return
        for key, tag in self._param_tags.items():
            try:
                val = dpg.get_value(tag)
                if val is not None:
                    orig = self._block.params[key]
                    if isinstance(orig, bool):
                        self._block.params[key] = bool(val)
                    elif isinstance(orig, float):
                        self._block.params[key] = float(val)
                    elif isinstance(orig, int):
                        self._block.params[key] = int(val)
                    else:
                        self._block.params[key] = val
            except Exception:
                pass
        self._on_apply()

    def _mirror(self):
        if self._block is None:
            return
        self._block.mirrored = not self._block.mirrored
        self._on_mirror(self._block.block_id)
        self.show_block(self._block)

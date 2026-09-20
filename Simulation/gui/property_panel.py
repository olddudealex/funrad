from __future__ import annotations
from typing import Callable
import dearpygui.dearpygui as dpg
from blocks.base import Block

_LABEL_COL_W = 155   # px — wide enough for "Tx Antenna Gain Dbi"


class PropertyPanel:
    """Right-side panel: shows and edits parameters of the selected block."""

    def __init__(self, on_apply: Callable[[str, dict], None],
                 on_mirror: Callable[[str], None],
                 on_reset_override: Callable[[str, str], None],
                 on_promote_overrides: Callable[[str], None]):
        self._on_apply = on_apply
        self._on_mirror = on_mirror
        self._on_reset_override = on_reset_override
        self._on_promote_overrides = on_promote_overrides
        self._block: Block | None = None
        self._child_window_tag: int | str = 0
        self._param_tags: dict[str, int | str] = {}
        self._shown_values: dict[str, object] = {}

    def build(self, parent: int | str):
        self._child_window_tag = dpg.add_child_window(
            parent=parent, width=-1, border=True, label="Properties"
        )
        with dpg.group(parent=self._child_window_tag):
            dpg.add_text("Select a block to edit its parameters.",
                         color=(160, 160, 160), wrap=-1)

    def show_block(self, block: Block | None, signal=None,
                   override_keys: set[str] | None = None,
                   base_params: dict | None = None):
        self._block = block
        override_keys = override_keys or set()
        base_params = base_params or {}
        dpg.delete_item(self._child_window_tag, children_only=True)
        self._param_tags.clear()
        self._shown_values.clear()

        if block is None:
            with dpg.group(parent=self._child_window_tag):
                dpg.add_text("Select a block to edit its parameters.",
                             color=(160, 160, 160), wrap=-1)
            return

        with dpg.group(parent=self._child_window_tag):
            dpg.add_text(block.instance_name, color=(100, 200, 255))
            dpg.add_text(f"Type: {type(block).__name__}", color=(140, 140, 140))
            if override_keys:
                dpg.add_text("* Active scenario override", color=(255, 195, 80))
            dpg.add_separator()

            # Two-column table: fixed label column | stretching input column
            with dpg.table(header_row=False,
                           borders_innerV=False, borders_outerV=False,
                           borders_innerH=False, borders_outerH=False):
                dpg.add_table_column(width_fixed=True,
                                     init_width_or_weight=_LABEL_COL_W - 20)
                dpg.add_table_column()   # stretches to fill panel width
                dpg.add_table_column(width_fixed=True, init_width_or_weight=48)

                for key, val in block.params.items():
                    spec = block.param_specs[key]
                    overridden = key in override_keys
                    label = f"{spec.label} *" if overridden else spec.label
                    with dpg.table_row():
                        label_tag = dpg.add_text(
                            label,
                            color=(255, 195, 80) if overridden else (180, 180, 180),
                        )
                        if overridden:
                            with dpg.tooltip(label_tag):
                                dpg.add_text(f"Base value: {base_params.get(key)!r}")
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
                            options = block.param_options.get(key)
                            if options:
                                tag = dpg.add_combo(
                                    items=options, default_value=val,
                                    label=f"##{key}", width=-1,
                                )
                            else:
                                tag = dpg.add_input_text(
                                    label=f"##{key}", default_value=val, width=-1,
                                )
                        else:
                            dpg.add_text(f"{val}", color=(140, 140, 140))
                            dpg.add_text("")
                            continue
                        self._param_tags[key] = tag
                        self._shown_values[key] = val
                        if overridden:
                            dpg.add_button(
                                label="Reset",
                                width=46,
                                callback=self._reset_override,
                                user_data=key,
                            )
                        else:
                            dpg.add_text("")

            dpg.add_spacer(height=8)
            with dpg.group(horizontal=True):
                dpg.add_button(label="Apply", width=160, callback=self._apply)
                mirror_label = "Un-mirror" if block.mirrored else "Mirror"
                dpg.add_button(label=mirror_label, width=160,
                               callback=self._mirror)
            if override_keys:
                dpg.add_button(
                    label="Promote block overrides to base",
                    width=-1,
                    callback=self._promote_overrides,
                )

            if getattr(block, 'model_help', ''):
                dpg.add_spacer(height=6)
                with dpg.collapsing_header(label="Model description",
                                           default_open=False):
                    dpg.add_text(block.model_help, wrap=0)

    def _apply(self):
        if self._block is None:
            return
        changes = {}
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
                    if self._block.params[key] != self._shown_values.get(key):
                        changes[key] = self._block.params[key]
            except Exception:
                pass
        if changes:
            self._on_apply(self._block.block_id, changes)

    def _mirror(self):
        if self._block is None:
            return
        self._block.mirrored = not self._block.mirrored
        self._on_mirror(self._block.block_id)

    def _reset_override(self, _sender, _app_data, key):
        if self._block is not None:
            self._on_reset_override(self._block.block_id, key)

    def _promote_overrides(self):
        if self._block is not None:
            self._on_promote_overrides(self._block.block_id)

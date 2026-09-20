from __future__ import annotations
import math
import os
import dearpygui.dearpygui as dpg

from config import load_configuration, save_configuration
from graph.node_graph import NodeGraph
from physics.signal import SignalKind
from scenario import BASE_SCENARIO_LABEL, ConfigurationSession
from blocks import (
    PLLChirpBlock, DACIQBlock, AmplifierBlock,
    AntennaBlock, CouplerBlock, FilterBlock, AttenuatorBlock, WilkinsonDividerBlock,
    TargetBlock, LNABlock, MixerBlock, IQAmplifierBlock, IFFilterBlock, ADCBlock,
    RangeFFTBlock,
)
from gui.node_editor import NodeEditor
from gui.palette import Palette
from gui.property_panel import PropertyPanel
from gui.plot_panel import PlotPanel
from gui.metrics_panel import MetricsPanel


_PANEL_OVERHEAD_PX = 55   # menu bar + metrics row + separator


class App:
    def __init__(self):
        self._graph = NodeGraph()
        self._session = ConfigurationSession(self._graph.to_dict())
        self._current_file: str | None = None
        self._unsaved = False
        self._scenario_combo_tag: int | str = 0
        self._delete_scenario_tag: int | str = 0
        self._scenario_display_to_id: dict[str, str | None] = {}

        self._metrics = MetricsPanel()
        self._plot = PlotPanel(
            get_budget_fn=self._graph.get_power_budget,
            get_adc_half_bw_fn=self._get_adc_half_bw,
        )
        self._props = PropertyPanel(
            on_apply=self._on_params_changed,
            on_mirror=self._on_mirror_block,
            on_reset_override=self._on_reset_override,
            on_promote_overrides=self._on_promote_overrides,
        )
        self._node_editor = NodeEditor(
            graph=self._graph,
            on_block_selected=self._on_block_selected,
            on_graph_changed=self._on_graph_changed,
        )
        self._palette = Palette(on_add_block=self._on_add_block)

    # ------------------------------------------------------------------
    # Build the UI
    # ------------------------------------------------------------------

    def build(self):
        with dpg.window(tag="primary_window", no_title_bar=True,
                        no_resize=True, no_move=True, no_scrollbar=True):
            # Menu bar
            with dpg.menu_bar():
                with dpg.menu(label="File"):
                    dpg.add_menu_item(label="New",
                                      callback=self._file_new,
                                      shortcut="Ctrl+N")
                    dpg.add_menu_item(label="Open…",
                                      callback=self._file_open,
                                      shortcut="Ctrl+O")
                    dpg.add_separator()
                    dpg.add_menu_item(label="Save",
                                      callback=self._file_save,
                                      shortcut="Ctrl+S")
                    dpg.add_menu_item(label="Save As…",
                                      callback=self._file_save_as)
                with dpg.menu(label="Edit"):
                    dpg.add_menu_item(label="Delete selected block",
                                      callback=self._node_editor.remove_selected_block)
                with dpg.menu(label="Simulation"):
                    dpg.add_menu_item(label="Run chain",
                                      callback=self._run_and_update,
                                      shortcut="F5")

            # Main vertical container
            with dpg.group(horizontal=False, tag="main_vgroup"):
                # Metrics bar
                with dpg.group(horizontal=True) as _metrics_group:
                    dpg.add_text("Scenario:")
                    self._scenario_combo_tag = dpg.add_combo(
                        items=[BASE_SCENARIO_LABEL],
                        default_value=BASE_SCENARIO_LABEL,
                        width=230,
                        callback=self._on_scenario_changed,
                    )
                    dpg.add_button(
                        label="Add scenario",
                        width=100,
                        callback=self._open_add_scenario_dialog,
                    )
                    self._delete_scenario_tag = dpg.add_button(
                        label="Delete scenario",
                        width=110,
                        enabled=False,
                        callback=self._delete_active_scenario,
                    )
                    dpg.add_spacer(width=10)
                    self._metrics.build(_metrics_group)

                dpg.add_separator()

                # Top half: palette | node editor | properties
                _top_h = max(200, (dpg.get_viewport_height() - _PANEL_OVERHEAD_PX) // 2)
                with dpg.child_window(height=_top_h, border=False,
                                      tag="_top_panel"):
                    with dpg.table(header_row=False,
                                   borders_innerH=False, borders_innerV=True,
                                   borders_outerH=False, borders_outerV=False,
                                   resizable=True):
                        dpg.add_table_column(width_fixed=True, init_width_or_weight=152)
                        dpg.add_table_column()
                        dpg.add_table_column(width_fixed=True, init_width_or_weight=360)

                        with dpg.table_row():
                            # Palette (left)
                            with dpg.table_cell():
                                self._palette.build(dpg.last_item())

                            # Node editor (centre)
                            with dpg.table_cell():
                                with dpg.child_window(border=False, tag="editor_cell"):
                                    self._node_editor.build("editor_cell")

                            # Properties (right)
                            with dpg.table_cell():
                                self._props.build(dpg.last_item())

                # Bottom half: signal plots for selected block
                with dpg.child_window(height=-1, border=False) as _plot_cell:
                    self._plot.build(_plot_cell)

        dpg.set_primary_window("primary_window", True)
        dpg.set_viewport_resize_callback(self._on_viewport_resize)
        self._load_default_chain()
        self._run_and_update()

    # ------------------------------------------------------------------
    # Default preset chain
    # ------------------------------------------------------------------

    def _load_default_chain(self):
        """Load the standard FMCW radar chain from its executable specification."""
        default_path = os.path.join(
            os.path.dirname(__file__), "configs", "FunRad.RevA.toyradar"
        )
        self._load_configuration(default_path)
        self._current_file = default_path
        self._unsaved = False

    def _load_configuration(self, path: str) -> None:
        document, warnings = load_configuration(path, require_connected=False)
        for warning in warnings:
            print(f"[Configuration] {warning}")
        self._session.load(document)
        self._graph.from_dict(self._session.effective_document())
        self._refresh_scenario_selector()
        self._node_editor.refresh_all()
        self._plot.clear_selection()
        self._props.show_block(None)

    def _refresh_scenario_selector(self) -> None:
        self._scenario_display_to_id.clear()
        used: set[str] = set()
        active_display = BASE_SCENARIO_LABEL
        for scenario_id, label in self._session.scenarios():
            display = label
            if display in used:
                display = f"{label} ({scenario_id})"
            used.add(display)
            self._scenario_display_to_id[display] = scenario_id
            if scenario_id == self._session.active_scenario_id:
                active_display = display
        if dpg.does_item_exist(self._scenario_combo_tag):
            dpg.configure_item(
                self._scenario_combo_tag,
                items=list(self._scenario_display_to_id),
            )
            dpg.set_value(self._scenario_combo_tag, active_display)
        if dpg.does_item_exist(self._delete_scenario_tag):
            dpg.configure_item(
                self._delete_scenario_tag,
                enabled=self._session.active_scenario_id is not None,
            )

    def _sync_structure_from_graph(self) -> None:
        self._node_editor.update_node_positions()
        self._session.sync_graph_structure(self._graph.to_dict())

    def _rebuild_effective_graph(self, selected_block_id: str | None = None) -> None:
        pinned = self._plot.pinned_block
        pinned_block_id = pinned.block_id if pinned is not None else None
        self._graph.from_dict(self._session.effective_document())
        self._node_editor.refresh_all()
        self._plot.clear_selection()
        self._props.show_block(None)
        self._run_and_update()
        if pinned_block_id in self._graph.blocks:
            pinned_block = self._graph.blocks[pinned_block_id]
            self._plot.restore_pin(
                pinned_block,
                self._get_block_signal(pinned_block),
            )
        else:
            self._plot.refresh_budget()
        if selected_block_id in self._graph.blocks:
            self._node_editor.select_block(selected_block_id)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _on_viewport_resize(self, _, app_data):
        new_h = max(200, (app_data[1] - _PANEL_OVERHEAD_PX) // 2)
        if dpg.does_item_exist("_top_panel"):
            dpg.configure_item("_top_panel", height=new_h)

    def _on_block_selected(self, block):
        signal = self._get_block_signal(block) if block is not None else None
        self._show_block_properties(block, signal)
        self._plot.show(block, signal)  # gated by pin inside PlotPanel

    def _show_block_properties(self, block, signal=None):
        if block is None:
            self._props.show_block(None)
            return
        self._props.show_block(
            block,
            signal,
            override_keys=self._session.override_keys(block.block_id),
            base_params=self._session.base_params(block.block_id),
        )

    def _refresh_panels(self):
        """Refresh properties for the selected block; refresh the plot for
        the pinned block (or selected block if nothing is pinned)."""
        selected = self._node_editor.get_selected_block()
        sel_signal = None
        if selected:
            sel_signal = self._get_block_signal(selected)
            self._show_block_properties(selected, sel_signal)

        if self._plot.budget_mode:
            self._plot.refresh_budget()
            return

        pinned = self._plot.pinned_block
        if pinned is not None:
            pin_signal = self._get_block_signal(pinned)
            self._plot.show(pinned, pin_signal, force=True)
        elif selected:
            self._plot.show(selected, sel_signal)

    def _on_graph_changed(self):
        self._sync_structure_from_graph()
        self._unsaved = True
        self._run_and_update()
        self._refresh_panels()

    def _on_params_changed(self, block_id: str, changes: dict):
        for key, value in changes.items():
            self._session.set_parameter(block_id, key, value)
        self._unsaved = True
        self._run_and_update()
        self._refresh_panels()

    def _on_reset_override(self, block_id: str, key: str):
        self._session.reset_override(block_id, key)
        self._unsaved = True
        self._rebuild_effective_graph(block_id)

    def _on_promote_overrides(self, block_id: str):
        self._session.promote_block_overrides(block_id)
        self._unsaved = True
        self._rebuild_effective_graph(block_id)

    def _on_scenario_changed(self, _sender, display: str):
        scenario_id = self._scenario_display_to_id.get(display)
        if scenario_id == self._session.active_scenario_id:
            return
        self._sync_structure_from_graph()
        self._session.select(scenario_id)
        self._refresh_scenario_selector()
        self._rebuild_effective_graph()

    def _open_add_scenario_dialog(self):
        if dpg.does_item_exist("_add_scenario_dlg"):
            dpg.delete_item("_add_scenario_dlg")
        active = self._session.active_scenario_id is not None
        with dpg.window(
            label="Add scenario",
            modal=True,
            width=390,
            height=190,
            tag="_add_scenario_dlg",
            no_resize=True,
        ):
            dpg.add_text("Scenario name")
            dpg.add_input_text(tag="_scenario_name_input", width=-1)
            dpg.add_checkbox(
                label="Copy active scenario overrides",
                default_value=active,
                tag="_scenario_copy_active",
                enabled=active,
            )
            dpg.add_text("", tag="_scenario_add_error", color=(255, 120, 120))
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Add",
                    width=90,
                    callback=self._create_scenario_from_dialog,
                )
                dpg.add_button(
                    label="Cancel",
                    width=90,
                    callback=lambda: dpg.delete_item("_add_scenario_dlg"),
                )

    def _create_scenario_from_dialog(self):
        label = dpg.get_value("_scenario_name_input") or ""
        copy_active = bool(dpg.get_value("_scenario_copy_active"))
        try:
            self._sync_structure_from_graph()
            self._session.add_scenario(label, copy_active=copy_active)
        except ValueError as exc:
            dpg.set_value("_scenario_add_error", str(exc))
            return
        dpg.delete_item("_add_scenario_dlg")
        self._unsaved = True
        self._refresh_scenario_selector()
        self._rebuild_effective_graph()

    def _delete_active_scenario(self):
        scenario_id = self._session.active_scenario_id
        if scenario_id is None:
            return
        label = next(
            (
                item.get("label", item["id"])
                for item in self._session.document.get("scenarios", [])
                if item["id"] == scenario_id
            ),
            scenario_id,
        )

        def _delete():
            self._session.delete_active_scenario()
            self._unsaved = True
            self._refresh_scenario_selector()
            self._rebuild_effective_graph()

        self._confirm_dialog(f"Delete scenario '{label}'?", _delete)

    def _on_mirror_block(self, block_id: str):
        self._node_editor.redraw_block(block_id)
        self._sync_structure_from_graph()
        self._unsaved = True
        block = self._graph.blocks.get(block_id)
        if block is not None:
            self._show_block_properties(block, self._get_block_signal(block))

    def _get_adc_half_bw(self) -> float:
        for b in self._graph.blocks.values():
            if isinstance(b, ADCBlock):
                return b.params["sample_rate_mhz"] * 1e6 / 2.0
        return 0.0

    def _get_block_signal(self, block):
        try:
            outputs = self._graph.run_to(block.block_id)
            if not outputs:
                return None
            i_sig = outputs.get("I_out")
            q_sig = outputs.get("Q_out")
            if (i_sig is not None and q_sig is not None
                    and len(i_sig.samples) and len(q_sig.samples)):
                import numpy as np
                combined = (i_sig.samples.real + 1j * q_sig.samples.real).astype(np.complex64)
                return i_sig.copy(
                    samples=combined,
                    power_dbm=i_sig.power_dbm + 10 * math.log10(2.0),
                    noise_floor_dbm=i_sig.noise_floor_dbm + 10 * math.log10(2.0),
                    kind=SignalKind.IF_IQ,
                )
            return next(iter(outputs.values()))
        except Exception:
            pass
        return None

    def _run_and_update(self):
        # Run simulation in a worker thread so Python debuggers (debugpy /
        # PyCharm) can trace it.  DPG owns the main thread; breakpoints inside
        # any block's process() / transform() only fire reliably from a thread
        # that is fully under Python's trace hook.
        import threading
        _result: dict = {}

        def _worker():
            try:
                self._graph.run()
                _result["metrics"] = self._graph.compute_metrics()
            except Exception as e:
                _result["error"] = e

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        t.join()   # block until done — same latency as before, UI safe

        if "metrics" in _result:
            self._metrics.update(_result["metrics"])
        elif "error" in _result:
            print(f"[App] Simulation error: {_result['error']}")

    def _on_add_block(self, cls: type):
        block = cls()
        self._node_editor.add_block(block)
        self._sync_structure_from_graph()
        self._unsaved = True

    # ------------------------------------------------------------------
    # File menu
    # ------------------------------------------------------------------

    def _file_new(self):
        def _do_new():
            self._graph.clear()
            self._session.load(NodeGraph().to_dict())
            self._graph.from_dict(self._session.effective_document())
            self._node_editor.refresh_all()
            self._refresh_scenario_selector()
            self._plot.clear_selection()
            self._current_file = None
            self._unsaved = False
            self._props.show_block(None)
            self._run_and_update()

        if self._unsaved:
            self._confirm_dialog("Discard unsaved changes and start a new chain?",
                                 _do_new)
        else:
            _do_new()

    def _file_open(self):
        def _on_selected(sender, app_data):
            path = app_data.get("file_path_name", "")
            if not path:
                return
            try:
                self._load_configuration(path)
                self._current_file = path
                self._unsaved = False
                self._run_and_update()
            except Exception as e:
                self._error_dialog(f"Failed to open file:\n{e}")

        with dpg.file_dialog(
            label="Open chain file",
            callback=_on_selected,
            modal=True,
            width=600, height=400,
        ):
            dpg.add_file_extension(".toyradar", color=(100, 200, 255))
            dpg.add_file_extension(".*")

    def _file_save(self):
        if self._current_file:
            self._do_save(self._current_file)
        else:
            self._file_save_as()

    def _file_save_as(self):
        def _on_selected(sender, app_data):
            path = app_data.get("file_path_name", "")
            if not path:
                return
            if not path.endswith(".toyradar"):
                path += ".toyradar"
            self._do_save(path)

        with dpg.file_dialog(
            label="Save chain file",
            callback=_on_selected,
            modal=True,
            width=600, height=400,
        ):
            dpg.add_file_extension(".toyradar", color=(100, 200, 255))
            dpg.add_file_extension(".*")

    def _do_save(self, path: str):
        try:
            self._sync_structure_from_graph()
            save_configuration(
                self._session.document,
                path,
                require_connected=False,
            )
            self._current_file = path
            self._unsaved = False
        except Exception as e:
            self._error_dialog(f"Failed to save file:\n{e}")

    # ------------------------------------------------------------------
    # Utility dialogs
    # ------------------------------------------------------------------

    def _confirm_dialog(self, message: str, on_yes):
        with dpg.window(label="Confirm", modal=True, width=340, height=120,
                        tag="_confirm_dlg", no_resize=True):
            dpg.add_text(message, wrap=320)
            dpg.add_spacer(height=8)
            with dpg.group(horizontal=True):
                dpg.add_button(label="Yes", width=80, callback=lambda: (
                    dpg.delete_item("_confirm_dlg"), on_yes()))
                dpg.add_button(label="Cancel", width=80,
                               callback=lambda: dpg.delete_item("_confirm_dlg"))

    def _error_dialog(self, message: str):
        with dpg.window(label="Error", modal=True, width=380, height=140,
                        tag="_error_dlg", no_resize=True):
            dpg.add_text(message, wrap=360, color=(255, 120, 120))
            dpg.add_spacer(height=8)
            dpg.add_button(label="OK", width=60,
                           callback=lambda: dpg.delete_item("_error_dlg"))

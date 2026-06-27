from __future__ import annotations
import math
import os
import dearpygui.dearpygui as dpg

from graph.node_graph import NodeGraph
from physics.signal import SignalKind
from blocks import (
    PLLChirpBlock, DACIQBlock, AmplifierBlock,
    AntennaBlock, CouplerBlock, FilterBlock, AttenuatorBlock,
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
        self._current_file: str | None = None
        self._unsaved = False

        self._metrics = MetricsPanel()
        self._plot = PlotPanel(
            get_budget_fn=self._graph.get_power_budget,
            get_adc_half_bw_fn=self._get_adc_half_bw,
        )
        self._props = PropertyPanel(
            on_apply=self._on_params_changed,
            on_mirror=self._on_mirror_block,
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
        """Build the standard FMCW radar chain on startup."""
        # TX source
        pll = PLLChirpBlock()
        pll._dpg_pos = (30, 60)
        pll.params.update({"center_freq_ghz": 5.8, "bandwidth_mhz": 150.0,
                           "chirp_duration_ms": 1.0, "power_dbm": 2.0})

        # TX attenuator (level-setting before PA)
        att = AttenuatorBlock()
        att._dpg_pos = (175, 60)
        att.params.update({"attenuation_db": 22.0})

        # TX amplifier / PA
        pa = AmplifierBlock()
        pa._dpg_pos = (320, 60)
        pa.params.update({"gain_db": 20.0, "nf_db": 1.4})
        pa.display_name = "PA"

        # Directional coupler
        coupler = CouplerBlock()
        coupler._dpg_pos = (465, 60)
        coupler.params.update({"coupling_db": 20.0, "through_loss_db": 0.5})

        # TX Antenna
        tx_ant = AntennaBlock()
        tx_ant._dpg_pos = (610, 60)
        tx_ant.params.update({"gain_dbi": 12.0, "direction": "TX"})

        # Target
        target = TargetBlock()
        target._dpg_pos = (755, 60)
        target.params.update({"distance_m": 50.0, "rcs_dbsm": 0.0,
                               "tx_antenna_gain_dbi": 12.0,
                               "rx_antenna_gain_dbi": 12.0})

        # RX Antenna
        rx_ant = AntennaBlock()
        rx_ant._dpg_pos = (900, 240)
        rx_ant.params.update({"gain_dbi": 12.0, "direction": "RX"})
        rx_ant.mirrored = True

        # LNA
        lna = LNABlock()
        lna._dpg_pos = (780, 240)
        lna.params.update({"gain_db": 17.9, "nf_db": 0.76})
        lna.mirrored = True

        # Mixer (active, positive gain)
        mixer = MixerBlock()
        mixer._dpg_pos = (660, 240)
        mixer.params.update({"conversion_loss_db": -5.8, "nf_db": 15.5})
        mixer.mirrored = True

        # IF filter 1 — image/channel select, before IF amp
        if_filter1 = IFFilterBlock()
        if_filter1._dpg_pos = (540, 240)
        if_filter1.params.update({"cutoff_hz": 5e6, "order": 4, "insertion_loss_db": 1.0})
        if_filter1.mirrored = True

        # IF Amplifier
        iq_amp = IQAmplifierBlock()
        iq_amp._dpg_pos = (420, 240)
        iq_amp.params.update({"gain_db": 20.0, "nf_db": 5.0})
        iq_amp.mirrored = True

        # IF filter 2 — anti-alias before ADC
        if_filter2 = IFFilterBlock()
        if_filter2._dpg_pos = (300, 240)
        if_filter2.params.update({"cutoff_hz": 5e6, "order": 4, "insertion_loss_db": 1.0})
        if_filter2.mirrored = True

        # ADC
        adc = ADCBlock()
        adc._dpg_pos = (180, 240)
        adc.params.update({"bits": 14, "sample_rate_mhz": 3.5,
                           "full_scale_dbm": 10.0})
        adc.mirrored = True

        # Range FFT
        range_fft = RangeFFTBlock()
        range_fft._dpg_pos = (30, 240)
        range_fft.mirrored = True

        blocks = [pll, att, pa, coupler, tx_ant, target,
                  rx_ant, lna, mixer, if_filter1, iq_amp, if_filter2, adc, range_fft]
        for b in blocks:
            self._graph.add_block(b)
        self._node_editor.draw_all_blocks()

        # Connect TX path
        self._graph.connect(pll.block_id,    "rf_out",  att.block_id,    "rf_in")
        self._graph.connect(att.block_id,    "rf_out",  pa.block_id,     "rf_in")
        self._graph.connect(pa.block_id,     "rf_out",  coupler.block_id,"rf_in")
        self._graph.connect(coupler.block_id,"through",  tx_ant.block_id, "rf_in")
        self._graph.connect(tx_ant.block_id, "rf_out",  target.block_id, "tx_in")

        # Connect RX path
        self._graph.connect(target.block_id,    "rx_out", rx_ant.block_id,   "rf_in")
        self._graph.connect(rx_ant.block_id,    "rf_out", lna.block_id,      "rf_in")
        self._graph.connect(lna.block_id,       "rf_out", mixer.block_id,    "rf_in")
        self._graph.connect(coupler.block_id,   "coupled",mixer.block_id,    "lo_in")
        self._graph.connect(mixer.block_id,     "I_out",  if_filter1.block_id,"I_in")
        self._graph.connect(mixer.block_id,     "Q_out",  if_filter1.block_id,"Q_in")
        self._graph.connect(if_filter1.block_id,"I_out",  iq_amp.block_id,   "I_in")
        self._graph.connect(if_filter1.block_id,"Q_out",  iq_amp.block_id,   "Q_in")
        self._graph.connect(iq_amp.block_id,    "I_out",  if_filter2.block_id,"I_in")
        self._graph.connect(iq_amp.block_id,    "Q_out",  if_filter2.block_id,"Q_in")
        self._graph.connect(if_filter2.block_id,"I_out",  adc.block_id,      "I_in")
        self._graph.connect(if_filter2.block_id,"Q_out",  adc.block_id,      "Q_in")
        self._graph.connect(adc.block_id,       "I_out",  range_fft.block_id,"I_in")
        self._graph.connect(adc.block_id,       "Q_out",  range_fft.block_id,"Q_in")

        self._node_editor.draw_all_connections()

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _on_viewport_resize(self, _, app_data):
        new_h = max(200, (app_data[1] - _PANEL_OVERHEAD_PX) // 2)
        if dpg.does_item_exist("_top_panel"):
            dpg.configure_item("_top_panel", height=new_h)

    def _on_block_selected(self, block):
        signal = self._get_block_signal(block) if block is not None else None
        self._props.show_block(block, signal)
        self._plot.show(block, signal)  # gated by pin inside PlotPanel

    def _refresh_panels(self):
        """Refresh properties for the selected block; refresh the plot for
        the pinned block (or selected block if nothing is pinned)."""
        selected = self._node_editor.get_selected_block()
        sel_signal = None
        if selected:
            sel_signal = self._get_block_signal(selected)
            self._props.show_block(selected, sel_signal)

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
        self._unsaved = True
        self._run_and_update()
        self._refresh_panels()

    def _on_params_changed(self):
        self._unsaved = True
        self._run_and_update()
        self._refresh_panels()

    def _on_mirror_block(self, block_id: str):
        self._node_editor.redraw_block(block_id)
        self._unsaved = True

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
        self._unsaved = True

    # ------------------------------------------------------------------
    # File menu
    # ------------------------------------------------------------------

    def _file_new(self):
        def _do_new():
            self._graph.clear()
            self._node_editor.refresh_all()
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
                self._graph.load_from_file(path)
                self._node_editor.refresh_all()
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
            self._node_editor.update_node_positions()
            self._graph.save_to_file(path)
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

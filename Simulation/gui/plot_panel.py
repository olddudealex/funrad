from __future__ import annotations
import math
import re
from typing import Callable
import numpy as np
import dearpygui.dearpygui as dpg

from blocks.base import Block, PlotData
from blocks.signal_plots import signal_time_plot, signal_freq_plot
from physics.signal import SignalState


def _extract_unit(axis_label: str) -> str:
    """Pull the unit out of 'Frequency (kHz)' → 'kHz'."""
    m = re.search(r'\(([^)]+)\)', axis_label)
    return m.group(1) if m else ""


class PlotPanel:
    """Bottom strip: native DPG tabbed plots for the selected block."""

    def __init__(self, get_budget_fn: Callable[[], list] | None = None,
                 get_adc_half_bw_fn: Callable[[], float] | None = None):
        self._container_tag: int | str = 0
        self._content_tag: int | str = 0
        self._use_hanning: bool = True
        self._last_block: Block | None = None
        self._last_signal: SignalState | None = None

        # Pin state
        self._pinned_block: Block | None = None
        self._pin_btn_tag: int | str = 0
        # Block/signal queued while pinned or in budget mode — shown on deactivate
        self._queued_block: Block | None = None
        self._queued_signal: SignalState | None = None

        # Budget mode
        self._get_budget_fn = get_budget_fn
        self._budget_mode: bool = False
        self._budget_btn_tag: int | str = 0

        # IF scale toggle
        self._get_adc_half_bw_fn = get_adc_half_bw_fn
        self._if_narrow: bool = False
        self._if_scale_btn_tag: int | str = 0

        # Tab memory: block_id → last tab label
        self._last_tab: dict[str, str] = {}

        # Budget hover state — RF plot (dBm)
        self._budget_rf_entries: list[dict] = []
        self._budget_rf_plot_tag: int | str = 0
        self._budget_rf_annot_tag: int | str = 0
        # Budget hover state — IF plot (dBV)
        self._budget_if_entries: list[dict] = []
        self._budget_if_plot_tag: int | str = 0
        self._budget_if_annot_tag: int | str = 0

        # Signal plot hover state — one entry per rendered tab plot
        # Each entry: {tag, annot_tag, x_arr, x_unit, y_unit, series: [(lbl, y_arr)]}
        self._signal_plot_infos: list[dict] = []

        # Series color themes — created once in build()
        self._theme_signal: int | str = 0
        self._theme_noise: int | str = 0

    @property
    def pinned_block(self) -> Block | None:
        return self._pinned_block

    @property
    def budget_mode(self) -> bool:
        return self._budget_mode

    def build(self, parent: int | str):
        self._container_tag = dpg.add_group(parent=parent)
        with dpg.group(horizontal=True, parent=self._container_tag):
            dpg.add_checkbox(
                label="Hanning window",
                default_value=True,
                callback=self._on_hanning_toggle,
            )
            dpg.add_spacer(width=16)
            self._pin_btn_tag = dpg.add_button(
                label="Pin plot",
                width=110,
                callback=self._on_pin_toggle,
            )
            dpg.add_spacer(width=8)
            self._budget_btn_tag = dpg.add_button(
                label="Power Budget",
                width=120,
                callback=self._on_budget_toggle,
            )
            dpg.add_spacer(width=8)
            self._if_scale_btn_tag = dpg.add_button(
                label="IF: Full",
                width=80,
                callback=self._on_if_scale_toggle,
            )
        self._content_tag = dpg.add_group(parent=self._container_tag)
        dpg.add_text("Select a block to view its signal plots.",
                     color=(160, 160, 160), parent=self._content_tag)

        # Persistent series color themes
        with dpg.theme() as self._theme_signal:
            with dpg.theme_component(dpg.mvLineSeries):
                dpg.add_theme_color(dpg.mvPlotCol_Line, (31, 119, 180, 255),
                                    category=dpg.mvThemeCat_Plots)
        with dpg.theme() as self._theme_noise:
            with dpg.theme_component(dpg.mvLineSeries):
                dpg.add_theme_color(dpg.mvPlotCol_Line, (255, 127, 14, 255),
                                    category=dpg.mvThemeCat_Plots)

        # Single global mouse-move handler — handles both budget and signal hovers
        with dpg.handler_registry():
            dpg.add_mouse_move_handler(callback=self._on_plot_hover)

    # ------------------------------------------------------------------
    # Hanning toggle
    # ------------------------------------------------------------------

    def _on_hanning_toggle(self, _, app_data):
        self._use_hanning = app_data
        if not self._budget_mode:
            self._render(self._last_block, self._last_signal)

    # ------------------------------------------------------------------
    # IF scale toggle
    # ------------------------------------------------------------------

    def _on_if_scale_toggle(self):
        self._if_narrow = not self._if_narrow
        dpg.configure_item(self._if_scale_btn_tag,
                           label="IF: ADC" if self._if_narrow else "IF: Full")
        if not self._budget_mode:
            self._render(self._last_block, self._last_signal)

    # ------------------------------------------------------------------
    # Tab selection memory
    # ------------------------------------------------------------------

    def _on_tab_bar_changed(self, _sender, app_data, user_data):
        block_key, tag_to_name = user_data
        tab_name = tag_to_name.get(app_data)
        if tab_name and block_key:
            self._last_tab[block_key] = tab_name

    # ------------------------------------------------------------------
    # Pin / unpin
    # ------------------------------------------------------------------

    def _on_pin_toggle(self):
        if self._pinned_block is not None:
            self._pinned_block = None
            dpg.configure_item(self._pin_btn_tag, label="Pin plot")
            if self._queued_block is not None and not self._budget_mode:
                self._render(self._queued_block, self._queued_signal)
                self._queued_block = None
                self._queued_signal = None
        else:
            if self._last_block is None:
                return
            self._pinned_block = self._last_block
            name = self._last_block.display_name
            dpg.configure_item(self._pin_btn_tag, label=f"Unpin ({name})")

    # ------------------------------------------------------------------
    # Budget toggle
    # ------------------------------------------------------------------

    def _on_budget_toggle(self):
        self._budget_mode = not self._budget_mode
        dpg.configure_item(
            self._budget_btn_tag,
            label="Hide Budget" if self._budget_mode else "Power Budget",
        )
        if self._budget_mode:
            self._render_budget()
        else:
            self._budget_rf_entries = []
            self._budget_if_entries = []
            b = self._queued_block or self._last_block
            s = self._queued_signal or self._last_signal
            self._queued_block = None
            self._queued_signal = None
            self._render(b, s)

    # ------------------------------------------------------------------
    # Unified hover handler
    # ------------------------------------------------------------------

    def _on_plot_hover(self, _sender=None, _app_data=None):
        if self._budget_mode:
            self._budget_hover_update()
        else:
            self._signal_hover_update()

    def _budget_hover_update(self):
        self._budget_hover_one(self._budget_rf_entries,
                               self._budget_rf_plot_tag,
                               self._budget_rf_annot_tag)
        self._budget_hover_one(self._budget_if_entries,
                               self._budget_if_plot_tag,
                               self._budget_if_annot_tag)

    def _budget_hover_one(self, entries: list[dict],
                          plot_tag: int | str,
                          annot_tag: int | str) -> None:
        if not entries:
            return
        if not dpg.does_item_exist(annot_tag):
            return
        if not dpg.does_item_exist(plot_tag):
            return
        if not dpg.is_item_hovered(plot_tag):
            dpg.configure_item(annot_tag, label="")
            return
        mx, _ = dpg.get_plot_mouse_pos()
        idx = max(0, min(int(round(mx)), len(entries) - 1))
        e   = entries[idx]
        sig = e["signal_level"]
        noi = e["noise_level"]
        snr = e["snr_db"]
        unit = e["unit"]
        dom  = e["domain"]
        text = (f"[{dom}] {e['label']}\n"
                f"Signal: {sig:.1f} {unit}\n"
                f"Noise:  {noi:.1f} {unit}\n"
                f"SNR:    {snr:.1f} dB")
        dpg.configure_item(annot_tag, label=text,
                           default_value=(float(idx), sig))

    def _signal_hover_update(self):
        for info in self._signal_plot_infos:
            tag = info["tag"]
            annot = info["annot_tag"]
            if not dpg.does_item_exist(tag) or not dpg.does_item_exist(annot):
                continue
            if not dpg.is_item_hovered(tag):
                dpg.configure_item(annot, label="")
                continue
            mx, _ = dpg.get_plot_mouse_pos()
            x_arr = info["x_arr"]
            # Binary search for nearest index
            i = int(np.searchsorted(x_arr, mx))
            i = max(0, min(i, len(x_arr) - 1))
            if i > 0 and abs(x_arr[i - 1] - mx) < abs(x_arr[i] - mx):
                i -= 1
            x_val = float(x_arr[i])
            x_unit = info["x_unit"]
            y_unit = info["y_unit"]
            lines = [f"{x_val:.4g} {x_unit}"]
            for lbl, y_arr in info["series"]:
                lines.append(f"{lbl}: {y_arr[i]:.2f} {y_unit}")
            text = "\n".join(lines)
            anchor_y = float(info["series"][0][1][i])
            dpg.configure_item(annot, label=text,
                               default_value=(x_val, anchor_y))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show(self, block: Block | None, signal: SignalState | None,
             force: bool = False):
        """Update the plot panel.

        If budget mode is active, or a block is pinned and force=False,
        the new block/signal are cached and shown when those modes deactivate.
        Pass force=True to update the display regardless of pin state.
        """
        if self._budget_mode:
            self._queued_block = block
            self._queued_signal = signal
            return
        if self._pinned_block is not None and not force:
            self._queued_block = block
            self._queued_signal = signal
            return
        self._render(block, signal)

    def refresh_budget(self):
        """Re-render the budget chart after the simulation reruns."""
        if self._budget_mode:
            self._render_budget()

    # ------------------------------------------------------------------
    # Internal rendering helpers
    # ------------------------------------------------------------------

    def _add_signal_plot(self, pd: PlotData) -> None:
        """Render one PlotData tab and register its hover info."""
        all_y = np.concatenate([pd.y] + [ey for _, _, ey in pd.extra_series])
        finite = all_y[np.isfinite(all_y)]
        if len(finite):
            ymin, ymax = float(finite.min()), float(finite.max())
            span = ymax - ymin
            margin = span * 0.10 if span > 0 else abs(ymax) * 0.10 + 1.0
        else:
            ymin, ymax, margin = -100.0, 0.0, 5.0

        x_unit = _extract_unit(pd.x_label)
        y_unit = _extract_unit(pd.y_label)

        # Build series list: main first, then extras that share the same x length
        series: list[tuple[str, np.ndarray]] = [(pd.title, pd.y)]
        for lbl, ex, ey in pd.extra_series:
            if len(ey) == len(pd.x):
                series.append((lbl, ey))

        with dpg.plot(width=-1, height=-1, label="") as plot_tag:
            dpg.add_plot_legend()
            x_ax = dpg.add_plot_axis(dpg.mvXAxis, label=pd.x_label)
            y_ax = dpg.add_plot_axis(dpg.mvYAxis, label=pd.y_label)
            sig_tag = dpg.add_line_series(pd.x.tolist(), pd.y.tolist(),
                                          label=pd.title, parent=y_ax)
            dpg.bind_item_theme(sig_tag, self._theme_signal)
            for lbl, ex, ey in pd.extra_series:
                s_tag = dpg.add_line_series(ex.tolist(), ey.tolist(),
                                            label=lbl, parent=y_ax)
                if "noise" in lbl.lower():
                    dpg.bind_item_theme(s_tag, self._theme_noise)
            dpg.set_axis_limits(y_ax, ymin - margin, ymax + margin)
            if pd.x_view is not None:
                dpg.set_axis_limits(x_ax, pd.x_view[0], pd.x_view[1])
            else:
                dpg.fit_axis_data(x_ax)

            annot_tag = dpg.add_plot_annotation(
                label="",
                default_value=(0.0, 0.0),
                offset=(15, -10),
                color=(40, 40, 40, 220),
                clamped=True,
            )

        self._signal_plot_infos.append({
            "tag":      plot_tag,
            "annot_tag": annot_tag,
            "x_arr":    pd.x,
            "x_unit":   x_unit,
            "y_unit":   y_unit,
            "series":   series,
        })

    # ------------------------------------------------------------------
    # Internal rendering
    # ------------------------------------------------------------------

    def _render(self, block: Block | None, signal: SignalState | None):
        if not dpg.does_item_exist(self._content_tag):
            return
        dpg.delete_item(self._content_tag, children_only=True)
        self._signal_plot_infos = []

        self._last_block = block
        self._last_signal = signal

        if block is None or signal is None:
            dpg.add_text("Select a block to view its signal plots.",
                         color=(160, 160, 160), parent=self._content_tag)
            return

        try:
            block_plots = block.get_plots(signal)
        except Exception as exc:
            dpg.add_text(f"Plot error: {exc}", color=(255, 100, 100),
                         parent=self._content_tag)
            return

        x_clip_hz = None
        if (self._if_narrow and self._get_adc_half_bw_fn
                and math.isfinite(signal.voltage_dbv)):
            x_clip_hz = self._get_adc_half_bw_fn() or None

        plots: dict[str, PlotData] = {
            "Signal (freq)": signal_freq_plot(signal, use_hanning=self._use_hanning,
                                              x_clip_hz=x_clip_hz),
            "Signal (time)": signal_time_plot(signal),
        }
        plots.update(block_plots)

        block_key = block.block_id
        remembered = self._last_tab.get(block_key)

        tag_to_name: dict[int | str, str] = {}
        tab_bar_tag = dpg.add_tab_bar(
            parent=self._content_tag,
            callback=self._on_tab_bar_changed,
            user_data=(block_key, tag_to_name),
        )
        tab_tags: dict[str, int | str] = {}
        for tab_name, pd in plots.items():
            with dpg.tab(label=tab_name, parent=tab_bar_tag) as t:
                tab_tags[tab_name] = t
                tag_to_name[t] = tab_name
                try:
                    self._add_signal_plot(pd)
                except Exception:
                    dpg.add_text("Plot error", color=(255, 100, 100))

        if remembered in tab_tags:
            dpg.set_value(tab_bar_tag, tab_tags[remembered])

    def _render_budget(self):
        if not dpg.does_item_exist(self._content_tag):
            return
        dpg.delete_item(self._content_tag, children_only=True)
        self._signal_plot_infos = []
        self._budget_rf_entries = []
        self._budget_if_entries = []
        self._budget_rf_plot_tag = 0
        self._budget_rf_annot_tag = 0
        self._budget_if_plot_tag = 0
        self._budget_if_annot_tag = 0

        if not self._get_budget_fn:
            dpg.add_text("No budget function configured.",
                         color=(160, 160, 160), parent=self._content_tag)
            return

        budget = self._get_budget_fn()
        if not budget:
            dpg.add_text("Run simulation first.",
                         color=(160, 160, 160), parent=self._content_tag)
            return

        rf_entries = [e for e in budget if e["domain"] == "RF"]
        if_entries = [e for e in budget if e["domain"] == "IF"]
        self._budget_rf_entries = rf_entries
        self._budget_if_entries = if_entries

        has_both = bool(rf_entries) and bool(if_entries)
        panel_h  = dpg.get_item_height(self._content_tag)
        half     = max(120, (panel_h - 20) // 2) if has_both else -1

        if rf_entries:
            self._budget_rf_plot_tag, self._budget_rf_annot_tag = \
                self._render_budget_plot(
                    rf_entries,
                    y_label="Power (dBm)",
                    height=half if has_both else -1,
                )

        if has_both:
            dpg.add_spacer(height=4, parent=self._content_tag)

        if if_entries:
            self._budget_if_plot_tag, self._budget_if_annot_tag = \
                self._render_budget_plot(
                    if_entries,
                    y_label="Voltage (dBV)",
                    height=-1,
                )

    def _render_budget_plot(self, entries: list[dict],
                            y_label: str,
                            height: int) -> tuple[int | str, int | str]:
        """Render one budget sub-plot; returns (plot_tag, annot_tag)."""
        n      = len(entries)
        xs     = [float(i) for i in range(n)]
        labels = [e["label"] for e in entries]
        sigs   = [e["signal_level"] for e in entries]
        nois   = [e["noise_level"]  for e in entries]
        unit   = entries[0]["unit"]

        with dpg.plot(width=-1, height=height,
                      parent=self._content_tag, label="") as plot_tag:
            dpg.add_plot_legend()
            x_ax = dpg.add_plot_axis(dpg.mvXAxis, label="")
            dpg.set_axis_limits(x_ax, -0.5, float(n) - 0.5)
            dpg.set_axis_ticks(x_ax, tuple((lbl, i)
                                           for i, lbl in enumerate(labels)))
            y_ax = dpg.add_plot_axis(dpg.mvYAxis, label=y_label)

            all_vals = [v for v in sigs + nois if np.isfinite(v)]
            if all_vals:
                lo, hi = min(all_vals), max(all_vals)
                span   = hi - lo
                margin = span * 0.12 if span > 0 else 5.0
                dpg.set_axis_limits(y_ax, lo - margin, hi + margin)

            sig_tag = dpg.add_line_series(xs, sigs,
                                          label=f"Signal ({unit})", parent=y_ax)
            dpg.bind_item_theme(sig_tag, self._theme_signal)
            noi_tag = dpg.add_line_series(xs, nois,
                                          label=f"Noise ({unit})", parent=y_ax)
            dpg.bind_item_theme(noi_tag, self._theme_noise)

            annot_tag = dpg.add_plot_annotation(
                label="",
                default_value=(0.0, 0.0),
                offset=(12, -8),
                color=(40, 40, 40, 220),
                clamped=True,
            )

        return plot_tag, annot_tag

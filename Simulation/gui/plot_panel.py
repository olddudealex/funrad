from __future__ import annotations
import numpy as np
import dearpygui.dearpygui as dpg

from blocks.base import Block, PlotData
from blocks.signal_plots import signal_time_plot, signal_freq_plot
from physics.signal import SignalState


def _add_dpg_plot(pd: PlotData) -> None:
    all_y = np.concatenate([pd.y] + [ey for _, _, ey in pd.extra_series])
    finite = all_y[np.isfinite(all_y)]
    if len(finite):
        ymin, ymax = float(finite.min()), float(finite.max())
        span = ymax - ymin
        margin = span * 0.10 if span > 0 else abs(ymax) * 0.10 + 1.0
    else:
        ymin, ymax, margin = -100.0, 0.0, 5.0

    with dpg.plot(width=-1, height=-1, label=""):
        dpg.add_plot_legend()
        x_ax = dpg.add_plot_axis(dpg.mvXAxis, label=pd.x_label)
        y_ax = dpg.add_plot_axis(dpg.mvYAxis, label=pd.y_label)
        dpg.add_line_series(pd.x.tolist(), pd.y.tolist(),
                            label=pd.title, parent=y_ax)
        for lbl, ex, ey in pd.extra_series:
            dpg.add_line_series(ex.tolist(), ey.tolist(), label=lbl, parent=y_ax)
        dpg.set_axis_limits(y_ax, ymin - margin, ymax + margin)
        dpg.fit_axis_data(x_ax)


class PlotPanel:
    """Bottom strip: native DPG tabbed plots for the selected block."""

    def __init__(self):
        self._container_tag: int | str = 0
        self._content_tag: int | str = 0
        self._use_hanning: bool = True
        self._last_block: Block | None = None
        self._last_signal: SignalState | None = None

    def build(self, parent: int | str):
        self._container_tag = dpg.add_group(parent=parent)
        with dpg.group(horizontal=True, parent=self._container_tag):
            dpg.add_checkbox(
                label="Hanning window",
                default_value=True,
                callback=self._on_hanning_toggle,
            )
        self._content_tag = dpg.add_group(parent=self._container_tag)
        dpg.add_text("Select a block to view its signal plots.",
                     color=(160, 160, 160), parent=self._content_tag)

    def _on_hanning_toggle(self, _, app_data):
        self._use_hanning = app_data
        self.show(self._last_block, self._last_signal)

    def show(self, block: Block | None, signal: SignalState | None):
        if not dpg.does_item_exist(self._content_tag):
            return
        dpg.delete_item(self._content_tag, children_only=True)

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

        # Universal signal plots always shown first, then block-specific ones
        plots: dict[str, PlotData] = {
            "Signal (freq)": signal_freq_plot(signal, use_hanning=self._use_hanning),
            "Signal (time)": signal_time_plot(signal),
        }
        plots.update(block_plots)

        with dpg.tab_bar(parent=self._content_tag):
            for tab_name, pd in plots.items():
                with dpg.tab(label=tab_name):
                    try:
                        _add_dpg_plot(pd)
                    except Exception:
                        dpg.add_text("Plot error", color=(255, 100, 100))

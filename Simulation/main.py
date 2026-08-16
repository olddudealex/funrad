import sys
import os

# Ensure the Simulation directory is on the path so relative imports work
sys.path.insert(0, os.path.dirname(__file__))

import dearpygui.dearpygui as dpg
from app import App


def _setup_font() -> None:
    """Load Consolas for the whole UI.

    DPG 2.x builds the glyph atlas automatically from all characters present
    in the loaded TTF file — no explicit range hints are needed or supported.
    Consolas is designed for screen rendering at small sizes and ships with
    Windows. It covers the Unicode symbols used in block model descriptions
    (±, ², ½, µ, ·, ×, −, ≤, ≥, ≈, →, √, —, λ, π, τ, Ω).
    Subscript digits (₀–₉) are not in common system fonts; use plain digits.
    """
    import os
    font_path = r"C:\Windows\Fonts\consola.ttf"
    if not os.path.exists(font_path):
        return   # fall back to DPG default if the font file is missing
    with dpg.font_registry():
        with dpg.font(font_path, 14) as courier:
            pass
    dpg.bind_font(courier)


def main():
    dpg.create_context()
    _setup_font()
    dpg.create_viewport(
        title="ToyRadar / FMCW Radar Simulator",
        width=1400, height=900,
        min_width=900, min_height=600,
    )
    dpg.setup_dearpygui()

    app = App()
    app.build()

    dpg.show_viewport()
    dpg.start_dearpygui()
    dpg.destroy_context()


if __name__ == "__main__":
    main()

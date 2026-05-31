import sys
import os

# Ensure the Simulation directory is on the path so relative imports work
sys.path.insert(0, os.path.dirname(__file__))

import dearpygui.dearpygui as dpg
from app import App


def main():
    dpg.create_context()
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

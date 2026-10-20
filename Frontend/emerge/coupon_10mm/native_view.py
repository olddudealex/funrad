"""Keep EMerge 2.8.9's interactive viewer alive after off-screen screenshots."""
import pyvista as pv


def interactive_view(model, **kwargs):
    # Emsutil's show(off_screen=True) resets its plotter while pv.OFF_SCREEN
    # is still True. That creates vtkGenericRenderWindowInteractor, whose
    # Start() has no native event loop. Changing off_screen afterwards is
    # insufficient: recreate the plotter with the global flag cleared first.
    pv.OFF_SCREEN = False
    model.display._reset()
    model.view(off_screen=False, **kwargs)

"""FluidX_Blender – Blender addon for generating and loading FluidX3D simulations.

bl_info is read by Blender to display add-on metadata in the Preferences window.
"""

bl_info = {
    "name": "FluidX_Blender",
    "author": "FluidX_Blender contributors",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "location": "View3D › Sidebar › FluidX",
    "description": "Generate FluidX3D simulation setups and import simulation results into Blender",
    "warning": "Requires FluidX3D (https://github.com/ProjectPhysX/FluidX3D) to run simulations",
    "doc_url": "https://github.com/Jcwscience/FluidX_Blender",
    "category": "Simulation",
}

from . import properties, operators, panels  # noqa: E402


def register():
    properties.register()
    operators.register()
    panels.register()


def unregister():
    panels.unregister()
    operators.unregister()
    properties.unregister()

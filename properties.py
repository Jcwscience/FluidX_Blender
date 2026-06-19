"""Blender RNA properties for the FluidX_Blender addon."""

import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    StringProperty,
)
from bpy.types import PropertyGroup

# ---------------------------------------------------------------------------
# Boundary condition enum
# ---------------------------------------------------------------------------

BC_ITEMS = [
    ("PERIODIC",   "Periodic",   "Periodic boundary (wraps around)"),
    ("WALL",       "Wall",       "No-slip solid wall"),
    ("FREE_SLIP",  "Free-slip",  "Free-slip (symmetry) boundary"),
    ("VELOCITY",   "Velocity",   "Prescribed velocity inlet/outlet"),
]


class FluidXProperties(PropertyGroup):
    """All simulation and I/O settings exposed to the user."""

    # ---- Domain --------------------------------------------------------
    domain_res_x: IntProperty(
        name="Resolution X",
        description="Lattice grid resolution along X",
        default=128,
        min=8,
        max=2048,
    )
    domain_res_y: IntProperty(
        name="Resolution Y",
        description="Lattice grid resolution along Y",
        default=64,
        min=8,
        max=2048,
    )
    domain_res_z: IntProperty(
        name="Resolution Z",
        description="Lattice grid resolution along Z",
        default=64,
        min=8,
        max=2048,
    )

    # ---- Physics -------------------------------------------------------
    viscosity: FloatProperty(
        name="Kinematic Viscosity",
        description="LBM kinematic viscosity (lattice units). "
                    "Re = u_max * L / nu",
        default=1.0 / 6.0,
        min=1e-6,
        max=1.0,
        precision=6,
    )
    density: FloatProperty(
        name="Density",
        description="Initial fluid density (lattice units)",
        default=1.0,
        min=0.01,
        max=10.0,
        precision=4,
    )

    # ---- Simulation time -----------------------------------------------
    time_steps: IntProperty(
        name="Time Steps",
        description="Total number of LBM time steps to simulate",
        default=5000,
        min=1,
        max=10_000_000,
    )
    output_every: IntProperty(
        name="Output Every N Steps",
        description="Write output files every N simulation steps",
        default=100,
        min=1,
        max=100_000,
    )

    # ---- Boundary conditions -------------------------------------------
    bc_x_neg: EnumProperty(
        name="X- boundary",
        items=BC_ITEMS,
        default="WALL",
    )
    bc_x_pos: EnumProperty(
        name="X+ boundary",
        items=BC_ITEMS,
        default="WALL",
    )
    bc_y_neg: EnumProperty(
        name="Y- boundary",
        items=BC_ITEMS,
        default="WALL",
    )
    bc_y_pos: EnumProperty(
        name="Y+ boundary",
        items=BC_ITEMS,
        default="WALL",
    )
    bc_z_neg: EnumProperty(
        name="Z- boundary",
        items=BC_ITEMS,
        default="WALL",
    )
    bc_z_pos: EnumProperty(
        name="Z+ boundary",
        items=BC_ITEMS,
        default="WALL",
    )

    # ---- FluidX3D executable / paths -----------------------------------
    fluidx3d_path: StringProperty(
        name="FluidX3D Directory",
        description="Path to the FluidX3D source directory (contains Makefile)",
        subtype="DIR_PATH",
        default="",
    )
    output_dir: StringProperty(
        name="Output Directory",
        description="Directory where simulation results will be written",
        subtype="DIR_PATH",
        default="//fluidx_output",
    )
    setup_output_dir: StringProperty(
        name="Setup File Directory",
        description="Directory to write the generated setup.cpp",
        subtype="DIR_PATH",
        default="//fluidx_setup",
    )

    # ---- Load results --------------------------------------------------
    results_dir: StringProperty(
        name="Results Directory",
        description="Directory containing simulation output files to import",
        subtype="DIR_PATH",
        default="",
    )
    load_format: EnumProperty(
        name="File Format",
        description="Format of the simulation output files to load",
        items=[
            ("VTK", "VTK (*.vtk)", "Legacy VTK surface/volume meshes"),
            ("OBJ", "OBJ (*.obj)", "Wavefront OBJ surface meshes"),
            ("PLY", "PLY (*.ply)", "Stanford PLY surface meshes"),
        ],
        default="VTK",
    )
    load_start_frame: IntProperty(
        name="Start Frame",
        description="Blender frame to assign to the first loaded file",
        default=1,
        min=0,
        max=1_000_000,
    )
    load_as_sequence: BoolProperty(
        name="Load as Frame Sequence",
        description="Import all files in the directory as a frame sequence",
        default=True,
    )

    # ---- Build / run flags ---------------------------------------------
    build_before_run: BoolProperty(
        name="Build Before Run",
        description="Run `make` in the FluidX3D directory before launching",
        default=False,
    )
    run_in_background: BoolProperty(
        name="Run in Background",
        description="Launch the simulation as a background process "
                    "(non-blocking; Blender remains responsive)",
        default=True,
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_classes = (FluidXProperties,)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.fluidx = bpy.props.PointerProperty(type=FluidXProperties)


def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.fluidx

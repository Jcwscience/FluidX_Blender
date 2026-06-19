"""Blender RNA properties for the FluidX_Blender addon."""

import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    StringProperty,
)
from bpy.types import PropertyGroup

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

BC_ITEMS = [
    ("PERIODIC",   "Periodic",   "Periodic boundary (wraps around)"),
    ("WALL",       "Wall",       "No-slip solid wall"),
    ("FREE_SLIP",  "Free-slip",  "Free-slip (symmetry) boundary"),
    ("EQUILIBRIUM", "Equilibrium", "Equilibrium (inflow/outflow) boundary"),
]

OBJECT_TYPE_ITEMS = [
    ("NONE",      "None",      "Not part of the FluidX3D simulation"),
    ("DOMAIN",    "Domain",    "Defines the simulation bounding box"),
    ("COLLISION", "Collision", "Solid obstacle voxelized from its mesh"),
    ("INFLOW",    "Inflow",    "Fluid velocity inlet (equilibrium boundary)"),
    ("OUTFLOW",   "Outflow",   "Fluid outflow / equilibrium outlet"),
]


# ---------------------------------------------------------------------------
# Per-object FluidX properties
# ---------------------------------------------------------------------------

class FluidXObjectProperties(PropertyGroup):
    """Per-object FluidX3D simulation role and parameters."""

    object_type: EnumProperty(
        name="FluidX Type",
        description="Role of this object in the FluidX3D simulation",
        items=OBJECT_TYPE_ITEMS,
        default="NONE",
    )
    inflow_velocity: FloatVectorProperty(
        name="Inflow Velocity",
        description="Velocity vector for inflow cells (LBM lattice units, max ≈ 0.57)",
        default=(0.1, 0.0, 0.0),
        size=3,
        subtype="VELOCITY",
    )
    inflow_density: FloatProperty(
        name="Inflow Density",
        description="Fluid density for inflow/outflow cells (LBM lattice units, default 1.0)",
        default=1.0,
        min=0.01,
        max=10.0,
        precision=4,
    )


# ---------------------------------------------------------------------------
# Scene-level FluidX properties
# ---------------------------------------------------------------------------

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
        description="LBM kinematic viscosity (lattice units). Re = u_max * L / nu",
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
    gravity: FloatVectorProperty(
        name="Gravity",
        description="Volume force / gravity vector (LBM lattice units). Typical: (0, 0, -0.0001)",
        default=(0.0, 0.0, 0.0),
        size=3,
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
        description="Write VTK output files every N simulation steps",
        default=100,
        min=1,
        max=100_000,
    )

    # ---- Boundary conditions -------------------------------------------
    bc_x_neg: EnumProperty(name="X- boundary", items=BC_ITEMS, default="WALL")
    bc_x_pos: EnumProperty(name="X+ boundary", items=BC_ITEMS, default="WALL")
    bc_y_neg: EnumProperty(name="Y- boundary", items=BC_ITEMS, default="WALL")
    bc_y_pos: EnumProperty(name="Y+ boundary", items=BC_ITEMS, default="WALL")
    bc_z_neg: EnumProperty(name="Z- boundary", items=BC_ITEMS, default="WALL")
    bc_z_pos: EnumProperty(name="Z+ boundary", items=BC_ITEMS, default="WALL")

    # ---- Cache / paths -------------------------------------------------
    cache_dir: StringProperty(
        name="Cache Directory",
        description="Root directory for all bake output (STL meshes, VTK volumes, VDB files)",
        subtype="DIR_PATH",
        default="//fluidx_cache",
    )
    fluidx3d_path: StringProperty(
        name="FluidX3D Directory",
        description="Path to the FluidX3D source directory (contains makefile). "
                    "Leave empty to use the bundled submodule.",
        subtype="DIR_PATH",
        default="",
    )

    # ---- Legacy paths (kept for backward compatibility) ----------------
    output_dir: StringProperty(
        name="Output Directory",
        description="(Legacy) Directory where simulation results will be written",
        subtype="DIR_PATH",
        default="//fluidx_output",
    )
    setup_output_dir: StringProperty(
        name="Setup File Directory",
        description="(Legacy) Directory to write the generated setup.cpp",
        subtype="DIR_PATH",
        default="//fluidx_setup",
    )

    # ---- Bake runtime state (not persisted) ----------------------------
    is_baking: BoolProperty(
        name="Is Baking",
        description="True while a bake process is running in the background",
        default=False,
    )
    bake_progress: FloatProperty(
        name="Bake Progress",
        description="Estimated bake completion (0–1)",
        default=0.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
    )
    bake_stats: StringProperty(
        name="Bake Stats",
        description="Last status line from the running simulation",
        default="",
    )

    # ---- Load / import results -----------------------------------------
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
            ("VDB", "OpenVDB (*.vdb)", "OpenVDB volume files (recommended for volume rendering)"),
            ("VTK", "VTK (*.vtk)", "Legacy VTK surface/volume meshes"),
            ("OBJ", "OBJ (*.obj)", "Wavefront OBJ surface meshes"),
            ("PLY", "PLY (*.ply)", "Stanford PLY surface meshes"),
        ],
        default="VDB",
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

    # ---- Build / run flags (legacy) ------------------------------------
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

_classes = (FluidXObjectProperties, FluidXProperties)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.fluidx = bpy.props.PointerProperty(
        type=FluidXProperties,
    )
    bpy.types.Object.fluidx = bpy.props.PointerProperty(
        type=FluidXObjectProperties,
    )


def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.fluidx
    del bpy.types.Object.fluidx

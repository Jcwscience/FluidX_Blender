"""Blender UI panels for the FluidX_Blender addon.

All panels live in the VIEW_3D sidebar under a "FluidX" tab.
"""

import bpy
from bpy.types import Panel


class FLUIDX_PT_base:
    """Mixin with shared settings for all FluidX panels."""

    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "FluidX"


# ---------------------------------------------------------------------------
# Simulation domain
# ---------------------------------------------------------------------------

class FLUIDX_PT_simulation(FLUIDX_PT_base, Panel):
    bl_label = "Simulation Domain"
    bl_idname = "FLUIDX_PT_simulation"

    def draw(self, context):
        props = context.scene.fluidx
        layout = self.layout

        col = layout.column(align=True)
        col.label(text="Grid Resolution:")
        row = col.row(align=True)
        row.prop(props, "domain_res_x", text="X")
        row.prop(props, "domain_res_y", text="Y")
        row.prop(props, "domain_res_z", text="Z")

        layout.separator()
        col2 = layout.column(align=True)
        col2.label(text="Time:")
        col2.prop(props, "time_steps")
        col2.prop(props, "output_every")


# ---------------------------------------------------------------------------
# Physics
# ---------------------------------------------------------------------------

class FLUIDX_PT_physics(FLUIDX_PT_base, Panel):
    bl_label = "Physics"
    bl_idname = "FLUIDX_PT_physics"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        props = context.scene.fluidx
        layout = self.layout

        col = layout.column(align=True)
        col.prop(props, "viscosity")
        col.prop(props, "density")


# ---------------------------------------------------------------------------
# Boundary conditions
# ---------------------------------------------------------------------------

class FLUIDX_PT_boundary(FLUIDX_PT_base, Panel):
    bl_label = "Boundary Conditions"
    bl_idname = "FLUIDX_PT_boundary"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        props = context.scene.fluidx
        layout = self.layout

        grid = layout.grid_flow(row_major=True, columns=2, even_columns=True)
        grid.label(text="X−")
        grid.prop(props, "bc_x_neg", text="")
        grid.label(text="X+")
        grid.prop(props, "bc_x_pos", text="")
        grid.label(text="Y−")
        grid.prop(props, "bc_y_neg", text="")
        grid.label(text="Y+")
        grid.prop(props, "bc_y_pos", text="")
        grid.label(text="Z−")
        grid.prop(props, "bc_z_neg", text="")
        grid.label(text="Z+")
        grid.prop(props, "bc_z_pos", text="")


# ---------------------------------------------------------------------------
# I/O and run
# ---------------------------------------------------------------------------

class FLUIDX_PT_io(FLUIDX_PT_base, Panel):
    bl_label = "Generate & Run"
    bl_idname = "FLUIDX_PT_io"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        props = context.scene.fluidx
        layout = self.layout

        layout.label(text="Setup File:")
        layout.prop(props, "setup_output_dir", text="")
        layout.operator("fluidx.generate_setup", icon="FILE_SCRIPT")

        layout.separator()
        layout.label(text="FluidX3D:")
        layout.prop(props, "fluidx3d_path", text="Directory")
        layout.prop(props, "output_dir", text="Output Dir")
        layout.prop(props, "build_before_run")
        layout.prop(props, "run_in_background")
        layout.operator("fluidx.run_simulation", icon="PLAY")


# ---------------------------------------------------------------------------
# Load results
# ---------------------------------------------------------------------------

class FLUIDX_PT_load(FLUIDX_PT_base, Panel):
    bl_label = "Load Results"
    bl_idname = "FLUIDX_PT_load"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        props = context.scene.fluidx
        layout = self.layout

        layout.prop(props, "results_dir", text="Directory")
        layout.prop(props, "load_format", text="Format")
        layout.prop(props, "load_as_sequence")

        col = layout.column()
        col.enabled = props.load_as_sequence
        col.prop(props, "load_start_frame")

        layout.separator()
        layout.operator("fluidx.load_results", icon="IMPORT")
        layout.operator("fluidx.load_single_file", icon="FILE_FOLDER")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_classes = (
    FLUIDX_PT_simulation,
    FLUIDX_PT_physics,
    FLUIDX_PT_boundary,
    FLUIDX_PT_io,
    FLUIDX_PT_load,
)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)

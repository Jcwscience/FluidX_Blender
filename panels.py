"""Blender UI panels for the FluidX_Blender addon.

All panels live in the VIEW_3D sidebar under a "FluidX" tab, plus an
additional object-properties panel in the N-panel.
"""

import bpy
from bpy.types import Panel


class FLUIDX_PT_base:
    """Mixin with shared settings for all FluidX panels."""

    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "FluidX"


# ---------------------------------------------------------------------------
# Object type assignment (shown for every selected object)
# ---------------------------------------------------------------------------

class FLUIDX_PT_object(FLUIDX_PT_base, Panel):
    bl_label = "FluidX Object"
    bl_idname = "FLUIDX_PT_object"
    bl_context = "objectmode"

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def draw(self, context):
        obj = context.active_object
        if obj is None or not hasattr(obj, "fluidx"):
            return
        ofluidx = obj.fluidx
        layout = self.layout

        layout.prop(ofluidx, "object_type", text="Type")

        if ofluidx.object_type == "INFLOW":
            box = layout.box()
            box.label(text="Inflow Settings:", icon="FORCE_WIND")
            box.prop(ofluidx, "inflow_velocity", text="Velocity")
            box.prop(ofluidx, "inflow_density", text="Density")

        # Quick-assign buttons for convenience
        row = layout.row(align=True)
        row.label(text="Quick-set selected:")
        col = layout.column(align=True)
        op = col.operator("fluidx.set_object_type", text="Domain", icon="CUBE")
        op.object_type = "DOMAIN"
        op = col.operator("fluidx.set_object_type", text="Collision", icon="MESH_ICOSPHERE")
        op.object_type = "COLLISION"
        op = col.operator("fluidx.set_object_type", text="Inflow", icon="FORCE_WIND")
        op.object_type = "INFLOW"
        op = col.operator("fluidx.set_object_type", text="Outflow", icon="FORCE_VORTEX")
        op.object_type = "OUTFLOW"
        op = col.operator("fluidx.set_object_type", text="None", icon="X")
        op.object_type = "NONE"


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

        layout.separator()
        col2 = layout.column(align=True)
        col2.label(text="Gravity (volume force):")
        col2.prop(props, "gravity", text="")


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
# Bake
# ---------------------------------------------------------------------------

class FLUIDX_PT_bake(FLUIDX_PT_base, Panel):
    bl_label = "Bake"
    bl_idname = "FLUIDX_PT_bake"

    def draw(self, context):
        props = context.scene.fluidx
        layout = self.layout

        # --- Cache directory ---
        layout.label(text="Cache Directory:")
        layout.prop(props, "cache_dir", text="")

        # --- FluidX3D source (optional override) ---
        box = layout.box()
        box.label(text="FluidX3D (optional override):")
        box.prop(props, "fluidx3d_path", text="Directory")
        box.prop(props, "build_before_run")

        layout.separator()

        if props.is_baking:
            # ---- Progress display ----
            layout.label(text="Simulation running…", icon="TIME")
            layout.prop(props, "bake_progress", text="Progress", slider=True)
            if props.bake_stats:
                box2 = layout.box()
                box2.label(text=props.bake_stats, icon="INFO")
            layout.operator("fluidx.cancel_bake", text="Cancel Bake", icon="CANCEL")
        else:
            # ---- Bake button ----
            layout.operator("fluidx.bake", text="Bake Simulation", icon="RENDER_ANIMATION")
            if props.bake_stats:
                box2 = layout.box()
                box2.label(text=props.bake_stats, icon="INFO")


# ---------------------------------------------------------------------------
# Import results
# ---------------------------------------------------------------------------

class FLUIDX_PT_load(FLUIDX_PT_base, Panel):
    bl_label = "Import Results"
    bl_idname = "FLUIDX_PT_load"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        props = context.scene.fluidx
        layout = self.layout

        layout.prop(props, "results_dir", text="Directory")
        layout.prop(props, "load_format", text="Format")
        layout.prop(props, "load_start_frame")

        layout.separator()

        # Primary: import VDB sequence from the last bake or results dir
        layout.operator(
            "fluidx.import_vdb_sequence",
            text="Import VDB Sequence",
            icon="VOLUME_DATA",
        )

        layout.separator()
        layout.label(text="Convert VTK → VDB:")
        layout.operator("fluidx.convert_to_vdb", icon="FILE_REFRESH")

        layout.separator()
        layout.label(text="Surface mesh import:")
        layout.prop(props, "load_as_sequence")
        layout.operator("fluidx.load_results", icon="IMPORT")
        layout.operator("fluidx.load_single_file", icon="FILE_FOLDER")


# ---------------------------------------------------------------------------
# Advanced / legacy panel
# ---------------------------------------------------------------------------

class FLUIDX_PT_advanced(FLUIDX_PT_base, Panel):
    bl_label = "Advanced / Legacy"
    bl_idname = "FLUIDX_PT_advanced"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        props = context.scene.fluidx
        layout = self.layout

        layout.label(text="Setup File (legacy):")
        layout.prop(props, "setup_output_dir", text="")
        layout.operator("fluidx.generate_setup", icon="FILE_SCRIPT")

        layout.separator()
        layout.label(text="Run (legacy):")
        layout.prop(props, "fluidx3d_path", text="Directory")
        layout.prop(props, "output_dir", text="Output Dir")
        layout.prop(props, "run_in_background")
        layout.operator("fluidx.run_simulation", icon="PLAY")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_classes = (
    FLUIDX_PT_object,
    FLUIDX_PT_simulation,
    FLUIDX_PT_physics,
    FLUIDX_PT_boundary,
    FLUIDX_PT_bake,
    FLUIDX_PT_load,
    FLUIDX_PT_advanced,
)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)

"""Blender operators for the FluidX_Blender addon."""

import os
import subprocess
import logging

import bpy
from bpy.types import Operator
from bpy.props import StringProperty

from . import utils

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _abs_path(blender_path: str) -> str:
    """Resolve a Blender-relative path (//…) to an absolute path."""
    return bpy.path.abspath(blender_path)


# ---------------------------------------------------------------------------
# Generate setup.cpp
# ---------------------------------------------------------------------------

class FLUIDX_OT_generate_setup(Operator):
    """Generate a FluidX3D setup.cpp file from the current settings"""

    bl_idname = "fluidx.generate_setup"
    bl_label = "Generate Setup File"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.fluidx
        out_dir = _abs_path(props.setup_output_dir) if props.setup_output_dir else _abs_path("//fluidx_setup")

        try:
            path = utils.write_setup_file(props, out_dir)
        except Exception as exc:
            self.report({"ERROR"}, f"Failed to write setup file: {exc}")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Setup file written to: {path}")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Run simulation
# ---------------------------------------------------------------------------

class FLUIDX_OT_run_simulation(Operator):
    """Run the FluidX3D simulation using the configured executable"""

    bl_idname = "fluidx.run_simulation"
    bl_label = "Run Simulation"
    bl_options = {"REGISTER"}

    def execute(self, context):
        props = context.scene.fluidx
        fluidx_dir = _abs_path(props.fluidx3d_path) if props.fluidx3d_path else ""

        if not fluidx_dir or not os.path.isdir(fluidx_dir):
            self.report(
                {"ERROR"},
                "FluidX3D directory is not set or does not exist. "
                "Please set it in the FluidX panel → I/O settings.",
            )
            return {"CANCELLED"}

        # Optionally build first
        if props.build_before_run:
            self.report({"INFO"}, "Building FluidX3D …")
            try:
                result = subprocess.run(
                    ["make"],
                    cwd=fluidx_dir,
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=600,
                )
                log.info("make stdout: %s", result.stdout)
            except subprocess.CalledProcessError as exc:
                self.report({"ERROR"}, f"Build failed: {exc.stderr}")
                return {"CANCELLED"}
            except FileNotFoundError:
                self.report({"ERROR"}, "`make` not found. Please install build tools.")
                return {"CANCELLED"}

        # Locate executable
        exe_candidates = [
            os.path.join(fluidx_dir, "FluidX3D"),
            os.path.join(fluidx_dir, "bin", "FluidX3D"),
            os.path.join(fluidx_dir, "FluidX3D.exe"),
        ]
        exe = next((p for p in exe_candidates if os.path.isfile(p)), None)
        if exe is None:
            self.report(
                {"ERROR"},
                "FluidX3D executable not found in the specified directory. "
                "Build it first or enable 'Build Before Run'.",
            )
            return {"CANCELLED"}

        out_dir = _abs_path(props.output_dir) if props.output_dir else _abs_path("//fluidx_output")
        os.makedirs(out_dir, exist_ok=True)

        cmd = [exe]
        env = {**os.environ, "FLUIDX_OUTPUT_DIR": out_dir}

        try:
            if props.run_in_background:
                subprocess.Popen(cmd, cwd=fluidx_dir, env=env)
                self.report(
                    {"INFO"},
                    f"FluidX3D simulation launched in background. "
                    f"Output will be written to: {out_dir}",
                )
            else:
                result = subprocess.run(
                    cmd, cwd=fluidx_dir, env=env,
                    check=True, capture_output=True, text=True,
                )
                log.info("FluidX3D stdout: %s", result.stdout)
                self.report({"INFO"}, f"Simulation finished. Output: {out_dir}")
        except subprocess.CalledProcessError as exc:
            self.report({"ERROR"}, f"Simulation failed: {exc.stderr}")
            return {"CANCELLED"}
        except FileNotFoundError:
            self.report({"ERROR"}, f"Could not launch executable: {exe}")
            return {"CANCELLED"}

        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Load simulation results
# ---------------------------------------------------------------------------

class FLUIDX_OT_load_results(Operator):
    """Import FluidX3D simulation output files into the current scene"""

    bl_idname = "fluidx.load_results"
    bl_label = "Load Simulation Results"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.fluidx
        results_dir = _abs_path(props.results_dir) if props.results_dir else ""

        if not results_dir or not os.path.isdir(results_dir):
            self.report(
                {"ERROR"},
                "Results directory is not set or does not exist. "
                "Please set it in the FluidX panel → Load Results.",
            )
            return {"CANCELLED"}

        file_format = props.load_format
        start_frame = props.load_start_frame

        if props.load_as_sequence:
            objects = utils.load_frame_sequence(
                context, results_dir, file_format, start_frame
            )
            if not objects:
                self.report(
                    {"WARNING"},
                    f"No {file_format} files found in: {results_dir}",
                )
                return {"CANCELLED"}
            self.report(
                {"INFO"},
                f"Loaded {len(objects)} frame(s) from: {results_dir}",
            )
        else:
            # Load only the first matching file
            ext_map = {"VTK": ".vtk", "OBJ": ".obj", "PLY": ".ply"}
            ext = ext_map.get(file_format, ".vtk")
            files = utils.collect_sequence_files(results_dir, ext)
            if not files:
                self.report(
                    {"WARNING"},
                    f"No {file_format} files found in: {results_dir}",
                )
                return {"CANCELLED"}

            fp = files[0]
            if file_format == "OBJ":
                obj = utils.load_obj_as_mesh(context, fp)
            elif file_format == "PLY":
                obj = utils.load_ply_as_mesh(context, fp)
            else:
                obj = utils.load_vtk_as_mesh(context, fp)

            if obj is None:
                self.report({"ERROR"}, f"Failed to load: {fp}")
                return {"CANCELLED"}

            self.report({"INFO"}, f"Loaded: {fp}")

        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Load single file (file browser operator)
# ---------------------------------------------------------------------------

class FLUIDX_OT_load_single_file(Operator):
    """Import a single FluidX3D output file chosen via the file browser"""

    bl_idname = "fluidx.load_single_file"
    bl_label = "Load Single File"
    bl_options = {"REGISTER", "UNDO"}

    filepath: StringProperty(subtype="FILE_PATH")
    filter_glob: StringProperty(
        default="*.vtk;*.obj;*.ply",
        options={"HIDDEN"},
    )

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        fp = self.filepath
        ext = os.path.splitext(fp)[1].lower()

        if ext == ".obj":
            obj = utils.load_obj_as_mesh(context, fp)
        elif ext == ".ply":
            obj = utils.load_ply_as_mesh(context, fp)
        elif ext == ".vtk":
            obj = utils.load_vtk_as_mesh(context, fp)
        else:
            self.report({"ERROR"}, f"Unsupported file format: {ext}")
            return {"CANCELLED"}

        if obj is None:
            self.report({"ERROR"}, f"Failed to load: {fp}")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Loaded: {fp}")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_classes = (
    FLUIDX_OT_generate_setup,
    FLUIDX_OT_run_simulation,
    FLUIDX_OT_load_results,
    FLUIDX_OT_load_single_file,
)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)

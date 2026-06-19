"""Blender operators for the FluidX_Blender addon."""

import os
import sys
import subprocess
import logging

import bpy
from bpy.types import Operator
from bpy.props import EnumProperty, StringProperty

from . import utils

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level bake state (persists across operator calls within a session)
# ---------------------------------------------------------------------------

_bake_state: dict = {
    "process":      None,   # subprocess.Popen or None
    "log_path":     None,   # path to the stdout log file
    "vtk_dir":      None,   # directory being written by FluidX3D
    "vdb_dir":      None,   # target VDB directory (filled after conversion)
    "total_steps":  0,
    "output_every": 100,
}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _abs_path(blender_path: str) -> str:
    """Resolve a Blender-relative path (//…) to an absolute path."""
    return bpy.path.abspath(blender_path)


def _addon_fluidx3d_dir() -> str:
    """Return the absolute path of the bundled FluidX3D submodule."""
    return os.path.join(os.path.dirname(__file__), "FluidX3D")


def _resolve_fluidx3d_dir(props) -> str:
    """Return the FluidX3D directory: user-supplied or bundled submodule."""
    user_path = _abs_path(props.fluidx3d_path) if props.fluidx3d_path else ""
    if user_path and os.path.isdir(user_path):
        return user_path
    return _addon_fluidx3d_dir()


# ---------------------------------------------------------------------------
# Background-process polling timer (registered with bpy.app.timers)
# ---------------------------------------------------------------------------

def _poll_bake_process() -> float | None:
    """Periodic timer callback that checks the running FluidX3D process.

    Returns the next poll interval in seconds, or None to unregister.
    """
    proc = _bake_state.get("process")
    if proc is None:
        return None  # nothing to poll

    ret_code = proc.poll()

    # Count VTK output files to estimate progress
    vtk_dir = _bake_state.get("vtk_dir", "")
    vtk_count = 0
    if vtk_dir and os.path.isdir(vtk_dir):
        vtk_count = sum(
            1 for f in os.listdir(vtk_dir)
            if f.lower().startswith("rho") and f.lower().endswith(".vtk")
        )

    total_steps = _bake_state.get("total_steps", 1)
    output_every = _bake_state.get("output_every", 100)
    expected = max(1, total_steps // output_every)
    progress = min(1.0, vtk_count / expected)

    # Read last non-empty line from the simulation log for stats
    stats = ""
    log_path = _bake_state.get("log_path", "")
    if log_path and os.path.isfile(log_path):
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                lines = [ln.rstrip() for ln in f if ln.strip()]
            if lines:
                stats = lines[-1]
        except OSError:
            pass

    # Push updates into every open scene
    for scene in bpy.data.scenes:
        fx = getattr(scene, "fluidx", None)
        if fx is not None:
            fx.bake_progress = progress
            fx.bake_stats = stats

    if ret_code is not None:
        # Process has ended — flush and close the log file now
        _bake_state["process"] = None
        log_file_handle = _bake_state.pop("log_file", None)
        if log_file_handle is not None:
            try:
                log_file_handle.close()
            except OSError:
                pass

        vdb_dir = _bake_state.get("vdb_dir") or ""
        if ret_code == 0 and vtk_dir:
            # Auto-convert VTK density volumes → OpenVDB
            if not vdb_dir:
                vdb_dir = os.path.join(vtk_dir, "vdb")
                _bake_state["vdb_dir"] = vdb_dir
            try:
                converted = utils.convert_vtk_cache_to_vdb(vtk_dir, vdb_dir)
                n_vdb = len(converted)
                final_msg = (
                    f"Bake complete – {vtk_count} VTK frames, "
                    f"{n_vdb} VDB files written to: {vdb_dir}"
                )
            except Exception as exc:
                final_msg = (
                    f"Simulation done (exit 0) but VDB conversion failed: {exc}. "
                    f"VTK files are in: {vtk_dir}"
                )
        elif ret_code != 0:
            final_msg = f"Simulation failed (exit code {ret_code}). Check log: {log_path}"
        else:
            final_msg = "Bake complete."

        for scene in bpy.data.scenes:
            fx = getattr(scene, "fluidx", None)
            if fx is not None:
                fx.is_baking = False
                fx.bake_progress = 1.0 if ret_code == 0 else fx.bake_progress
                fx.bake_stats = final_msg

        _redraw_all()
        return None  # Unregister timer

    _redraw_all()
    return 2.0  # Poll again in 2 seconds


def _redraw_all() -> None:
    """Request a redraw of all 3-D-viewport areas."""
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Object-type assignment operator
# ---------------------------------------------------------------------------

class FLUIDX_OT_set_object_type(Operator):
    """Set the FluidX3D simulation role of the selected objects"""

    bl_idname = "fluidx.set_object_type"
    bl_label = "Set FluidX Object Type"
    bl_options = {"REGISTER", "UNDO"}

    object_type: EnumProperty(
        name="Type",
        items=[
            ("NONE",      "None",      ""),
            ("DOMAIN",    "Domain",    ""),
            ("COLLISION", "Collision", ""),
            ("INFLOW",    "Inflow",    ""),
            ("OUTFLOW",   "Outflow",   ""),
        ],
        default="NONE",
    )

    def execute(self, context):
        count = 0
        for obj in context.selected_objects:
            if hasattr(obj, "fluidx"):
                obj.fluidx.object_type = self.object_type
                count += 1
        self.report({"INFO"}, f"Set {count} object(s) to type '{self.object_type}'")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Bake operator
# ---------------------------------------------------------------------------

class FLUIDX_OT_bake(Operator):
    """Export scene meshes, generate setup.cpp, build FluidX3D (optional),
    and launch the simulation as a background process"""

    bl_idname = "fluidx.bake"
    bl_label = "Bake Simulation"
    bl_options = {"REGISTER"}

    def execute(self, context):
        props = context.scene.fluidx

        if props.is_baking:
            self.report({"WARNING"}, "A bake is already running. Cancel it first.")
            return {"CANCELLED"}

        # --- Resolve paths --------------------------------------------------
        cache_dir = _abs_path(props.cache_dir) if props.cache_dir else _abs_path("//fluidx_cache")
        stl_dir   = os.path.join(cache_dir, "stl")
        vtk_dir   = os.path.join(cache_dir, "vtk")
        vdb_dir   = os.path.join(cache_dir, "vdb")
        log_path  = os.path.join(cache_dir, "fluidx3d.log")

        os.makedirs(stl_dir, exist_ok=True)
        os.makedirs(vtk_dir, exist_ok=True)

        fluidx_dir = _resolve_fluidx3d_dir(props)
        if not os.path.isdir(fluidx_dir):
            self.report(
                {"ERROR"},
                f"FluidX3D directory not found: {fluidx_dir}\n"
                "Either initialise the bundled submodule (`git submodule update --init`) "
                "or set a custom path in the panel.",
            )
            return {"CANCELLED"}

        fluidx_src = os.path.join(fluidx_dir, "src")

        # --- Validate domain object -----------------------------------------
        domain_obj = utils.get_domain_object(context.scene)
        if domain_obj is None:
            self.report(
                {"WARNING"},
                "No object is tagged as 'Domain'.  Proceeding without scene-object "
                "mapping (resolution from panel settings only).",
            )

        # --- Export collision objects as binary STL -------------------------
        for obj in utils.get_objects_by_type(context.scene, "COLLISION"):
            stl_path = os.path.join(stl_dir, f"collision_{utils._safe_name(obj.name)}.stl")
            ok = utils.export_object_as_stl(obj, stl_path)
            if not ok:
                self.report({"WARNING"}, f"STL export failed for '{obj.name}', skipping.")

        # --- Generate and write setup.cpp -----------------------------------
        try:
            setup_path = utils.write_bake_setup_file(
                props, context.scene, fluidx_src, vtk_dir, stl_dir
            )
            self.report({"INFO"}, f"setup.cpp written to: {setup_path}")
        except Exception as exc:
            self.report({"ERROR"}, f"Failed to generate setup.cpp: {exc}")
            return {"CANCELLED"}

        # --- Patch defines.hpp to enable required FluidX3D features ---------
        gravity = props.gravity
        gravity_on = any(abs(v) > 1e-9 for v in gravity)
        try:
            utils.patch_defines_hpp(fluidx_src, gravity_enabled=gravity_on)
        except Exception as exc:
            self.report({"ERROR"}, f"Failed to patch defines.hpp: {exc}")
            return {"CANCELLED"}

        # --- Build FluidX3D (optional) --------------------------------------
        if props.build_before_run:
            self.report({"INFO"}, "Building FluidX3D …")
            make_target = _make_target()
            try:
                result = subprocess.run(
                    ["make", make_target],
                    cwd=fluidx_dir,
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=600,
                )
                log.info("make stdout:\n%s", result.stdout)
            except subprocess.CalledProcessError as exc:
                self.report({"ERROR"}, f"Build failed:\n{exc.stderr[-2000:]}")
                return {"CANCELLED"}
            except FileNotFoundError:
                self.report({"ERROR"}, "`make` not found. Install build tools.")
                return {"CANCELLED"}
            except subprocess.TimeoutExpired:
                self.report({"ERROR"}, "Build timed out after 10 minutes.")
                return {"CANCELLED"}

        # --- Locate executable ----------------------------------------------
        exe_candidates = [
            os.path.join(fluidx_dir, "bin", "FluidX3D"),
            os.path.join(fluidx_dir, "FluidX3D"),
            os.path.join(fluidx_dir, "FluidX3D.exe"),
            os.path.join(fluidx_dir, "bin", "FluidX3D.exe"),
        ]
        exe = next((p for p in exe_candidates if os.path.isfile(p)), None)
        if exe is None:
            self.report(
                {"ERROR"},
                "FluidX3D executable not found.  "
                "Enable 'Build Before Run' or build manually first.",
            )
            return {"CANCELLED"}

        # --- Launch simulation ----------------------------------------------
        log_file = open(log_path, "w", encoding="utf-8")  # noqa: WPS515
        try:
            proc = subprocess.Popen(
                [exe],
                cwd=vtk_dir,          # FluidX3D writes output relative to cwd
                stdout=log_file,
                stderr=subprocess.STDOUT,
            )
        except OSError as exc:
            log_file.close()
            self.report({"ERROR"}, f"Failed to launch {exe}: {exc}")
            return {"CANCELLED"}

        # --- Store state and start polling timer ---------------------------
        # log_file is kept open intentionally so the subprocess can write to it;
        # it is closed by _poll_bake_process() when the process exits or by
        # FLUIDX_OT_cancel_bake if the user cancels early.
        _bake_state["log_file"]     = log_file
        _bake_state["process"]      = proc
        _bake_state["log_path"]     = log_path
        _bake_state["vtk_dir"]      = vtk_dir
        _bake_state["vdb_dir"]      = vdb_dir
        _bake_state["total_steps"]  = props.time_steps
        _bake_state["output_every"] = props.output_every

        props.is_baking     = True
        props.bake_progress = 0.0
        props.bake_stats    = "Simulation started …"

        if not bpy.app.timers.is_registered(_poll_bake_process):
            bpy.app.timers.register(_poll_bake_process, first_interval=2.0)

        self.report(
            {"INFO"},
            f"FluidX3D launched (PID {proc.pid}).  "
            f"VTK output → {vtk_dir}  |  log → {log_path}",
        )
        return {"FINISHED"}


def _make_target() -> str:
    """Return the make target appropriate for the current OS."""
    if sys.platform == "darwin":
        return "macOS"
    if sys.platform.startswith("linux"):
        return "Linux"
    # Windows uses MSVC / Visual Studio; fall back to attempting 'Linux'
    return "Linux"


# ---------------------------------------------------------------------------
# Cancel bake
# ---------------------------------------------------------------------------

class FLUIDX_OT_cancel_bake(Operator):
    """Terminate the running FluidX3D background simulation"""

    bl_idname = "fluidx.cancel_bake"
    bl_label = "Cancel Bake"
    bl_options = {"REGISTER"}

    def execute(self, context):
        proc = _bake_state.get("process")
        if proc is None or proc.poll() is not None:
            self.report({"INFO"}, "No simulation is currently running.")
            return {"CANCELLED"}

        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

        _bake_state["process"] = None
        log_file_handle = _bake_state.pop("log_file", None)
        if log_file_handle is not None:
            try:
                log_file_handle.close()
            except OSError:
                pass
        props = context.scene.fluidx
        props.is_baking    = False
        props.bake_stats   = "Bake cancelled by user."

        self.report({"INFO"}, "Simulation cancelled.")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Manual VTK → VDB conversion
# ---------------------------------------------------------------------------

class FLUIDX_OT_convert_to_vdb(Operator):
    """Convert all rho VTK files in a directory to OpenVDB format"""

    bl_idname = "fluidx.convert_to_vdb"
    bl_label = "Convert VTK → VDB"
    bl_options = {"REGISTER"}

    def execute(self, context):
        props = context.scene.fluidx
        results_dir = _abs_path(props.results_dir) if props.results_dir else ""

        if not results_dir or not os.path.isdir(results_dir):
            self.report({"ERROR"}, "Results directory is not set or does not exist.")
            return {"CANCELLED"}

        vdb_dir = os.path.join(results_dir, "vdb")
        try:
            converted = utils.convert_vtk_cache_to_vdb(results_dir, vdb_dir)
        except Exception as exc:
            self.report({"ERROR"}, f"Conversion failed: {exc}")
            return {"CANCELLED"}

        if not converted:
            self.report({"WARNING"}, f"No rho*.vtk files found in: {results_dir}")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Converted {len(converted)} file(s) to: {vdb_dir}")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Import OpenVDB sequence
# ---------------------------------------------------------------------------

class FLUIDX_OT_import_vdb_sequence(Operator):
    """Import the OpenVDB volume sequence from the bake cache or results directory"""

    bl_idname = "fluidx.import_vdb_sequence"
    bl_label = "Import VDB Sequence"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.fluidx

        # Prefer the bake vdb_dir, fall back to results_dir/vdb or results_dir
        vdb_dir = _bake_state.get("vdb_dir") or ""
        if not vdb_dir or not os.path.isdir(vdb_dir):
            base = _abs_path(props.results_dir) if props.results_dir else \
                   _abs_path(props.cache_dir)
            vdb_dir = os.path.join(base, "vdb")
        if not os.path.isdir(vdb_dir):
            vdb_dir = _abs_path(props.results_dir) if props.results_dir else ""

        if not vdb_dir or not os.path.isdir(vdb_dir):
            self.report(
                {"ERROR"},
                "VDB directory not found.  Run a bake first, or set 'Results Directory'.",
            )
            return {"CANCELLED"}

        vol_obj = utils.load_vdb_sequence(context, vdb_dir, props.load_start_frame)
        if vol_obj is None:
            self.report({"WARNING"}, f"No .vdb files found in: {vdb_dir}")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Imported VDB volume sequence from: {vdb_dir}")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# (Legacy) Generate setup.cpp
# ---------------------------------------------------------------------------

class FLUIDX_OT_generate_setup(Operator):
    """Generate a FluidX3D setup.cpp file from the current settings (legacy)"""

    bl_idname = "fluidx.generate_setup"
    bl_label = "Generate Setup File"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.fluidx
        out_dir = _abs_path(props.setup_output_dir) if props.setup_output_dir \
            else _abs_path("//fluidx_setup")

        try:
            path = utils.write_setup_file(props, out_dir)
        except Exception as exc:
            self.report({"ERROR"}, f"Failed to write setup file: {exc}")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Setup file written to: {path}")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# (Legacy) Run simulation
# ---------------------------------------------------------------------------

class FLUIDX_OT_run_simulation(Operator):
    """Run the FluidX3D simulation using the configured executable (legacy)"""

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

        if props.build_before_run:
            self.report({"INFO"}, "Building FluidX3D …")
            try:
                result = subprocess.run(
                    ["make", _make_target()],
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

        exe_candidates = [
            os.path.join(fluidx_dir, "bin", "FluidX3D"),
            os.path.join(fluidx_dir, "FluidX3D"),
            os.path.join(fluidx_dir, "FluidX3D.exe"),
        ]
        exe = next((p for p in exe_candidates if os.path.isfile(p)), None)
        if exe is None:
            self.report(
                {"ERROR"},
                "FluidX3D executable not found. Build it first or enable 'Build Before Run'.",
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
                    f"FluidX3D launched in background. Output: {out_dir}",
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
# (Legacy) Load simulation results
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
                "Results directory is not set or does not exist.",
            )
            return {"CANCELLED"}

        file_format = props.load_format
        start_frame = props.load_start_frame

        # VDB handled separately
        if file_format == "VDB":
            vol_obj = utils.load_vdb_sequence(context, results_dir, start_frame)
            if vol_obj is None:
                self.report({"WARNING"}, f"No .vdb files found in: {results_dir}")
                return {"CANCELLED"}
            self.report({"INFO"}, f"Imported VDB sequence from: {results_dir}")
            return {"FINISHED"}

        if props.load_as_sequence:
            objects = utils.load_frame_sequence(
                context, results_dir, file_format, start_frame
            )
            if not objects:
                self.report(
                    {"WARNING"}, f"No {file_format} files found in: {results_dir}",
                )
                return {"CANCELLED"}
            self.report({"INFO"}, f"Loaded {len(objects)} frame(s) from: {results_dir}")
        else:
            ext_map = {"VTK": ".vtk", "OBJ": ".obj", "PLY": ".ply"}
            ext = ext_map.get(file_format, ".vtk")
            files = utils.collect_sequence_files(results_dir, ext)
            if not files:
                self.report({"WARNING"}, f"No {file_format} files found in: {results_dir}")
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
# (Legacy) Load single file via file browser
# ---------------------------------------------------------------------------

class FLUIDX_OT_load_single_file(Operator):
    """Import a single FluidX3D output file chosen via the file browser"""

    bl_idname = "fluidx.load_single_file"
    bl_label = "Load Single File"
    bl_options = {"REGISTER", "UNDO"}

    filepath: StringProperty(subtype="FILE_PATH")
    filter_glob: StringProperty(
        default="*.vtk;*.obj;*.ply;*.vdb",
        options={"HIDDEN"},
    )

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        fp = self.filepath
        ext = os.path.splitext(fp)[1].lower()

        if ext == ".vdb":
            vol_obj = utils.load_vdb_sequence(context, os.path.dirname(fp))
            if vol_obj is None:
                self.report({"ERROR"}, f"Failed to import VDB: {fp}")
                return {"CANCELLED"}
        elif ext == ".obj":
            obj = utils.load_obj_as_mesh(context, fp)
            if obj is None:
                self.report({"ERROR"}, f"Failed to load: {fp}")
                return {"CANCELLED"}
        elif ext == ".ply":
            obj = utils.load_ply_as_mesh(context, fp)
            if obj is None:
                self.report({"ERROR"}, f"Failed to load: {fp}")
                return {"CANCELLED"}
        elif ext == ".vtk":
            obj = utils.load_vtk_as_mesh(context, fp)
            if obj is None:
                self.report({"ERROR"}, f"Failed to load: {fp}")
                return {"CANCELLED"}
        else:
            self.report({"ERROR"}, f"Unsupported file format: {ext}")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Loaded: {fp}")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_classes = (
    FLUIDX_OT_set_object_type,
    FLUIDX_OT_bake,
    FLUIDX_OT_cancel_bake,
    FLUIDX_OT_convert_to_vdb,
    FLUIDX_OT_import_vdb_sequence,
    FLUIDX_OT_generate_setup,
    FLUIDX_OT_run_simulation,
    FLUIDX_OT_load_results,
    FLUIDX_OT_load_single_file,
)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister():
    # Stop any running bake timer before unregistering
    if bpy.app.timers.is_registered(_poll_bake_process):
        bpy.app.timers.unregister(_poll_bake_process)

    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)


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
                    # 10-minute timeout; large GPU projects may need more time
                    # depending on hardware.  Increase if your build routinely
                    # exceeds this limit.
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

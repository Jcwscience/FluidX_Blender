# FluidX_Blender

A Blender add-on that bridges [FluidX3D](https://github.com/ProjectPhysX/FluidX3D) — an ultra-fast GPU-accelerated
lattice Boltzmann fluid simulator — with Blender's 3-D viewport.

FluidX3D is included as a **git submodule** at `FluidX3D/`.  Initialise it after cloning:

```bash
git submodule update --init --recursive
```

## Features

| Feature | Details |
|---|---|
| **Object tagging** | Mark any Blender object as Domain, Collision, Inflow, or Outflow |
| **Bake workflow** | One-click bake: exports meshes, generates C++ setup, (optionally) compiles FluidX3D, and launches the simulation in the background |
| **Live progress** | Bake progress bar and live stats line in the sidebar; cancel button to terminate mid-bake |
| **VTK → OpenVDB** | Density fields written by FluidX3D are auto-converted to `.vdb` files after the bake |
| **VDB import** | Import the resulting OpenVDB volume sequence into Blender for animated volume rendering |
| **Legacy support** | Manual setup.cpp generator and standalone simulation runner are still available |

## Requirements

* Blender **4.2** or newer (with OpenVDB support for volume rendering)
* A C++ build environment with `make` and an OpenCL SDK on the build machine
  (only required when using the **Build Before Run** option)
* FluidX3D submodule initialised (`git submodule update --init`)

## Installation

1. Clone this repository **with submodules**:
   ```bash
   git clone --recurse-submodules https://github.com/Jcwscience/FluidX_Blender.git
   ```
   Or, if you already cloned without submodules:
   ```bash
   git submodule update --init --recursive
   ```
2. Zip the `FluidX_Blender` directory into `FluidX_Blender.zip`.
3. In Blender 4.2+, open **Edit → Preferences → Get Extensions** (top-right drop-down **▾**) → **Install from Disk …**
4. Select the `FluidX_Blender.zip` file and click **Install Extension**.
5. The add-on activates automatically and the **FluidX** tab appears in the 3-D Viewport sidebar (`N` key).

> **Blender 4.0 / 4.1 (legacy):** Zip the `FluidX_Blender` directory, then use **Edit → Preferences → Add-ons → Install …**, select the zip, and enable the add-on by ticking the checkbox next to **Simulation: FluidX_Blender**.

## Quick-Start Bake Workflow

Open the **FluidX** tab in the **3-D Viewport sidebar** (`N` key).

### 1 · Tag your objects

Select each object in your scene and use the **FluidX Object** panel to assign its role:

| Type | Description |
|---|---|
| **Domain** | The bounding box of the simulation (typically a cube) |
| **Collision** | Solid obstacles — exported as binary STL and voxelised by FluidX3D |
| **Inflow** | A region where fluid enters; set velocity and density in the panel |
| **Outflow** | A region where fluid leaves (equilibrium boundary) |

### 2 · Configure the simulation

| Panel | Settings |
|---|---|
| **Simulation Domain** | Grid resolution (X/Y/Z), total time steps, output frequency |
| **Physics** | Kinematic viscosity, initial density, gravity vector |
| **Boundary Conditions** | Per-face boundary type for domain faces |

### 3 · Set a cache directory and bake

1. In the **Bake** panel, set the **Cache Directory** (e.g. `//fluidx_cache`).
2. Optionally point **FluidX3D Directory** to a custom FluidX3D build; leave blank to use the bundled submodule.
3. Enable **Build Before Run** if the FluidX3D executable does not yet exist.
4. Click **Bake Simulation**.

The bake will:
1. Export each Collision object as a binary STL.
2. Write `FluidX3D/src/setup.cpp` with the full simulation setup.
3. Patch `FluidX3D/src/defines.hpp` to enable `EQUILIBRIUM_BOUNDARIES` and (if gravity ≠ 0) `VOLUME_FORCE`.
4. Optionally build the FluidX3D executable.
5. Launch FluidX3D in the background — Blender stays responsive.
6. Poll every 2 seconds: update the progress bar and status message.
7. When the simulation finishes, auto-convert the density VTK files to OpenVDB.

### 4 · Import the volume sequence

When the bake completes the status line shows the VDB directory.  Click
**Import VDB Sequence** in the **Import Results** panel.  A Volume object
appears in your scene and can be rendered with Cycles / EEVEE.

## File Structure

```
FluidX_Blender/
├── FluidX3D/             – FluidX3D source code (git submodule)
├── __init__.py           – Add-on registration and bl_info
├── properties.py         – Scene- and object-level RNA properties
├── operators.py          – Blender operators (bake, cancel, convert, import …)
├── panels.py             – Sidebar UI panels
└── utils.py              – VTK/OBJ/PLY loaders, STL export, VDB conversion,
                            setup.cpp + defines.hpp generators
```

## Generated setup.cpp

The bake pipeline writes a `setup.cpp` directly into `FluidX3D/src/`.
Key features of the generated file:

* Uses `EQUILIBRIUM_BOUNDARIES` for inflow/outflow regions (requires define).
* Calls `lbm.voxelize_stl(...)` for each Collision object.
* Exports density (`rho`) and velocity (`u`) as binary VTK files every N steps.
* Accepts a `VOLUME_FORCE` build-time flag for gravity.

## VTK → OpenVDB Conversion

`utils.convert_vtk_cache_to_vdb()` reads the binary `rho_*.vtk` files
(STRUCTURED_POINTS format written by FluidX3D) and converts them to
`.vdb` fog-volume files using Blender's bundled `pyopenvdb`.

You can also trigger this step manually via the **Convert VTK → VDB** button
in the **Import Results** panel.

## Supported Output Formats

| Format | Description |
|---|---|
| `.vdb` | OpenVDB fog volume (density field) — recommended for rendering |
| `.vtk` | Binary VTK STRUCTURED_POINTS (density/velocity from FluidX3D) |
| `.obj` | Wavefront OBJ surface mesh |
| `.ply` | Stanford PLY surface mesh |

## License

MIT – see repository for details.


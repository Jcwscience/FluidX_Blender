# FluidX_Blender

A Blender add-on that bridges [FluidX3D](https://github.com/ProjectPhysX/FluidX3D) — an ultra-fast GPU-accelerated
lattice Boltzmann fluid simulator — with Blender's 3-D viewport.

## Features

| Feature | Details |
|---|---|
| **Setup generation** | Fill in simulation parameters in the sidebar and export a ready-to-compile `setup.cpp` |
| **Simulation runner** | Launch FluidX3D from inside Blender (blocking or background process) |
| **Result importer** | Import VTK, OBJ, and PLY output files as Blender mesh objects |
| **Frame sequence** | Load an entire output directory as a keyframe-animated sequence |

## Requirements

* Blender **4.0** or newer
* [FluidX3D](https://github.com/ProjectPhysX/FluidX3D) compiled and available on your system
  (only required for the *Run Simulation* feature; file import works without it)

## Installation

1. Download or clone this repository.
2. In Blender, open **Edit → Preferences → Add-ons → Install …**
3. Navigate to the cloned folder, select the `FluidX_Blender` directory (or a `.zip` of it), and click **Install Add-on**.
4. Enable the add-on by ticking the checkbox next to **Simulation: FluidX_Blender**.

## Quick Start

Open the **FluidX** tab in the **3-D Viewport sidebar** (`N` key).

### 1 · Configure the simulation

| Panel | Settings |
|---|---|
| **Simulation Domain** | Grid resolution (X/Y/Z), total time steps, output frequency |
| **Physics** | Kinematic viscosity, initial density |
| **Boundary Conditions** | Per-face boundary type (Periodic / Wall / Free-slip / Velocity) |

### 2 · Generate a setup file

1. In the **Generate & Run** panel, set *Setup File Directory* (e.g. the `src/` folder of your FluidX3D clone).
2. Click **Generate Setup File**.  
   A `setup.cpp` is written that you can compile directly into FluidX3D.

### 3 · (Optional) Run the simulation from Blender

1. Set *FluidX3D Directory* to the root of your FluidX3D clone.
2. Set *Output Dir* to where the simulation should write its output files.
3. Enable *Build Before Run* if you want Blender to invoke `make` first.
4. Click **Run Simulation**.

### 4 · Import results

1. In the **Load Results** panel, point *Directory* to the folder containing `.vtk`, `.obj`, or `.ply` files.
2. Choose the *Format* that matches your output.
3. Enable *Load as Frame Sequence* to animate every file as a separate frame.
4. Click **Load Simulation Results** (or **Load Single File** for one-off imports).

## File Structure

```
FluidX_Blender/
├── __init__.py       – Add-on registration and bl_info
├── properties.py     – All simulation/IO properties (RNA)
├── operators.py      – Blender operators (generate, run, load)
├── panels.py         – Sidebar UI panels
└── utils.py          – VTK/OBJ/PLY loaders and setup-code generator
```

## Generated setup.cpp

The generator produces a C++ file compatible with the FluidX3D `main_setup()` API.
Place it at `<FluidX3D>/src/setup.cpp` and recompile.

Supported boundary flags: `TYPE_P` (periodic), `TYPE_W` (no-slip wall),
`TYPE_S` (free-slip), `TYPE_V` (velocity).

## Supported Output Formats

| Format | Description |
|---|---|
| `.vtk` | Legacy VTK POLYDATA or UNSTRUCTURED_GRID (ASCII) |
| `.obj` | Wavefront OBJ surface mesh |
| `.ply` | Stanford PLY surface mesh |

## License

MIT – see repository for details.

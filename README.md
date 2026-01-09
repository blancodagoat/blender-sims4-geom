# Blender Sims 4 GEOM Tools

A Blender add-on for importing and exporting Sims 4 SimGeom (.simgeom) mesh files.

> **📥 [Download Latest Release](https://github.com/blancodagoat/blender-sims4-geom/releases/latest)** - Click to download the addon zip file

This is a fork of [SmugTomato's Blender Sims 3 GEOM Tools](https://github.com/SmugTomato/blender-sims3-geom), updated to support **The Sims 4** GEOM format.

## Features

### Import
- **Import directly from .package files** - No need for S4PE or other extraction tools!
- **Import Sims 4 SimGeom files** (.simgeom)
- **Auto-create materials** - Automatically extracts and applies textures from packages
- **Import highest LOD only** - Option to skip lower quality LOD meshes
- **Custom normals support** - Preserves original mesh normals
- **Multiple UV channels** - Supports meshes with multiple UV maps
- **Vertex colors** - Imports vertex color data (TagValue)
- **Bone weights** - Full vertex group and weight support
- **Morph support** - Import morph GEOMs

### Export
- **Export Sims 4 SimGeom files** (.simgeom)
- **Export RLE textures to DDS** - Batch extract all textures from a package file
- **Morph export** - Export morphs linked to base meshes

### Compatibility
- **Blender 4.0+ / 5.0 compatible**
- **No external dependencies** - Pure Python, no pip installs required

## Supported Sims 4 GEOM Versions

- GEOM Version 12, 13, 14, 15 (RCOL wrapper v3)
- UVStitch, SeamStitch, and SlotrayIntersection data sections

## Installation

> ⚠️ **Do NOT clone this repo** - Download the release zip instead!

1. **[Download the latest release](https://github.com/blancodagoat/blender-sims4-geom/releases/latest)** (`sims4-geom-tools-vX.X.X.zip`)
2. In Blender, go to **Edit > Preferences > Add-ons**
3. Click **Install** and select the downloaded zip file
4. Enable the add-on by checking the box next to "**Import-Export: Sims 4 GEOM Tools**"
5. Press **N** in the 3D View to open the sidebar - look for the **Sims 4** tab

## Usage

### Importing from a Package File (Recommended)

The easiest way to get meshes - import directly from .package files:

1. **File > Import > Sims 4 Package (.package)**
2. Select your .package file (CC mod, extracted game files, etc.)
3. Configure import options:
   - **Choose Rig** - Select a rig to import alongside the meshes
   - **Preserve Normals** - Import original normals as custom split normals
   - **Import All LODs** - Check to import all LOD versions, uncheck for highest quality only
   - **Import Materials** - Auto-create materials from textures in the package
4. Click **Import**

This supports both compressed and uncompressed package files - no external tools needed!

### Importing a Standalone GEOM

If you have an extracted .simgeom file:

1. **File > Import > Sims 4 GEOM (.simgeom)**
2. Select your .simgeom file
3. Optionally select a rig to import alongside the mesh

### Exporting a GEOM

1. Select your mesh object (must have the `__S4_GEOM__` property)
2. **File > Export > Sims 4 GEOM (.simgeom)**
3. Choose your export location

### Exporting Textures (RLE to DDS)

Extract all textures from a package file as standard DDS files:

1. **File > Export > Sims 4 Textures (RLE → DDS)**
2. Select a .package file
3. A dialog shows the texture counts found:
   - **RLE2** - Diffuse/color textures
   - **RLES** - Specular/detail textures
   - **DDS** - Raw DDS textures
4. Choose which texture types to export
5. Select an output folder
6. Click **OK** to export

Exported files are named:
- `diffuse_XXXXXXXXXXXXXXXX.dds` - RLE2 textures
- `specular_XXXXXXXXXXXXXXXX.dds` - RLES textures
- `texture_XXXXXXXXXXXXXXXX.dds` - Raw DDS textures

## Tools Panel

The add-on adds a panel in the 3D View sidebar (press `N` to open) under the **SimGeom** tab.

### Available Tools

| Tool | Description |
|------|-------------|
| **Import Rig** | Import a Sims 4 rig (.grannyrig) |
| **Recalculate Vertex IDs** | Renumbers vertex IDs starting from the specified start_id |
| **Remove Vertex IDs** | Removes vertex ID data from the mesh |
| **Transfer GEOM Data** | Copy GEOM properties from active object to selected objects |
| **Rename Vertex Groups** | Converts FNV32 hash names to readable bone names |
| **Rebuild Bonehash Database** | Updates the bone name lookup table from imported rigs |
| **Make Morph** | Create a morph from selected mesh linked to active mesh |

## Morphs

Morphs can be imported from GEOM morph meshes (extracted from BGEO files using tools like Cmar's S4PE plugins).

### How Morphs Work

- Morphs are separate mesh objects linked to a base GEOM
- Each morph has a **Morph Name** and **Linked to** property
- When exporting, all morphs linked to the selected GEOM will be exported as separate morph files
- Morphs support custom normals just like base meshes

### Importing Morphs

1. Select your base GEOM mesh
2. **File > Import > Sims 4 Morph (.simgeom)**
3. Select one or more morph .simgeom files

## Materials & Textures

When importing from .package files with **Import Materials** enabled:

- The addon automatically finds all textures in the package
- Textures are converted from Sims 4's RLE format to standard DDS
- **A separate material is created for EACH diffuse texture** (e.g., `Diffuse_1_XXXXXXXX`, `Diffuse_2_XXXXXXXX`)
- Each material includes:
  - **Diffuse** (RLE2) → Base Color input
  - **Specular** (RLES) → Specular IOR Level input (shared across all materials)
- **All materials are added to the mesh's material slots** - switch between them using Blender's material dropdown
- Textures are saved to a temporary folder and loaded into Blender

This makes it easy to preview different texture variations (recolors) by simply selecting a different material from the dropdown.

### Texture Types

| Type | Format ID | Description |
|------|-----------|-------------|
| RLE2 | 0x3453CF95 | Diffuse/color maps (DXT5 compressed) |
| RLES | 0xBA856C78 | Specular/normal maps (DXT5 compressed) |
| DDS | 0x00B2D882 | Raw DDS textures |

## Splitting UV Seams

This is an important step for proper mesh editing:

1. Open the **UV Editor**
2. Go to **UV > Seams from Islands**
3. In the 3D View with **Edge Select** mode active
4. Select an edge marked as a seam (orange)
5. Go to **Select > Select Similar > Seam**
6. Press `V` to split the seams
7. **Recalculate Vertex IDs** if your mesh uses them

## Vertex IDs

- `start_id` - The vertex ID to start renumbering at
- The panel shows the highest vertex ID and unique ID count
- Don't modify these if you're not adding/removing vertices (preserves original IDs)
- Some items (like pet accessories) may not use vertex IDs

## Transferring GEOM Data

To copy GEOM properties from one mesh to others:

1. Select the target meshes
2. Make the source GEOM mesh the **active** object (last selected)
3. Click **Transfer GEOM Data** in the panel

## Fixing Bone Names

If vertex groups show as hex values like `0xef89a3e3`:

1. Import the appropriate rig for your mesh
2. Select the rig and click **Rebuild Bonehash Database**
3. Select your mesh and click **Rename Vertex Groups**

This only needs to be done once - bone names are saved to a JSON file.

## Technical Details

### Package (DBPF) Format

The addon includes a full Python implementation of EA's DBPF package format:

- **DBPF Version 2.1** - Standard Sims 4 package format
- **Compression Support**:
  - DEFLATE/zlib (standard compression)
  - RefPack (legacy EA compression)
- **Resource Types**:
  - GEOM meshes (0x015A1849)
  - DDS textures (0x00B2D882)
  - RLE2 textures (0x3453CF95)
  - RLES textures (0xBA856C78)

### Sims 4 GEOM Format

- **RCOL Wrapper**: Version 3 with ITG (Instance-Type-Group) ordering
- **GEOM Chunk**: Version 12-15
- **MTNF Shader Data**: Embedded material/texture references
- **Vertex Data**: 9-byte format entries (usage, datatype, size)
- **Weights**: Stored as bytes (0-255) normalized to floats
- **Additional Sections**: UVStitch, SeamStitch, SlotrayIntersection

### Supported Vertex Formats

| Usage | Type | Description |
|-------|------|-------------|
| 1 | Position | 3 floats (X, Y, Z) |
| 2 | Normal | 3 floats |
| 3 | UV | 2 floats per channel |
| 4 | Bone Assignment | 4 bytes |
| 5 | Weights | 4 bytes (0-255) |
| 6 | Tangent | 3 floats |
| 7 | Color/TagValue | 4 bytes (ARGB) |
| 10 | Vertex ID | 1 uint32 |

### RLE Texture Format

The addon includes a pure Python RLE decompressor:

- **RLE2** (0x32454C52): Standard diffuse textures
- **RLES** (0x53454C52): Specular textures with extra channel
- Converts to DXT5-compressed DDS format
- Supports all mipmap levels

## File Menu Reference

### Import Menu (File > Import)

| Option | Description |
|--------|-------------|
| Sims 4 Package (.package) | Import GEOMs directly from package files |
| Sims 4 GEOM (.simgeom) | Import standalone GEOM files |
| Sims 4 Morph (.simgeom) | Import morph GEOM files |
| Sims 4 Rig (.grannyrig) | Import skeleton/rig files |

### Export Menu (File > Export)

| Option | Description |
|--------|-------------|
| Sims 4 GEOM (.simgeom) | Export mesh as GEOM file |
| Sims 4 Textures (RLE → DDS) | Extract textures from package to DDS |

## Reporting Bugs

If you encounter any issues, please include the **console output** when reporting:

### How to Open the Console

**Windows:**
1. Go to **Window > Toggle System Console**
2. A black console window will appear showing debug output

**macOS:**
1. Open Terminal app
2. Navigate to Blender: `/Applications/Blender.app/Contents/MacOS/Blender`
3. Run Blender from Terminal to see console output

**Linux:**
1. Run Blender from a terminal window
2. Console output appears in the terminal

### What to Include in Bug Reports

1. **Full console output** - Copy everything from the console after the error occurs
2. **Blender version** (Help > About Blender)
3. **Operating system**
4. **Steps to reproduce** the issue
5. **The .package file** (if possible) that caused the error

The console shows detailed debug info like:
- GEOM version and structure details
- Texture conversion progress
- Specific error messages and line numbers

## Credits

- **[SmugTomato](https://github.com/SmugTomato)** - Original Sims 3 GEOM Tools
- **cmomoney** - Original rig importer
- **[blancodagoat](https://github.com/blancodagoat)** - Sims 4 adaptation

## License

This project is licensed under the GPL-3.0 License - see the [LICENSE](io_simgeom/LICENSE) file for details.

## Links

- **GitHub**: https://github.com/blancodagoat/blender-sims4-geom
- **Original Sims 3 Version**: https://github.com/SmugTomato/blender-sims3-geom

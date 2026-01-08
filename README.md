# Blender Sims 4 GEOM Tools

A Blender add-on for importing and exporting Sims 4 SimGeom (.simgeom) mesh files.

This is a fork of [SmugTomato's Blender Sims 3 GEOM Tools](https://github.com/SmugTomato/blender-sims3-geom), updated to support **The Sims 4** GEOM format.

## Features

- **Import/Export Sims 4 SimGeom files** (.simgeom)
- **Custom normals support** - preserves original mesh normals
- **Multiple UV channels** - supports meshes with multiple UV maps
- **Vertex colors** - imports/exports vertex color data (TagValue)
- **Bone weights** - full vertex group and weight support
- **Morph support** - import and export morph GEOMs
- **Blender 4.0+ / 5.0 compatible**

## Supported Sims 4 GEOM Versions

- GEOM Version 12, 13, 14 (RCOL wrapper v3)
- UVStitch, SeamStitch, and SlotrayIntersection data sections

## Installation

This add-on is installed like any other Blender add-on:

1. Download the `io_simgeom` folder
2. In Blender, go to **Edit > Preferences > Add-ons > Install**
3. Navigate to and select the `io_simgeom` folder (or zip it first)
4. Enable the add-on by checking the box next to "Sims 4 SimGeom Tools"

## Usage

### Importing a GEOM

1. **File > Import > Sims 4 SimGeom (.simgeom)**
2. Select your .simgeom file
3. Optionally select a rig to import alongside the mesh

### Exporting a GEOM

1. Select your mesh object (must have the `__S4_GEOM__` property)
2. **File > Export > Sims 4 SimGeom (.simgeom)**
3. Choose your export location

## Tools Panel

The add-on adds a panel in the 3D View sidebar (press `N` to open) under the **SimGeom** tab.

### Available Tools

- **Recalculate Vertex IDs** - Renumbers vertex IDs starting from the specified start_id
- **Remove Vertex IDs** - Removes vertex ID data from the mesh
- **Transfer GEOM Data** - Copy GEOM properties from active object to selected objects
- **Rename Vertex Groups** - Converts FNV32 hash names to readable bone names
- **Rebuild Bonehash Database** - Updates the bone name lookup table from imported rigs

## Morphs

Morphs can be imported from GEOM morph meshes (extracted from BGEO files using tools like Cmar's S4PE plugins).

### How Morphs Work

- Morphs are separate mesh objects linked to a base GEOM
- Each morph has a **Morph Name** and **Linked to** property
- When exporting, all morphs linked to the selected GEOM will be exported as separate morph files
- Morphs support custom normals just like base meshes

### Importing Morphs

1. Select your base GEOM mesh
2. **File > Import > Sims 4 SimGeom Morph**
3. Select one or more morph .simgeom files

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

### Sims 4 GEOM Format

- **RCOL Wrapper**: Version 3 with ITG (Instance-Type-Group) ordering
- **GEOM Chunk**: Version 12-14
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

## Credits

- **[SmugTomato](https://github.com/SmugTomato)** - Original Sims 3 GEOM Tools
- **cmomoney** - Original rig importer
- **[blancodagoat](https://github.com/blancodagoat)** - Sims 4 adaptation

## License

This project is licensed under the GPL-3.0 License - see the [LICENSE](LICENSE) file for details.

## Links

- **GitHub**: https://github.com/blancodagoat/blender-sims4-geom
- **Original Sims 3 Version**: https://github.com/SmugTomato/blender-sims3-geom

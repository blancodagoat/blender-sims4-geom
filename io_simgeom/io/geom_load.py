# Copyright (C) 2019 SmugTomato
# Updated for Sims 4 support
# 
# This file is part of BlenderGeom.
# 
# BlenderGeom is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# BlenderGeom is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with BlenderGeom.  If not, see <http://www.gnu.org/licenses/>.

from io_simgeom.models.geom       import Geom
from io_simgeom.models.vertex     import Vertex
from io_simgeom.util.bytereader   import ByteReader
from io_simgeom.util.globals      import Globals


class GeomLoader:
    """
    Sims 4 GEOM Loader
    
    Sims 4 GEOM files use RCOL wrapper format (like Sims 3) with:
    - RCOL header (version 3)
    - GEOM chunk (version 12, 13, or 14)
    - MTNF shader data
    - Additional sections (UVStitch, SeamStitch, SlotrayIntersection)
    """
    

    @staticmethod
    def readGeom(filepath: str) -> Geom:
        geomdata = None
        with open(filepath, "rb") as f:
            geomdata = f.read()

        meshdata    = Geom()
        reader      = ByteReader(geomdata)

        print(f"=== GEOM LOADER DEBUG ===")
        print(f"File size: {len(geomdata)} bytes")

        # RCOL Header - skip first 12 bytes (version, unused fields)
        reader.skip(12)
        
        external_count = reader.getUint32()
        internal_count = reader.getUint32()
        print(f"External: {external_count}, Internal: {internal_count}")

        # Read internal chunk TGIs (ITG order: Instance, Type, Group)
        meshdata.internal_chunks = []
        for _ in range(internal_count):
            meshdata.internal_chunks.append(GeomLoader.getITG(reader))
        
        # Read external resource TGIs
        meshdata.external_resources = []
        for _ in range(external_count):
            meshdata.external_resources.append(GeomLoader.getITG(reader))
        
        # Read chunk positions and sizes
        for _ in range(internal_count):
            chunk_pos = reader.getUint32()
            chunk_size = reader.getUint32()
            print(f"Chunk at {chunk_pos}, size {chunk_size}")

        print(f"Offset before GEOM magic: {reader.getOffset()}")

        # GEOM Chunk starts here
        geom_magic = reader.getString(4)
        if geom_magic != "GEOM":
            raise ValueError(f"Invalid GEOM chunk: expected 'GEOM' magic, got '{geom_magic}'")
        
        meshdata.version = reader.getUint32()
        print(f"GEOM version: {meshdata.version}")
        
        # TGI offset (relative) and size
        tgi_offset = reader.getUint32()
        tgi_size = reader.getUint32()
        print(f"TGI offset: {tgi_offset}, size: {tgi_size}")
        
        # Embedded shader ID
        _embeddedID = reader.getUint32()
        meshdata.embeddedID = hex(_embeddedID)
        print(f"Embedded shader ID: {meshdata.embeddedID}")
        
        meshdata.shaderdata = []
        if _embeddedID != 0:
            meshdata.embeddedID = Globals.get_shader_name(_embeddedID)
            
            # MTNF block: Size does NOT include the size field itself
            mtnf_size = reader.getUint32()
            print(f"MTNF block size: {mtnf_size}")
            
            # Skip the entire MTNF block content
            if mtnf_size > 0:
                reader.skip(mtnf_size)
            
            print(f"Offset after MTNF: {reader.getOffset()}")
        
        # Mesh data
        meshdata.merge_group = reader.getUint32()
        meshdata.sort_order = reader.getUint32()
        print(f"Merge: {meshdata.merge_group}, Sort: {meshdata.sort_order}")
        
        vertex_count = reader.getUint32()
        vertex_format_count = reader.getUint32()
        print(f"Vertices: {vertex_count}, Formats: {vertex_format_count}")
        print(f"Offset before vertex formats: {reader.getOffset()}")

        # Read vertex format declarations and vertex data
        meshdata.element_data = GeomLoader.getElementData(reader, vertex_format_count, vertex_count)
        print(f"Offset after vertices: {reader.getOffset()}")
        
        # Face data
        meshdata.faces = GeomLoader.getGroupData(reader)
        print(f"Offset after faces: {reader.getOffset()}, Faces: {len(meshdata.faces)}")
        
        # TS4 additional data sections (after faces)
        # UVStitch data
        uvstitch_count = reader.getUint32()
        print(f"UVStitch count: {uvstitch_count}")
        for _ in range(uvstitch_count):
            reader.skip(4)  # Index
            uv_count = reader.getUint32()
            reader.skip(uv_count * 8)  # UV pairs (2 floats each)
        
        # SeamStitch data
        seamstitch_count = reader.getUint32()
        print(f"SeamStitch count: {seamstitch_count}")
        for _ in range(seamstitch_count):
            reader.skip(4)  # Index
            seam_count = reader.getUint32()
            reader.skip(seam_count * 4)  # float values
        
        # SlotrayIntersection data
        slotray_count = reader.getUint32()
        print(f"Slotray count: {slotray_count}")
        reader.skip(slotray_count * 4)  # uint32 indices
        
        print(f"Offset before bones: {reader.getOffset()}")
        
        # Bones (TS4 doesn't have skin_controller_index before bones)
        meshdata.skin_controller_index = 0
        meshdata.bones = GeomLoader.getBones(reader)
        print(f"Bones: {len(meshdata.bones)}")
        
        # TGI list at end
        tgi_count = reader.getUint32()
        print(f"TGI count: {tgi_count}")
        meshdata.tgi_list = []
        for _ in range(tgi_count):
            meshdata.tgi_list.append(GeomLoader.getTGI(reader))

        print(f"=== END DEBUG ===")
        return meshdata
    

    @staticmethod
    def getFloatList(reader: ByteReader, count: int) -> list:
        data = []
        for _ in range(count):
            data.append(reader.getFloat())
        return data

    
    @staticmethod
    def getByteList(reader: ByteReader, count: int) -> list:
        data = []
        for _ in range(count):
            data.append(reader.getByte())
        return data


    @staticmethod
    def getTGI(reader: ByteReader) -> dict:
        """Read TGI in Type-Group-Instance order"""
        tgi = {'type': None, 'group': None, 'instance': None}
        tgi['type']     = Globals.padded_hex(reader.getUint32(), 4)
        tgi['group']    = Globals.padded_hex(reader.getUint32(), 4)
        tgi['instance'] = Globals.padded_hex(reader.getUint64(), 8)
        return tgi


    @staticmethod
    def getITG(reader: ByteReader) -> dict:
        """Read TGI in Instance-Type-Group order (RCOL format)"""
        tgi = {'type': None, 'group': None, 'instance': None}
        tgi['instance'] = Globals.padded_hex(reader.getUint64(), 8)
        tgi['type']     = Globals.padded_hex(reader.getUint32(), 4)
        tgi['group']    = Globals.padded_hex(reader.getUint32(), 4)
        return tgi
    

    @staticmethod
    def getElementData(reader: ByteReader, element_count: int, vert_count: int) -> list:
        """
        Read vertex format declarations and vertex data
        
        Sims 4 vertex format - each entry is 9 bytes (same as Sims 3):
        - Usage type (uint32): 1=Position, 2=Normal, 3=UV, 4=BoneAssign, 5=Weights, 6=Tangent, 7=Color, 10=VertexID
        - Data type (uint32): 1=float, 2=byte, etc.
        - Size in bytes (uint8): how many bytes per vertex for this attribute
        """
        vertices = []

        # Read vertex format declarations (9 bytes each: uint32 usage + uint32 datatype + uint8 size)
        format_entries = []
        for i in range(element_count):
            usage_type = reader.getUint32()
            data_type = reader.getUint32()
            byte_size = reader.getByte()
            format_entries.append({
                'usage': usage_type,
                'datatype': data_type,
                'size': byte_size
            })
            print(f"  Format[{i}]: usage={usage_type}, datatype={data_type}, size={byte_size}")
        
        print(f"Offset after format declarations: {reader.getOffset()}")
        
        # Read vertex data
        for v_idx in range(vert_count):
            vertex = Vertex()
            for fmt in format_entries:
                usage = fmt['usage']
                byte_size = fmt['size']
                
                if usage == 1:  # Position
                    vertex.position = GeomLoader.getFloatList(reader, 3)
                elif usage == 2:  # Normal
                    vertex.normal = GeomLoader.getFloatList(reader, 3)
                elif usage == 3:  # UV
                    uv = GeomLoader.getFloatList(reader, 2)
                    if not vertex.uv:
                        vertex.uv = [uv]
                    else:
                        vertex.uv.append(uv)
                elif usage == 4:  # Bone Assignment
                    vertex.assignment = GeomLoader.getByteList(reader, 4)
                elif usage == 5:  # Weights (TS4 uses bytes normalized 0-255)
                    raw_weights = GeomLoader.getByteList(reader, 4)
                    vertex.weights = [w / 255.0 for w in raw_weights]
                elif usage == 6:  # Tangent
                    vertex.tangent = GeomLoader.getFloatList(reader, 3)
                elif usage == 7:  # TagValue/Color (4 bytes ARGB)
                    vertex.tagvalue = GeomLoader.getByteList(reader, 4)
                elif usage == 10:  # Vertex ID
                    vertex.vertex_id = [reader.getUint32()]
                else:
                    # Unknown type - skip the bytes based on size field
                    print(f"  WARNING: Unknown vertex usage type {usage}, skipping {byte_size} bytes")
                    reader.skip(byte_size)
            vertices.append(vertex)

        return vertices
    

    @staticmethod
    def getGroupData(reader: ByteReader) -> list:
        """Read face/index data"""
        faces = []
        
        # Number of index groups (usually 1)
        reader.skip(4)  # Skip item count (always 1)
        
        # Index format (2 = 16-bit indices)
        index_type = reader.getByte()
        
        # Number of face points (indices)
        num_facepoints = reader.getUint32()
        print(f"  Face index type: {index_type}, points: {num_facepoints}")
        
        # Read faces (triangles)
        for _ in range(num_facepoints // 3):
            if index_type == 2:  # 16-bit indices
                faces.append([
                    reader.getUint16(),
                    reader.getUint16(),
                    reader.getUint16()
                ])
            else:  # 32-bit indices
                faces.append([
                    reader.getUint32(),
                    reader.getUint32(),
                    reader.getUint32()
                ])

        return faces


    @staticmethod
    def getBones(reader: ByteReader) -> list:
        """Read bone hash list"""
        bones = []

        count = reader.getUint32()
        for _ in range(count):
            bones.append(
                Globals.get_bone_name(reader.getUint32())
            )

        return bones

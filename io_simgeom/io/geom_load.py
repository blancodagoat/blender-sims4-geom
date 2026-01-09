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
        """Load GEOM from file path"""
        with open(filepath, "rb") as f:
            geomdata = f.read()
        return GeomLoader.readGeomFromBytes(geomdata)
    
    @staticmethod
    def readGeomFromBytes(geomdata: bytes) -> Geom:
        """Load GEOM from raw bytes (used for package import)"""
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
        
        # TGI offset (relative to current position) and size
        tgi_offset_pos = reader.getOffset()
        tgi_offset = reader.getUint32()
        tgi_size = reader.getUint32()
        # Calculate absolute TGI position (offset is relative to position after reading it)
        absolute_tgi_pos = tgi_offset_pos + 4 + tgi_offset  # +4 for the uint32 we just read
        print(f"TGI offset: {tgi_offset}, size: {tgi_size}")
        
        # Embedded shader ID
        _embeddedID = reader.getUint32()
        meshdata.embeddedID = hex(_embeddedID)
        print(f"Embedded shader ID: {meshdata.embeddedID}")
        
        meshdata.shaderdata = []
        meshdata.texture_refs = {}  # Maps texture type to TGI index
        if _embeddedID != 0:
            meshdata.embeddedID = Globals.get_shader_name(_embeddedID)
            
            # MTNF block: Size does NOT include the size field itself
            mtnf_size = reader.getUint32()
            print(f"MTNF block size: {mtnf_size}")
            
            # Parse MTNF shader data to extract texture references
            if mtnf_size > 0:
                mtnf_start = reader.getOffset()
                meshdata.texture_refs = GeomLoader.parseMTNF(reader, mtnf_start, mtnf_size)
                # Ensure we're at the end of MTNF block
                reader.setOffset(mtnf_start + mtnf_size)
            
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
        # UVStitch data (UnknownThingList in s4pi)
        # Structure per entry: index (uint32) + Vector2List (count + count * 2 floats)
        uvstitch_count = reader.getUint32()
        print(f"UVStitch count: {uvstitch_count}")
        for _ in range(uvstitch_count):
            reader.skip(4)  # Index (uint32)
            uv_count = reader.getUint32()  # Vector2List count
            reader.skip(uv_count * 8)  # UV pairs (2 floats = 8 bytes each)
        
        # For version 14+, SeamStitch and SlotrayIntersection appear to use
        # fixed-size entries similar to s4pi's UnknownThing2 (53 bytes each)
        # but stored as separate lists
        
        # SeamStitch data - FIXED 53 bytes per entry (s4pi comment mentions this size)
        seamstitch_count = reader.getUint32()
        print(f"SeamStitch count: {seamstitch_count}, offset: {reader.getOffset()}")
        SEAMSTITCH_ENTRY_SIZE = 53  # Based on s4pi UnknownThing2 comment
        seamstitch_bytes = seamstitch_count * SEAMSTITCH_ENTRY_SIZE
        
        overflow_detected = False
        # Sanity check: don't skip past TGI position
        if reader.getOffset() + seamstitch_bytes < absolute_tgi_pos:
            reader.skip(seamstitch_bytes)
        else:
            print(f"  WARNING: SeamStitch would overflow, seeking to TGI-based position")
            overflow_detected = True
        
        if not overflow_detected:
            # SlotrayIntersection data - also FIXED 53 bytes per entry
            slotray_count = reader.getUint32()
            print(f"Slotray count: {slotray_count}, offset: {reader.getOffset()}")
            SLOTRAY_ENTRY_SIZE = 53
            slotray_bytes = slotray_count * SLOTRAY_ENTRY_SIZE
            if reader.getOffset() + slotray_bytes < absolute_tgi_pos:
                reader.skip(slotray_bytes)
            else:
                print(f"  WARNING: Slotray would overflow, seeking to TGI position")
                overflow_detected = True
        
        # If overflow was detected, seek backwards from TGI to find bone data
        if overflow_detected:
            # Bones are right before TGI. We need to find where bone data starts.
            # Structure: bone_count (4 bytes) + bone_hashes (count * 4 bytes)
            # Since we don't know the count, we'll try to estimate or skip bones
            # For safety, seek to slightly before TGI and try to read bone count
            # The minimum space is 4 bytes (count) + TGI count (4 bytes)
            estimated_bone_pos = absolute_tgi_pos - 8  # Minimal: just bone count + tgi count
            if estimated_bone_pos > reader.getOffset():
                # Try to find bone data by scanning backwards from TGI
                # For now, just skip to TGI position - bones will be empty
                print(f"  Seeking to TGI position {absolute_tgi_pos}, skipping bone data")
                reader.setOffset(absolute_tgi_pos)
        
        print(f"Offset before bones: {reader.getOffset()}")
        
        # Bones (TS4 doesn't have skin_controller_index before bones)
        meshdata.skin_controller_index = 0
        
        # If we seeked past bones due to overflow, bones will be empty
        if reader.getOffset() >= absolute_tgi_pos:
            meshdata.bones = []
            print(f"Bones: 0 (skipped due to overflow)")
        else:
            meshdata.bones = GeomLoader.getBones(reader)
            print(f"Bones: {len(meshdata.bones)}")
        
        # TGI list at end - ensure we're at the right position
        if reader.getOffset() < absolute_tgi_pos:
            # Seek to TGI position if we're not there yet
            reader.setOffset(absolute_tgi_pos)
        
        # Only read TGI if we have room left in the file
        if reader.getOffset() + 4 <= len(reader.data):
            tgi_count = reader.getUint32()
            print(f"TGI count: {tgi_count}")
            meshdata.tgi_list = []
            for _ in range(tgi_count):
                if reader.getOffset() + 16 <= len(reader.data):
                    meshdata.tgi_list.append(GeomLoader.getTGI(reader))
        else:
            meshdata.tgi_list = []
            print(f"TGI count: 0 (end of file)")

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
    
    # Texture field type hashes
    TEXTURE_FIELDS = {
        0x6CC0FD85: 'diffuse',      # DiffuseMap
        0x6E56548A: 'normal',       # NormalMap
        0xAD528A60: 'specular',     # SpecularMap
        0xC3FAAC4F: 'alpha',        # AlphaMap
        0xF303D152: 'emission',     # EmissionMap
        0x6E067554: 'selfillum',    # SelfIlluminationMap
    }
    
    # Data types
    DT_FLOAT = 1
    DT_INT = 2
    DT_TEXTURE = 4
    
    @staticmethod
    def parseMTNF(reader: ByteReader, start: int, size: int) -> dict:
        """
        Parse MTNF shader data block to extract texture references
        
        MTNF format:
        - "MTNF" magic (4 bytes)
        - Unknown1 (4 bytes)
        - Data length (4 bytes) - size of data section after headers
        - Entry count (4 bytes)
        - Entry headers (16 bytes each: field, datatype, count, offset)
        - Data section
        
        Returns dict mapping texture type ('diffuse', 'normal', etc.) to TGI index
        """
        texture_refs = {}
        mtnf_start = reader.getOffset()
        
        # Read MTNF header
        mtnf_magic = reader.getString(4)
        if mtnf_magic != "MTNF" and mtnf_magic != "MTRL":
            print(f"  Warning: Expected MTNF/MTRL magic, got '{mtnf_magic}'")
            return texture_refs
        
        unknown1 = reader.getUint32()
        data_length = reader.getUint32()  # Size of data section
        entry_count = reader.getUint32()  # Number of shader entries
        
        print(f"  MTNF entries: {entry_count}, data length: {data_length}")
        
        # Sanity check
        if entry_count > 100 or entry_count < 0:
            print(f"  Warning: Suspicious entry count {entry_count}, skipping MTNF parse")
            return texture_refs
        
        # Read entry headers (16 bytes each: field, datatype, count, offset)
        entries = []
        for i in range(entry_count):
            field = reader.getUint32()
            datatype = reader.getUint32()
            count = reader.getUint32()
            offset = reader.getUint32()
            entries.append({
                'field': field,
                'datatype': datatype,
                'count': count,
                'offset': offset
            })
        
        # Data section starts after all headers
        # Offset in entries is relative to start of MTNF block
        data_start = mtnf_start
        
        # Process texture entries
        for entry in entries:
            if entry['datatype'] == GeomLoader.DT_TEXTURE and entry['count'] == 4:
                # This is a texture reference (index into TGI list)
                field_hash = entry['field']
                if field_hash in GeomLoader.TEXTURE_FIELDS:
                    tex_type = GeomLoader.TEXTURE_FIELDS[field_hash]
                    # Read texture index from data section
                    reader.setOffset(data_start + entry['offset'])
                    tgi_index = reader.getUint32()
                    texture_refs[tex_type] = tgi_index
                    print(f"    Texture {tex_type}: TGI index {tgi_index}")
        
        return texture_refs
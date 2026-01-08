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
from io_simgeom.util.bytewriter   import ByteWriter
from io_simgeom.util              import fnv

"""
Write out a new GEOM File for Sims 4

Sims 4 GEOM uses RCOL wrapper format:
- RCOL Header (version 3)
- GEOM chunk (version 14)
- MTNF shader data
- Vertex formats and data
- Faces
- UVStitch data
- SeamStitch data (v14+)
- SlotrayIntersection data
- Bones
- TGI list

Reference:
http://simswiki.info/wiki.php?title=Sims_3:RCOL
http://simswiki.info/wiki.php?title=Sims_3:0x015A1849
"""


class GeomWriter:

    @staticmethod
    def writeGeom(filepath: str, geomData: Geom) -> None:
        with open(filepath, "wb+") as f:
            f.write(GeomWriter.buildData(geomData))
    

    @staticmethod
    def buildData(geomData: Geom) -> bytearray:
        b = ByteWriter()

        # RCOL Header (TS4 format)
        b.setUInt32(3)  # RCOL version 3
        b.setUInt32(0)  # Public chunks
        b.setUInt32(0)  # Unused
        
        b.setUInt32(len(geomData.external_resources) if geomData.external_resources else 0)
        b.setUInt32(len(geomData.internal_chunks) if geomData.internal_chunks else 1)
        
        # Write internal chunk TGIs (ITG order)
        if geomData.internal_chunks:
            for chunk in geomData.internal_chunks:
                b.setUInt64(int(chunk['instance'], 0))
                b.setUInt32(int(chunk['type'], 0))
                b.setUInt32(int(chunk['group'], 0))
        else:
            # Default GEOM TGI
            b.setUInt64(0)
            b.setUInt32(0x015A1849)  # GEOM type
            b.setUInt32(0)
        
        # Write external resource TGIs
        if geomData.external_resources:
            for res in geomData.external_resources:
                b.setUInt64(int(res['instance'], 0))
                b.setUInt32(int(res['type'], 0))
                b.setUInt32(int(res['group'], 0))
        
        # Chunk position placeholder
        chunk_pos_offset = b.getLength()
        b.setUInt32(b.getLength() + 8)  # Position (right after this and size)
        chunksize_offset = b.getLength()
        b.setUInt32(0xFFFFFFFF)  # Size placeholder

        # GEOM Chunk Header
        b.setIdentifier("GEOM")
        b.setUInt32(geomData.version if geomData.version else 14)
        
        tgi_offset_pos = b.getLength()
        b.setUInt32(0xFFFFFFFF)  # TGI offset placeholder
        
        tgi_list = geomData.tgi_list if geomData.tgi_list else []
        tgilen = 4 + len(tgi_list) * 16
        b.setUInt32(tgilen)

        # Embedded Shader ID and MTNF data
        embedded_id = geomData.embeddedID if geomData.embeddedID else "0x0"
        if embedded_id != hex(0) and embedded_id != "0x0":
            if embedded_id[0:2] == '0x':
                b.setUInt32(int(embedded_id, 0))
            else:
                b.setUInt32(fnv.fnv32(embedded_id))
            
            mtnfsize_offset = b.getLength()
            b.setUInt32(0xFFFFFFFF)  # MTNF size placeholder
            b.setIdentifier("MTNF")
            b.setUInt64(0x0000007400000000)  # Unknown bytes
            
            shaderdata = []
            if geomData.shaderdata:
                for d in geomData.shaderdata:
                    if d.get('type') == 4 and d.get('size') == 5:
                        continue
                    shaderdata.append(d)
            
            b.setUInt32(len(shaderdata))
            offset = 16 + len(shaderdata) * 16
            
            # Write shader parameter info
            for d in shaderdata:
                name = d.get('name', '0x0')
                if name[0:2] == '0x':
                    b.setUInt32(int(name, 0))
                else:
                    b.setUInt32(fnv.fnv32(name))
                b.setUInt32(d.get('type', 1))
                b.setUInt32(d.get('size', 0))
                b.setUInt32(offset)
                offset += d.get('size', 0) * 4
            
            # Write shader parameter data
            for d in shaderdata:
                dtype = d.get('type', 1)
                data = d.get('data', [])
                if dtype == 1:  # Float
                    for entry in data:
                        b.setFloat(entry)
                elif dtype == 2:  # Integer
                    for entry in data:
                        b.setUInt32(entry)
                elif dtype == 4:  # Texture
                    if d.get('size') == 4:
                        b.setUInt64(data if isinstance(data, int) else 0)
                        b.setUInt64(0)
            
            b.replaceAt(mtnfsize_offset, 'I', b.getLength() - mtnfsize_offset - 4)
        else:
            b.setUInt32(0)

        # Mesh Data
        b.setUInt32(geomData.merge_group if geomData.merge_group else 0)
        b.setUInt32(geomData.sort_order if geomData.sort_order else 0)
        b.setUInt32(len(geomData.element_data))

        # Vertex format info
        order = GeomWriter.set_vertex_info(geomData.element_data[0], b)
        
        # Vertex data
        for vertex in geomData.element_data:
            uv_layer = 0
            for entry in order:
                var = getattr(vertex, entry[0])
                if entry[0] == 'uv':
                    var = getattr(vertex, entry[0])[uv_layer]
                    uv_layer += 1
                if entry[0] == 'weights':
                    # TS4 uses byte weights
                    for val in var:
                        b.setByte(int(round(val * 255)))
                else:
                    for val in var:
                        b.setArbitrary(entry[1], val)

        # Face data
        b.setUInt32(1)  # Item count
        b.setByte(2)    # Index type (16-bit)
        b.setUInt32(len(geomData.faces) * 3)
        for face in geomData.faces:
            for vert in face:
                b.setUInt16(vert)
        
        # UVStitch data (empty for now)
        b.setUInt32(0)
        
        # SeamStitch data (empty)
        b.setUInt32(0)
        
        # SlotrayIntersection data (empty)
        b.setUInt32(0)
        
        # Bones (TS4 doesn't have skin_controller_index)
        b.setUInt32(len(geomData.bones) if geomData.bones else 0)
        if geomData.bones:
            for bone in geomData.bones:
                if bone[0:2] == '0x':
                    b.setUInt32(int(bone, 0))
                else:
                    b.setUInt32(fnv.fnv32(bone))
        
        # Update TGI offset
        b.replaceAt(tgi_offset_pos, 'I', b.getLength() - tgi_offset_pos - 4)
        
        # TGI list
        b.setUInt32(len(tgi_list))
        for tgi in tgi_list:
            b.setUInt32(int(tgi['type'], 0))
            b.setUInt32(int(tgi['group'], 0))
            b.setUInt64(int(tgi['instance'], 0))
        
        # Update chunk size
        b.replaceAt(chunksize_offset, 'I', b.getLength() - chunksize_offset - 4)

        return b.getData()
    

    @staticmethod
    def set_vertex_info(vertex: Vertex, writer: ByteWriter) -> list:
        """
        Write vertex format declarations
        
        Each entry is 9 bytes: uint32 usage + uint32 datatype + uint8 size
        
        Usage types:
        1 = Position (3 floats, 12 bytes)
        2 = Normal (3 floats, 12 bytes)
        3 = UV (2 floats, 8 bytes)
        4 = Bone Assignment (4 bytes)
        5 = Bone Weights (4 bytes)
        6 = Tangent (3 floats, 12 bytes)
        7 = TagValue/Color (4 bytes ARGB)
        10 = Vertex ID (1 uint32, 4 bytes)
        
        Data types:
        1 = float32
        2 = byte/uint8
        """
        # Maps attribute name to [usage_type, data_format, datatype_id, byte_size]
        datatypes = {
            'position':     [1, 'f', 1, 12],   # 3 floats = 12 bytes
            'normal':       [2, 'f', 1, 12],   # 3 floats = 12 bytes
            'uv':           [3, 'f', 1, 8],    # 2 floats = 8 bytes
            'assignment':   [4, 'B', 2, 4],    # 4 bytes
            'weights':      [5, 'B', 2, 4],    # 4 bytes
            'tangent':      [6, 'f', 1, 12],   # 3 floats = 12 bytes
            'tagvalue':     [7, 'B', 2, 4],    # 4 bytes ARGB
            'vertex_id':    [10, 'I', 2, 4],   # 1 uint32 = 4 bytes
        }

        order = []

        for key, values in datatypes.items():
            if getattr(vertex, key):
                if key == 'uv':
                    for _ in range(len(vertex.uv)):
                        order.append([key, values[1]])
                else:
                    order.append([key, values[1]])
        
        # Write format count
        writer.setUInt32(len(order))
        
        # Write each format entry (9 bytes: usage uint32 + datatype uint32 + size uint8)
        for item in order:
            attr_name = item[0]
            info = datatypes[attr_name]
            usage_type = info[0]
            datatype_id = info[2]
            byte_size = info[3]
            
            writer.setUInt32(usage_type)    # Usage type
            writer.setUInt32(datatype_id)   # Data type (1=float, 2=byte)
            writer.setByte(byte_size)       # Byte size per vertex
        
        return order

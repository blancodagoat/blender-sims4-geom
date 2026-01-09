# Copyright (C) 2019 SmugTomato
# Package support added 2024
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

"""
Sims 4 .package (DBPF) file reader

DBPF format:
- 96 byte header starting with "DBPF" magic
- Package index at position specified in header
- Resources can be compressed with DEFLATE (zlib) or legacy RefPack
"""

import zlib
from io_simgeom.util.bytereader import ByteReader
from io_simgeom.util.globals import Globals


# Resource type IDs
GEOM_TYPE = 0x015A1849  # CAS Geometry
DDS_TYPE = 0x00B2D882   # DDS Image texture (plain)
RLE2_TYPE = 0x3453CF95  # RLE2 compressed texture
RLES_TYPE = 0xBA856C78  # RLES compressed texture (with specular)


class ResourceEntry:
    """Represents a resource entry in the package index"""
    def __init__(self):
        self.resource_type: int = 0
        self.resource_group: int = 0
        self.instance: int = 0
        self.chunk_offset: int = 0
        self.file_size: int = 0
        self.mem_size: int = 0
        self.compressed: int = 0
        
    @property
    def is_compressed(self) -> bool:
        return self.file_size != self.mem_size
    
    @property
    def type_hex(self) -> str:
        return f"0x{self.resource_type:08X}"
    
    @property
    def group_hex(self) -> str:
        return f"0x{self.resource_group:08X}"
    
    @property
    def instance_hex(self) -> str:
        return f"0x{self.instance:016X}"
    
    def get_display_name(self) -> str:
        """Get a human-readable name for display in UI"""
        type_names = {
            0x015A1849: "GEOM",
            0x00B2D882: "DDS Image",
            0x034AEECB: "CAS Part",
        }
        type_name = type_names.get(self.resource_type, f"Type {self.type_hex}")
        return f"{type_name} - {self.instance_hex}"


class PackageReader:
    """
    Reads Sims 4 .package (DBPF) files
    
    Based on s4pi implementation with Python port for Blender addon.
    """
    
    # DBPF header constants
    HEADER_SIZE = 96
    MAGIC = b"DBPF"
    
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.data: bytes = None
        self.reader: ByteReader = None
        
        # Header fields
        self.major_version: int = 0
        self.minor_version: int = 0
        self.index_count: int = 0
        self.index_position: int = 0
        self.index_size: int = 0
        
        # Index
        self.entries: list[ResourceEntry] = []
        
    def load(self) -> bool:
        """Load and parse the package file"""
        try:
            with open(self.filepath, "rb") as f:
                self.data = f.read()
            
            self.reader = ByteReader(self.data)
            
            if not self._read_header():
                return False
                
            if not self._read_index():
                return False
                
            return True
            
        except Exception as e:
            print(f"Error loading package: {e}")
            return False
    
    def _read_header(self) -> bool:
        """Read and validate the DBPF header"""
        if len(self.data) < self.HEADER_SIZE:
            print("File too small for DBPF header")
            return False
        
        # Check magic
        magic = self.reader.getRaw(4)
        if magic != bytearray(self.MAGIC):
            print(f"Invalid DBPF magic: {magic}")
            return False
        
        # Version
        self.major_version = self.reader.getInt32()
        self.minor_version = self.reader.getInt32()
        
        if self.major_version != 2:
            print(f"Warning: Expected DBPF major version 2, got {self.major_version}")
        
        # Skip unused fields (user version major/minor, unused1, creation/update time, unused2)
        self.reader.skip(24)  # bytes 12-35
        
        # Index count at offset 36
        self.index_count = self.reader.getInt32()
        
        # Index record position low at offset 40
        index_pos_low = self.reader.getInt32()
        
        # Index size at offset 44
        self.index_size = self.reader.getInt32()
        
        # Skip unused3 (12 bytes) at offset 48
        self.reader.skip(12)
        
        # Unused4 at offset 60 (always 3)
        self.reader.skip(4)
        
        # Index position at offset 64
        index_pos_high = self.reader.getInt32()
        
        # Use high position if set, otherwise use low
        self.index_position = index_pos_high if index_pos_high != 0 else index_pos_low
        
        return True
    
    def _read_index(self) -> bool:
        """Read the package index"""
        if self.index_position == 0 or self.index_count == 0:
            return True  # Empty package
        
        self.reader.setOffset(self.index_position)
        
        # Index type flags
        index_type = self.reader.getUint32()
        
        # Calculate header size based on flags
        # Bit 0: Type is constant
        # Bit 1: Group is constant  
        # Bit 2: Instance high is constant
        header_size = 1  # Always have index type
        if index_type & 0x01:
            header_size += 1
        if index_type & 0x02:
            header_size += 1
        if index_type & 0x04:
            header_size += 1
        
        # Read constant values from header
        const_type = self.reader.getUint32() if (index_type & 0x01) else None
        const_group = self.reader.getUint32() if (index_type & 0x02) else None
        const_instance_hi = self.reader.getUint32() if (index_type & 0x04) else None
        
        # Read entries
        for _ in range(self.index_count):
            entry = ResourceEntry()
            
            # Type
            entry.resource_type = const_type if const_type is not None else self.reader.getUint32()
            
            # Group
            entry.resource_group = const_group if const_group is not None else self.reader.getUint32()
            
            # Instance (high + low)
            instance_hi = const_instance_hi if const_instance_hi is not None else self.reader.getUint32()
            instance_lo = self.reader.getUint32()
            entry.instance = (instance_hi << 32) | instance_lo
            
            # Chunk offset
            entry.chunk_offset = self.reader.getUint32()
            
            # File size (with flag in high bit)
            file_size_raw = self.reader.getUint32()
            entry.file_size = file_size_raw & 0x7FFFFFFF
            
            # Memory size
            entry.mem_size = self.reader.getUint32()
            
            # Compressed flag
            entry.compressed = self.reader.getUint16()
            
            # Unknown2 (always 1)
            self.reader.skip(2)
            
            self.entries.append(entry)
        
        return True
    
    def get_resources_by_type(self, resource_type: int) -> list[ResourceEntry]:
        """Get all resources of a specific type"""
        return [e for e in self.entries if e.resource_type == resource_type]
    
    def get_geom_resources(self) -> list[ResourceEntry]:
        """Get all GEOM resources in the package"""
        return self.get_resources_by_type(GEOM_TYPE)
    
    def get_dds_resources(self) -> list[ResourceEntry]:
        """Get all DDS texture resources in the package"""
        return self.get_resources_by_type(DDS_TYPE)
    
    def get_rle_resources(self) -> list[ResourceEntry]:
        """Get all RLE texture resources in the package (RLE2 + RLES)"""
        rle2 = self.get_resources_by_type(RLE2_TYPE)
        rles = self.get_resources_by_type(RLES_TYPE)
        return rle2 + rles
    
    def get_all_texture_resources(self) -> list[ResourceEntry]:
        """Get all texture resources (DDS + RLE)"""
        return self.get_dds_resources() + self.get_rle_resources()
    
    def find_resource_by_tgi(self, res_type: int, group: int, instance: int) -> ResourceEntry:
        """Find a specific resource by Type-Group-Instance"""
        for entry in self.entries:
            if (entry.resource_type == res_type and 
                entry.resource_group == group and 
                entry.instance == instance):
                return entry
        return None
    
    def find_resource_by_instance(self, res_type: int, instance: int) -> ResourceEntry:
        """Find a resource by type and instance (ignoring group)"""
        for entry in self.entries:
            if entry.resource_type == res_type and entry.instance == instance:
                return entry
        return None
    
    def get_resource_data(self, entry: ResourceEntry) -> bytes:
        """
        Extract and decompress resource data
        
        Returns the raw uncompressed resource bytes
        """
        if entry.chunk_offset == 0xFFFFFFFF:
            return None
        
        # Seek to resource
        self.reader.setOffset(entry.chunk_offset)
        
        # Read raw data
        raw_data = self.reader.getRaw(entry.file_size)
        
        # Check if compressed
        if not entry.is_compressed:
            return bytes(raw_data)
        
        # Decompress
        return self._decompress(raw_data, entry.mem_size)
    
    def _decompress(self, data: bytearray, expected_size: int) -> bytes:
        """
        Decompress resource data
        
        Supports:
        - DEFLATE/zlib (header 0x78)
        - Legacy RefPack (header byte1 == 0xFB)
        """
        if len(data) < 2:
            return bytes(data)
        
        # Check compression type
        if data[0] == 0x78:
            # DEFLATE/zlib compression
            try:
                decompressed = zlib.decompress(bytes(data))
                return decompressed
            except zlib.error as e:
                print(f"DEFLATE decompression failed: {e}")
                return None
        
        elif data[1] == 0xFB:
            # Legacy RefPack compression
            return self._decompress_refpack(data, expected_size)
        
        else:
            print(f"Unknown compression format: {data[0]:02X} {data[1]:02X}")
            return None
    
    def _decompress_refpack(self, data: bytearray, expected_size: int) -> bytes:
        """
        Decompress RefPack (EA compression) data
        
        This is the legacy compression format used in older packages.
        """
        reader = ByteReader(data)
        
        # Determine if 3 or 4 byte size based on compression type byte
        compression_type = reader.getByte()
        reader.skip(1)  # Skip 0xFB
        
        # Read uncompressed size (big-endian)
        if compression_type != 0x80:
            # 3-byte size
            size_bytes = [reader.getByte(), reader.getByte(), reader.getByte()]
            uncompressed_size = (size_bytes[0] << 16) | (size_bytes[1] << 8) | size_bytes[2]
        else:
            # 4-byte size
            size_bytes = [reader.getByte(), reader.getByte(), reader.getByte(), reader.getByte()]
            uncompressed_size = (size_bytes[0] << 24) | (size_bytes[1] << 16) | (size_bytes[2] << 8) | size_bytes[3]
        
        output = bytearray(uncompressed_size)
        pos = 0
        
        while pos < uncompressed_size:
            byte0 = reader.getByte()
            
            if byte0 <= 0x7F:
                # Type 1: short copy
                byte1 = reader.getByte()
                num_plain = byte0 & 0x03
                num_copy = ((byte0 & 0x1C) >> 2) + 3
                copy_offset = ((byte0 & 0x60) << 3) + byte1 + 1
                
                # Copy plain text
                for _ in range(num_plain):
                    output[pos] = reader.getByte()
                    pos += 1
                
                # Copy from output buffer
                copy_src = pos - copy_offset
                for i in range(num_copy):
                    output[pos] = output[copy_src + i]
                    pos += 1
                    
            elif byte0 <= 0xBF:
                # Type 2: medium copy
                byte1 = reader.getByte()
                byte2 = reader.getByte()
                num_plain = ((byte1 & 0xC0) >> 6) & 0x03
                num_copy = (byte0 & 0x3F) + 4
                copy_offset = ((byte1 & 0x3F) << 8) + byte2 + 1
                
                for _ in range(num_plain):
                    output[pos] = reader.getByte()
                    pos += 1
                
                copy_src = pos - copy_offset
                for i in range(num_copy):
                    output[pos] = output[copy_src + i]
                    pos += 1
                    
            elif byte0 <= 0xDF:
                # Type 3: long copy
                byte1 = reader.getByte()
                byte2 = reader.getByte()
                byte3 = reader.getByte()
                num_plain = byte0 & 0x03
                num_copy = ((byte0 & 0x0C) << 6) + byte3 + 5
                copy_offset = ((byte0 & 0x10) << 12) + (byte1 << 8) + byte2 + 1
                
                for _ in range(num_plain):
                    output[pos] = reader.getByte()
                    pos += 1
                
                copy_src = pos - copy_offset
                for i in range(num_copy):
                    output[pos] = output[copy_src + i]
                    pos += 1
                    
            elif byte0 <= 0xFB:
                # Type 4: long plain
                num_plain = ((byte0 & 0x1F) << 2) + 4
                for _ in range(num_plain):
                    output[pos] = reader.getByte()
                    pos += 1
                    
            else:
                # Type 5: short plain (end marker)
                num_plain = byte0 & 0x03
                for _ in range(num_plain):
                    output[pos] = reader.getByte()
                    pos += 1
        
        return bytes(output)

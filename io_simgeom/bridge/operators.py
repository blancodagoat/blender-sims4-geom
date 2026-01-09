# Blender operators for Sollumz bridge functionality

import bpy
from bpy.types import Operator
from bpy.props import BoolProperty, EnumProperty

from . import check_sollumz, get_sollumz_status
from .converters import (
    geom_to_sollumz,
    sollumz_to_geom,
    copy_materials_geom_to_sollumz,
    copy_materials_sollumz_to_geom,
)


def is_sollumz_available():
    """Get current Sollumz availability"""
    from . import SOLLUMZ_AVAILABLE
    return SOLLUMZ_AVAILABLE


class SIMGEOM_OT_convert_to_sollumz(Operator):
    """Convert selected Sims 4 GEOM mesh(es) to Sollumz drawable geometry format"""
    bl_idname = "simgeom.convert_to_sollumz"
    bl_label = "Convert to Sollumz (GTA V)"
    bl_options = {'REGISTER', 'UNDO'}
    
    copy_materials: BoolProperty(
        name="Copy Materials",
        description="Attempt to convert and copy materials to Sollumz format",
        default=True
    )
    
    keep_original: BoolProperty(
        name="Keep Original",
        description="Keep the original GEOM object after conversion",
        default=True
    )
    
    @classmethod
    def poll(cls, context):
        # Check Sollumz availability
        check_sollumz()
        if not is_sollumz_available():
            return False
        
        # Need at least one selected mesh
        return (context.selected_objects and 
                any(obj.type == 'MESH' for obj in context.selected_objects))
    
    def execute(self, context):
        converted = 0
        failed = 0
        
        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue
            
            new_obj = geom_to_sollumz(obj)
            
            if new_obj:
                if self.copy_materials:
                    copy_materials_geom_to_sollumz(obj, new_obj)
                
                if not self.keep_original:
                    bpy.data.objects.remove(obj, do_unlink=True)
                
                converted += 1
            else:
                failed += 1
        
        if converted > 0:
            self.report({'INFO'}, f"Converted {converted} object(s) to Sollumz format")
        if failed > 0:
            self.report({'WARNING'}, f"Failed to convert {failed} object(s)")
        
        return {'FINISHED'}
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "copy_materials")
        layout.prop(self, "keep_original")


class SIMGEOM_OT_convert_from_sollumz(Operator):
    """Convert selected Sollumz drawable geometry to Sims 4 GEOM compatible format"""
    bl_idname = "simgeom.convert_from_sollumz"
    bl_label = "Convert from Sollumz (GTA V)"
    bl_options = {'REGISTER', 'UNDO'}
    
    copy_materials: BoolProperty(
        name="Copy Materials",
        description="Attempt to convert and copy materials to GEOM format",
        default=True
    )
    
    keep_original: BoolProperty(
        name="Keep Original",
        description="Keep the original Sollumz object after conversion",
        default=True
    )
    
    @classmethod
    def poll(cls, context):
        # Need at least one selected mesh
        return (context.selected_objects and 
                any(obj.type == 'MESH' for obj in context.selected_objects))
    
    def execute(self, context):
        converted = 0
        failed = 0
        
        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue
            
            new_obj = sollumz_to_geom(obj)
            
            if new_obj:
                if self.copy_materials:
                    copy_materials_sollumz_to_geom(obj, new_obj)
                
                if not self.keep_original:
                    bpy.data.objects.remove(obj, do_unlink=True)
                
                converted += 1
            else:
                failed += 1
        
        if converted > 0:
            self.report({'INFO'}, f"Converted {converted} object(s) to GEOM format")
        if failed > 0:
            self.report({'WARNING'}, f"Failed to convert {failed} object(s)")
        
        return {'FINISHED'}
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "copy_materials")
        layout.prop(self, "keep_original")


class SIMGEOM_OT_copy_textures_to_sollumz(Operator):
    """Copy textures from active GEOM material to Sollumz material"""
    bl_idname = "simgeom.copy_textures_to_sollumz"
    bl_label = "Copy Textures to Sollumz"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        check_sollumz()
        obj = context.active_object
        return (is_sollumz_available() and 
                obj is not None and 
                obj.type == 'MESH' and 
                obj.data.materials)
    
    def execute(self, context):
        obj = context.active_object
        
        # Check for Sollumz target
        target_objs = [o for o in context.selected_objects 
                       if o != obj and o.type == 'MESH' and 
                       hasattr(o, 'sollum_type')]
        
        if not target_objs:
            self.report({'ERROR'}, "Select a Sollumz object as target")
            return {'CANCELLED'}
        
        count = copy_materials_geom_to_sollumz(obj, target_objs[0])
        self.report({'INFO'}, f"Copied {count} material(s)")
        
        return {'FINISHED'}


class SIMGEOM_OT_check_sollumz(Operator):
    """Check if Sollumz addon is installed and available"""
    bl_idname = "simgeom.check_sollumz"
    bl_label = "Check Sollumz Status"
    
    def execute(self, context):
        check_sollumz()
        self.report({'INFO'}, get_sollumz_status())
        return {'FINISHED'}


# Registration
classes = [
    SIMGEOM_OT_convert_to_sollumz,
    SIMGEOM_OT_convert_from_sollumz,
    SIMGEOM_OT_copy_textures_to_sollumz,
    SIMGEOM_OT_check_sollumz,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

# UI panels for Sollumz bridge

import bpy
from bpy.types import Panel

from . import check_sollumz, get_sollumz_status


def is_sollumz_available():
    """Get current Sollumz availability"""
    from . import SOLLUMZ_AVAILABLE
    return SOLLUMZ_AVAILABLE


class SIMGEOM_PT_sollumz_bridge(Panel):
    """Sollumz Bridge panel in Sims 4 sidebar"""
    bl_label = "Sollumz Bridge"
    bl_idname = "SIMGEOM_PT_sollumz_bridge"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Sims 4"
    bl_parent_id = "SIMGEOM_PT_sidebar_panel"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw_header(self, context):
        check_sollumz()
        if is_sollumz_available():
            self.layout.label(text="", icon='LINKED')
        else:
            self.layout.label(text="", icon='UNLINKED')
    
    def draw(self, context):
        layout = self.layout
        check_sollumz()
        available = is_sollumz_available()
        
        # Status box
        box = layout.box()
        row = box.row()
        if available:
            row.label(text="Sollumz Detected", icon='CHECKMARK')
        else:
            row.label(text="Sollumz Not Found", icon='X')
            box.label(text="Install Sollumz for GTA V conversion", icon='INFO')
            box.operator("wm.url_open", text="Get Sollumz", icon='URL').url = "https://github.com/Sollumz/Sollumz"
            return
        
        layout.separator()
        
        # Conversion section
        box = layout.box()
        box.label(text="Convert Selected:", icon='ARROW_LEFTRIGHT')
        
        col = box.column(align=True)
        col.operator("simgeom.convert_to_sollumz", 
                     text="GEOM → Sollumz", 
                     icon='EXPORT')
        col.operator("simgeom.convert_from_sollumz", 
                     text="Sollumz → GEOM", 
                     icon='IMPORT')
        
        layout.separator()
        
        # Material tools
        box = layout.box()
        box.label(text="Material Tools:", icon='MATERIAL')
        box.operator("simgeom.copy_textures_to_sollumz", 
                     text="Copy Textures to Sollumz",
                     icon='TEXTURE')
        
        # Info section
        layout.separator()
        box = layout.box()
        box.label(text="Info:", icon='INFO')
        
        obj = context.active_object
        if obj and obj.type == 'MESH':
            # Check object type
            if hasattr(obj, 'sollum_type') and obj.sollum_type != 'sollumz_none':
                box.label(text=f"Type: Sollumz ({obj.sollum_type})")
            elif 'geom_instance' in obj:
                box.label(text=f"Type: Sims 4 GEOM")
            else:
                box.label(text="Type: Standard mesh")
            
            # Vertex count
            box.label(text=f"Vertices: {len(obj.data.vertices)}")
            box.label(text=f"Faces: {len(obj.data.polygons)}")
            box.label(text=f"Materials: {len(obj.data.materials)}")
        else:
            box.label(text="Select a mesh object")


# Registration
classes = [
    SIMGEOM_PT_sollumz_bridge,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

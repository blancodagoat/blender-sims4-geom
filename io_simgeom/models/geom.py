from typing import List

from io_simgeom.models.vertex import Vertex


class Geom:
    """
    Sims 4 GEOM data model
    
    Stores all mesh data needed for import/export of Sims 4 GEOM files.
    """

    def __init__(self):
        # GEOM Version (Sims 4 uses 12, 13, 14)
        self.version:               int             = 14
        
        # Legacy RCOL data (for compatibility, not used in Sims 4)
        self.internal_chunks:       List[dict]      = None
        self.external_resources:    List[dict]      = None

        # GEOM data
        self.embeddedID:            str             = None
        self.merge_group:           int             = None
        self.sort_order:            int             = None
        self.skin_controller_index: int             = None
        self.tgi_list:              List[dict]      = None
        self.shaderdata:            List[dict]      = None
        self.element_data:          List[Vertex]    = None
        self.bones:                 List[str]       = None
        self.faces:                 List[List[int]] = None

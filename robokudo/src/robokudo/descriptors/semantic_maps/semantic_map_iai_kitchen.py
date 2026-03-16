"""Semantic map definition for IAI kitchen environment.

This module provides semantic map definitions for the IAI kitchen environment,
defining regions and their spatial relationships. It specifies the physical
layout and semantic annotations of the kitchen space.

The semantic map includes:

* Region definitions with dimensions
* Spatial relationships between regions
* Frame transformations
* Semantic annotations for regions

.. note::
    This semantic map is specifically designed for the IAI kitchen environment
    and includes detailed specifications for regions like the kitchen island.
"""

from robokudo.semantic_map import SemanticMapEntry, BaseSemanticMap


class SemanticMap(BaseSemanticMap):
    """Semantic map for IAI kitchen environment.

    This class defines a semantic map containing region specifications for
    the IAI kitchen environment. It includes detailed region definitions with
    their physical properties and spatial relationships.

    The semantic map includes:

    * Kitchen island region
    * Region dimensions and poses
    * Frame transformations
    * Region type annotations

    .. note::
        The dimensions and poses are calibrated for the IAI kitchen setup
        and may need adjustment for other environments.
    """

    def __init__(self) -> None:
        """Initialize the IAI kitchen semantic map.

        Creates region definitions for:

        * Kitchen island (counter top)
        * Additional regions can be added as needed
        """
        super().__init__()

        # SEMANTIC MAP ENTRIES BEGIN
        semantic_map_entries = [
            SemanticMapEntry(
                name="kitchen_island",
                frame_id="map",
                type="CounterTop",
                position_x=2.30,
                position_y=2.72,
                position_z=1.40,
                orientation_x=0,
                orientation_y=0,
                orientation_z=0,
                orientation_w=1,
                x_size=1.0,
                y_size=3.18,
                z_size=0.85,
            ),
        ]
        # SEMANTIC MAP ENTRIES END

        self.add_entries(semantic_map_entries)

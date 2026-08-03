"""
The measurable size of a world body's geometry.

Both the live bridge (which sizes placeholder boxes for objects the viewer has no
mesh for) and the onboarder (which records each object's height into a bundle) need
the same measurement, taken the same way.
"""

from __future__ import annotations

from dataclasses import dataclass

from semantic_digital_twin.world_description.geometry import Box, Mesh
from typing_extensions import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from semantic_digital_twin.world_description.world_entity import Body


@dataclass(frozen=True)
class BodyExtent:
    """
    A body's size along each axis, in metres.
    """

    x: float
    """
    Extent along the world x axis.
    """

    y: float
    """
    Extent along the world y axis.
    """

    z: float
    """
    Extent along the world z axis, i.e. the body's height.
    """

    @classmethod
    def of(cls, body: Body) -> Optional[BodyExtent]:
        """
        Measure a body from the first of its shapes that carries a scale.

        Only :class:`Box` and :class:`Mesh` do; other primitives describe themselves
        by radius or length, and are reported as unmeasured rather than guessed at.

        :return: The extent, or None when no shape carries a scale.
        """
        for shape_collection in (body.visual, body.collision):
            for shape in shape_collection.shapes:
                if isinstance(shape, (Box, Mesh)):
                    return cls(
                        x=float(shape.scale.x),
                        y=float(shape.scale.y),
                        z=float(shape.scale.z),
                    )
        return None

    def rounded(self, precision: int) -> List[float]:
        """
        The extent as ``[x, y, z]``, rounded for publication.
        """
        return [
            round(self.x, precision),
            round(self.y, precision),
            round(self.z, precision),
        ]

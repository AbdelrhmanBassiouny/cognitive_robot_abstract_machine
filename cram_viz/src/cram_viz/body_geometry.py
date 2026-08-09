"""
The measurable size of a world body's geometry.

Both the live bridge (which sizes placeholder boxes for objects the viewer has no mesh
for) and the onboarder (which records each object's height into a bundle) need the same
measurement, taken the same way.
"""

from __future__ import annotations

from semantic_digital_twin.world_description.geometry import Scale
from typing_extensions import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from semantic_digital_twin.world_description.world_entity import Body


def measure_body(body: Body) -> Optional[Scale]:
    """
    Measure a body from the first of its shape collections that has any shapes.

    Checks :attr:`Body.visual` before :attr:`Body.collision`, using
    :attr:`ShapeCollection.scale`, which measures any shape type from its bounding box
    rather than relying on a shape-specific scale attribute.

    :param body: The body to measure.
    :return: The body's size along each world axis in metres, or None when both
        collections are empty.
    """
    for shape_collection in (body.visual, body.collision):
        if not shape_collection.shapes:
            continue
        scale = shape_collection.scale
        return Scale(x=float(scale.x), y=float(scale.y), z=float(scale.z))
    return None


def rounded_scale(scale: Scale, precision: int) -> List[float]:
    """
    A scale as ``[x, y, z]``, rounded for publication.

    :param scale: The scale to round.
    :param precision: Number of decimal places to round each axis to.
    """
    return [
        round(scale.x, precision),
        round(scale.y, precision),
        round(scale.z, precision),
    ]

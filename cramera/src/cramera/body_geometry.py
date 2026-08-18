"""
The publishable size, pose and coordinates of a world body.

Both the live bridge (which sizes placeholder boxes for objects the viewer has no mesh
for) and the onboarder (which records each object's height into a bundle) need the same
measurement, taken the same way, and both publish body poses rounded the same way.
"""

from __future__ import annotations

from semantic_digital_twin.spatial_types import Point3, Pose
from semantic_digital_twin.spatial_types.numeric import NumericPose
from semantic_digital_twin.world_description.geometry import Scale
from typing_extensions import (
    List,
    Optional,
    Protocol,
    runtime_checkable,
    TYPE_CHECKING,
)

POSE_PRECISION = 5
"""
Decimal places a pose is rounded to before it is published or recorded.
"""

if TYPE_CHECKING:
    from semantic_digital_twin.world_description.world_entity import Body


@runtime_checkable
class CarriesAMeshFile(Protocol):
    """
    A shape whose geometry lives in a file of its own.

    Structural, because a world built in code writes its generated geometry out to a
    file just as a loaded mesh names the file it came from.
    """

    filename: str


def mesh_file_of(body: Body) -> Optional[str]:
    """
    The file a body's own geometry lives in, or None for one built from primitives.

    :param body: The body whose geometry is inspected.
    """
    for shape_collection in (body.visual, body.collision):
        for shape in shape_collection.shapes:
            if isinstance(shape, CarriesAMeshFile) and shape.filename:
                return shape.filename
    return None


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


def rounded_pose(body: Body, precision: int = POSE_PRECISION) -> List[float]:
    """
    A body's world pose as ``[x, y, z, qx, qy, qz, qw]``, rounded for publication.

    Reads the pose numerically, so publishing one builds no symbolic expression.

    :param body: The body whose world pose is read.
    :param precision: Number of decimal places to round each value to.
    """
    return [
        round(value, precision)
        for value in body.numeric_global_pose.to_position_quaternion_list()
    ]


def position_label(position: Point3) -> str:
    """
    A position's coordinates, formatted to two decimal places for display.

    :class:`Point3` has no plain-value ``__repr__`` of its own (it is a CasADi-symbolic
    type), so the coordinates are read out explicitly.

    :param position: The position to format.
    """
    return "(%.2f, %.2f, %.2f)" % tuple(position.to_np().tolist()[:3])


def pose_label(pose: Pose) -> str:
    """
    A pose's position and orientation, formatted to two decimal places for display.

    Formats the position exactly as :func:`position_label` does, so an answer showing
    both a position and a pose reads consistently.

    :param pose: The pose to format.
    """
    return NumericPose.of_pose(pose).label

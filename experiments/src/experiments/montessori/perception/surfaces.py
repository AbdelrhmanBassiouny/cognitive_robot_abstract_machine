"""
Read the horizontal surfaces perception looks at out of the world the robot knows.

Where a scene stands, how far it reaches and how high it lies are all in the world the
node already fetches, so perception asks it rather than being told in constants that go
stale the moment the furniture moves.
"""

from __future__ import annotations

from dataclasses import dataclass

from experiments.montessori.perception.exceptions import SurfaceHasNothingToMeasure
from experiments.montessori.perception.orthophoto import WorkspaceRegion
from semantic_digital_twin.semantic_annotations.mixins import HasSupportingSurface
from semantic_digital_twin.world_description.geometry import VolumetricBoundingBox
from semantic_digital_twin.world_description.world_entity import (
    Body,
    KinematicStructureEntity,
)

# %% a surface the scene stands on


@dataclass(frozen=True)
class SupportingSurface:
    """
    A horizontal surface of the scene: how high it lies, and the stretch of it worth
    looking at.
    """

    region: WorkspaceRegion
    """
    The stretch of the surface perception looks at.
    """

    height: float
    """
    Height of the surface above the world frame's origin, in metres.
    """

    @classmethod
    def of(
        cls,
        supporter: HasSupportingSurface,
        reference_frame: KinematicStructureEntity,
    ) -> SupportingSurface:
        """
        The surface something in the world offers to whatever rests on it.

        Follows the region the world declares for it, and falls back to the shape of its
        own body where the world declares none.

        :param supporter: The annotated thing whose surface is read.
        :param reference_frame: Frame to express the surface in.
        :raises SurfaceHasNothingToMeasure: If neither the declared region nor the body
            carries a shape.
        """
        declared = supporter.supporting_surface
        if declared is None:
            return cls.of_body(supporter.root, reference_frame)
        boxes = declared.area.as_bounding_box_collection_in_frame(reference_frame)
        if not boxes.bounding_boxes:
            raise SurfaceHasNothingToMeasure(str(declared.name))
        return cls._of_box(boxes.bounding_box())

    @classmethod
    def of_body(
        cls, body: Body, reference_frame: KinematicStructureEntity
    ) -> SupportingSurface:
        """
        The surface a body offers: its widest horizontal face.

        A table is a top and four legs, and only the top is a surface, so the widest
        face is taken rather than everything the body is made of.

        :param body: The body whose surface is read.
        :param reference_frame: Frame to express the surface in.
        :raises SurfaceHasNothingToMeasure: If the body carries no collision shape.
        """
        boxes = body.collision.as_bounding_box_collection_in_frame(
            reference_frame
        ).bounding_boxes
        if not boxes:
            raise SurfaceHasNothingToMeasure(str(body.name))
        return cls._of_box(max(boxes, key=lambda box: box.scale.x * box.scale.y))

    @classmethod
    def _of_box(cls, box: VolumetricBoundingBox) -> SupportingSurface:
        """
        The surface a box's top face describes.

        :param box: The box, already expressed in the frame the surface is wanted in.
        """
        return cls(
            region=WorkspaceRegion(
                minimum_x=float(box.min_x),
                maximum_x=float(box.max_x),
                minimum_y=float(box.min_y),
                maximum_y=float(box.max_y),
            ),
            height=float(box.max_z),
        )

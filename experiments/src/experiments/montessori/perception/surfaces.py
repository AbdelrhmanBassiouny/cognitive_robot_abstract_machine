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

# %% one plane, and the patch of it that is searched


@dataclass(frozen=True)
class WorkspaceSurface:
    """
    One horizontal plane perception rectifies onto, and the patch of it it searches.

    This is a measurement taken *of* a surface, not the surface itself: the digital twin
    already models that, as the :class:`Region` a
    :class:`~semantic_digital_twin.semantic_annotations.mixins.HasSupportingSurface`
    carries. A region is a world entity with a name, a pose and three-dimensional
    geometry; this is a plain value derived from one, holding only what rectifying a
    camera frame needs, and it is never added to a world.

    It is also not a :class:`~experiments.montessori.perception.orthophoto.WorkspaceRegion`
    with a height bolted on. A region is deliberately height-free because one region is
    projected onto several planes in turn -- the table, the lid, and the table plus a
    piece's own height -- so a height belongs to the surface, not to the patch.
    """

    region: WorkspaceRegion
    """
    The stretch of the plane perception searches.
    """

    height: float
    """
    Height of the plane above the world frame's origin, in metres.
    """

    @classmethod
    def of(
        cls,
        supporter: HasSupportingSurface,
        reference_frame: KinematicStructureEntity,
    ) -> WorkspaceSurface:
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
    ) -> WorkspaceSurface:
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
    def _of_box(cls, box: VolumetricBoundingBox) -> WorkspaceSurface:
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

"""
The horizontal surfaces perception looks at, and which of them a detection belongs to.

Where a scene stands, how far it reaches and how high it lies are all in the world the
node already fetches, so perception asks it rather than being told in constants that go
stale the moment the furniture moves. A scene has more than one such surface -- the
table, and whatever stands on it that things can be set down on in turn -- so each is
searched on its own, and each says which of what was seen rests on it.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Optional, Tuple

from experiments.montessori.perception.detections import MontessoriDetection
from experiments.montessori.perception.exceptions import SurfaceHasNothingToMeasure
from experiments.montessori.perception.orthophoto import WorkspaceRegion
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
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

    name: PrefixedName
    """
    What the world calls the surface this was measured from.

    A detection carries this to say what it rests on, so it has to be the name the world
    knows rather than one perception made up.
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
        return cls._of_box(declared.name, boxes.bounding_box())

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
        return cls._of_box(
            body.name, max(boxes, key=lambda box: box.scale.x * box.scale.y)
        )

    @classmethod
    def _of_box(
        cls, name: PrefixedName, box: VolumetricBoundingBox
    ) -> WorkspaceSurface:
        """
        The surface a box's top face describes.

        :param name: What the world calls the thing the box was measured from.
        :param box: The box, already expressed in the frame the surface is wanted in.
        """
        return cls(
            name=name,
            region=WorkspaceRegion(
                minimum_x=float(box.min_x),
                maximum_x=float(box.max_x),
                minimum_y=float(box.min_y),
                maximum_y=float(box.max_y),
            ),
            height=float(box.max_z),
        )


# %% which surface a detection belongs to


@dataclass(frozen=True)
class SurfaceSearch:
    """
    One supporting surface, and the part of its plane a detection pass may claim.

    A scene's surfaces stand on one another, so the same position on two planes is one
    place seen twice, and only the surface it actually rests on may report it. Which one
    that is has to be settled per pass, from what the surface itself was seen to cover
    and from what stands on it.
    """

    surface: WorkspaceSurface
    """
    The plane rectified onto, and the stretch of it searched.
    """

    boundary: Optional[MontessoriDetection] = None
    """
    What was seen of the surface itself, outside which nothing rests on it.

    None where the surface reaches across the whole stretch that is searched, as the
    table the scene is set up on does.
    """

    supported_surfaces: Tuple[MontessoriDetection, ...] = ()
    """
    The surfaces standing on this one.

    Whatever lies within one of them rests on it and is that surface's pass to report,
    even though this plane sees it too.
    """

    def claims(self, x: float, y: float) -> bool:
        """
        Whether something standing at a position on this plane rests on this surface.

        :param x: Position along the world frame's x-axis, in metres.
        :param y: Position along the world frame's y-axis, in metres.
        """
        if self.boundary is not None and not self.boundary.encloses(x, y):
            return False
        return not any(
            supported.encloses(x, y) for supported in self.supported_surfaces
        )

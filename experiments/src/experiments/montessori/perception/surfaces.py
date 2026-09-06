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
from experiments.montessori.pieces import LARGEST_PIECE_RADIUS
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.semantic_annotations.mixins import HasSupportingSurface
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.geometry import (
    Color,
    Shape,
    SurfaceFinish,
    VolumetricBoundingBox,
)
from semantic_digital_twin.world_description.world_entity import (
    Body,
    KinematicStructureEntity,
    Region,
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

    entity: KinematicStructureEntity
    """
    The thing of the world this was measured of: the region a supporter declares for
    itself, or the body carrying it where it declares none.

    A statement names that entity to say what it is looking on, so the surface has to
    carry it rather than a name standing in for it.
    """

    region: WorkspaceRegion
    """
    The stretch of the plane perception searches.
    """

    height: float
    """
    Height of the plane above the world frame's origin, in metres.
    """

    finish: Optional[SurfaceFinish] = None
    """
    How the surface takes the light that falls on it, or ``None`` where the world states
    no finish for it.

    This is what decides whether colour separates anything from the surface at all, so
    it is read here rather than looked up again wherever a look is being chosen.
    ``None`` is *not stated* rather than :attr:`SurfaceFinish.MATTE`, so an unannotated
    surface never silently reads as one colour segmentation works on.
    """

    color: Optional[Color] = None
    """
    The colour the world states for the surface, or ``None`` where it states none.

    A target wearing this colour cannot be told from the surface by colour, whatever the
    finish.
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
        return cls.of_region(declared, reference_frame)

    @classmethod
    def of_region(
        cls, region: Region, reference_frame: KinematicStructureEntity
    ) -> WorkspaceSurface:
        """
        The surface a region the world declares describes.

        :param region: The declared region.
        :param reference_frame: Frame to express the surface in.
        :raises SurfaceHasNothingToMeasure: If the region carries no shape.
        """
        boxes = region.area.as_bounding_box_collection_in_frame(reference_frame)
        if not boxes.bounding_boxes:
            raise SurfaceHasNothingToMeasure(str(region.name))
        return cls._of_box(region, boxes.bounding_box(), cls._one_shape_of(region.area))

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
        measured = [
            (shape, box)
            for shape in body.collision.shapes
            for box in ShapeCollection([shape])
            .as_bounding_box_collection_in_frame(reference_frame)
            .bounding_boxes
        ]
        if not measured:
            raise SurfaceHasNothingToMeasure(str(body.name))
        shape, box = max(measured, key=lambda pair: pair[1].scale.x * pair[1].scale.y)
        return cls._of_box(body, box, shape)

    @property
    def name(self) -> PrefixedName:
        """
        What the world calls the thing this was measured of.

        A detection carries this to say what it rests on, since a detection names what
        it saw rather than holding an entity of a world.
        """
        return self.entity.name

    @staticmethod
    def _one_shape_of(area: ShapeCollection) -> Optional[Shape]:
        """
        The shape an appearance can be read off, where the collection holds exactly one.

        A collection of several shapes may state several finishes, and merging them
        would be a rule nothing asks for, so it answers with none at all.

        :param area: The shapes the surface is described by.
        """
        [shape] = area.shapes if len(area.shapes) == 1 else [None]
        return shape

    @classmethod
    def _of_box(
        cls,
        entity: KinematicStructureEntity,
        box: VolumetricBoundingBox,
        shape: Optional[Shape] = None,
    ) -> WorkspaceSurface:
        """
        The surface a box's top face describes.

        :param entity: The thing of the world the box was measured of.
        :param box: The box, already expressed in the frame the surface is wanted in.
        :param shape: The shape the box was measured from, whose appearance the surface
            takes, or None where no single shape describes it.
        """
        return cls(
            entity=entity,
            region=WorkspaceRegion.of_box(box),
            height=float(box.max_z),
            finish=None if shape is None else shape.finish,
            color=None if shape is None else shape.color,
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

    narrowed_to: Optional[WorkspaceRegion] = None
    """
    A stretch of the world the look was asked to stay inside, or None where it was asked
    to search wherever this surface reaches.
    """

    overhang: float = LARGEST_PIECE_RADIUS
    """
    How far past :attr:`boundary` something resting on this surface may reach, in
    metres.

    A thing standing at the very edge of a surface has its centre on it and its outline
    beyond it, so a picture cut to the boundary alone would have nothing to measure at
    the thing's far side. The widest piece this set holds is what has to fit.
    """

    @property
    def is_searched(self) -> bool:
        """
        Whether any of this surface is left once the look's own narrowing is applied.

        A look asked about a stretch of the world that this surface never reaches has no
        pass to run here, which is not a failure: it is the narrowing doing its work.
        """
        return self._narrowing is None or self._reach.meets(self._narrowing)

    @property
    def region(self) -> WorkspaceRegion:
        """
        The stretch of this plane one pass rectifies and searches.

        :raises RegionsDoNotMeet: If the look was narrowed away from this surface, which
            :attr:`is_searched` answers before it is asked.
        """
        if self._narrowing is None:
            return self._reach
        return self._reach.intersection(self._narrowing)

    @property
    def _narrowing(self) -> Optional[WorkspaceRegion]:
        """
        The stretch of the world the look was asked to stay inside, as much of it as a
        picture has to reach to measure something standing at its very edge.

        A statement says where the *thing* is, not which pixels may be read, so the
        picture reaches an :attr:`overhang` past it for the same reason it does past a
        surface's own boundary -- otherwise a piece standing just inside the stretch a
        statement allows has its far side cut off and is never fitted.
        """
        if self.narrowed_to is None:
            return None
        return self.narrowed_to.grown_by(self.overhang)

    @property
    def _reach(self) -> WorkspaceRegion:
        """
        How far this surface itself reaches, before the look's own narrowing.

        A surface seen only where its boundary was found reaches no further than that
        boundary, since where it stands is measured every frame rather than modelled;
        one with no boundary of its own reaches across everything the world says it
        spans.
        """
        if self.boundary is None:
            return self.surface.region
        seen = WorkspaceRegion.of_outline(
            self.boundary.outline, self.surface.region.resolution
        )
        return self.surface.region.intersection(seen.grown_by(self.overhang))

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

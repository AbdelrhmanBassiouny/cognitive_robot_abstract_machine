"""
Answer an :mod:`entity query language <krrood.entity_query_language>` statement about
the Montessori scene by looking at it.

Perception is a backend beside the native and SQLAlchemy ones, so asking and looking are
the same act::

    statement = an(MontessoriShapeDetection)(pose=...)
    statement = statement.where(SupportedBy(statement.variable, board_lid))
    [seen] = statement.evaluate(backend=MontessoriPerceptionBackend(source=node))
    reach_for = seen.pose

Everything about how a statement is read, narrowed and checked belongs to
:class:`~krrood.entity_query_language.backends.PerceptionBackend` and is the same for
any sensor. What is here is only what is particular to this scene: that a look is taken
by the Montessori pipeline, and which relations its search can narrow itself by.

Two can. *Supported by* names a surface, and a surface is a stretch of a plane the world
already describes, so a look narrowed by it rectifies that stretch instead of the whole
table. *Inside* names a region outright, which is extents in the world's own vocabulary.
Either way the picture searched shrinks before anything is detected, rather than the
detections being filtered after.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import ClassVar, Iterable, Optional, Tuple, Type

from experiments.montessori.perception.detections import MontessoriDetection
from experiments.montessori.perception.exceptions import LookHasNoReferenceFrame
from experiments.montessori.perception.orthophoto import WorkspaceRegion
from experiments.montessori.perception.scene_request import SceneRequest
from experiments.montessori.perception.scene_source import MontessoriSceneSource
from experiments.montessori.perception.surfaces import WorkspaceSurface
from krrood.entity_query_language.backends import LookRequest, PerceptionBackend
from krrood.entity_query_language.predicate import Triple
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.reasoning.predicates import InsideRegion, SupportedBy

# %% the backend


@dataclass
class MontessoriPerceptionBackend(PerceptionBackend):
    """
    Answers a statement about the Montessori scene by looking at it.
    """

    source: MontessoriSceneSource
    """
    Where a look at the scene comes from.
    """

    narrowing_relations: ClassVar[Tuple[Type[Triple], ...]] = (
        SupportedBy,
        InsideRegion,
    )
    """
    A look here searches one supporting surface at a time and only the stretch of it a
    statement allows, so support and containment are what it can narrow itself by.
    """

    def look(
        self, request: LookRequest[MontessoriDetection]
    ) -> Iterable[MontessoriDetection]:
        """
        Take a look at the scene.

        :param request: What the statement asks a look for.
        :return: Everything the look found.
        """
        return self.source.scene(self.scene_request(request)).detections

    def relations_hold(
        self, instance: MontessoriDetection, request: LookRequest[MontessoriDetection]
    ) -> bool:
        """
        Whether a detection stands where the statement said the thing sought stands.

        A look already taken cannot be narrowed, so what the search was asked for is
        checked again here over whatever came back -- which is what makes the narrowing
        an economy rather than the thing the answer's correctness rests on.

        :param instance: One detection the look reported.
        :param request: What the statement asks a look for.
        """
        return self._rests_on_the_surface_asked_about(
            instance, request
        ) and self._stands_in_the_region_asked_about(instance, request)

    def _rests_on_the_surface_asked_about(
        self, instance: MontessoriDetection, request: LookRequest[MontessoriDetection]
    ) -> bool:
        """
        :param instance: One detection the look reported.
        :param request: What the statement asks a look for.
        """
        supporting_surface = self.supporting_surface_asked_about(request)
        return (
            supporting_surface is None
            or instance.supporting_surface == supporting_surface
        )

    def _stands_in_the_region_asked_about(
        self, instance: MontessoriDetection, request: LookRequest[MontessoriDetection]
    ) -> bool:
        """
        Whether a detection was seen inside the region the statement named.

        A detection is a sighting rather than a body, so where it stands is the position
        it was reported at rather than a volume a containment can be measured against.

        :param instance: One detection the look reported.
        :param request: What the statement asks a look for.
        """
        patch = self.region_asked_about(request)
        if patch is None:
            return True
        seen_at = instance.pose.to_position().to_np()
        return patch.contains(float(seen_at[0]), float(seen_at[1]))

    def region_asked_about(
        self, request: LookRequest[MontessoriDetection]
    ) -> Optional[WorkspaceRegion]:
        """
        The stretch of the world a statement says the thing it is looking for lies in.

        :param request: What the statement asks a look for.
        :return: That stretch in metres, or None where the statement names no region.
        :raises LookHasNoReferenceFrame: If a region is named but the source reports its
            detections in no frame.
        """
        region = request.related_by(InsideRegion)
        if region is None:
            return None
        if self.source.reference_frame is None:
            raise LookHasNoReferenceFrame(str(region.name))
        return WorkspaceSurface.of_region(region, self.source.reference_frame).region

    @classmethod
    def scene_request(cls, request: LookRequest[MontessoriDetection]) -> SceneRequest:
        """
        Read what a statement asks for as something a look at this scene can act on.

        :param request: What the statement asks a look for.
        :return: The kind of detection to run detectors for, the surface to search, and
            the region of the world to stay inside.
        """
        return SceneRequest(
            detection_type=request.type_,
            supporting_surface=cls.supporting_surface_asked_about(request),
            region=request.related_by(InsideRegion),
        )

    @classmethod
    def supporting_surface_asked_about(
        cls, request: LookRequest[MontessoriDetection]
    ) -> Optional[PrefixedName]:
        """
        The surface a statement says the thing it is looking for rests on.

        A detection says what it rests on by the name the world knows that surface by,
        so what the statement names is read back the same way.

        :param request: What the statement asks a look for.
        :return: The name of the surface asked about, or ``None`` when the statement
            asks about none.
        """
        supporter = request.related_by(SupportedBy)
        if supporter is None:
            return None
        return supporter.name

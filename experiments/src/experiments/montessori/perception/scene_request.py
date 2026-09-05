"""
What a look is asked for.

A look at the scene is not free: every supporting surface is rectified and searched on
its own plane. Whoever asks usually wants less than everything, and says so here, so the
look runs what was asked for rather than everything and discarding the rest.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from typing_extensions import Optional, Tuple, Type

from experiments.montessori.perception.detections import MontessoriDetection
from krrood.patterns.belief_source import BeliefSource
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.reasoning.predicates import PlacementRelation, Turned
from semantic_digital_twin.world_description.geometry import (
    Color,
    VolumetricBoundingBox,
)
from semantic_digital_twin.world_description.world_entity import (
    KinematicStructureEntity,
)

# %% what to look for


@dataclass(frozen=True)
class SceneRequest:
    """
    The kind of thing a look is asked for, and where it is asked to search.

    Both parts are a narrowing, never a promise: a source that cannot act on either -- a
    camera whose look was already taken -- may answer with more than was asked for, and
    whoever asked is expected to keep filtering. Asking for everything is what an
    unnarrowed :class:`SceneRequest` says.
    """

    detection_type: Type[MontessoriDetection] = MontessoriDetection
    """
    The kind of detection asked for.

    A detector whose results cannot be of this kind has nothing to contribute to the
    answer and does not run.
    """

    supporting_surface: Optional[KinematicStructureEntity] = None
    """
    The surface to search, as the world holds it, or ``None`` to search every surface of
    the scene.
    """

    placements: Tuple[PlacementRelation, ...] = ()
    """
    Everything the statement says about where the thing sought lies, each as the
    relation that says it with nothing standing in the place of that thing.

    The relations themselves rather than a patch in metres: what one of them allows is
    read where the frame the detections are reported in is known, which is the look
    rather than the statement.
    """

    color: Optional[Color] = None
    """
    The colour the thing sought has, or ``None`` where the statement says none.

    A colour is a narrowing like the others: a look asked for one marks that colour
    alone and fits only the pieces that have it.
    """

    turn: Optional[Turned] = None
    """
    Which way the thing sought is turned, as the relation that says it with nothing
    standing in the place of that thing, or ``None`` where the statement says nothing
    about its turn.
    """

    believed_by: Optional[BeliefSource] = None
    """
    Who vouches for the stated placements as a belief about where the thing is, or
    ``None`` where they only say where to read.

    A placement that confines the thing closely enough is a place worth fitting a piece
    at whether or not any colour separates one there, and a look does that only on
    someone's say-so: a statement narrows what is read, a belief seeds a fit.
    """

    def wants(self, detection_type: Type[MontessoriDetection]) -> bool:
        """
        Whether a detector producing this kind of detection can contribute to the
        answer.

        :param detection_type: The kind of detection the detector produces.
        """
        return issubclass(detection_type, self.detection_type)

    def searches(self, surface_name: PrefixedName) -> bool:
        """
        Whether a surface is one this look was asked to search.

        :param surface_name: What the world calls the surface, which is how a measured
            surface answers for the entity a statement names.
        """
        return (
            self.supporting_surface is None
            or self.supporting_surface.name == surface_name
        )

    def believed_stretch(self) -> Optional[VolumetricBoundingBox]:
        """
        The stretch of the world the stated placements together confine the thing sought
        to, along the plane it rests on.

        :return: That stretch, or ``None`` where the placements leave it unbounded along
            the plane -- a direction alone confines nothing a fit could sweep -- or
            leave nothing at all.
        """
        if not self.placements:
            return None
        allowed = self.placements[0].allowed_space
        for placement in self.placements[1:]:
            allowed = allowed.intersection_with(placement.allowed_space)
            if allowed is None:
                return None
        bounds = [
            allowed.x_interval.lower,
            allowed.x_interval.upper,
            allowed.y_interval.lower,
            allowed.y_interval.upper,
        ]
        if not np.all(np.isfinite(bounds)):
            return None
        return allowed

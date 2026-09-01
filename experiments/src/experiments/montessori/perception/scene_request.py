"""
What a look is asked for.

A look at the scene is not free: every supporting surface is rectified and searched on
its own plane. Whoever asks usually wants less than everything, and says so here, so the
look runs what was asked for rather than everything and discarding the rest.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Optional, Type

from experiments.montessori.perception.detections import MontessoriDetection
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.world_description.world_entity import Region

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

    supporting_surface: Optional[PrefixedName] = None
    """
    The surface to search, by the name the world knows it by, or ``None`` to search
    every surface of the scene.
    """

    region: Optional[Region] = None
    """
    The region of the world the thing sought is said to lie in, or ``None`` where the
    statement says none.

    The world entity itself rather than a patch in metres: what a region reaches is read
    where the frame the detections are reported in is known, which is the look rather
    than the statement.
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

        :param surface_name: What the world calls the surface.
        """
        return (
            self.supporting_surface is None or self.supporting_surface == surface_name
        )

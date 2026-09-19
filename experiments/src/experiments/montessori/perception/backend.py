"""
Answer an :mod:`entity query language <krrood.entity_query_language>` statement about
the Montessori scene by looking at it.

Perception is a backend beside the native and SQLAlchemy ones, so asking and looking are
the same act::

    statement = an(MontessoriShapeDetection)(supporting_surface=board_lid_name, pose=...)
    [seen] = statement.evaluate(backend=MontessoriPerceptionBackend(source=node))
    reach_for = seen.pose

Everything about how a statement is read, narrowed and checked belongs to
:class:`~krrood.entity_query_language.backends.PerceptionBackend` and is the same for
any sensor. What is here is only what is particular to this scene: that a look is taken
by the Montessori pipeline, and that the one attribute its search can narrow itself by
is the surface a detection rests on.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import ClassVar, Iterable

from experiments.montessori.perception.detections import MontessoriDetection
from experiments.montessori.perception.scene_request import SceneRequest
from experiments.montessori.perception.scene_source import MontessoriSceneSource
from krrood.entity_query_language.backends import LookRequest, PerceptionBackend

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

    SUPPORTING_SURFACE_ATTRIBUTE_NAME: ClassVar[str] = "supporting_surface"
    """
    The attribute of a detection that names the surface it was found on, and so the one
    the search can narrow itself by.
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

    @classmethod
    def scene_request(cls, request: LookRequest[MontessoriDetection]) -> SceneRequest:
        """
        Read what a statement asks for as something a look at this scene can act on.

        :param request: What the statement asks a look for.
        :return: The kind of detection to run detectors for, and the surface to search.
        """
        return SceneRequest(
            detection_type=request.type_,
            supporting_surface=request.value_stated_for(
                cls.SUPPORTING_SURFACE_ATTRIBUTE_NAME
            ),
        )

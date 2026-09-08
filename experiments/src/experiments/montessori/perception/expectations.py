"""
What perception expects of a Montessori piece the robot has acted on, and how a look at
the scene checks it.

The expectation itself is the general one Segmind keeps -- the relations of the world's
vocabulary a thing is expected to stand in, moved by what each event declares. What is
particular to this scene is how a look is asked for it and how a sighting is checked
against it: a look here is a :class:`SceneRequest`, and a sighting is read the way the
look established it rather than only through the body standing for it.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from typing_extensions import List, Tuple, Type

from experiments.montessori.perception.backend import MontessoriPerceptionBackend
from experiments.montessori.perception.detections import DetectedMontessoriShape
from experiments.montessori.perception.scene_request import SceneRequest
from krrood.entity_query_language.predicate import Relation
from segmind.expectations import Expectation, Expectations

# %% what is expected of one piece


@dataclass(eq=False)
class MontessoriExpectation(Expectation):
    """
    What is expected of one Montessori piece, as a look at the scene can act on it.
    """

    def scene_request(self) -> SceneRequest:
        """
        This expectation as something a look at the Montessori scene can act on, vouched
        for by whatever put the belief here so the look fits a piece where it is
        expected.
        """
        return replace(
            MontessoriPerceptionBackend.scene_request(
                self.look_request(DetectedMontessoriShape)
            ),
            believed_by=self.source,
        )

    def contradicted_by(self, seen: DetectedMontessoriShape) -> Tuple[Relation, ...]:
        """
        Every expected relation a sighting does not stand in, each read the way the look
        established it.

        :param seen: The piece a look reported where this one was expected.
        """
        return MontessoriPerceptionBackend.contradicted_by(seen, self.holds)


# %% what the robot expects of the pieces


@dataclass
class MontessoriExpectations(Expectations):
    """
    What is expected of every Montessori piece the robot has acted on.
    """

    @classmethod
    def expectation_type(cls) -> Type[MontessoriExpectation]:
        """
        What is expected of a piece is expected as a look at this scene can act on it.
        """
        return MontessoriExpectation

    def scene_requests(self) -> List[SceneRequest]:
        """
        What a look at the scene is armed with: one request per piece something has
        acted on.
        """
        return [expectation.scene_request() for expectation in self.expected.values()]

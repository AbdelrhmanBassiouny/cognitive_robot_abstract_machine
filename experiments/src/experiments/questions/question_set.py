"""
The frozen set of questions the paper is scored on.

What is frozen is the questions themselves -- which ones are asked, in which bucket, of
which memory -- and the roles a scene fills in for the ones that single out one thing.
The things themselves change from scene to scene; the set does not.
"""

from __future__ import annotations

from dataclasses import dataclass

from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.world_description.world_entity import Body
from typing_extensions import Any, List

from experiments.questions.question import (
    BloomLevel,
    Bucket,
    Memory,
    Question,
)
from experiments.questions.working_memory import (
    AnythingMoved,
    HeldInTheHand,
    NumberOfOwnBodies,
    NumberOfOwnDegreesOfFreedom,
    ObjectColours,
    ObjectPlaces,
    ObjectsSeen,
    ObjectsThatMoved,
    ObjectsTheRobotMoved,
    PickedUpRecently,
    PlaceOfOwnBody,
    Side,
    SideOfAnotherObject,
    SupportingSurfaces,
)

# %% what a scene fills in


@dataclass
class QuestionedThings:
    """
    What a scene fills in for the questions of the set that single out one thing.
    """

    object_asked_about: Body
    """
    The object the questions about one object are about.
    """

    object_compared_against: Body
    """
    The object the first one is placed against, which is what a spatial question needs a
    second thing for.
    """

    object_in_the_hand: Body
    """
    The object the robot is being asked whether it is holding.
    """

    own_body_asked_about: PrefixedName
    """
    The robot's own link the self-model questions are about.
    """


# %% the set


@dataclass
class QuestionSet:
    """
    Every question the paper asks, in the order its buckets are reported in.
    """

    questions: List[Question[Any, Any]]
    """
    The questions, bucket by bucket.
    """

    @classmethod
    def over_working_memory(cls, things: QuestionedThings) -> QuestionSet:
        """
        The questions put to what the robot holds right now.

        :param things: What this scene fills in for the questions about one thing.
        """
        return cls(
            questions=[
                ObjectsSeen(),
                ObjectColours(),
                ObjectPlaces(),
                SupportingSurfaces(subject=things.object_asked_about),
                SideOfAnotherObject(
                    subject=things.object_asked_about,
                    other=things.object_compared_against,
                    side=Side.LEFT,
                ),
                SideOfAnotherObject(
                    subject=things.object_asked_about,
                    other=things.object_compared_against,
                    side=Side.RIGHT,
                ),
                AnythingMoved(),
                ObjectsThatMoved(),
                ObjectsTheRobotMoved(),
                PickedUpRecently(subject=things.object_asked_about),
                HeldInTheHand(subject=things.object_in_the_hand),
                PlaceOfOwnBody(body_name=things.own_body_asked_about),
                NumberOfOwnBodies(),
                NumberOfOwnDegreesOfFreedom(),
            ]
        )

    def for_bucket(self, bucket: Bucket) -> List[Question[Any, Any]]:
        """
        The questions of one bucket, in the set's own order.

        :param bucket: The kind of thing the questions ask about.
        """
        return [question for question in self.questions if question.bucket is bucket]

    def for_memory(self, memory: Memory) -> List[Question[Any, Any]]:
        """
        The questions put to one store, in the set's own order.

        :param memory: The store the questions are answered from.
        """
        return [question for question in self.questions if question.memory is memory]

    def for_bloom_level(self, bloom_level: BloomLevel) -> List[Question[Any, Any]]:
        """
        The questions exercising one level of the taxonomy, in the set's own order.

        :param bloom_level: The level answering the questions exercises.
        """
        return [
            question
            for question in self.questions
            if question.bloom_level is bloom_level
        ]

    @property
    def buckets(self) -> List[Bucket]:
        """
        The buckets this set has a question for, in the set's own order.
        """
        found: List[Bucket] = []
        for question in self.questions:
            if question.bucket not in found:
                found.append(question.bucket)
        return found

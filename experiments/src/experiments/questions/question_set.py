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

from experiments.questions.long_term_memory import (
    AnythingMovedInTheEpisode,
    NumberOfDegreesOfFreedomInTheEpisode,
    ObjectsSeenInTheEpisode,
    ObjectsThatMovedInTheEpisode,
    ObjectsTheRobotMovedInTheEpisode,
    PickedUpInTheEpisode,
)
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


@dataclass
class RememberedThings:
    """
    What a recorded run fills in for the questions of the set that single out one thing.
    """

    episode_identifier: str
    """
    Which run the questions are about.
    """

    object_name: str
    """
    What the object the questions about one object are about was called.

    A name rather than the body itself, because the body a run recorded is read back out
    of the database and is not the object anyone still holds.
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

    @classmethod
    def over_long_term_memory(cls, things: RememberedThings) -> QuestionSet:
        """
        The questions put to what past runs recorded.

        ..note:: Thinner than the working-memory set, and the gaps are what other items
            still owe: the support and spatial relations bucket needs geometric predicates
            routed to a backend that can answer them from rows, the embodiment bucket
            reduces to the pick-up record unless an episode also records which links were
            the robot's, and the control bucket has no spelling in either memory yet.

        :param things: What this run fills in for the questions about one thing.
        """
        return cls(
            questions=[
                ObjectsSeenInTheEpisode(episode_identifier=things.episode_identifier),
                AnythingMovedInTheEpisode(episode_identifier=things.episode_identifier),
                ObjectsThatMovedInTheEpisode(
                    episode_identifier=things.episode_identifier
                ),
                ObjectsTheRobotMovedInTheEpisode(
                    episode_identifier=things.episode_identifier
                ),
                PickedUpInTheEpisode(
                    episode_identifier=things.episode_identifier,
                    object_name=things.object_name,
                ),
                NumberOfDegreesOfFreedomInTheEpisode(
                    episode_identifier=things.episode_identifier
                ),
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

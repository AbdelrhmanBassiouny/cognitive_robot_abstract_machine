"""
The frozen set of questions the paper is scored on.

What is frozen is the questions themselves -- which ones are asked, in which bucket, of
which memory -- and the roles a scene fills in for the ones that single out one thing.
The things themselves change from scene to scene; the set does not.

The set is read off the questions rather than listed here, so a question joins it by
being written and none can be written and then forgotten.
"""

from __future__ import annotations

import inspect
import time
from dataclasses import dataclass

from krrood.utils import recursive_subclasses
from typing_extensions import Any, List, Type, TypeVar

from experiments.episodes.episode import RecordedQuery
from experiments.questions.long_term_memory import LongTermMemoryQuestion
from experiments.questions.question import (
    BloomLevel,
    Bucket,
    Memory,
    Question,
    QuestionedThings,
    RememberedThings,
)
from experiments.questions.working_memory import WorkingMemoryQuestion

QuestionType = TypeVar("QuestionType", bound=Question[Any, Any])

# %% the set


def questions_of(kind: Type[QuestionType]) -> List[Type[QuestionType]]:
    """
    Every question of one kind that can be asked, in the order they are written.

    Written order is bucket order, because each module is laid out bucket by bucket,
    which is also the order the paper reports them in.

    :param kind: The kind of question, which is the memory it is put to.
    """
    return [
        question
        for question in recursive_subclasses(kind)
        if not inspect.isabstract(question)
    ]


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
                asked
                for question in questions_of(WorkingMemoryQuestion)
                for asked in question.asked_of(things)
            ]
        )

    @classmethod
    def over_long_term_memory(cls, things: RememberedThings) -> QuestionSet:
        """
        The questions put to what past runs recorded.

        ..note:: Thinner than the working-memory set, and the gaps are what other items
            still owe: the support and spatial relations bucket needs geometric
            predicates routed to a backend that can answer them from rows, the
            embodiment bucket reduces to the pick-up record unless an episode also
            records which links were the robot's, and the control bucket has no spelling
            in either memory yet.

        :param things: What this run fills in for the questions about one thing.
        """
        return cls(
            questions=[
                asked
                for question in questions_of(LongTermMemoryQuestion)
                for asked in question.asked_of(things)
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

    def answer_and_record(self, source: Any) -> List[RecordedQuery]:
        """
        Ask every question of this set, score each against ground truth, and return the
        outcome as episode rows.

        :param source: The memory every question of this set is asked of.
        """
        batch_started_at = time.perf_counter()
        recorded: List[RecordedQuery] = []
        for question in self.questions:
            asked_at = time.perf_counter()
            answer = question.ask(source)
            latency = time.perf_counter() - asked_at
            recorded.append(
                RecordedQuery(
                    text=question.english,
                    answer=str(answer),
                    latency=latency,
                    moment=asked_at - batch_started_at,
                    question=question,
                    answered_correctly=question.values_agree(
                        answer, question.ground_truth(source)
                    ),
                )
            )
        return recorded

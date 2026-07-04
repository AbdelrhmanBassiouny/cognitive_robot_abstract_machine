"""The capability contract for view types that propose their own candidates."""

from __future__ import annotations

from abc import ABC, abstractmethod

from typing_extensions import Any

from krrood.entity_query_language.query.query import Query


class HasCandidates(ABC):
    """A view type that can propose its candidate instances from a world.

    This is the recall-oriented capability of a recognizable view (the "what"): it
    declares that the type knows how to build its own candidate query, typically by
    delegating to a :class:`~krrood.entity_query_language.rdr.recognition.candidate_generator.CandidateGenerator`
    strategy (the "how"). The recognition engine depends on this one-method interface,
    never on a concrete generator.
    """

    @classmethod
    @abstractmethod
    def candidates(cls, world: Any) -> Query:
        """Build, but do not evaluate, the query proposing candidate instances.

        :param world: The structure to propose candidates from.
        :return: The unevaluated EQL query whose solutions are the candidate views.
        """
        ...

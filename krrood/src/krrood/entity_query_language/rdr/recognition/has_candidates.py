"""The capability contract for view types that propose their own candidates."""

from __future__ import annotations

from abc import ABC, abstractmethod

from typing_extensions import Any

from krrood.entity_query_language.query.match import Match


class HasCandidates(ABC):
    """A view type that can propose its candidate instances from a world.

    This is the recall-oriented capability of a recognizable view (the "what"): it declares
    that the type knows how to describe itself as an *underspecified view* — a
    :class:`~krrood.entity_query_language.query.match.Match` a generative backend constructs
    into candidate instances — typically by delegating to a
    :class:`~krrood.entity_query_language.rdr.recognition.candidate_generator.CandidateGenerator`
    strategy (the "how"). The recognition engine depends on this one-method interface, never
    on a concrete generator.
    """

    @classmethod
    @abstractmethod
    def candidates(cls, world: Any) -> Match:
        """Describe the candidate instances as an underspecified view, without constructing them.

        :param world: The structure to propose candidates from.
        :return: The underspecified ``Match`` a generative backend constructs into candidates.
        """
        ...

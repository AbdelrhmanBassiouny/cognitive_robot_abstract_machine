"""Candidate generation for the recognition layer.

A candidate generator proposes instances of a view type from a world's structure
without judging whether each proposal is correct. It is the recall-oriented,
judgment-free half of the recognition split; :mod:`.definition` supplies precision.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from typing_extensions import Any, Generic, TypeVar

from krrood.entity_query_language.query.match import Match

ViewType = TypeVar("ViewType")
"""The view type whose candidates the generator proposes (e.g. ``Drawer``)."""


@dataclass
class CandidateGenerator(ABC, Generic[ViewType]):
    """Proposes candidate view instances from a world, without judging them.

    This is the data-abstraction / hypothesise half of heuristic classification
    (:cite:t:`clancey1985heuristic`) and the generation step of hypothesise-and-test
    recognition (:cite:t:`erman1980hearsay`). It deliberately over-generates and
    encodes no expert judgment; a view's ``candidates`` classmethod (see
    :class:`~krrood.entity_query_language.rdr.recognition.has_candidates.HasCandidates`)
    delegates to a generator, and a
    :class:`~krrood.entity_query_language.rdr.recognition.definition.Definition`
    supplies the precision.
    """

    @abstractmethod
    def generate(self, world: Any) -> Match:
        """Describe the candidate views as an underspecified view, without constructing them.

        Returning the underspecified :class:`~krrood.entity_query_language.query.match.Match`
        keeps generation lazy and composable: a generative backend decides when to construct,
        and the recall signal stays introspectable. Recall constraints belong in the candidate
        variables' domains, leaving the match's single ``where`` free for the definition's
        judgment (a ``Match`` locks after one ``where``).

        :param world: The structure to propose candidate views from.
        :return: The underspecified ``Match`` a generative backend constructs into candidates.
        """
        ...

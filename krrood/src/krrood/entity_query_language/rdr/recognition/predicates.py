"""Predicate that filters candidates by a definition's judgment inside an EQL query."""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Any, Mapping

from krrood.entity_query_language.predicate import Predicate
from krrood.entity_query_language.rdr.recognition.definition import Definition
from krrood.entity_query_language.verbalization.fragments.base import (
    VerbalizationFragment,
)
from krrood.entity_query_language.verbalization.vocabulary.parts_of_speech import (
    Copula,
    Noun,
    clause,
)


@dataclass(eq=False)
class JudgedGenuine(Predicate):
    """Holds for a candidate exactly when its definition judges it a genuine instance.

    Lets a definition's precision filter compose into the candidate generator's query
    as an ordinary ``where`` condition, so recognition is a single lazy query rather
    than a Python loop.
    """

    candidate: Any
    """The candidate view instance being judged (bound per solution)."""

    definition: Definition
    """The definition whose judgment decides whether the candidate is genuine."""

    def __call__(self) -> bool:
        return self.definition.judge(self.candidate)

    @classmethod
    def _verbalization_fragment_(
        cls, fields: Mapping[str, VerbalizationFragment]
    ) -> VerbalizationFragment:
        return clause(Noun(fields["candidate"]), Copula(), Noun("a genuine instance"))

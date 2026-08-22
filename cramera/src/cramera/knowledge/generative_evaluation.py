"""
Answering a question that leaves a field open by building what could fill it.

Kept out of :mod:`cramera.knowledge.queryable_knowledge` so that nothing is pulled in
from krrood's query backends unless a demo actually offers such a body of knowledge.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from krrood.entity_query_language.backends import EntityQueryLanguageGenerativeBackend
from krrood.entity_query_language.core.base_expressions import Selectable
from krrood.entity_query_language.evaluable import Evaluable
from krrood.entity_query_language.factories import variable
from krrood.entity_query_language.query.match import Match
from typing_extensions import Any, Dict

from cramera.knowledge.queryable_knowledge import QueryEvaluation


@dataclass(frozen=True)
class GenerativeEvaluation(QueryEvaluation):
    """
    Answers by constructing what the question leaves open, once per value it could take.

    A field written as ``...`` stands for every value it can hold, so a pattern naming
    an enum-typed field is answered with one instance per member of that enum, and a
    pattern naming several is answered with one per combination.
    """

    backend: EntityQueryLanguageGenerativeBackend = field(
        default_factory=EntityQueryLanguageGenerativeBackend
    )
    """
    What constructs the instances an open field is filled in with.
    """

    def evaluate(self, expression: Evaluable) -> Any:
        """
        Answer one question about what could be built.

        A pattern is answered by building it; anything else is a question about what was
        already built, and is answered where it stands.

        :param expression: The query to answer.
        """
        if isinstance(expression, Match):
            return self.backend.evaluate(expression)
        return expression.evaluate()

    def names(self) -> Dict[str, Any]:
        """
        ``generate``, so a question can be asked of what a pattern is filled in with.
        """
        return {"generate": self.generate}

    def generate(self, pattern: Match) -> Selectable:
        """
        A variable over every instance a pattern's open fields are filled in with.

        :param pattern: The pattern to fill in.
        """
        return variable(pattern.type, list(self.backend.evaluate(pattern)))

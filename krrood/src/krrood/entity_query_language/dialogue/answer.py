from __future__ import annotations

from abc import ABC
from dataclasses import dataclass

from typing_extensions import Any, Tuple

from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.questions.cause import CauseSet


@dataclass
class Answer(ABC):
    """The propositional content asserted by an :class:`Inform` or :class:`Explain` act.

    Distinct answer types let assertive acts be told apart by what they answer (a retrieval vs an
    explanation) without inspecting strings.
    """


@dataclass
class WhatAnswer(Answer):
    """The answer to a ``what`` (retrieval) question: the results and the query that produced them."""

    query: SymbolicExpression
    """The retrieval query whose evaluation produced :attr:`results`; kept for verbalization provenance."""

    results: Tuple[Any, ...]
    """The instances the query selected."""


@dataclass
class CauseSetAnswer(Answer):
    """The answer to a ``why`` question: the cause set explaining an inference."""

    cause_set: CauseSet
    """The conditions (with bindings) that explain why the asked-about instance was inferred."""

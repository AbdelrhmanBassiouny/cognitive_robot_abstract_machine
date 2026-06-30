"""
Performatives -- speech acts over EQL descriptions.

A *performative* applies an illocutionary force (Searle 1976; cf. the FIPA-ACL / KQML performatives) to a
propositional *content* expressed as an EQL
:class:`~krrood.entity_query_language.core.base_expressions.SymbolicExpression`. The force decides what is
*done* with the description -- found, asserted, explained, warned -- while the description stays a reusable,
verbalizable query.

This module owns the **framework-agnostic** layer: the :class:`Performable` interface and the atomic acts
that need only EQL evaluation / verbalization / exceptions (:class:`Find`, :class:`Inform`,
:class:`Explain`, :class:`Warn`). Acts that need a solver or a robot -- ``Achieve``, ``Monitor``,
``Perform`` -- live in the framework that owns that capability (giskardpy, coraplex) and subclass
:class:`Performative` there. Compositions (control structures over child performables -- sequential,
parallel, try) are the plan layer's plan nodes (coraplex), which verbalize through the shared
:mod:`~krrood.entity_query_language.verbalization.composition` shapes; each act's framing comes from its
own opener via :meth:`Performative.framed_fragment`.

Every act renders through real verbalization **fragments** (a single :meth:`Performable.as_fragment` tree),
so coordination and punctuation are produced by the verbalization engine rather than string concatenation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from typing_extensions import Any, List, Optional

from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.verbalization.context import MicroplanningServices
from krrood.entity_query_language.verbalization.fragments.base import (
    PhraseFragment,
    VerbalizationFragment,
    WordFragment,
    flatten_fragment_to_plain_text,
)
from krrood.entity_query_language.verbalization.fragments.features import Separator
from krrood.entity_query_language.verbalization.pipeline import fragment_for_expression
from krrood.entity_query_language.verbalization.vocabulary.english import (
    PerformativeDirective,
    PlanConnectives,
)
from krrood.entity_query_language.verbalization.vocabulary.words import VocabEnum
from krrood.exceptions import DataclassException


class Performable(ABC):
    """A speech act: something that can be performed and rendered as a verbalization fragment.

    A pure interface (no fields, so not a dataclass): this keeps it free of a generated ``__eq__`` that
    would otherwise shadow the identity equality of a subclass that wants it (e.g. a plan node in a graph).

    Atomic acts (:class:`Performative`), warnings (:class:`Warn`), and the plan layer's compositions
    (coraplex plan nodes) all share this interface, so a plan is a tree of performables that both
    executes (:meth:`perform`) and verbalizes (:meth:`verbalize`).
    """

    @abstractmethod
    def perform(self) -> Any:
        """Carry out the act and return its result."""

    @abstractmethod
    def as_fragment(
        self, services: Optional[MicroplanningServices] = None
    ) -> VerbalizationFragment:
        """:return: the act as a verbalization fragment, composed from its content and its force.

        :param services: Shared microplanning services threaded through a composition so repeated
            mentions corefer across acts; built per-act when omitted.
        """

    def eql_scan_targets(self) -> List[SymbolicExpression]:
        """:return: the EQL contents this act (and its children) verbalize, for a shared coreference
        map. Empty for acts whose content is not an EQL expression (e.g. a warning)."""
        return []

    def verbalize(self) -> str:
        """:return: the act rendered as a natural-language utterance, capitalised as a sentence.

        Builds one coreference map over all the EQL contents in this act's tree, so a referent shared
        across composed acts is named once and corefers (*"a Pose … the Pose"*).
        """
        services = MicroplanningServices.from_expressions(self.eql_scan_targets())
        text = flatten_fragment_to_plain_text(self.as_fragment(services))
        return text[:1].upper() + text[1:]


@dataclass
class Performative(Performable, ABC):
    """An atomic speech act applied to an EQL description."""

    content: SymbolicExpression
    """The propositional content -- the EQL description the force is applied to."""

    def eql_scan_targets(self) -> List[SymbolicExpression]:
        return [self.content]

    def framed_fragment(
        self,
        opener: VocabEnum,
        introducer: VocabEnum,
        services: Optional[MicroplanningServices],
    ) -> VerbalizationFragment:
        """Frame the content with a directive opener and a clause introducer.

        :param opener: The illocutionary-force verb (e.g. ``PerformativeDirective.ACHIEVE``).
        :param introducer: The clause introducer (e.g. ``PlanConnectives.THAT``).
        :param services: Shared microplanning services (coreference across acts), or ``None``.
        :return: A fragment reading *"<opener> <introducer> <content>"* (e.g. *"Achieve that …"*).
        """
        return PhraseFragment(
            parts=[
                opener.as_fragment(),
                introducer.as_fragment(),
                fragment_for_expression(self.content, services),
            ],
            separator=Separator.SPACE,
        )


@dataclass
class Find(Performative):
    """Search the world for the values matching the description -- the existing query speech act."""

    def perform(self) -> List[Any]:
        return list(self.content.evaluate())

    def as_fragment(
        self, services: Optional[MicroplanningServices] = None
    ) -> VerbalizationFragment:
        return fragment_for_expression(self.content, services)


@dataclass
class Inform(Performative):
    """Assert the described proposition to a listener."""

    def perform(self) -> str:
        return self.verbalize()

    def as_fragment(
        self, services: Optional[MicroplanningServices] = None
    ) -> VerbalizationFragment:
        return fragment_for_expression(self.content, services)


@dataclass
class Explain(Performative):
    """Explain why the described proposition holds, or failed to."""

    def perform(self) -> Any:
        raise NotImplementedError(
            "Explain is provided by the EQL explanation machinery (future integration)."
        )

    def as_fragment(
        self, services: Optional[MicroplanningServices] = None
    ) -> VerbalizationFragment:
        return self.framed_fragment(
            PerformativeDirective.EXPLAIN, PlanConnectives.WHY, services
        )


@dataclass
class Warn(Performable):
    """A warning: an assertion of an illegal state plus a suggested remedy.

    Carries the situation and remedy a :class:`~krrood.exceptions.DataclassException` already holds, so
    :meth:`of` lifts any such exception into the speech-act layer.
    """

    situation: str
    """A human-readable description of what is wrong."""

    suggestion: str = ""
    """Advice on how to fix it, or empty when there is none."""

    @classmethod
    def of(cls, exception: DataclassException) -> "Warn":
        """:return: the warning a :class:`~krrood.exceptions.DataclassException` expresses."""
        return cls(
            situation=exception.error_message(),
            suggestion=exception.suggest_correction(),
        )

    def perform(self) -> "Warn":
        return self

    def as_fragment(
        self, services: Optional[MicroplanningServices] = None
    ) -> VerbalizationFragment:
        parts: List[VerbalizationFragment] = [
            PerformativeDirective.WARNING.as_fragment(),
            WordFragment(text=f": {self.situation}"),
        ]
        if self.suggestion:
            parts.append(
                WordFragment(
                    text=f" {PerformativeDirective.SUGGESTION.text}: {self.suggestion}"
                )
            )
        return PhraseFragment(parts=parts, separator=Separator.NONE)

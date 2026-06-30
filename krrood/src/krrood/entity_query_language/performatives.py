"""
Performatives -- speech acts over EQL descriptions.

A *performative* applies an illocutionary force (Searle 1976; cf. the FIPA-ACL / KQML performatives) to a
propositional *content* expressed as an EQL
:class:`~krrood.entity_query_language.core.base_expressions.SymbolicExpression`. The force decides what is
*done* with the description -- found, asserted, explained, warned -- while the description stays a reusable,
verbalizable query.

This module owns the **framework-agnostic** layer: the :class:`Performable` interface, the atomic acts that
need only EQL evaluation / verbalization / exceptions (:class:`Find`, :class:`Inform`, :class:`Explain`,
:class:`Warn`), and the :class:`Composition` combinators. Acts that need a solver or a robot -- ``Achieve``,
``Observe``, ``Perform`` -- live in the framework that owns that capability (giskardpy, coraplex) and
subclass :class:`Performative` there, declaring their own directive opener via :meth:`Performative.framed_fragment`.

Every act renders through real verbalization **fragments** (a single :meth:`Performable.as_fragment` tree),
so coordination and punctuation are produced by the verbalization engine rather than string concatenation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, replace

from typing_extensions import Any, List, Optional

from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.verbalization import morphology
from krrood.entity_query_language.verbalization.context import MicroplanningServices
from krrood.entity_query_language.verbalization.fragments.base import (
    BlockFragment,
    PhraseFragment,
    RoleFragment,
    VerbalizationFragment,
    WordFragment,
    flatten_fragment_to_plain_text,
    oxford_comma,
)
from krrood.entity_query_language.verbalization.fragments.features import Separator
from krrood.entity_query_language.verbalization.fragments.roles import SemanticRole
from krrood.entity_query_language.verbalization.pipeline import fragment_for_expression
from krrood.entity_query_language.verbalization.vocabulary.english import (
    Conjunctions,
    Keywords,
    PerformativeDirective,
    PlanConnectives,
)
from krrood.entity_query_language.verbalization.vocabulary.register import Register
from krrood.entity_query_language.verbalization.vocabulary.words import VocabEnum
from krrood.exceptions import DataclassException

#: The register an action speech act verbalizes its description in: an imperative command
#: (*"navigate to …"*) for a self-verbalizing action, or *"Perform … such that …"* otherwise.
PERFORM_REGISTER = Register(
    binding_connective=Keywords.SUCH_THAT,
    fixed_opener=PerformativeDirective.PERFORM,
    imperative=True,
)


def _as_participle(fragment: VerbalizationFragment) -> VerbalizationFragment:
    """:return: *fragment* with its leading verb / directive opener as a present participle
    (*"monitor whether …"* → *"monitoring whether …"*), so a concurrent act reads as a *"while …-ing"*
    clause. A fragment with no leading verb (a bare assertion) is returned unchanged."""
    if isinstance(fragment, RoleFragment) and fragment.role in (
        SemanticRole.VERB,
        SemanticRole.KEYWORD,
    ):
        return replace(fragment, text=morphology.present_participle(fragment.text))
    if isinstance(fragment, BlockFragment) and fragment.header is not None:
        return replace(fragment, header=_as_participle(fragment.header))
    if isinstance(fragment, PhraseFragment) and fragment.parts:
        return replace(
            fragment, parts=[_as_participle(fragment.parts[0]), *fragment.parts[1:]]
        )
    return fragment


@dataclass
class Performable(ABC):
    """A speech act: something that can be performed and rendered as a verbalization fragment.

    Atomic acts (:class:`Performative`), warnings (:class:`Warn`), and compositions
    (:class:`Composition`) all share this interface, so a plan is a tree of performables that both
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
class Perform(Performative):
    """Carry out the described action -- the directive that drives a plan.

    The content is an action description (e.g. ``a(NavigateAction)(...).where(...)``); it verbalizes in the
    imperative register (*"Perform … such that …"*), and executing it is delegated to the plan layer.
    """

    def perform(self) -> Any:
        raise NotImplementedError(
            "Perform is executed by the coraplex plan layer."
        )

    def as_fragment(
        self, services: Optional[MicroplanningServices] = None
    ) -> VerbalizationFragment:
        return fragment_for_expression(
            self.content, services, register=PERFORM_REGISTER
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


@dataclass
class Composition(Performable, ABC):
    """A composite act: a control structure over child performables (a Searle commissive).

    ..note:: Verbalization is owned here; *executing* a composition (ordering, parallelism, failure
        fall-through) is the plan layer's responsibility, so :meth:`perform` raises here.
    """

    children: List[Performable]
    """The performables this composition coordinates."""

    def perform(self) -> Any:
        raise NotImplementedError(
            "Executing a composition is provided by the coraplex plan layer."
        )

    def eql_scan_targets(self) -> List[SymbolicExpression]:
        return [target for child in self.children for target in child.eql_scan_targets()]

    def _interleave(
        self,
        connective: PlanConnectives,
        services: Optional[MicroplanningServices],
        lead: Optional[VocabEnum] = None,
    ) -> VerbalizationFragment:
        """Join the children, placing *connective* before every child after the first.

        :param connective: The word inserted between steps (e.g. ``PlanConnectives.THEN``).
        :param services: Shared microplanning services threaded to each child (coreference across acts).
        :param lead: An optional opening word placed before the first child (e.g. ``PlanConnectives.TRY``).
        :return: A fragment reading *"[lead] A, <connective> B, <connective> C"*.
        """
        head, *rest = [child.as_fragment(services) for child in self.children]
        parts: List[VerbalizationFragment] = []
        if lead is not None:
            parts.extend([lead.as_fragment(), WordFragment(text=Separator.SPACE)])
        parts.append(head)
        for fragment in rest:
            parts.append(WordFragment(text=f"{Separator.COMMA}{connective.text} "))
            parts.append(fragment)
        return PhraseFragment(parts=parts, separator=Separator.NONE)

    def _coordinate(
        self,
        conjunction: Conjunctions,
        services: Optional[MicroplanningServices],
        lead: Optional[VocabEnum] = None,
        tail: Optional[VocabEnum] = None,
    ) -> VerbalizationFragment:
        """Join the children as an Oxford-comma coordination, reusing the And/Or coordination.

        :param conjunction: ``Conjunctions.AND`` (parallel) or ``Conjunctions.OR`` (try-all).
        :param services: Shared microplanning services threaded to each child (coreference across acts).
        :param lead: An optional opening word (e.g. ``PlanConnectives.TRY``).
        :param tail: An optional closing word (e.g. ``PlanConnectives.SIMULTANEOUSLY``).
        :return: A fragment reading *"[lead] A, B, <conjunction> C [tail]"*.
        """
        joined = oxford_comma(
            [child.as_fragment(services) for child in self.children],
            conjunction.as_fragment(),
        )
        parts: List[VerbalizationFragment] = []
        if lead is not None:
            parts.append(lead.as_fragment())
        parts.append(joined)
        if tail is not None:
            parts.append(tail.as_fragment())
        return PhraseFragment(parts=parts, separator=Separator.SPACE)


@dataclass
class Sequential(Composition):
    """Do the children one after another -- a temporal conjunction (*"A, then B"*)."""

    def as_fragment(
        self, services: Optional[MicroplanningServices] = None
    ) -> VerbalizationFragment:
        return self._interleave(PlanConnectives.THEN, services)


@dataclass
class Parallel(Composition):
    """Do the children at the same time -- the first act as the main clause, the rest as concurrent
    *"while …-ing"* clauses (*"navigate to X, while simultaneously monitoring whether …"*)."""

    def as_fragment(
        self, services: Optional[MicroplanningServices] = None
    ) -> VerbalizationFragment:
        head, *rest = [child.as_fragment(services) for child in self.children]
        if not rest:
            return head
        concurrent = oxford_comma(
            [_as_participle(fragment) for fragment in rest],
            Conjunctions.AND.as_fragment(),
        )
        connective = WordFragment(
            text=f"{Separator.COMMA}{PlanConnectives.WHILE.text} "
            f"{PlanConnectives.SIMULTANEOUSLY.text} "
        )
        return PhraseFragment(
            parts=[head, connective, concurrent], separator=Separator.NONE
        )


@dataclass
class TryInOrder(Composition):
    """Try the children in order, falling through on failure -- an ordered disjunction
    (*"try A, otherwise B"*)."""

    def as_fragment(
        self, services: Optional[MicroplanningServices] = None
    ) -> VerbalizationFragment:
        return self._interleave(
            PlanConnectives.OTHERWISE, services, lead=PlanConnectives.TRY
        )


@dataclass
class TryAll(Composition):
    """Try the children at once, succeeding if any does -- a disjunction with concurrency
    (*"try A, B, or C simultaneously"*)."""

    def as_fragment(
        self, services: Optional[MicroplanningServices] = None
    ) -> VerbalizationFragment:
        return self._coordinate(
            Conjunctions.OR,
            services,
            lead=PlanConnectives.TRY,
            tail=PlanConnectives.SIMULTANEOUSLY,
        )

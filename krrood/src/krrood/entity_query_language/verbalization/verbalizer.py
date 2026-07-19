from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from krrood.entity_query_language.verbalization.vocabulary.english import Directive

from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.query.match import Match
from krrood.entity_query_language.rdr.why import WhyAnswer
from krrood.entity_query_language.verbalization.context import MicroplanningServices
from krrood.entity_query_language.verbalization.engine import fold, root_context
from krrood.entity_query_language.verbalization.fragments.base import (
    VerbalizationFragment,
)
from krrood.entity_query_language.verbalization.grammar.framework.phrase_rule import (
    RuleContext,
)
from krrood.entity_query_language.verbalization.grammar.framework.registry import RULES
from krrood.entity_query_language.verbalization.grammar.match.assembler import (
    MatchAssembler,
)
from krrood.entity_query_language.verbalization.rendering.discourse import (
    DiscourseModel,
)
from krrood.entity_query_language.verbalization.rendering.realization import (
    realize_tree,
)


@dataclass
class EQLVerbalizer:
    """
    Builds the natural-language fragment tree that represents an EQL expression.
    """

    def build(
        self,
        expression: SymbolicExpression,
        services: Optional[MicroplanningServices] = None,
        performative: Optional[Directive] = None,
    ) -> VerbalizationFragment:
        """
        Translate *expression* into its natural-language fragment tree.

        A fresh services bundle is created when *services* is ``None``; pass a shared one across
        calls so repeated mentions corefer (a Robot … the Robot).

        :param expression: Any EQL symbolic expression.
        :param services: Shared verbalization state; created automatically when omitted.
        :param performative: Explicit opening directive (Find / Generate) — usually resolved from
            the evaluating backend. When omitted the verb is derived from the query type.
        :return: Root of the fragment tree representing *expression* in natural language.

        >>> from krrood.entity_query_language.verbalization.fragments.base import flatten_fragment_to_plain_text
        >>> flatten_fragment_to_plain_text(EQLVerbalizer().build(a(entity(variable(Robot, [])))))
        'Find a Robot'
        """
        # A match and a why-answer are not foldable EQL nodes but non-foldable roots; each is
        # scanned through the EQL expression that stands in for it (the match's resolved query, the
        # why-answer's firing condition) so disambiguation and discourse focus see the case variable.
        scan_target = self._scan_target(expression)
        if services is None:
            services = MicroplanningServices.from_expression(scan_target)
        if performative is not None:
            services.performative_override = performative
        # Referents already introduced by prior builds on these (shared) services, so the same
        # expression verbalized twice reads "a Robot" then "the Robot".  Snapshot BEFORE the
        # fold, which records this build's own mentions in the same set.
        previously_introduced_referents = set(services.referring.seen)
        if isinstance(expression, Match):
            fragment = MatchAssembler(self._match_context(services)).assemble(
                expression
            )
        else:
            # A why-answer dispatches through the fold like any node: ``select`` routes it to the
            # auto-registered ``CausalExplanationRule`` (its construct is ``WhyAnswer``).
            fragment = fold(expression, services, RULES)
        # The discourse focus per query scope, projected once from the shared plan read model; the
        # coreference pass consults it instead of rule-emitted subject markers.
        discourse = DiscourseModel.from_expression(scan_target, services.microplan)
        return realize_tree(
            fragment,
            previously_introduced_referents=previously_introduced_referents,
            discourse=discourse,
            numbered_labels=services.referring.numbered_labels,
        )

    @staticmethod
    def _scan_target(expression: SymbolicExpression) -> SymbolicExpression:
        """
        :param expression: The value being verbalized.
        :return: The EQL expression to scan for disambiguation and discourse focus — the resolved
            query for a ``Match``, the firing condition for a ``WhyAnswer`` (both non-foldable
            roots), or *expression* itself for an ordinary node.
        """
        match expression:
            case Match():
                return expression.expression
            case WhyAnswer():
                return expression.condition
            case _:
                return expression

    @staticmethod
    def _match_context(services: MicroplanningServices) -> RuleContext:
        """
        :param services: The pass-wide microplanning services.
        :return: A root context whose ``child`` is the fold continuation, so the match assembler
            recurses its selection / values / conditions through the standard grammar.
        """
        return root_context(services, RULES)

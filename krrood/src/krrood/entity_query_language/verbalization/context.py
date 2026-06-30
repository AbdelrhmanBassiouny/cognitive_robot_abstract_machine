from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import TYPE_CHECKING, List, Optional

from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.query.match import Match
from krrood.entity_query_language.verbalization.microplanning.binding_scope import (
    BindingScope,
)
from krrood.entity_query_language.verbalization.microplanning.config import (
    RenderConfiguration,
)
from krrood.entity_query_language.verbalization.microplanning.microplan import (
    Microplan,
)
from krrood.entity_query_language.verbalization.microplanning.referring import (
    ReferringExpressions,
)

if TYPE_CHECKING:
    from krrood.entity_query_language.verbalization.vocabulary.register import Register


@dataclass
class MicroplanningServices:
    """
    The three microplanning services for one verbalization pass: the referring-expression
    service, the binding scope, and the render configuration.

    The split mirrors the microplanning subtasks of :cite:t:`reiter2000building`.
    """

    referring: ReferringExpressions = field(default_factory=ReferringExpressions)
    """Coreference / article / disambiguation / pronoun service."""

    binding: BindingScope = field(default_factory=BindingScope)
    """Deferred-constraint frames and field-reference overrides."""

    configuration: RenderConfiguration = field(default_factory=RenderConfiguration)
    """Render-mode flags (query depth, compact predicates)."""

    microplan: Microplan = field(default_factory=Microplan)
    """The plan read model — each node's plan computed once and shared (lazy / memoised)."""

    register: Optional[Register] = None
    """The register a description is verbalized in (query opener + *"given that"*, or an imperative
    opener + *"such that"*). ``None`` means the default query register."""

    @classmethod
    def from_expression(cls, expression: SymbolicExpression) -> MicroplanningServices:
        """
        Create a context with the disambiguation map pre-built for *expression*.

        :param expression: Root EQL expression or query to scan.
        :return: A fresh context whose referring service has its disambiguation map populated.
        """
        return cls(referring=ReferringExpressions.from_expression(expression))

    @classmethod
    def from_expressions(
        cls, expressions: List[SymbolicExpression]
    ) -> MicroplanningServices:
        """Create a context whose disambiguation map spans *expressions* together.

        Verbalizing each with this shared context makes a referent that appears in more than one corefer
        across them (e.g. the same pose in a navigate act and a monitor act).

        :param expressions: The expressions or matches to scan together, in order.
        :return: A fresh context with the combined disambiguation map.
        """
        scan_targets = [
            expression.expression if isinstance(expression, Match) else expression
            for expression in expressions
        ]
        return cls(referring=ReferringExpressions.from_expressions(scan_targets))

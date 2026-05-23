"""
Expert protocol for the EQL-native RDR.

During fitting the target conclusion is already known, so the expert is asked only
for the *conditions* that justify it. The answer is a live EQL condition expression
built over the RDR's shared case variable — never a string or a list.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from typing_extensions import Any, Optional

from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.core.mapped_variable import CanBehaveLikeAVariable


class Expert(ABC):
    """Supplies the conditions for a new rule when the RDR mis/under-classifies a case."""

    @abstractmethod
    def ask_for_conditions(
        self,
        case: Any,
        current_conclusion: Optional[Any],
        target_conclusion: Any,
        case_variable: CanBehaveLikeAVariable,
    ) -> SymbolicExpression:
        """
        :param case: The case being fit (e.g. an ``Animal`` instance).
        :param current_conclusion: What the RDR currently concludes (``None`` if no rule fired).
        :param target_conclusion: The known correct conclusion.
        :param case_variable: The RDR's shared EQL variable; conditions must be built
            over it (e.g. ``case_variable.milk == True``) so they share the rule-tree DAG.
        :return: A live EQL condition expression that holds for ``case`` and distinguishes it.
        """
        ...

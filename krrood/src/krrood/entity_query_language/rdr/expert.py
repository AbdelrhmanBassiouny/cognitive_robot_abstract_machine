"""
Expert protocol for the EQL-native RDR.

During fitting the target conclusion is already known, so the expert is asked only
for the *conditions* that justify it. The answer is a live EQL condition expression
built over the RDR's shared case variable — never a string or a list.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from typing_extensions import Any, Optional, Tuple

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

    def ask_for_rule(
        self,
        case: Any,
        current_conclusion: Optional[Any],
        case_variable: CanBehaveLikeAVariable,
    ) -> Tuple[Any, SymbolicExpression]:
        """
        Ask the expert for **both** a conclusion and its conditions, for fitting when no
        ground-truth target is supplied (the expert is the one labelling the case).

        Conditions-only experts need not implement this; it is invoked only when a case is
        fit without a known target.

        :param case: The case being fit.
        :param current_conclusion: What the RDR currently concludes (``None`` if no rule fired).
        :param case_variable: The RDR's shared EQL variable; conditions are built over it.
        :return: ``(conclusion, conditions)`` — the value to conclude and a live EQL
            condition expression over ``case_variable`` that justifies it.
        """
        raise NotImplementedError(
            f"{type(self).__name__} cannot supply a conclusion. Provide ground-truth "
            "targets when fitting, or use an expert that implements ask_for_rule "
            "(e.g. IPythonExpert)."
        )

"""
The *policy* half of the expert split: what to ask, and how to validate the answer.

An :class:`Expert` decides which answers a new rule needs — only the *conditions* when the
target conclusion is known (ground-truth fit), or *both* a conclusion and its conditions
when no target is given (the expert labels the case). It owns the validators (conditions
must be an EQL :class:`SymbolicExpression`; a conclusion must lie in the attribute's
resolved :class:`~krrood.entity_query_language.rdr.conclusion_domain.ConclusionDomain`) and
delegates the actual expert interaction to its :class:`ExpertInterface`.

Answers are EQL expression objects built over the shared ``case_variable`` — never
strings or lists.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum

from typing_extensions import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.rdr.conclusion_domain import ConclusionDomain
from krrood.entity_query_language.rdr.exceptions import (
    ConditionsNotAnExpression,
    ConditionsNotProvided,
    NoConclusionProvided,
    NoConditionsProvided,
)
from krrood.entity_query_language.rdr.interface import (
    CASE_INSTANCE_NAME,
    CASE_VARIABLE_NAME,
    AnswerRequest,
    CaseContext,
    ExpertAbort,
    ExpertInterface,
)
from krrood.entity_query_language.rdr.utils import UNSET
from krrood.exceptions import DataclassException

if TYPE_CHECKING:
    from krrood.entity_query_language.rdr.aid import ConclusionAid


class AnswerName(StrEnum):
    """
    The namespace-variable names an :class:`Expert` asks the expert to assign.
    """

    CONDITIONS = "conditions"
    """
    Assigned an EQL condition expression, built over ``case_variable``.
    """

    CONCLUSION = "conclusion"
    """
    Assigned the conclusion value the expert labels the case with.
    """

    @property
    def example_assignment(self) -> str:
        """:return: A copy-pasteable example ``conditions = ...`` assignment."""
        return f"{self} = {CASE_VARIABLE_NAME}.some_attr == True"


def _validate_conditions(value: Any) -> Optional[DataclassException]:
    if isinstance(value, SymbolicExpression):
        return None
    if value is None:
        return ConditionsNotProvided(
            answer_name=AnswerName.CONDITIONS, case_variable_name=CASE_VARIABLE_NAME
        )
    return ConditionsNotAnExpression(
        value=value,
        answer_name=AnswerName.CONDITIONS,
        case_variable_name=CASE_VARIABLE_NAME,
        case_instance_name=CASE_INSTANCE_NAME,
    )


def make_conclusion_validator(
    domain: ConclusionDomain, allow_unset: bool
) -> Callable[[Any], Optional[DataclassException]]:
    """
    Build a validator for a conclusion answer from its resolved domain.

    :param domain: The resolved allowable-value domain of the conclusion attribute.
    :param allow_unset: Whether leaving the conclusion unset is acceptable.
    :return: A validator returning the violated exception, or ``None`` when acceptable.
    """
    return lambda value: domain.validate(value, allow_unset)


@dataclass
class RuleAnswer:
    """
    The expert's answer to :meth:`Expert.ask_for_rule`.
    """

    conclusion: Any
    """
    The conclusion the expert chose, or kept unchanged.
    """

    conditions: Optional[SymbolicExpression]
    """
    The conditions distinguishing the case, or ``None`` when the conclusion was kept
    (nothing to insert).
    """


@dataclass
class Expert:
    """
    Supplies a new rule's answers when the RDR mis/under-classifies a case.

    Holds an :class:`ExpertInterface` that performs the actual expert interaction; this
    class only builds the request specs and translates an :class:`ExpertAbort` into the
    policy-level :class:`NoConditionsProvided` / :class:`NoConclusionProvided`.
    """

    interface: ExpertInterface
    """
    The interface to use to interact with the expert.
    """

    aids: List[ConclusionAid] = field(default_factory=list)
    """
    Optional task-specific aids consulted while labelling a case: each may present an
    information / visual aid and / or suggest a conclusion (see :class:`ConclusionAid`).
    """

    def ask_for_conditions(
        self,
        context: CaseContext,
        prior_errors: Optional[Dict[str, DataclassException]] = None,
    ) -> SymbolicExpression:
        """
        :param context: Everything known about the case, built by the caller — the concrete
            instance, the shared variable, the current/target conclusion, the classification
            trace, and (in HINT mode) the suggested condition.
        :param prior_errors: Errors from a previous attempt (e.g. a
            :class:`~krrood.entity_query_language.exceptions.SelfReferentialInsertionError`)
            to display on the first render of the re-prompt shell.
        :return: An EQL condition expression that holds for the case and distinguishes it.
        """
        suggestion = context.suggested_condition
        request = AnswerRequest(
            name=AnswerName.CONDITIONS,
            validate=_validate_conditions,
            example=AnswerName.CONDITIONS.example_assignment,
            default=suggestion.expression if suggestion is not None else None,
        )
        try:
            return self.interface.interact(
                context, [request], initial_errors=prior_errors
            )[AnswerName.CONDITIONS]
        except ExpertAbort:
            raise NoConditionsProvided(case=context.case_instance)

    def ask_for_rule(self, context: CaseContext) -> RuleAnswer:
        """
        Ask the expert to label the case (no ground truth), then justify the label.

        Sequential: first a focused **conclusion-only** question — the allowable values are
        shown and a valid aid suggestion pre-seeds the answer — then, when the chosen
        conclusion differs from the current one, the **conditions** are requested via
        :meth:`ask_for_conditions` (the full conditions-only flow with the chosen conclusion as
        the target). Leaving the conclusion unset (only permitted when a current conclusion
        already stands) keeps the current conclusion and skips the conditions step.

        :param context: Everything known about the case, built by the caller — must carry a
            resolved :attr:`~CaseContext.conclusion_domain`.
        :return: The chosen conclusion and the conditions distinguishing it; ``conditions``
            is ``None`` when the expert kept the current conclusion (nothing to insert).
        """
        conclusion = self._ask_for_conclusion(context)
        if conclusion is UNSET or conclusion == context.current_conclusion:
            return RuleAnswer(conclusion=context.current_conclusion, conditions=None)
        conditions = self.ask_for_conditions(
            replace(context, target_conclusion=conclusion)
        )
        return RuleAnswer(conclusion=conclusion, conditions=conditions)

    def _ask_for_conclusion(self, context: CaseContext) -> Any:
        """
        Run the focused conclusion-only question.

        :param context: The case being labelled; must carry a resolved
            :attr:`~CaseContext.conclusion_domain`.
        :return: The chosen conclusion, or ``UNSET`` meaning "keep the current one".
        """
        domain = context.conclusion_domain
        validator = make_conclusion_validator(
            domain, allow_unset=context.has_current_conclusion
        )
        request = AnswerRequest(
            name=AnswerName.CONCLUSION,
            validate=validator,
            example=domain.example_for(AnswerName.CONCLUSION),
            default=self._suggested_conclusion(context, validator),
        )
        try:
            return self.interface.interact(context, [request])[AnswerName.CONCLUSION]
        except ExpertAbort:
            raise NoConclusionProvided(case=context.case_instance)

    def _suggested_conclusion(
        self,
        context: CaseContext,
        validator: Callable[[Any], Optional[DataclassException]],
    ) -> Any:
        """
        :param context: The case being labelled, carrying the aids to consult.
        :param validator: The conclusion validator; a suggestion is only offered when it
            validates.
        :return: The first aid suggestion that validates, else ``UNSET`` (no pre-seed).
        """
        for aid in self.aids:
            suggestion = aid.suggest(context)
            if suggestion is not None and validator(suggestion) is None:
                return suggestion
        return UNSET

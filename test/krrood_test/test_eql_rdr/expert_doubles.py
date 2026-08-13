"""
Programmatic experts the engine tests drive :class:`EQLSingleClassRDR` with.

Every double answers through :class:`FunctionInterface`, so it exercises the same build-
namespace → validate → re-prompt loop an interactive expert would; only the *collection*
step is scripted. Conditions are always live EQL expressions built over the RDR's shared
case variable, never strings.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

from typing_extensions import Any, Callable, Dict, List

from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.factories import and_
from krrood.entity_query_language.rdr.answer_vocabulary import AnswerName
from krrood.entity_query_language.rdr.expert import Expert
from krrood.entity_query_language.rdr.interface import (
    AnswerRequest,
    CaseContext,
    FunctionInterface,
)

from .animal import Animal

FEATURE_FIELDS = [
    field_.name
    for field_ in dataclasses.fields(Animal)
    if field_.name not in ("name", "species")
]
"""
Every :class:`Animal` trait column except the identifier and the predicted attribute.
"""

# %% recording the interaction


@dataclass
class ExpertCall:
    """
    One expert interaction, recorded by :class:`RecordingExpert`.
    """

    case_name: str
    """
    The ``name`` of the case the expert was asked about.
    """

    current_conclusion: Any
    """
    What the RDR concluded before the question (``...`` if no rule fired).
    """

    target_conclusion: Any
    """
    The ground-truth conclusion, or ``...`` when the expert must label the case.
    """

    requested: List[AnswerName]
    """
    The answers this interaction asked for, in order.
    """


@dataclass
class RecordingInterface(FunctionInterface):
    """
    A :class:`FunctionInterface` that records every :meth:`interact` call before
    delegating, so a test can assert which questions the engine asked and how often.
    """

    calls: List[ExpertCall] = field(init=False, default_factory=list)
    """
    The recorded interactions, oldest first.
    """

    def interact(
        self,
        context: CaseContext,
        requests: List[AnswerRequest],
        initial_errors: Any = None,
    ) -> Dict[AnswerName, Any]:
        self.calls.append(
            ExpertCall(
                case_name=context.case_instance.name,
                current_conclusion=context.current_conclusion,
                target_conclusion=context.target_conclusion,
                requested=[request.name for request in requests],
            )
        )
        return super().interact(context, requests, initial_errors=initial_errors)


def recording_expert(
    answer_function: Callable[
        [CaseContext, List[AnswerRequest]], Dict[AnswerName, Any]
    ],
) -> Expert:
    """
    Wrap ``answer_function`` in an expert whose interface records every interaction.

    :param answer_function: Supplies the answers for each request.
    :return: An expert whose ``interface.calls`` is the interaction log.
    """
    return Expert(interface=RecordingInterface(answer_function=answer_function))


# %% answer functions


def full_feature_conditions(case_variable: Any, case: Any) -> SymbolicExpression:
    """
    :param case_variable: The RDR's shared EQL variable.
    :param case: The concrete case to match.
    :return: A condition matching ``case``'s complete feature vector.
    """
    return and_(
        *[
            getattr(case_variable, name) == getattr(case, name)
            for name in FEATURE_FIELDS
        ]
    )


def maximally_specific_answer(
    context: CaseContext, requests: List[AnswerRequest]
) -> Dict[AnswerName, Any]:
    """
    Answer with the case's full feature vector, so each distinct case gets its own rule.

    :param context: The case being fitted.
    :param requests: The answers asked for; ignored, conditions are always supplied.
    :return: The conditions answer.
    """
    return {
        AnswerName.CONDITIONS: full_feature_conditions(
            context.case_variable, context.case_instance
        )
    }


def maximally_specific_expert() -> Expert:
    """
    :return: An expert whose every rule matches one case's full feature vector, so
        fitting memorises the training set.
    """
    return Expert(
        interface=FunctionInterface(answer_function=maximally_specific_answer)
    )


def labelling_answer(
    target_by_name: Dict[str, Any],
) -> Callable[[CaseContext, List[AnswerRequest]], Dict[AnswerName, Any]]:
    """
    Build the answer function for the no-target path, where the expert labels the case.

    The conclusion is supplied only when asked for, so the two-step ``ask_for_rule``
    protocol (conclusion, then conditions) is exercised as the engine drives it.

    :param target_by_name: Maps each case's ``name`` to the conclusion to label it with.
    :return: An answer function supplying the label and full-feature conditions.
    """

    def answer(
        context: CaseContext, requests: List[AnswerRequest]
    ) -> Dict[AnswerName, Any]:
        answers: Dict[AnswerName, Any] = {
            AnswerName.CONDITIONS: full_feature_conditions(
                context.case_variable, context.case_instance
            )
        }
        if any(request.name is AnswerName.CONCLUSION for request in requests):
            answers[AnswerName.CONCLUSION] = target_by_name[context.case_instance.name]
        return answers

    return answer


def labelling_expert(target_by_name: Dict[str, Any]) -> Expert:
    """
    :param target_by_name: Maps each case's ``name`` to the conclusion to label it with.
    :return: An expert that supplies both the conclusion and its conditions.
    """
    return Expert(
        interface=FunctionInterface(answer_function=labelling_answer(target_by_name))
    )


def conditions_by_target(
    conditions_for: Dict[Any, Callable[[Any], SymbolicExpression]],
) -> Callable[[CaseContext, List[AnswerRequest]], Dict[AnswerName, Any]]:
    """
    Build an answer function that looks the conditions up by the target conclusion.

    :param conditions_for: Maps a target conclusion to ``(case_variable) -> condition``.
    :return: An answer function supplying that conclusion's conditions.
    """

    def answer(
        context: CaseContext, requests: List[AnswerRequest]
    ) -> Dict[AnswerName, Any]:
        return {
            AnswerName.CONDITIONS: conditions_for[context.target_conclusion](
                context.case_variable
            )
        }

    return answer


def scripted_expert(
    conditions_for: Dict[Any, Callable[[Any], SymbolicExpression]],
) -> Expert:
    """
    :param conditions_for: Maps a target conclusion to ``(case_variable) -> condition``.
    :return: A recording expert answering from ``conditions_for``.
    """
    return recording_expert(conditions_by_target(conditions_for))

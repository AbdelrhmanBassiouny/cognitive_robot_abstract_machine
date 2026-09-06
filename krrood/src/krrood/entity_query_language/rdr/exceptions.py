"""
Exceptions raised by the EQL-RDR subsystem.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import TYPE_CHECKING, Any, Callable, List, Tuple, Type

from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.rdr.answer_vocabulary import AnswerName
from krrood.exceptions import DataclassException

if TYPE_CHECKING:
    from krrood.entity_query_language.rdr.conclusion_domain import ConclusionDomain


# %% branch-semantics dispatch


@dataclass
class AmbiguousBranchSemanticsError(DataclassException):
    """
    Two or more branch-semantics classes are equally specific for the same conclusion
    selector, so the winner would otherwise be decided by declaration order.

    Surfaced as an error so an accidental overlap is caught rather than masked.
    """

    selector: object
    """The conclusion selector node being dispatched when the collision occurred."""

    candidates: List[Type]
    """
    The equally-specific branch-semantics classes that collided.
    """

    def error_message(self) -> str:
        names = ", ".join(sorted(candidate.__name__ for candidate in self.candidates))
        return f"{names} are equally specific for {type(self.selector).__name__}."

    def suggest_correction(self) -> str:
        return (
            "Give each class a distinct ``selector``, or have one subclass the other to "
            "declare it the more-specific special case."
        )


# %% rule construction


@dataclass
class ExpertAbort(DataclassException):
    """
    Raised by
    :meth:`~krrood.entity_query_language.rdr.interface.ExpertInterface.interact` when
    the expert cancels the session.
    """

    missing: list[str]
    """The names of the still-missing required answers, so the calling
    :class:`~krrood.entity_query_language.rdr.expert.Expert` can raise its own specific
    exception."""

    def error_message(self) -> str:
        return f"Expert cancelled without supplying: {', '.join(self.missing) or '(nothing)'}"

    def suggest_correction(self) -> str:
        return ""


@dataclass
class ConclusionSelectorAsConditionError(DataclassException):
    """Raised when a
    :class:`~krrood.entity_query_language.rules.conclusion_selector.ConclusionSelector` is
    used as a rule condition."""

    condition: SymbolicExpression
    """The offending node that was passed as a condition."""

    def error_message(self) -> str:
        return f"A ConclusionSelector cannot be used as a rule condition: {self.condition!r}"

    def suggest_correction(self) -> str:
        return ""


# %% rules stated outright


@dataclass
class RulesAlreadyPresent(DataclassException):
    """
    Raised when a rule tree is stated for an RDR that already has rules.
    """

    case_type: Type
    """The type of case the RDR classifies."""

    def error_message(self) -> str:
        return (
            f"The {self.case_type.__name__} RDR already has rules, so a stated tree has "
            "nowhere to go."
        )

    def suggest_correction(self) -> str:
        return (
            "State the rules before fitting anything, or add each one with `fit_case`."
        )


@dataclass
class RulesOverAnotherCase(DataclassException):
    """
    Raised when a stated rule tree ranges over a variable other than the RDR's own case
    variable.
    """

    case_variable: Any
    """The variable the RDR classifies."""

    stated_over: Any
    """The variable the stated tree selects instead."""

    def error_message(self) -> str:
        return (
            f"The rules range over {self.stated_over!r}, but the RDR classifies "
            f"{self.case_variable!r}."
        )

    def suggest_correction(self) -> str:
        return "Write the conditions over the RDR's own `case_variable`."


# %% underspecified inference targets


@dataclass
class NoInferenceTarget(DataclassException):
    """
    Raised when an underspecified ``Match`` has no ``...`` attribute to infer.
    """

    case_type: type
    """The type whose instances were queried."""

    def error_message(self) -> str:
        return f"{self.case_type.__name__} has no underspecified (`...`) attribute to infer."

    def suggest_correction(self) -> str:
        return "Mark the attribute to infer with `...`, e.g. an(Animal)(species=...)."


@dataclass
class QueryIsNotAMatch(DataclassException):
    """
    Raised when the RDR backend is asked to answer an expression that is not a ``Match``.

    Only a ``Match`` marks an attribute with ``...``, so anything else names no attribute
    for the backend to complete.
    """

    expression: Any
    """The expression the backend was handed."""

    def error_message(self) -> str:
        return (
            f"{type(self.expression).__name__} marks no attribute with `...`, so there "
            "is nothing for an RDR to infer."
        )

    def suggest_correction(self) -> str:
        return (
            "Evaluate a match that underspecifies the attribute, e.g. "
            "an(Animal)(species=...).from_(animals)."
        )


@dataclass
class MultipleInferenceTargets(DataclassException):
    """
    Raised when a single-class RDR is handed more than one ``...`` attribute.
    """

    attribute_names: list[str]
    """The names of the attributes that were all marked with ``...``."""

    def error_message(self) -> str:
        return (
            "Single-class RDR infers one attribute, but several were underspecified: "
            f"{self.attribute_names}."
        )

    def suggest_correction(self) -> str:
        return "Use a separate RDR per attribute (or a future MultiClassRDR)."


@dataclass
class UnsupportedInferenceTarget(DataclassException):
    """
    Raised when an ``...`` attribute is an unbounded iterable.

    .. note::
        Inferring an unbounded-iterable (multi-valued) attribute is not currently
        supported; it is planned as a future feature of ``MultiClassRDR``.
    """

    case_type: type
    """The type whose instances were queried."""

    attribute_name: str
    """
    The name of the unbounded-iterable attribute that was marked with ``...``.
    """

    def error_message(self) -> str:
        return (
            f"{self.case_type.__name__}.{self.attribute_name} is an unbounded iterable; "
            "single-class RDR only infers single-valued attributes."
        )

    def suggest_correction(self) -> str:
        return "This will be supported by a future MultiClassRDR."


# %% rule-tree serialization


@dataclass
class CaseNotSerializableError(DataclassException):
    """
    Raised when a :class:`~krrood.entity_query_language.rdr.corner_case.CaseSerializer`
    cannot emit constructor source for a value.
    """

    value: Any
    """The field value that could not be serialized."""

    supported_types: Tuple[Type, ...]
    """
    The scalar types the serializer does support (``None`` and nested dataclasses are
    always supported in addition to these, so are not part of this list).
    """

    def error_message(self) -> str:
        type_names = ", ".join(t.__name__ for t in self.supported_types)
        return (
            f"Cannot serialize value of type {type(self.value).__name__!r} to Python "
            f"constructor source. Only None, {type_names} members, and nested "
            "dataclasses are supported."
        )

    def suggest_correction(self) -> str:
        return "For other types, implement a custom CaseSerializer."


@dataclass
class UnsupportedNodeForSerialization(DataclassException):
    """
    Raised when the rule-tree DAG contains a node the serializer cannot emit.
    """

    node: Any
    """
    The node (or leaf value) the serializer does not know how to emit as Python source.
    """

    def error_message(self) -> str:
        return f"Cannot serialize node of type {type(self.node).__name__!r} to Python source."

    def suggest_correction(self) -> str:
        return ""


@dataclass
class EmptyRuleTreeError(DataclassException):
    """
    Raised when serializing an RDR that has no rules yet.
    """

    def error_message(self) -> str:
        return "Cannot serialize an empty RDR (no rules have been added)."

    def suggest_correction(self) -> str:
        return "Fit at least one rule before saving."


# %% expert answers


@dataclass
class NoAnswerProvided(DataclassException):
    """
    Raised when the expert session ended (via :class:`ExpertAbort`) without supplying a
    required answer. Concrete subclasses (:class:`NoConditionsProvided`,
    :class:`NoConclusionProvided`) fix which answer.
    """

    case: Any
    """
    The case for which the answer was never supplied.
    """

    answer_name: AnswerName
    """
    Which answer (conditions or conclusion) was never supplied.
    """

    def error_message(self) -> str:
        return f"The expert cancelled without supplying `{self.answer_name}` for {self.case!r}."

    def suggest_correction(self) -> str:
        return f"Retry with an interface that can supply `{self.answer_name}`."


@dataclass
class NoConditionsProvided(NoAnswerProvided):
    """
    Raised when the expert session ended without supplying the conditions answer.
    """

    answer_name: AnswerName = field(default=AnswerName.CONDITIONS, init=False)


@dataclass
class NoConclusionProvided(NoAnswerProvided):
    """
    Raised when the expert session ended without supplying the conclusion answer.
    """

    answer_name: AnswerName = field(default=AnswerName.CONCLUSION, init=False)


@dataclass
class ConditionsRequired(DataclassException):
    """
    Raised when a conditions answer is validated while still unset.
    """

    answer_name: AnswerName
    """
    The namespace variable the expert must assign a conditions expression to.
    """

    case_variable_name: str
    """
    The shared EQL variable the conditions expression must be built over.
    """

    def error_message(self) -> str:
        return f"Assign an EQL condition to `{self.answer_name}`, built over `{self.case_variable_name}`."

    def suggest_correction(self) -> str:
        return (
            f"e.g. `{self.answer_name} = {self.case_variable_name}.some_attr == True`."
        )


@dataclass
class ConditionsNotAnExpression(DataclassException):
    """
    Raised when a conditions answer is not an EQL expression.
    """

    value: Any
    """
    The offending value the expert assigned.
    """

    answer_name: AnswerName
    """
    The namespace variable the expert must assign a conditions expression to.
    """

    case_variable_name: str
    """
    The shared EQL variable the conditions expression must be built over.
    """

    case_instance_name: str
    """
    The namespace variable bound to the concrete case (a common source of confusion).
    """

    def error_message(self) -> str:
        return (
            f"`{self.answer_name}` must be an EQL expression built over `{self.case_variable_name}` "
            f"(got {type(self.value).__name__})."
        )

    def suggest_correction(self) -> str:
        return (
            f"Did you build it over `{self.case_instance_name}` (the concrete case) instead of "
            f"`{self.case_variable_name}`?"
        )


@dataclass
class ConclusionRequired(DataclassException):
    """
    Raised when no rule fired and the expert left the conclusion answer unset.
    """

    domain: ConclusionDomain
    """
    The resolved allowable-value domain of the conclusion attribute.
    """

    answer_name: AnswerName = field(default=AnswerName.CONCLUSION, init=False)
    """
    Always the conclusion answer.
    """

    def error_message(self) -> str:
        return "No rule fired for this case."

    def suggest_correction(self) -> str:
        return f"Assign a conclusion ({self.domain.hint()})."


@dataclass
class WrongConclusionProvided(DataclassException):
    """
    Raised when a conclusion answer was supplied but violates the resolved
    :class:`ConclusionDomain` in some way. Concrete subclasses each cover one violation.
    """

    domain: ConclusionDomain
    """
    The resolved allowable-value domain of the conclusion attribute.
    """

    answer_name: AnswerName = field(default=AnswerName.CONCLUSION, init=False)
    """
    Always the conclusion answer.
    """


@dataclass
class ConclusionMayNotBeNone(WrongConclusionProvided):
    """
    Raised when a conclusion answer is ``None`` but the declared type does not admit it.
    """

    def error_message(self) -> str:
        return "The conclusion may not be None."

    def suggest_correction(self) -> str:
        return f"Set {self.domain.hint()}."


@dataclass
class ConclusionNotInDomain(WrongConclusionProvided):
    """
    Raised when a conclusion answer is not one of the domain's enumerable members.
    """

    value: Any
    """
    The offending value the expert assigned.
    """

    def error_message(self) -> str:
        return f"The conclusion must be one of: {self.domain.display()} (got {self.value!r})."

    def suggest_correction(self) -> str:
        return f"Choose a value from the conclusion domain: {self.domain.display()}."


@dataclass
class ConclusionWrongType(WrongConclusionProvided):
    """
    Raised when a conclusion answer is not an instance of the domain's expected type(s).
    """

    value: Any
    """
    The offending value the expert assigned.
    """

    def error_message(self) -> str:
        return (
            f"The conclusion must be a {self.domain.type_display} "
            f"(got {type(self.value).__name__})."
        )

    def suggest_correction(self) -> str:
        return f"Provide a {self.domain.type_display}."


# %% fitting


@dataclass
class ExpertRequired(DataclassException):
    """
    Raised when a case needs a new rule but no expert was supplied to author it.
    """

    case: Any
    """
    The case that could not be fitted.
    """

    def error_message(self) -> str:
        return f"No expert was supplied to author a rule for {self.case!r}."

    def suggest_correction(self) -> str:
        return "Pass an `Expert` to `fit_case`/`fit`, or fit only cases the rule tree already classifies correctly."


@dataclass
class RDRDidNotConvergeError(DataclassException):
    """
    Raised when the fitting loop stops because the misclassified-case set repeated,
    meaning the rule tree oscillates instead of converging.
    """

    clashing_cases: List[Any]
    """
    The cases still misclassified when the repeat was detected.
    """

    passes: int
    """
    How many passes had completed at that point.
    """

    def error_message(self) -> str:
        cases = ", ".join(repr(case) for case in self.clashing_cases)
        return f"Fitting stopped after {self.passes} pass(es) without converging. Clashing cases: {cases}."

    def suggest_correction(self) -> str:
        return (
            "Supply conditions that distinguish the clashing cases from each other; a condition "
            "shared by all of them lets every new rule intercept the previously fitted case."
        )


@dataclass
class ConditionsNotInsertable(DataclassException):
    """
    Raised when a conditions answer is a well-formed expression that still cannot become
    a rule, because it is the node the new rule would be anchored on.
    """

    anchor: SymbolicExpression
    """
    The condition node the new rule would have been spliced beneath.
    """

    answer_name: AnswerName = field(default=AnswerName.CONDITIONS, init=False)
    """
    Names the conditions answer, so a re-prompt can attribute the failure to it.
    """

    def error_message(self) -> str:
        return f"The conditions are the rule's own anchor {self.anchor!r}, so the rule would refine itself."

    def suggest_correction(self) -> str:
        return "Give a condition that distinguishes this case from the one the anchored rule was written for."


# %% the model file on disk


@dataclass
class ModelFileMissing(DataclassException):
    """
    Raised when a decorated function's model file is read before anything wrote it.
    """

    function: Callable
    """
    The decorated function whose model was being read.
    """

    path: str
    """
    Where the model file was expected.
    """

    def error_message(self) -> str:
        return f"No model file for {self.function.__name__!r} at {self.path!r}."

    def suggest_correction(self) -> str:
        return (
            "Fit the function's RDR first; saving a fit is what writes the model file."
        )

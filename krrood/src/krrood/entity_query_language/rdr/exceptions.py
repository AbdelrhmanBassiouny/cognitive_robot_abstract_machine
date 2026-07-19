"""Exceptions raised by the EQL-native RDR engine."""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Any, Tuple, Type

from krrood.exceptions import DataclassException


@dataclass
class NoInferenceTarget(DataclassException):
    """Raised when an underspecified ``Match`` has no ``...`` attribute to infer."""

    case_type: type
    """The type whose instances were queried."""

    def error_message(self) -> str:
        return f"{self.case_type.__name__} has no underspecified (`...`) attribute to infer."

    def suggest_correction(self) -> str:
        return "Mark the attribute to infer with `...`, e.g. an(Animal)(species=...)."


@dataclass
class MultipleInferenceTargets(DataclassException):
    """Raised when a single-class RDR is handed more than one ``...`` attribute."""

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
    """The name of the unbounded-iterable attribute that was marked with ``...``."""

    def error_message(self) -> str:
        return (
            f"{self.case_type.__name__}.{self.attribute_name} is an unbounded iterable; "
            "single-class RDR only infers single-valued attributes."
        )

    def suggest_correction(self) -> str:
        return "This will be supported by a future MultiClassRDR."


@dataclass
class CaseNotSerializableError(DataclassException):
    """Raised when a :class:`~krrood.entity_query_language.rdr.corner_case.CaseSerializer`
    cannot emit constructor source for a value."""

    value: Any
    """The field value that could not be serialized."""

    supported_types: Tuple[Type, ...]
    """The scalar types the serializer does support (``None`` and nested dataclasses are
    always supported in addition to these, so are not part of this list)."""

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
    """Raised when the rule-tree DAG contains a node the serializer cannot emit."""

    node: Any
    """The node (or leaf value) the serializer does not know how to emit as Python source."""

    def error_message(self) -> str:
        return f"Cannot serialize node of type {type(self.node).__name__!r} to Python source."

    def suggest_correction(self) -> str:
        return ""


@dataclass
class NoConclusionToExplainError(DataclassException):
    """Raised when a why-question is asked about a case for which no rule fired."""

    case: Any
    """The case that produced no conclusion, so there is nothing to explain."""

    def error_message(self) -> str:
        return f"No rule fired for {self.case!r}, so there is no conclusion to explain."

    def suggest_correction(self) -> str:
        return "Fit a rule that classifies this case before asking why it was concluded."


@dataclass
class EmptyRuleTreeError(DataclassException):
    """Raised when serializing an RDR that has no rules yet."""

    def error_message(self) -> str:
        return "Cannot serialize an empty RDR (no rules have been added)."

    def suggest_correction(self) -> str:
        return "Fit at least one rule before saving."

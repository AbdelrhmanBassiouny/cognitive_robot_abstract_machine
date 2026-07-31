"""
Sentinel value and shared namespace vocabulary for the EQL-RDR subsystem.

Lives below :mod:`~krrood.entity_query_language.rdr.interface` and
:mod:`~krrood.entity_query_language.rdr.exceptions` in the dependency graph, so both can
share this module's names (:class:`AnswerName`, :class:`NamespaceName`) without either
depending on the other.
"""

from __future__ import annotations

from enum import Enum, StrEnum


class _Unset(Enum):
    """
    Sentinel enum for a missing current/target conclusion.

    A single-member enum yields a hashable, identity-stable sentinel (compared with ``is
    UNSET``) without a hand-rolled singleton class. The type is private; only the
    :data:`UNSET` member is part of the public interface.
    """

    UNSET = "unset"
    """
    The sole sentinel member, exported module-wide as :data:`UNSET`.
    """

    def __repr__(self) -> str:
        return "UNSET"

    def __str__(self) -> str:
        return "UNSET"


UNSET: _Unset = _Unset.UNSET
"""
Sentinel for "no current/target conclusion was supplied" (e.g. the ask-for-rule path).
"""


class NamespaceName(StrEnum):
    """
    Reserved shell-namespace variable names the expert interaction loop injects,
    distinct from the answers the expert is asked to assign (see :class:`AnswerName`).

    Lives here rather than on
    :class:`~krrood.entity_query_language.rdr.interface.ExpertInterface` because
    :attr:`AnswerName.example_assignment` below is built over :attr:`CASE_VARIABLE`.
    """

    CASE_VARIABLE = "case_variable"
    """Shell name bound to the shared EQL variable (author: ``case_variable.milk == True``)."""

    CASE_INSTANCE = "case_instance"
    """Shell name bound to the concrete case (inspect/experiment: ``case_instance.milk``)."""

    EXIT = "exit"
    """Shell name of the zero-arg callable the expert calls to leave without answering."""

    ABORT_FLAG = "__expert_abort__"
    """Private flag set by calling :attr:`EXIT`; checked by the expert interaction loop."""


class AnswerName(StrEnum):
    """
    The namespace-variable names an
    :class:`~krrood.entity_query_language.rdr.expert.Expert` asks the expert to assign.
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
        return f"{self} = {NamespaceName.CASE_VARIABLE}.some_attr == True"

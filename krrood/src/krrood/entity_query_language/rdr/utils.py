"""
Sentinel value and shared namespace vocabulary for the EQL-RDR subsystem.

Lives below :mod:`~krrood.entity_query_language.rdr.interface` and
:mod:`~krrood.entity_query_language.rdr.exceptions` in the dependency graph, so both can
share this module's names (:class:`AnswerName`, :data:`CASE_VARIABLE_NAME`,
:data:`CASE_INSTANCE_NAME`) without either depending on the other.
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

#: Shell name bound to the shared EQL variable (author: ``case_variable.milk == True``).
CASE_VARIABLE_NAME = "case_variable"

#: Shell name bound to the concrete case (inspect/experiment: ``case_instance.milk``).
CASE_INSTANCE_NAME = "case_instance"


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
        return f"{self} = {CASE_VARIABLE_NAME}.some_attr == True"

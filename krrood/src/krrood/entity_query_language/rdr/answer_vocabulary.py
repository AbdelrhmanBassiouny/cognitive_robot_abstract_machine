"""
The reserved names the expert interaction loop speaks in: the answers an expert is asked
to assign, and the shell-namespace variables those answers are authored against.

Lives below :mod:`~krrood.entity_query_language.rdr.interface` and
:mod:`~krrood.entity_query_language.rdr.exceptions` in the dependency graph, so both can
share these names without either depending on the other. The two enums stay together in one
module because :attr:`AnswerName.example_assignment` is built over
:attr:`NamespaceName.CASE_VARIABLE`.
"""

from __future__ import annotations

from enum import StrEnum


class NamespaceName(StrEnum):
    """
    Reserved shell-namespace variable names the expert interaction loop injects,
    distinct from the answers the expert is asked to assign (see :class:`AnswerName`).
    """

    CASE_VARIABLE = "case_variable"
    """
    Shell name bound to the shared EQL variable (author: ``case_variable.milk ==
    True``).
    """

    CASE_INSTANCE = "case_instance"
    """
    Shell name bound to the concrete case (inspect/experiment: ``case_instance.milk``).
    """

    EXIT = "exit"
    """
    Shell name of the zero-arg callable the expert calls to leave without answering.
    """

    ABORT_FLAG = "__expert_abort__"
    """
    Private flag set by calling :attr:`EXIT`; checked by the expert interaction loop.
    """


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
        """:return: A copy-pasteable example assignment for this answer name."""
        return f"{self} = {NamespaceName.CASE_VARIABLE}.some_attr == True"

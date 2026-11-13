"""
Tests for the answer magics — ``%conclusion`` and ``%conditions`` — which assign an
expression to their answer variable, validate it, and leave the shell in one step.

Exercised against a shell stub rather than a real IPython shell, so the magic's own
contract is what is under test.
"""

from __future__ import annotations

import contextlib
import io
import unittest

from krrood.entity_query_language.rdr.answer_vocabulary import AnswerName
from krrood.entity_query_language.rdr.conclusion_domain import (
    resolve_conclusion_domain,
)
from krrood.entity_query_language.rdr.exceptions import ConclusionRequired
from krrood.entity_query_language.rdr.interactive import IPythonInterface
from krrood.entity_query_language.rdr.magics import AssignAndExitMagic

from .animal import Animal, Species


def _make_palette():
    """
    :return: A no-colour palette, so assertions read the text and not the escapes.
    """
    return IPythonInterface(use_color=False).palette


def _rejected_conclusion() -> ConclusionRequired:
    """
    :return: The error a real validator produces for a conclusion it will not accept.
    """
    return ConclusionRequired(domain=resolve_conclusion_domain(Animal, "species"))


class _FakeShell:
    """
    Minimal shell stub, so the magic can be exercised without a real IPython shell.
    """

    def __init__(self):
        """
        Start with neither a forced exit nor an exit request recorded.
        """
        self._force_exit = False
        """
        Whether the magic forced the shell to leave.
        """
        self._exit_called = False
        """
        Whether :meth:`ask_exit` was called.
        """

    def ask_exit(self):
        """
        Record that the shell was asked to leave.
        """
        self._exit_called = True


class TestAssignExitMagic(unittest.TestCase):
    """
    :class:`AssignAndExitMagic` assigns its argument, validates it, and exits.
    """

    def _make_namespace_and_shell(self):
        """:return: An empty namespace paired with a fresh shell stub."""
        namespace = {}
        shell = _FakeShell()
        return namespace, shell

    def test_valid_input_sets_variable_in_namespace(self):
        """
        A valid expression is evaluated and the target name is set in the namespace.
        """
        namespace, shell = self._make_namespace_and_shell()

        def validate():
            """:return: The answers that failed validation."""
            return []

        magic = AssignAndExitMagic(
            palette=_make_palette(),
            answer_name=AnswerName.CONCLUSION,
            shell=shell,
            namespace=namespace,
            validate=validate,
        )
        magic.run("42")
        self.assertIn(AnswerName.CONCLUSION, namespace)
        self.assertEqual(namespace[AnswerName.CONCLUSION], 42)

    def test_valid_input_sets_force_exit_true(self):
        """
        A valid expression causes _force_exit to be set to True on the shell.
        """
        namespace, shell = self._make_namespace_and_shell()

        def validate():
            """:return: The answers that failed validation."""
            return []

        magic = AssignAndExitMagic(
            palette=_make_palette(),
            answer_name=AnswerName.CONCLUSION,
            shell=shell,
            namespace=namespace,
            validate=validate,
        )
        magic.run("42")
        self.assertTrue(shell._force_exit)

    def test_valid_input_calls_ask_exit(self):
        """
        A valid expression causes ask_exit() to be called on the shell.
        """
        namespace, shell = self._make_namespace_and_shell()

        def validate():
            """:return: The answers that failed validation."""
            return []

        magic = AssignAndExitMagic(
            palette=_make_palette(),
            answer_name=AnswerName.CONCLUSION,
            shell=shell,
            namespace=namespace,
            validate=validate,
        )
        magic.run("42")
        self.assertTrue(shell._exit_called)

    def test_invalid_input_does_not_set_force_exit(self):
        """
        When validate() returns an error dict for the target name, _force_exit stays
        False.
        """
        namespace, shell = self._make_namespace_and_shell()

        def validate():
            """:return: The answers that failed validation."""
            return [_rejected_conclusion()]

        magic = AssignAndExitMagic(
            palette=_make_palette(),
            answer_name=AnswerName.CONCLUSION,
            shell=shell,
            namespace=namespace,
            validate=validate,
        )
        with contextlib.redirect_stdout(io.StringIO()):
            magic.run("99")

        self.assertFalse(shell._force_exit)

    def test_invalid_input_does_not_call_ask_exit(self):
        """
        When validate() returns an error, ask_exit is NOT called.
        """
        namespace, shell = self._make_namespace_and_shell()

        def validate():
            """:return: The answers that failed validation."""
            return [_rejected_conclusion()]

        magic = AssignAndExitMagic(
            palette=_make_palette(),
            answer_name=AnswerName.CONCLUSION,
            shell=shell,
            namespace=namespace,
            validate=validate,
        )
        with contextlib.redirect_stdout(io.StringIO()):
            magic.run("99")

        self.assertFalse(shell._exit_called)

    def test_unevaluatable_expression_does_not_exit(self):
        """
        A syntax-error expression causes no exit: _force_exit stays False.
        """
        namespace, shell = self._make_namespace_and_shell()

        def validate():
            """:return: The answers that failed validation."""
            return []

        magic = AssignAndExitMagic(
            palette=_make_palette(),
            answer_name=AnswerName.CONCLUSION,
            shell=shell,
            namespace=namespace,
            validate=validate,
        )
        with contextlib.redirect_stdout(io.StringIO()):
            magic.run("this is not valid python !!!!")

        self.assertFalse(shell._force_exit)

    def test_magic_can_reference_existing_namespace_names(self):
        """
        An expression referencing a name already in namespace resolves correctly.
        """
        namespace = {"Species": Species}
        shell = _FakeShell()

        def validate():
            """:return: The answers that failed validation."""
            return []

        magic = AssignAndExitMagic(
            palette=_make_palette(),
            answer_name=AnswerName.CONCLUSION,
            shell=shell,
            namespace=namespace,
            validate=validate,
        )
        magic.run("Species.mammal")
        self.assertEqual(namespace[AnswerName.CONCLUSION], Species.mammal)


if __name__ == "__main__":
    unittest.main()

"""
Tests for which magics a session offers the expert, and how each one is registered.

The real embedded shell only opens at a terminal, so the selection and the registration
call are exercised here against a shell stub instead.
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass, field

from typing_extensions import Any, Dict, List, Tuple

from krrood.entity_query_language.rdr.answer_vocabulary import AnswerName
from krrood.entity_query_language.rdr.interactive import IPythonInterface
from krrood.entity_query_language.rdr.magics import (
    AssignAndExitMagic,
    HelpMagic,
    HelperMagic,
    MagicKind,
    MagicName,
    NamespaceKey,
    RuleTreeMagic,
    SaveModelMagic,
    SufficientConditionsMagic,
)
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR

from .animal import Animal


@dataclass
class RegisteringShell:
    """
    Records what was registered into it, in place of a real IPython shell.
    """

    registered: List[Tuple[str, str]] = field(default_factory=list)
    """
    One ``(magic_name, magic_kind)`` pair per registration, in registration order.
    """

    def register_magic_function(
        self, function: Any, magic_kind: str, magic_name: str
    ) -> None:
        """
        :param function: The callable the shell would invoke.
        :param magic_kind: The kind of magic being registered.
        :param magic_name: The name the expert would invoke it by.
        """
        self.registered.append((magic_name, magic_kind))


def _no_errors() -> List[Any]:
    """
    :return: An empty failure list, standing in for a validator that accepts everything.
    """
    return []


def _magics_for(namespace: Dict[str, Any]) -> List[Any]:
    """
    :param namespace: The interaction namespace the selection is made from.
    :return: The magics an interface would offer for that namespace.
    """
    interface = IPythonInterface(use_color=False)
    return interface._magics(RegisteringShell(), namespace, _no_errors)


# %% which magics a namespace earns


class TestMagicSelection(unittest.TestCase):
    """
    What the namespace holds decides which magics there is anything to offer.
    """

    def test_save_is_offered_even_with_nothing_else_in_the_namespace(self):
        """
        ``%save`` is unconditional — it prints its own hint when no model is attached.
        """
        magics = _magics_for({})

        self.assertEqual([type(magic) for magic in magics], [SaveModelMagic])

    def test_each_renderer_in_the_namespace_earns_its_magic(self):
        """
        A renderer the question has is offered; one it does not have is not.
        """
        magics = _magics_for(
            {
                NamespaceKey.RULE_TREE_TEXT: lambda: "tree",
                NamespaceKey.HELP_TEXT: lambda: "help",
            }
        )

        self.assertEqual(
            [type(magic) for magic in magics],
            [SaveModelMagic, RuleTreeMagic, HelpMagic],
        )

    def test_helper_magic_is_offered_when_a_helper_has_something_to_say(self):
        """
        The helper renderer is seeded only when a helper presents material.
        """
        magics = _magics_for({NamespaceKey.HELPER_TEXT: lambda: "helper"})

        self.assertEqual(
            [type(magic) for magic in magics], [SaveModelMagic, HelperMagic]
        )

    def test_an_answer_in_flight_earns_its_assign_and_exit_magic(self):
        """
        Each answer pre-seeded into the namespace gets the magic that assigns it.
        """
        magics = _magics_for({AnswerName.CONDITIONS: ...})

        assign_magics = [
            magic for magic in magics if isinstance(magic, AssignAndExitMagic)
        ]
        self.assertEqual(
            [magic.answer_name for magic in assign_magics], [AnswerName.CONDITIONS]
        )

    def test_both_answers_in_flight_earn_both_magics(self):
        """
        Asking for a conclusion and conditions offers a magic for each.
        """
        magics = _magics_for({AnswerName.CONCLUSION: ..., AnswerName.CONDITIONS: ...})

        assign_magics = [
            magic for magic in magics if isinstance(magic, AssignAndExitMagic)
        ]
        self.assertEqual(
            [magic.answer_name for magic in assign_magics],
            [AnswerName.CONCLUSION, AnswerName.CONDITIONS],
        )

    def test_sufficient_conditions_is_offered_only_with_an_rdr_in_the_namespace(self):
        """
        The backward-inference magic needs a rule tree to query.
        """
        without_rdr = _magics_for({})
        with_rdr = _magics_for(
            {NamespaceKey.SUFFICIENT_CONDITIONS: EQLSingleClassRDR(Animal, "species")}
        )

        self.assertNotIn(
            SufficientConditionsMagic, [type(magic) for magic in without_rdr]
        )
        self.assertIn(SufficientConditionsMagic, [type(magic) for magic in with_rdr])


# %% how a magic reaches the shell


class TestMagicRegistration(unittest.TestCase):
    """
    A magic registers itself under its own name, as a line magic.
    """

    def test_a_magic_registers_under_its_own_name_as_a_line_magic(self):
        """
        The shell is told the magic's name and kind, not a literal spelled at the call
        site.
        """
        shell = RegisteringShell()

        SaveModelMagic(
            palette=IPythonInterface(use_color=False).palette,
            interface=IPythonInterface(),
        ).register(shell)

        self.assertEqual(shell.registered, [(MagicName.SAVE, MagicKind.LINE)])

    def test_every_offered_magic_registers_under_a_distinct_name(self):
        """
        A full namespace offers each magic once, and no two share a name.
        """
        shell = RegisteringShell()
        namespace = {
            NamespaceKey.RULE_TREE_TEXT: lambda: "tree",
            NamespaceKey.HELP_TEXT: lambda: "help",
            NamespaceKey.HELPER_TEXT: lambda: "helper",
            NamespaceKey.SUFFICIENT_CONDITIONS: EQLSingleClassRDR(Animal, "species"),
            AnswerName.CONCLUSION: ...,
            AnswerName.CONDITIONS: ...,
        }

        for magic in _magics_for(namespace):
            magic.register(shell)

        registered_names = [name for name, _ in shell.registered]
        self.assertEqual(
            sorted(registered_names),
            sorted(
                [
                    MagicName.SAVE,
                    MagicName.SHOW_TREE,
                    MagicName.HELP,
                    MagicName.HELPER,
                    MagicName.CONCLUSION,
                    MagicName.CONDITIONS,
                    MagicName.SUFFICIENT_CONDITIONS_FOR,
                ]
            ),
        )


if __name__ == "__main__":
    unittest.main()

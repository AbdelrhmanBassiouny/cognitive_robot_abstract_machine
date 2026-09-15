"""
Tests for :mod:`bastler.command_line`, the command base and registry both the
maintenance executor's and the plan-item bootstrap's own command classes are built from.
"""

from __future__ import annotations

import argparse

import pytest

from bastler.command_line import Command, commands_of


def test_every_subclass_is_reachable_in_the_order_it_was_defined():
    """
    The registry is what a parser is built from, so a command that exists but is
    unreachable should not be expressible - and the order is the order a reader sees in
    ``--help``.

    Asked of a tool's own base rather than of :class:`Command`, whose direct subclasses
    are the tool bases themselves.
    """

    class ExampleTool(Command):
        """The base one tool's commands are defined under."""

    class SecondCommand(ExampleTool):
        """Defined first, so it is expected first."""

        @property
        def invoked_as(self) -> str:
            """:return: The word selecting it."""
            return "second"

        @property
        def description(self) -> str:
            """:return: What it does."""
            return "defined first"

    class FirstCommand(ExampleTool):
        """Defined second, to prove the order is definition order rather than sorted."""

        @property
        def invoked_as(self) -> str:
            """:return: The word selecting it."""
            return "first"

        @property
        def description(self) -> str:
            """:return: What it does."""
            return "defined second"

    assert [command.invoked_as for command in commands_of(ExampleTool)] == [
        "second",
        "first",
    ]


def test_a_command_that_says_neither_what_it_is_called_nor_what_it_does_is_refused():
    """
    Both are abstract, and the registry builds every subclass - so the refusal lands as
    the caller's module is imported rather than when someone invokes the command.
    """

    class CommandWithoutAName(Command):
        """A command that never says what it is called."""

    with pytest.raises(TypeError, match="invoked_as"):
        CommandWithoutAName()


def test_a_command_declares_no_flags_unless_it_has_some():
    """
    Concrete rather than abstract: most commands take none, and requiring an empty
    override of every one of them would say nothing.
    """

    class CommandWithoutFlags(Command):
        """A command taking no flags of its own."""

        @property
        def invoked_as(self) -> str:
            """:return: The word selecting it."""
            return "flagless"

        @property
        def description(self) -> str:
            """:return: What it does."""
            return "takes nothing"

    parser = argparse.ArgumentParser()
    CommandWithoutFlags().declare_arguments(parser)

    assert parser.parse_args([]) == argparse.Namespace()

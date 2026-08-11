"""
One command of a command-line tool, and the registry that finds every one of them.

A command that exists should be reachable, and a command that cannot say what it is
called should not be expressible. Both follow from the command being a class: the
registry is built from the subclasses, so nothing has to be listed twice, and the name
and description are abstract, so a subclass supplying neither is refused as its module
is imported.

Deliberately says nothing about ``run``. What a command is handed and what it answers
with differ per tool, so each declares its own.
"""

from __future__ import annotations

import argparse
from abc import ABC, abstractmethod
from typing import TypeVar

CommandSubclass = TypeVar("CommandSubclass", bound="Command")
"""
The concrete command type a caller's own registry is built from.
"""


class Command(ABC):
    """
    One operation a command-line tool offers, owning its own name, help and flags.

    Not a dataclass, so a caller is free to make its own commands frozen dataclasses or
    plain classes - a frozen base would force every subclass to be frozen too.
    """

    @property
    @abstractmethod
    def invoked_as(self) -> str:
        """
        The word that selects this command on the command line.
        """

    @property
    @abstractmethod
    def description(self) -> str:
        """
        What it does, as ``--help`` puts it.
        """

    def declare_arguments(self, parser: argparse.ArgumentParser) -> None:
        """
        Declare this command's own flags.

        Concrete rather than abstract: most commands take none, and requiring an empty
        override of every one of them would say nothing.

        :param parser: The subparser to declare them on.
        """


def commands_of(base: type[CommandSubclass]) -> tuple[CommandSubclass, ...]:
    """
    Build every command defined under *base*, in the order they are defined.

    Found from the subclasses rather than from a list beside them, so a command cannot
    exist without being reachable. Instantiating here is also what makes the refusal
    land: a subclass that named neither itself nor what it does is abstract, so it
    raises as the caller's module is imported rather than when someone invokes it.

    Ask this of the tool's own base, never of :class:`Command` - only direct subclasses
    are found, and :class:`Command`'s are the tool bases themselves, which are abstract.

    :param base: The command class of the tool being built.
    :return: One instance of each of its direct subclasses, in definition order.
    :raises TypeError: If any of them is still abstract.
    """
    return tuple(subclass() for subclass in base.__subclasses__())

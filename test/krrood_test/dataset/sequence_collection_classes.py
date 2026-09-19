"""
Classes used to verify that ORMatic can persist and reconstruct a ``Sequence``-valued
many-to-many relationship (a field typed as ``Sequence[SomeMappedClass]``).

Kept in their own module so the generated interface can import them by name.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Sequence


@dataclass(frozen=True)
class SequenceCollectionMember:
    """
    A flat value object referenced from a sequence-valued collection field.
    """

    label: str
    """
    The label of the member.
    """


@dataclass
class SequenceCollectionOwner:
    """
    An object whose collection of mapped members is declared as the abstract
    ``Sequence`` rather than as a concrete container.
    """

    members: Sequence[SequenceCollectionMember] = ()
    """
    The members of the owner, in the order they were given.
    """

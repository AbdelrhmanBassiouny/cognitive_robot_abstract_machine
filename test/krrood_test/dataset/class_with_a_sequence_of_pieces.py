"""
A class whose field is annotated with the typing alias its own module imports.

The module deliberately imports ``Sequence`` from ``typing_extensions``, so what the
annotation means is settled here rather than by whatever else in a class diagram
answers to that name.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Sequence


@dataclass
class Piece:
    """
    One of the things the sequence holds.
    """

    name: str = ""
    """
    What this piece is called.
    """


@dataclass
class ClassWithASequenceOfPieces:
    """
    A class holding several pieces in the order they were given.
    """

    pieces: Sequence[Piece] = ()
    """
    The pieces, in order.
    """

"""
A pattern-named *decision object* mimic for the decision-query pattern.

A decision is a partially-specified object whose ``...`` attribute is filled by
evaluating it with a reasoning backend. :class:`SlotAssignment` stands for that pattern
(not for any concrete external action): ``chosen`` is the underspecified slot an RDR
backend fills, and the object's other fields are the features the choice is made from.

Deliberately ordinary: a plain dataclass with an enum-valued decision attribute, so an
RDR concludes one :class:`Slot` per assignment exactly as it concludes a species per
animal.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from typing_extensions import Optional


class Slot(enum.Enum):
    """
    The mutually-exclusive slots a shape can be assigned to.
    """

    left = 1
    right = 2
    center = 3

    def __repr__(self) -> str:
        return f"Slot.{self.name}"


@dataclass
class SlotAssignment:
    """
    A shape awaiting a slot decision.

    ``chosen`` is ``None`` until a backend fills it; it is the attribute a decision
    query marks with ``...``.
    """

    shape: str
    """
    The shape being placed (the feature the decision is made from).
    """

    heavy: bool = False
    """
    Whether the shape is heavy (a second decision feature).
    """

    chosen: Optional[Slot] = None
    """
    The slot decided for this shape; the underspecified (``...``) decision attribute.
    """

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import List, Optional

from krrood.entity_query_language.core.mapped_variable import (
    Attribute,
    Call,
    FlatVariable,
    Index,
    MappedVariable,
)
from krrood.entity_query_language.verbalization import morphology
from krrood.entity_query_language.verbalization.fragments.source_reference import (
    SourceReference,
)


@dataclass(frozen=True)
class PathStep:
    """
    One hop of a navigation chain — a display name and the source reference it links to.

    Replaces a bare ``(name, source_reference)`` tuple so the two halves are named (``.name`` /
    ``.source_reference``) rather than positional.
    """

    name: str
    """The display text for this hop (e.g. ``"amount"``, ``"handle[0]"``, ``"()"``)."""

    source_reference: Optional[SourceReference] = None
    """The attribute's source reference, or ``None`` for composite / index / call hops."""


def build_path_parts(chain: List[MappedVariable]) -> List[PathStep]:
    """
    Convert a walked chain into :class:`PathStep` hops.

    Hop rules:

    * ``Attribute`` nodes appear as the attribute name, linked to their source reference.
    * Integer ``Index`` nodes appear as their ordinal word (``0`` → ``"first"``) with no source
      reference, so the possessive path reads *"the first of the tasks of …"* rather than leaking a
      raw subscript (``"tasks[0]"``). Non-integer keys keep the ``"[key]"`` bracket form.
    * ``Call`` nodes appear as ``"()"`` with no source reference.
    * ``FlatVariable`` nodes are skipped.

    :param chain: Innermost-first chain list (nearest the root first).
    :return: Ordered list of :class:`PathStep`, innermost hop first.
    """
    parts: List[PathStep] = []
    for node in chain:
        if isinstance(node, Attribute):
            owner = node._owner_class_
            name = node._attribute_name_
            parts.append(PathStep(name, SourceReference.for_attribute(owner, name)))
        elif isinstance(node, Index):
            parts.append(_index_step(node._key_))
        elif isinstance(node, Call):
            parts.append(PathStep("()", None))
        elif isinstance(node, FlatVariable):
            pass
    return parts


def _index_step(key: object) -> PathStep:
    """:return: An ordinal hop (*"first"*) for an integer *key*, else the bracketed *"[key]"* form."""
    if isinstance(key, int) and not isinstance(key, bool):
        return PathStep(morphology.ordinal(key), None)
    return PathStep(f"[{repr(key)}]", None)

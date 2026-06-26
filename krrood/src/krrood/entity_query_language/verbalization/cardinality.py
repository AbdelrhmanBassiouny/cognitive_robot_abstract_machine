"""How many values a selected column yields per entity — the semantic *number* feature.

A grouped report (``For each period, report …``) collects each non-aggregate column into a list per
group, but how that column reads depends on its cardinality *per entity*:

* a **scalar** attribute (``p.revenue.total`` — ``Money``, reached by a one-to-one path) yields one
  value per statement, so it reads singular: *"the total of the revenue"*;
* a column whose path crosses a **collection** (``p.line_items`` — ``List[…]``) yields many values
  per statement, so it reads as a quantified plural: *"all the line items"*.

This is the reliable, structural half of the cardinality question (the per-entity count); the
per-group count — how many entities share a key value — is a data/constraint property the schema does
not encode, so it is deliberately not inferred here. The collection check reuses krrood's own
forward-ref-tolerant type resolution (:func:`get_type_hints_of_object`), so a new collection type is
handled by the origin test, never by a special case (OCP).
"""

from __future__ import annotations

import enum
import inspect
import typing

from typing_extensions import Optional, Type

from krrood.class_diagrams.utils import get_type_hints_of_object
from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.core.expression_structure import walk_chain
from krrood.entity_query_language.core.mapped_variable import Attribute

#: The generic origins that mark a field as holding *many* values (a collection).
_COLLECTION_ORIGINS = frozenset({list, set, frozenset, tuple})


class Cardinality(enum.Enum):
    """How many values an expression yields per entity."""

    ONE = enum.auto()
    """A single value per entity — a scalar attribute reached by a one-to-one path."""

    MANY = enum.auto()
    """Many values per entity — the path crosses (or ends in) a collection."""

    @property
    def number(self) -> "Number":
        """:return: the grammatical number this cardinality realises — plural for many, else singular.

        >>> Cardinality.MANY.number.name
        'PLURAL'
        >>> Cardinality.ONE.number.name
        'SINGULAR'
        """
        from krrood.entity_query_language.verbalization.fragments.features import Number

        return Number.PLURAL if self is Cardinality.MANY else Number.SINGULAR


def _resolved_attribute_type(owner: Type, attribute_name: str) -> Optional[object]:
    """:return: the resolved type of ``owner.attribute_name`` — a dataclass field's annotation, a
    property's or method's return annotation — or ``None`` when it cannot be determined (then read as
    a scalar, the safe default that never over-quantifies with *"all"*)."""
    field_hints = get_type_hints_of_object(owner)
    if attribute_name in field_hints:
        return field_hints[attribute_name]
    member = inspect.getattr_static(owner, attribute_name, None)
    function = member.fget if isinstance(member, property) else member
    if not callable(function):
        return None
    return typing.get_type_hints(function).get("return")


def _is_collection_type(type_hint: object) -> bool:
    """:return: whether *type_hint* is a collection (its origin is a list/set/tuple), looking through
    an ``Optional`` so ``Optional[List[X]]`` still counts.

    >>> from typing import List, Optional, Set
    >>> _is_collection_type(List[int])
    True
    >>> _is_collection_type(Optional[Set[int]])
    True
    >>> _is_collection_type(int)
    False
    """
    origin = typing.get_origin(type_hint)
    if origin is typing.Union:
        present = [arg for arg in typing.get_args(type_hint) if arg is not type(None)]
        origin = typing.get_origin(present[0]) if len(present) == 1 else origin
    return origin in _COLLECTION_ORIGINS


def column_cardinality(column: SymbolicExpression) -> Cardinality:
    """:return: ``ONE`` when *column* is a scalar attribute reached by a one-to-one path (one value
    per entity, read distributively — *"the total of the revenue"*), else ``MANY``: an attribute path
    that crosses a collection (*"all the tasks"*) or a bare entity variable (the grouped *population*
    — *"all Employees"*).

    >>> from krrood.entity_query_language.factories import variable
    >>> from krrood.entity_query_language.verbalization.example_domain import Robot, Worker
    >>> column_cardinality(variable(Robot, []).battery).name   # a scalar attribute
    'ONE'
    >>> column_cardinality(variable(Worker, []).tasks).name    # a List[...] field
    'MANY'
    >>> column_cardinality(variable(Worker, []).tasks.name).name  # past the collection
    'MANY'
    >>> column_cardinality(variable(Worker, [])).name          # the bare entity (population)
    'MANY'
    """
    if not isinstance(column, Attribute):
        return Cardinality.MANY
    chain, _ = walk_chain(column)
    for hop in chain:
        if _is_collection_type(_resolved_attribute_type(hop._owner_class_, hop._attribute_name_)):
            return Cardinality.MANY
    return Cardinality.ONE

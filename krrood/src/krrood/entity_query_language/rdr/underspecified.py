"""
Adapter from an underspecified EQL ``Match`` to RDR attribute inference.

An underspecified query marks the attributes to infer with ``...`` (Ellipsis) and may
carry concrete attribute constraints plus a domain of instances, e.g.::

    underspecified(Animal, domain=animals)(hair=True, species=...)

This adapter reads that query: it locates the ``...`` inference targets, keeps the
concrete attributes as an ordinary EQL filter (the ellipsis conditions stripped out), and
streams the domain instances that pass the filter — the cases an RDR backend then fills.

Single-class RDR fills a single, scalar attribute; an ``...`` slot whose declared type is
an unbounded iterable (``list``/``set``/...) is rejected here and left to a future
``MultiClassRDR``.
"""

from __future__ import annotations

import types
import typing
from dataclasses import dataclass
from functools import cached_property

from typing_extensions import (
    Any,
    Iterator,
    List,
    Type,
    get_args,
    get_origin,
)

from krrood.class_diagrams.utils import get_type_hints_of_object
from krrood.entity_query_language.core.variable import Variable
from krrood.entity_query_language.factories import entity
from krrood.entity_query_language.query.match import AttributeMatch, Match

#: Generic origins whose instances are unbounded iterables we cannot conclude as one value.
_UNBOUNDED_ITERABLE_ORIGINS = (list, set, frozenset, tuple, dict)


class NoInferenceTarget(Exception):
    """Raised when an underspecified ``Match`` has no ``...`` attribute to infer."""

    def __init__(self, case_type: Type) -> None:
        super().__init__(
            f"{case_type.__name__} has no underspecified (`...`) attribute to infer."
        )


class MultipleInferenceTargets(Exception):
    """Raised when a single-class RDR is handed more than one ``...`` attribute."""

    def __init__(self, attribute_names: List[str]) -> None:
        super().__init__(
            "Single-class RDR infers one attribute, but several were underspecified: "
            f"{attribute_names}. Use a separate RDR per attribute (or a future MultiClassRDR)."
        )
        self.attribute_names = attribute_names


class UnsupportedInferenceTarget(Exception):
    """Raised when an ``...`` attribute is an unbounded iterable (needs MultiClassRDR)."""

    def __init__(self, case_type: Type, attribute_name: str) -> None:
        super().__init__(
            f"{case_type.__name__}.{attribute_name} is an unbounded iterable; single-class "
            "RDR only infers single-valued attributes. This will be supported by MultiClassRDR."
        )
        self.case_type = case_type
        self.attribute_name = attribute_name


def is_ellipsis_target(attribute_match: AttributeMatch) -> bool:
    """:return: Whether ``attribute_match`` assigns ``...`` (i.e. is an inference target)."""
    return getattr(attribute_match.assigned_variable, "_value_", None) is ...


def _is_unbounded_iterable(annotation: Any) -> bool:
    """:return: Whether ``annotation`` denotes a collection type (``Optional`` unwrapped)."""
    origin = get_origin(annotation)
    if origin is typing.Union or origin is getattr(types, "UnionType", None):
        return any(
            _is_unbounded_iterable(arg)
            for arg in get_args(annotation)
            if arg is not type(None)
        )
    return origin in _UNBOUNDED_ITERABLE_ORIGINS


@dataclass
class UnderspecifiedMatch:
    """Reads an underspecified :class:`Match` for RDR-based attribute inference."""

    match: Match

    def __post_init__(self) -> None:
        self.match.resolve()

    @property
    def case_type(self) -> Type:
        """The type whose instances are being completed (e.g. ``Animal``)."""
        return self.match.type

    @property
    def variable(self) -> Variable:
        """The EQL variable the query ranges over."""
        return self.match.variable

    @cached_property
    def inference_targets(self) -> List[AttributeMatch]:
        """The ``...`` attribute leaves to infer (each validated as single-valued)."""
        targets = [
            m for m in self.match.matches_with_variables if is_ellipsis_target(m)
        ]
        for target in targets:
            self._guard_single_valued(target)
        return targets

    def single_target(self) -> AttributeMatch:
        """:return: The sole inference target, enforcing the single-class invariant."""
        targets = self.inference_targets
        if not targets:
            raise NoInferenceTarget(self.case_type)
        if len(targets) > 1:
            raise MultipleInferenceTargets([t.attribute_name for t in targets])
        return targets[0]

    @property
    def target_attribute_name(self) -> str:
        """The name of the single attribute this query asks to infer."""
        return self.single_target().attribute_name

    def filtered_cases(self) -> Iterator[Any]:
        """
        Lazily yield the domain instances that satisfy the concrete (non-``...``)
        constraints — ordinary EQL evaluation, with the ellipsis conditions stripped.
        """
        query = entity(self.variable)
        conditions = self._concrete_conditions()
        if conditions:
            query = query.where(*conditions)
        return query.evaluate()

    def _concrete_conditions(self) -> List[Any]:
        """Fresh comparator nodes for the concrete attribute constraints (``...`` dropped)."""
        conditions: List[Any] = []
        for leaf in self.match.matches_with_variables:
            if is_ellipsis_target(leaf):
                continue
            attribute = getattr(self.variable, leaf.attribute_name)
            conditions.append(attribute == leaf.assigned_variable._value_)
        return conditions

    def _guard_single_valued(self, target: AttributeMatch) -> None:
        name = target.attribute_name
        annotation = get_type_hints_of_object(self.case_type).get(name)
        if annotation is not None and _is_unbounded_iterable(annotation):
            raise UnsupportedInferenceTarget(self.case_type, name)

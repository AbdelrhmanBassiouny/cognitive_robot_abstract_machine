"""
Exercises calling a :class:`~krrood.entity_query_language.predicate.Predicate`'s *method* inside a
``where`` clause and comparing its (float) result — the pattern::

    entity(inference(ExampleDrawer)(root=prismatic_connection.child))
        .where(
            contains(prismatic_connection.child.name.name.lower(), "drawer"),
            ExampleInsideOf(prismatic_connection.child, prismatic_connection.parent)
                .compute_containment_ratio() > 0.7,
        )
        .tolist()

``ExampleInsideOf`` is a predicate that also carries a normal method returning a float
"probability". The mimic classes stand in for the semantic-world types (kept inside krrood, per the
test rules).
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from krrood.entity_query_language.factories import (
    contains,
    entity,
    inference,
    variable,
)
from krrood.entity_query_language.predicate import Predicate, Symbol


@dataclass(unsafe_hash=True)
class ExamplePrefixedName(Symbol):
    """A name wrapper (mirrors a semantic-world ``PrefixedName``; its ``name`` holds the text)."""

    name: str


@dataclass(unsafe_hash=True)
class ExampleBody(Symbol):
    """A world body identified by a nested :class:`ExamplePrefixedName` and carrying a volume."""

    name: ExamplePrefixedName
    volume: float = 1.0


@dataclass(unsafe_hash=True)
class ExamplePrismaticConnection(Symbol):
    """A parent→child sliding connection (the joint of a drawer)."""

    parent: ExampleBody
    child: ExampleBody


@dataclass
class ExampleDrawer(Symbol):
    """A drawer view rooted at a body (mirrors ``Drawer(root=...)``)."""

    root: ExampleBody

    def __hash__(self) -> int:
        return hash((self.__class__.__name__, self.root))

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ExampleDrawer) and self.root == other.root


@dataclass(eq=False)
class ExampleInsideOf(Predicate):
    """Spatial predicate asserting ``inner`` sits inside ``outer``.

    Besides being a boolean predicate it exposes :meth:`compute_containment_ratio`, a plain method
    returning a float — the value the query calls symbolically and compares in ``where``.
    """

    inner: ExampleBody
    outer: ExampleBody

    def compute_containment_ratio(self) -> float:
        """:return: the fraction of ``inner`` contained in ``outer`` (here ``inner``/``outer`` volume)."""
        return self.inner.volume / self.outer.volume

    def __call__(self) -> bool:
        return self.compute_containment_ratio() > 0.0


@dataclass
class ExampleDrawerAssembly(Symbol):
    """A view wrapping a drawer — lets an outer inference nest over a filtered inner drawer query."""

    drawer: ExampleDrawer

    def __hash__(self) -> int:
        return hash((self.__class__.__name__, self.drawer))

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ExampleDrawerAssembly) and self.drawer == other.drawer


def _connections() -> list:
    """A cabinet with four sliding children: two are 'drawer'-named and well-contained (should
    match), one is a 'drawer' but poorly contained (fails the ratio), one is not a drawer.
    """
    cabinet = ExampleBody(name=ExamplePrefixedName("cabinet"), volume=10.0)
    return [
        ExamplePrismaticConnection(
            parent=cabinet,
            child=ExampleBody(name=ExamplePrefixedName("drawer_top"), volume=9.0),
        ),  # drawer, ratio 0.9  -> match
        ExamplePrismaticConnection(
            parent=cabinet,
            child=ExampleBody(name=ExamplePrefixedName("Drawer_Left"), volume=8.0),
        ),  # Drawer, ratio 0.8  -> match (name lower-cased)
        ExamplePrismaticConnection(
            parent=cabinet,
            child=ExampleBody(name=ExamplePrefixedName("drawer_tiny"), volume=3.0),
        ),  # drawer, ratio 0.3  -> ratio too low
        ExamplePrismaticConnection(
            parent=cabinet,
            child=ExampleBody(name=ExamplePrefixedName("shelf"), volume=9.5),
        ),  # ratio 0.95 but not a drawer -> filtered by name
    ]


def test_predicate_method_call_in_where_filters_and_infers_drawers():
    connections = _connections()
    prismatic_connection = variable(ExamplePrismaticConnection, domain=connections)

    drawers = (
        entity(inference(ExampleDrawer)(root=prismatic_connection.child))
        .where(
            contains(prismatic_connection.child.name.name.lower(), "drawer"),
            ExampleInsideOf(
                prismatic_connection.child, prismatic_connection.parent
            ).compute_containment_ratio()
            > 0.7,
        )
        .tolist()
    )

    assert all(isinstance(drawer, ExampleDrawer) for drawer in drawers)
    assert sorted(drawer.root.name.name for drawer in drawers) == [
        "Drawer_Left",
        "drawer_top",
    ]


@pytest.mark.xfail(
    reason=(
        "Binding propagation is lost when an outer inference wraps an inner "
        "entity(...).where(...) that shares the prismatic_connection variable: the shared binding "
        "is not correlated across the nested-query (slim-bindings) boundary, so the result is a 3x3 "
        "cross product (9, incl. the non-'drawer' shelf) instead of the correlated 2. Same root "
        "cause as test_inference_binding_loss.py. Remove this marker once fixed."
    ),
    strict=True,
)
def test_binding_propagates_through_nested_inference_sharing_a_variable():
    """Deeper nesting — the historically fragile case (cf. ``test_inference_binding_loss.py``).

    An outer inference wraps an inner ``entity(...).where(...)`` (which emits *slim* bindings), and
    **both** the inner where (a predicate-method comparison) and the outer where (a name check)
    constrain the *same* ``prismatic_connection`` variable. The shared variable's binding must stay
    consistent across the nested-query boundary, so each assembly wraps the drawer rooted at the
    connection that its own conditions matched — no cross-product blow-up and no lost bindings.

    Currently ``xfail``: the shared binding is dropped and the query returns a 3x3 cross product.
    """
    connections = _connections()
    prismatic_connection = variable(ExamplePrismaticConnection, domain=connections)

    # Inner query: a drawer inferred from the connection's child, kept only when well-contained.
    well_contained_drawer = entity(
        inference(ExampleDrawer)(root=prismatic_connection.child)
    ).where(
        ExampleInsideOf(
            prismatic_connection.child, prismatic_connection.parent
        ).compute_containment_ratio()
        > 0.7
    )

    # Outer inference wraps that inner query and adds a name check on the SAME connection.
    assemblies = (
        entity(inference(ExampleDrawerAssembly)(drawer=well_contained_drawer))
        .where(contains(prismatic_connection.child.name.name.lower(), "drawer"))
        .tolist()
    )

    assert all(isinstance(a, ExampleDrawerAssembly) for a in assemblies)
    # shelf (ratio 0.95) passes the inner ratio filter but fails the outer name filter;
    # drawer_tiny (ratio 0.3) passes the name filter but fails the inner ratio filter.
    # Only drawer_top and Drawer_Left satisfy both across the nesting, and each assembly wraps the
    # drawer rooted at *its own* connection's child — proving the shared binding survived.
    assert sorted(a.drawer.root.name.name for a in assemblies) == [
        "Drawer_Left",
        "drawer_top",
    ]

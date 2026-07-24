"""
Golden-surface snapshot over every symbolic callable krrood defines.

Uses the reusable
:class:`~krrood.entity_query_language.verbalization.surface_verification.SymbolicSurfaceSnapshot`:
it discovers every concrete Predicate / SymbolicFunction in the ``krrood`` package, renders each with
placeholder operands, and checks it against the committed snapshot in :mod:`verbalization_surfaces`
(one :class:`~...surface_verification.VerbalizationSurface` per class). Every covered class must
implement a fragment; a fragment-less class, an uncovered class, or a changed wording each fails.

When an intentional change alters a surface, the match test prints each class and its new sentence;
update that class's entry in ``verbalization_surfaces.py`` and commit it (the diff is the review
record). A newly added symbolic callable fails the coverage test until it gets an entry.
"""

from __future__ import annotations

import krrood

from krrood.entity_query_language.predicate import HasType, HasTypes
from krrood.entity_query_language.testing.surface_verification import (
    OverriddenOperand,
    SymbolicSurfaceSnapshot,
)

from .verbalization_surfaces import SURFACES

SNAPSHOT = SymbolicSurfaceSnapshot(
    package=krrood,
    surfaces=SURFACES,
    operand_overrides={
        HasType: [OverriddenOperand("types_", int)],
        HasTypes: [OverriddenOperand("types_", (int, str))],
    },
)
"""
``HasType`` / ``HasTypes`` read the type(s) by name, so they get a concrete type rather than a
symbolic operand; every other field defaults to a placeholder variable of its annotated type.
"""


def test_covered_symbolic_callables_match_the_declared_surfaces():
    SNAPSHOT.assert_surfaces_cover_every_callable()


def test_every_declared_surface_matches_what_its_class_renders():
    SNAPSHOT.assert_declared_surfaces_render_as_stated()

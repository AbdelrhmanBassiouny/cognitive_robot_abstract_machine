"""
Golden-surface snapshot over every symbolic callable semantic_digital_twin defines.

Uses the reusable
:class:`~krrood.entity_query_language.verbalization.surface_verification.SymbolicSurfaceSnapshot`:
it discovers every concrete Predicate / SymbolicFunction in the ``semantic_digital_twin`` package,
renders each with placeholder operands, and checks it against the committed snapshot in
:mod:`verbalization_surfaces` (one
:class:`~...surface_verification.VerbalizationSurface` per class). Every covered class must implement
a fragment; a fragment-less class, an uncovered class, or a changed wording each fails.

When an intentional change alters a surface, the match test prints each class and its new sentence;
update that class's entry in ``verbalization_surfaces.py`` and commit it (the diff is the review
record). A newly added predicate or function fails the coverage test until it gets an entry.
"""

from __future__ import annotations

import semantic_digital_twin

from krrood.entity_query_language.verbalization.surface_verification import (
    SymbolicSurfaceSnapshot,
)

from .verbalization_surfaces import SURFACES

SNAPSHOT = SymbolicSurfaceSnapshot(package=semantic_digital_twin, surfaces=SURFACES)


def test_every_covered_symbolic_callable_has_a_verbalization_fragment():
    SNAPSHOT.assert_every_callable_has_a_fragment()


def test_covered_symbolic_callables_match_the_declared_surfaces():
    SNAPSHOT.assert_surfaces_cover_every_callable()


def test_every_declared_surface_matches_what_its_class_renders():
    SNAPSHOT.assert_declared_surfaces_render_as_stated()

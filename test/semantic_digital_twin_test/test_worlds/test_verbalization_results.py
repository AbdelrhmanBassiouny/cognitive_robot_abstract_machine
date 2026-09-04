"""
Verbalization coverage for semantic_digital_twin's symbolic callables.

The sentences themselves live in :mod:`verbalization_results`, which ``conftest.py``
regenerates on every run -- so they are reviewed as a diff, not asserted here. What a
test still has to catch is a predicate or symbolic function that never decided its own
wording: the generator covers only callables implementing their own fragment, so one
without a fragment would be dropped from that file silently.
"""

from __future__ import annotations

import semantic_digital_twin
from krrood.entity_query_language.testing.result_verification import (
    VerbalizationResultsOfPackage,
)
from krrood.utils import module_and_class_name

# %% every symbolic callable decides its own wording


def test_every_symbolic_callable_declares_its_own_verbalization_fragment():
    """
    A callable relying on the inherited fragment is excluded from the generated results
    rather than rendered, so it must be reported here instead of passing unnoticed.
    """
    snapshot = VerbalizationResultsOfPackage(package=semantic_digital_twin, results=())

    without_own_fragment = sorted(
        module_and_class_name(symbolic_callable)
        for symbolic_callable in snapshot.discovered_callables()
        if not snapshot.has_fragment(symbolic_callable)
    )

    assert without_own_fragment == []

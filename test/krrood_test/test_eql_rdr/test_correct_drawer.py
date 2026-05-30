"""Test-correct drawer dataset — a classic spatial-relations domain.

A *correct* drawer is a handle--container pair joined by a fixed connection.
The dataset has 2 handles × 2 containers = 4 candidates; only the pair
(``left_handle``, ``bottom_drawer``) is correct.

All types are prefixed with ``TestCorrect`` to clearly signal they belong to
the "correct drawer" test classification problem, not to production code.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Optional


@dataclass
class RDRTestCorrectHandle:
    """A drawer handle identified by name."""

    name: str


@dataclass
class RDRTestCorrectContainer:
    """A drawer container identified by name."""

    name: str


@dataclass
class RDRTestCorrectDrawer:
    """A candidate drawer: a handle--container pair whose correctness is to be judged.

    The ``correct`` field is the conclusion the RDR should learn to set: ``True``
    when ``FixedConnection(container, handle)`` would exist, ``False`` otherwise.
    """

    handle: RDRTestCorrectHandle
    container: RDRTestCorrectContainer
    correct: Optional[bool] = None


def generate_test_correct_drawer_cases():
    """Return ``(drawers, targets)`` — 4 drawer cases, 1 is correct.

    The ground truth: only ``(TestCorrectHandle("left_handle"),
    TestCorrectContainer("bottom_drawer"))`` is a correct drawer.
    """
    left = RDRTestCorrectHandle("left_handle")
    right = RDRTestCorrectHandle("right_handle")
    top = RDRTestCorrectContainer("top_drawer")
    bottom = RDRTestCorrectContainer("bottom_drawer")

    drawers = [
        RDRTestCorrectDrawer(handle=left, container=bottom),  # correct=True
        RDRTestCorrectDrawer(handle=left, container=top),  # correct=False
        RDRTestCorrectDrawer(handle=right, container=bottom),  # correct=False
        RDRTestCorrectDrawer(handle=right, container=top),  # correct=False
    ]
    targets = [True, False, False, False]
    return drawers, targets

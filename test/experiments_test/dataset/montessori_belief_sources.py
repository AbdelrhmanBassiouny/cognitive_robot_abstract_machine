"""
Where a test's beliefs come from when nothing in perception put them there.
"""

from __future__ import annotations

from dataclasses import dataclass

from krrood.patterns.belief_source import BeliefSource


@dataclass(eq=False)
class SomethingThatAskedForALook(BeliefSource):
    """
    Stands for whoever wanted a look and said what to expect - a plan, an action or a
    person - in a test that only needs a belief to have come from outside perception.

    Two askers are the same one only where they are the same object, so a test can say
    which of them a detection answered.
    """

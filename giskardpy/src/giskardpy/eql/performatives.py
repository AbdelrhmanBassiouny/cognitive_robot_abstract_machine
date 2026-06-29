"""
Motion speech acts -- the giskardpy half of the performative layer.

``Achieve`` and ``Observe`` are the directives that need a solver / monitor, so they live here (the
framework that owns that capability) rather than in krrood, which keeps only the framework-agnostic acts.
Both are :class:`~krrood.entity_query_language.performatives.Performable`, so a krrood
:class:`~krrood.entity_query_language.performatives.Composition` composes them alongside acts from any
other framework, and both verbalize through the shared fragment vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass

from krrood.entity_query_language.performatives import Performable
from krrood.entity_query_language.verbalization.fragments.base import (
    PhraseFragment,
    VerbalizationFragment,
)
from krrood.entity_query_language.verbalization.fragments.features import Separator
from krrood.entity_query_language.verbalization.vocabulary.english import (
    PerformativeDirective,
    PlanConnectives,
)

from giskardpy.eql.constraints import GiskardGoal
from giskardpy.qp.constraint_collection import ConstraintCollection


@dataclass
class Achieve(Performable):
    """Bring about a declarative motion goal by compiling it into giskard QP constraints."""

    goal: GiskardGoal
    """The motion goal to drive to satisfaction."""

    def perform(self) -> ConstraintCollection:
        return self.goal.compile_into(ConstraintCollection())

    def as_fragment(self) -> VerbalizationFragment:
        return PhraseFragment(
            parts=[
                PerformativeDirective.ACHIEVE.as_fragment(),
                PlanConnectives.THAT.as_fragment(),
                self.goal.as_fragment(),
            ],
            separator=Separator.SPACE,
        )


@dataclass
class Observe(Performable):
    """Monitor whether a declarative condition holds throughout the motion."""

    goal: GiskardGoal
    """The condition to watch."""

    def perform(self) -> None:
        raise NotImplementedError(
            "Observe is executed by a giskard monitor at runtime (needs the ROS execution stack)."
        )

    def as_fragment(self) -> VerbalizationFragment:
        return PhraseFragment(
            parts=[
                PerformativeDirective.OBSERVE.as_fragment(),
                PlanConnectives.WHETHER.as_fragment(),
                self.goal.as_fragment(),
            ],
            separator=Separator.SPACE,
        )

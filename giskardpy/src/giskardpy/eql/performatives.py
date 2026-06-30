"""
Motion speech acts -- the giskardpy half of the performative layer.

``Achieve`` and ``Monitor`` are the directives that need a solver / monitor, so they live here (the
framework that owns that capability) rather than in krrood, which keeps only the framework-agnostic acts.
Both are :class:`~krrood.entity_query_language.performatives.Performable`, so a krrood
:class:`~krrood.entity_query_language.performatives.Composition` composes them alongside acts from any
other framework, and both verbalize through the shared fragment vocabulary.

The division of labour follows the goal/condition split: ``Achieve`` drives a **motion goal or task** to
satisfaction (it compiles to QP constraints), while ``Monitor`` watches a **predicate or constraint** hold
over time (a runtime monitor).
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import List, Optional, Union

from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.performatives import Performable
from krrood.entity_query_language.verbalization.context import MicroplanningServices
from krrood.entity_query_language.verbalization.fragments.base import (
    PhraseFragment,
    VerbalizationFragment,
)
from krrood.entity_query_language.verbalization.fragments.features import Separator
from krrood.entity_query_language.verbalization.pipeline import fragment_for_expression
from krrood.entity_query_language.verbalization.vocabulary.english import (
    PerformativeDirective,
    PlanConnectives,
)

from giskardpy.eql.constraints import GiskardGoal
from giskardpy.qp.constraint_collection import ConstraintCollection


@dataclass
class Achieve(Performable):
    """Bring about a motion goal or task by compiling it into giskard QP constraints."""

    goal: GiskardGoal
    """The motion goal to drive to satisfaction."""

    def perform(self) -> ConstraintCollection:
        return self.goal.compile_into(ConstraintCollection())

    def as_fragment(
        self, services: Optional[MicroplanningServices] = None
    ) -> VerbalizationFragment:
        return PhraseFragment(
            parts=[
                PerformativeDirective.ACHIEVE.as_fragment(),
                PlanConnectives.THAT.as_fragment(),
                self.goal.as_fragment(),
            ],
            separator=Separator.SPACE,
        )


@dataclass
class Monitor(Performable):
    """Watch whether a predicate or constraint holds throughout the motion -- a runtime monitor."""

    condition: Union[SymbolicExpression, GiskardGoal]
    """The condition to watch: an EQL predicate, or a constraint (a :class:`GiskardGoal`)."""

    def perform(self) -> None:
        raise NotImplementedError(
            "Monitor is executed by a giskard monitor at runtime (needs the ROS execution stack)."
        )

    def eql_scan_targets(self) -> List[SymbolicExpression]:
        if isinstance(self.condition, GiskardGoal):
            return []
        return [self.condition]

    def _condition_fragment(
        self, services: Optional[MicroplanningServices]
    ) -> VerbalizationFragment:
        if isinstance(self.condition, GiskardGoal):
            return self.condition.as_fragment()
        return fragment_for_expression(self.condition, services)

    def as_fragment(
        self, services: Optional[MicroplanningServices] = None
    ) -> VerbalizationFragment:
        return PhraseFragment(
            parts=[
                PerformativeDirective.MONITOR.as_fragment(),
                PlanConnectives.WHETHER.as_fragment(),
                self._condition_fragment(services),
            ],
            separator=Separator.SPACE,
        )

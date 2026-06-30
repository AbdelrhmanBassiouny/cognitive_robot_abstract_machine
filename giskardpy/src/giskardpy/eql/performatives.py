"""
Motion speech acts -- the giskardpy half of the performative layer.

``Achieve`` and ``Monitor`` are the directives that need a solver / monitor, so they live here (the
framework that owns that capability) rather than in krrood, which keeps only the framework-agnostic acts.
Both are :class:`~krrood.entity_query_language.performatives.Performative` acts over an EQL description, so
a krrood :class:`~krrood.entity_query_language.performatives.Composition` composes them alongside acts from
any other framework and both verbalize through the shared EQL pipeline.

The division of labour follows the goal/condition split: ``Achieve`` drives a description to satisfaction
(*"Achieve that …"*), while ``Monitor`` watches a description hold over time (*"Monitor whether …"*).
Executing either is delegated to the giskard motion runtime (a seam that needs the ROS execution stack);
the toy QP-constraint bridge that once stood in for it has been removed.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import NoReturn, Optional

from krrood.entity_query_language.performatives import Performative
from krrood.entity_query_language.verbalization.context import MicroplanningServices
from krrood.entity_query_language.verbalization.fragments.base import (
    VerbalizationFragment,
)
from krrood.entity_query_language.verbalization.vocabulary.english import (
    PerformativeDirective,
    PlanConnectives,
)


@dataclass
class Achieve(Performative):
    """Drive an EQL-described motion goal to satisfaction (*"Achieve that …"*)."""

    def perform(self) -> NoReturn:
        raise NotImplementedError(
            "Achieve is executed by the giskard motion runtime (needs the ROS execution stack)."
        )

    def as_fragment(
        self, services: Optional[MicroplanningServices] = None
    ) -> VerbalizationFragment:
        return self.framed_fragment(
            PerformativeDirective.ACHIEVE, PlanConnectives.THAT, services
        )


@dataclass
class Monitor(Performative):
    """Watch whether an EQL-described condition holds throughout the motion (*"Monitor whether …"*)."""

    def perform(self) -> NoReturn:
        raise NotImplementedError(
            "Monitor is executed by a giskard monitor at runtime (needs the ROS execution stack)."
        )

    def as_fragment(
        self, services: Optional[MicroplanningServices] = None
    ) -> VerbalizationFragment:
        return self.framed_fragment(
            PerformativeDirective.MONITOR, PlanConnectives.WHETHER, services
        )

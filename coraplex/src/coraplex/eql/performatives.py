"""
Action speech acts -- the coraplex half of the performative layer.

``Perform`` is the directive that *carries out* an action, so it lives here, in the framework that owns
plan execution, rather than in krrood (which keeps only the framework-agnostic acts). It is a
:class:`~krrood.entity_query_language.performatives.Performable`, so a coraplex plan node composes it, as a
plan, alongside acts from any other framework, and it verbalizes through the shared fragment vocabulary.

Its content is an action description -- an EQL :class:`~krrood.entity_query_language.query.match.Match`
(e.g. ``a(NavigateAction)(...)``), which coraplex's plan layer already accepts as an ``ActionLike`` -- so
executing the act builds and runs the corresponding plan node. ``Perform`` makes the *carry out* force
explicit; putting the action ``Match`` directly in a plan reads the same way.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import TYPE_CHECKING, Optional

from krrood.entity_query_language.performatives import Performative
from krrood.entity_query_language.verbalization.context import MicroplanningServices
from krrood.entity_query_language.verbalization.fragments.base import (
    VerbalizationFragment,
)
from krrood.entity_query_language.verbalization.pipeline import fragment_for_expression
from krrood.entity_query_language.verbalization.vocabulary.register import (
    ACTION_COMMAND_REGISTER,
)

if TYPE_CHECKING:
    from coraplex.plans.plan_node import PlanNode


@dataclass
class Perform(Performative):
    """Carry out the described action -- the directive that drives a plan.

    The content is an action description (e.g. ``a(NavigateAction)(...).where(...)``); it verbalizes in the
    imperative register (*"navigate to …"*, or *"Perform … such that …"* when the action is not
    self-verbalizing), and executing it builds and runs the corresponding coraplex plan node.
    """

    def perform(self) -> PlanNode:
        from coraplex.plans.factories import execute_single

        return execute_single(self.content)

    def as_fragment(
        self, services: Optional[MicroplanningServices] = None
    ) -> VerbalizationFragment:
        return fragment_for_expression(
            self.content, services, register=ACTION_COMMAND_REGISTER
        )

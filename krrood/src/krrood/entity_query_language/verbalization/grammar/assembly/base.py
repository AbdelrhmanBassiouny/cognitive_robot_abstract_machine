from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from typing_extensions import ClassVar, Generic, Optional, Type, TypeVar

from krrood.entity_query_language.verbalization.fragments.base import Fragment
from krrood.entity_query_language.verbalization.grammar.phrase_rule import RuleContext
from krrood.entity_query_language.verbalization.grammar.planning.base import Planner

N = TypeVar("N")
"""The EQL node type the assembler realises."""

P = TypeVar("P")
"""The plan (data record) the assembler realises."""


@dataclass
class Assembler(ABC, Generic[N, P]):
    """
    Realise an EQL *node* into a fragment, planning it first via the paired planner.

    An assembler owns its paired planner: ``assemble`` plans the node, then realises the plan
    into a fragment. A realisation-only construct (e.g. an ORDER BY / HAVING clause, which has
    nothing to decide) sets ``planner = None`` and receives ``plan=None``.

    Reference: Gatt, A. & Reiter, E. (2009), "SimpleNLG: A realisation engine for practical
    applications", ENLG — surface realisation as a dedicated stage.
    """

    context: RuleContext
    """The per-node context (recursion entry and microplanning services)."""

    planner: ClassVar[Optional[Type[Planner]]] = None
    """The paired planner (set per family); ``None`` for realisation-only assemblers."""

    def plan(self, node: N) -> Optional[P]:
        """
        :param node: The node to plan.
        :return: The plan from the paired planner, or ``None`` when there is nothing to plan.
        """
        return self.planner(node).plan() if self.planner is not None else None

    def assemble(self, node: N) -> Fragment:
        """
        Plan *node*, then realise the plan.

        :param node: The node to assemble.
        :return: The fragment for *node*.
        """
        return self.realize(node, self.plan(node))

    @abstractmethod
    def realize(self, node: N, plan: P) -> Fragment:
        """
        :param node: The node to realise.
        :param plan: The plan computed for *node* (``None`` for realisation-only assemblers).
        :return: The fragment for *node* built from its *plan*.
        """

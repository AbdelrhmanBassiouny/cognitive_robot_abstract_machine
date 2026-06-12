"""
Assembler — abstract parent for the **realisation** half of a complex construct's
verbalization.

An assembler **owns its paired planner**: it declares it as the :attr:`Assembler.planner`
class attribute, and :meth:`assemble` plans the node then realises the plan.  Callers
therefore only say ``XAssembler(ctx).assemble(node)`` — the planner is an implementation
detail of the assembler, and the planner↔assembler pairing is explicit and declarative.
:meth:`realize` is the single-responsibility core (plan → fragment) and stays directly
unit-testable with a stub plan.

The assembler owns the things that genuinely cannot be pre-planned: recursion into
children (``self.ctx.child``) and the render-scope mutations (query depth, coreference
subject, compact predicates, constraint deferral).  Realisation sub-steps are **methods**
sharing ``self.ctx`` (no parameter threading), mirroring the microplanning service classes.
A realisation-only construct (e.g. a chain, which has nothing to decide) sets
``planner = None`` and receives ``plan=None``.

Reference: Gatt, A. & Reiter, E. (2009), "SimpleNLG: A realisation engine for
practical applications", ENLG — surface realisation as a dedicated stage.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from typing_extensions import ClassVar, Generic, Optional, Type, TypeVar

from krrood.entity_query_language.verbalization.fragments.base import Fragment
from krrood.entity_query_language.verbalization.grammar.phrase_rule import Ctx
from krrood.entity_query_language.verbalization.grammar.planning.base import Planner

N = TypeVar("N")
"""The EQL node type the assembler realises."""

P = TypeVar("P")
"""The plan (data record) the assembler realises."""


@dataclass
class Assembler(ABC, Generic[N, P]):
    """
    Realise an EQL *node* into a
    :class:`~krrood.entity_query_language.verbalization.fragments.base.Fragment`,
    planning it first via the paired :attr:`planner`.

    Holds the :class:`~krrood.entity_query_language.verbalization.grammar.phrase_rule.Ctx`
    so realisation sub-steps (methods) share ``self.ctx`` rather than threading it.
    """

    ctx: Ctx
    """The per-node context (recursion entry + microplanning services)."""

    planner: ClassVar[Optional[Type[Planner]]] = None
    """The paired planner (set per family); ``None`` for realisation-only assemblers."""

    def plan(self, node: N) -> Optional[P]:
        """Run the paired planner on *node* (or ``None`` when there is nothing to plan)."""
        return self.planner(node).plan() if self.planner is not None else None

    def assemble(self, node: N) -> Fragment:
        """Plan *node*, then realise the plan — the single public entry point."""
        return self.realize(node, self.plan(node))

    @abstractmethod
    def realize(self, node: N, plan: P) -> Fragment:
        """Build the fragment for *node* from its *plan*, recursing via ``self.ctx.child``."""

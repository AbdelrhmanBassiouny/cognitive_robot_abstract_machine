from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import List

from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.core.mapped_variable import MappedVariable
from krrood.entity_query_language.verbalization.chain_utils import (
    PathStep,
    build_path_parts,
    chain_ends_in_boolean_attribute,
    walk_chain,
)
from krrood.entity_query_language.verbalization.grammar.planning.base import Planner


@dataclass(frozen=True)
class ChainPlan:
    """
    A ``MappedVariable`` chain analysed once into the values its rendering needs: the walked
    chain, its root, the display path-parts, and whether it ends in a boolean attribute.
    """

    chain: List[MappedVariable]
    """The access path, root-adjacent first."""

    root: SymbolicExpression
    """The chain root (first non-``MappedVariable`` node)."""

    parts: List[PathStep]
    """The display path-parts."""

    is_boolean_terminal: bool
    """``True`` when the chain ends in a ``bool``-typed attribute (predicative form)."""


@dataclass
class ChainPlanner(Planner[MappedVariable, ChainPlan]):
    """
    Analyse a ``MappedVariable`` chain into a ``ChainPlan``: its root, the display path-parts, and
    whether it ends in a boolean attribute (predicative form) — the chain decisions of *what to
    say*, before any surface form is chosen.

    Reference: Reiter & Dale (2000) — content/structure determination (microplanning).
    """

    def plan(self) -> ChainPlan:
        """:return: The chain plan: the walked chain, its root, display parts, and boolean form."""
        chain, root = walk_chain(self.node)
        return ChainPlan(
            chain=chain,
            root=root,
            parts=build_path_parts(chain),
            is_boolean_terminal=chain_ends_in_boolean_attribute(chain),
        )

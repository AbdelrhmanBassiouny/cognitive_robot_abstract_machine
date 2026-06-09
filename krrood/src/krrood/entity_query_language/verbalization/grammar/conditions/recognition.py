"""
Condition **recognizers** — the single source of truth for the structural shapes a
condition (a :class:`~krrood.entity_query_language.operators.comparator.Comparator` or a
:class:`~krrood.entity_query_language.core.mapped_variable.MappedVariable` chain) can take.

Previously these tests were re-implemented independently in the restriction rules, the
inference planner, the chain assembler, and the grammar (the bool-attr guard).  They are
pure structural predicates — no fragments, no context — so they live here once and every
surface-form decision consults them.
"""

from __future__ import annotations

from typing_extensions import List, Optional

from krrood.entity_query_language.core.mapped_variable import Attribute, MappedVariable
from krrood.entity_query_language.core.variable import Variable
from krrood.entity_query_language.verbalization.chain_utils import (
    chain_root,
    walk_chain,
)


def attribute_names(left) -> List[str]:
    """The attribute names along a MappedVariable chain, outermost last (``[]`` if none)."""
    names: List[str] = []
    current = left
    while isinstance(current, MappedVariable):
        if isinstance(current, Attribute):
            names.append(current._attribute_name_)
        current = current._child_
    return names


def single_hop_attr(expression, subject_variable) -> Optional[Attribute]:
    """The :class:`Attribute` node when *expression* is exactly ``subject_variable.<attr>``, else ``None``."""
    if subject_variable is None or not isinstance(expression, MappedVariable):
        return None
    chain, root = walk_chain(expression)
    if not (isinstance(root, Variable) and root._id_ == subject_variable._id_):
        return None
    if len(chain) != 1 or not isinstance(chain[0], Attribute):
        return None
    return chain[0]


def references(expression, subject_variable) -> bool:
    """``True`` when *expression* mentions *subject_variable* (so it is not a clean RHS value)."""
    try:
        return any(
            getattr(variable, "_id_", None) == subject_variable._id_
            for variable in expression._unique_variables_
        )
    except AttributeError:
        return chain_root(expression) is subject_variable


def is_bool_attr_chain(expression) -> bool:
    """``True`` when *expression* is a MappedVariable chain ending in a bool-typed Attribute."""
    if not isinstance(expression, MappedVariable):
        return False
    chain, _ = walk_chain(expression)
    return bool(chain) and isinstance(chain[-1], Attribute) and chain[-1]._type_ is bool

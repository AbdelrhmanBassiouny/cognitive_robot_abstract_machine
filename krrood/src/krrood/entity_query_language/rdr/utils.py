"""General utility objects for the EQL-RDR subsystem."""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import TYPE_CHECKING, Any, List

from krrood.entity_query_language.core.variable import Literal
from krrood.entity_query_language.rules.conclusion import Add

if TYPE_CHECKING:
    from krrood.entity_query_language.core.base_expressions import SymbolicExpression


@dataclass(frozen=True, eq=False, repr=False)
class _Unset:
    """
    Class for UNSET Sentinel for "no current/target conclusion was supplied" (useful, for example, for ask-for-rule path).
    """

    def __repr__(self) -> str:
        return "UNSET"

    def __eq__(self, other):
        return isinstance(other, _Unset)

    def __hash__(self):
        return hash(type(self))


#: Sentinel for "no current/target conclusion was supplied" (useful, for example, for ask-for-rule path).
UNSET: _Unset = _Unset()


def _extract_value(add_node: Add) -> Any:
    """:return: The Python value from an ``Add`` conclusion's right-hand side."""
    target = add_node.right
    return target._value_ if isinstance(target, Literal) else target


def _conclusions_of(node: "SymbolicExpression") -> List[Add]:
    """:return: The ``Add`` conclusion nodes attached to *node*."""
    return [c for c in node._conclusions_ if isinstance(c, Add)]

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Any, Mapping

from krrood.entity_query_language.predicate import Predicate
from krrood.entity_query_language.verbalization.fragments.base import (
    VerbalizationFragment,
)
from krrood.entity_query_language.verbalization.vocabulary.parts_of_speech import (
    Adjective,
    clause,
    Copula,
    Noun,
    Preposition,
)
from krrood.patterns.role import Role


@dataclass(eq=False)
class IsSameEntity(Predicate):
    """
    Predicate asserting that two operands refer to the same underlying entity.

    Each operand is unwrapped to its :attr:`root_persistent_entity
    <krrood.patterns.role.Role.root_persistent_entity>` when it is a
    :class:`~krrood.patterns.role.Role` (otherwise used as-is), and the two resolved roots
    are compared by object identity. This sees through role chains, so a role, any role
    layered on top of it, and the root taker itself all count as the same entity.

    Like every :class:`~krrood.entity_query_language.predicate.Predicate` it can be used
    both as a direct boolean on concrete operands (``bool(IsSameEntity(a, b))``) and
    symbolically inside an entity-query-language ``where`` clause.
    """

    entity_1: Any
    """The first operand; unwrapped to its root persistent entity when it is a role."""

    entity_2: Any
    """The second operand; unwrapped to its root persistent entity when it is a role."""

    def __call__(self) -> bool:
        return self._root_of(self.entity_1) is self._root_of(self.entity_2)

    @classmethod
    def _verbalization_fragment_(
        cls, fields: Mapping[str, VerbalizationFragment]
    ) -> VerbalizationFragment:
        return clause(
            Noun(fields["entity_1"]),
            Copula(),
            Adjective("identical"),
            Preposition.TO,
            Noun(fields["entity_2"]),
        )

    @staticmethod
    def _root_of(value: Any) -> Any:
        """
        :return: ``value``'s root persistent entity when it is a role, otherwise ``value``.
        """
        return value.root_persistent_entity if isinstance(value, Role) else value

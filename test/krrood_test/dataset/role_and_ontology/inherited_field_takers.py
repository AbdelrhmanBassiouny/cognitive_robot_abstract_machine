from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeVar

from krrood.entity_query_language.factories import variable_from
from krrood.patterns.role.role import Role
from krrood.patterns.role import HasRoles
from test.krrood_test.dataset.role_and_ontology.role_mixins.inherited_field_takers_role_mixins import (
    RoleForTakerA,
    RoleForTakerB,
)


@dataclass
class FieldOrigin:
    """Grandparent: where `shared_field` is first defined."""

    shared_field: str = field(default="", kw_only=True)


@dataclass
class IntermediateMixin(FieldOrigin):
    """Intermediate: inherits `shared_field` without re-annotating it."""

    def intermediate_method(self) -> str: ...


@dataclass
class TakerA(IntermediateMixin, HasRoles):
    """Role taker: inherits `shared_field` transitively through IntermediateMixin."""

    taker_a_field: int = field(default=0, kw_only=True)


@dataclass
class TakerB(IntermediateMixin, HasRoles):
    """Second role taker: same grandparent but independent branch."""

    taker_b_field: float = field(default=0.0, kw_only=True)


TTakerA = TypeVar("TTakerA", bound=TakerA)
TTakerB = TypeVar("TTakerB", bound=TakerB)


@dataclass
class TakerARole(Role[TTakerA], RoleForTakerA):
    taker: TTakerA = field(kw_only=True)

    @classmethod
    def role_taker_attribute(cls) -> TTakerA:
        return variable_from(cls).taker


@dataclass
class TakerBRole(Role[TTakerB], RoleForTakerB):
    taker: TTakerB = field(kw_only=True)

    @classmethod
    def role_taker_attribute(cls) -> TTakerB:
        return variable_from(cls).taker

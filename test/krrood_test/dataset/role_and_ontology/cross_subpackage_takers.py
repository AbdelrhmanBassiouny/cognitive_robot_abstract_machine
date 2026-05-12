from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeVar

from krrood.entity_query_language.factories import variable_from
from krrood.patterns.role.role import Role

from test.krrood_test.dataset.sibling_package.cross_subpackage_base import (
    CrossSubpackageBase,
)
from krrood.patterns.role import HasRoles
from test.krrood_test.dataset.role_and_ontology.role_mixins.cross_subpackage_takers_role_mixins import (
    RoleForTakerP,
    RoleForTakerQ,
)


@dataclass
class TakerP(CrossSubpackageBase, HasRoles):
    def taker_p_only_method(self) -> str: ...


@dataclass
class TakerQ(CrossSubpackageBase, HasRoles):
    def taker_q_only_method(self) -> float: ...


TTakerP = TypeVar("TTakerP", bound=TakerP)
TTakerQ = TypeVar("TTakerQ", bound=TakerQ)


@dataclass
class RoleP(Role[TTakerP], RoleForTakerP):
    taker_p: TTakerP = field(kw_only=True)

    @classmethod
    def role_taker_attribute(cls) -> TTakerP:
        return variable_from(cls).taker_p


@dataclass
class RoleQ(Role[TTakerQ], RoleForTakerQ):
    taker_q: TTakerQ = field(kw_only=True)

    @classmethod
    def role_taker_attribute(cls) -> TTakerQ:
        return variable_from(cls).taker_q

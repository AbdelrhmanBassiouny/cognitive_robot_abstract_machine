from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeVar

from krrood.entity_query_language.factories import variable_from
from krrood.patterns.role.role import Role
from krrood.patterns.role import HasRoles
from test.krrood_test.dataset.role_and_ontology.role_mixins.shared_base_takers_role_mixins import (
    RoleForExclusiveTakerA,
    RoleForExclusiveTakerB,
)


@dataclass
class SharedBase:
    shared_field: str = ""

    def shared_method(self) -> int: ...

    def another_shared_method(self) -> str: ...


@dataclass
class ExclusiveTakerA(SharedBase, HasRoles):
    def taker_a_only_method(self) -> str: ...


@dataclass
class ExclusiveTakerB(SharedBase, HasRoles):
    def taker_b_only_method(self) -> float: ...


TExclusiveTakerA = TypeVar("TExclusiveTakerA", bound=ExclusiveTakerA)
TExclusiveTakerB = TypeVar("TExclusiveTakerB", bound=ExclusiveTakerB)


@dataclass
class RoleA(Role[TExclusiveTakerA], RoleForExclusiveTakerA):
    taker_a: TExclusiveTakerA = field(kw_only=True)

    @classmethod
    def role_taker_attribute(cls) -> TExclusiveTakerA:
        return variable_from(cls).taker_a


@dataclass
class RoleB(Role[TExclusiveTakerB], RoleForExclusiveTakerB):
    taker_b: TExclusiveTakerB = field(kw_only=True)

    @classmethod
    def role_taker_attribute(cls) -> TExclusiveTakerB:
        return variable_from(cls).taker_b

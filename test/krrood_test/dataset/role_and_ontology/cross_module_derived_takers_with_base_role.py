from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeVar

from krrood.entity_query_language.factories import variable_from
from krrood.patterns.role.role import Role

from test.krrood_test.dataset.role_and_ontology.cross_module_base_taker import (
    CrossModuleBaseTaker,
)
from test.krrood_test.dataset.role_and_ontology.role_mixins.cross_module_base_taker_role_mixins import (
    RoleForCrossModuleBaseTaker,
)
from test.krrood_test.dataset.role_and_ontology.role_mixins.cross_module_derived_takers_with_base_role_role_mixins import (
    RoleForDerivedTakerA,
    RoleForDerivedTakerB,
)


@dataclass
class DerivedTakerA(CrossModuleBaseTaker):
    derived_a_field: str = ""

    def derived_a_method(self) -> str: ...


@dataclass
class DerivedTakerB(CrossModuleBaseTaker):
    derived_b_field: str = ""

    def derived_b_method(self) -> int: ...


TBase = TypeVar("TBase", bound=CrossModuleBaseTaker)
TDerivedA = TypeVar("TDerivedA", bound=DerivedTakerA)
TDerivedB = TypeVar("TDerivedB", bound=DerivedTakerB)


@dataclass
class RoleBase(Role[TBase], RoleForCrossModuleBaseTaker):
    base: TBase = field(kw_only=True)

    @classmethod
    def role_taker_attribute(cls) -> TBase:
        return variable_from(cls).base


@dataclass
class RoleDerivedA(Role[TDerivedA], RoleForDerivedTakerA):
    derived_a: TDerivedA = field(kw_only=True)

    @classmethod
    def role_taker_attribute(cls) -> TDerivedA:
        return variable_from(cls).derived_a


@dataclass
class RoleDerivedB(Role[TDerivedB], RoleForDerivedTakerB):
    derived_b: TDerivedB = field(kw_only=True)

    @classmethod
    def role_taker_attribute(cls) -> TDerivedB:
        return variable_from(cls).derived_b

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeVar

from krrood.entity_query_language.factories import variable_from
from krrood.patterns.role.role import Role

from .cross_module_base_taker import CrossModuleBaseTaker


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
class RoleBase(Role[TBase]):
    base: TBase = field(kw_only=True)

    @classmethod
    def role_taker_attribute(cls) -> TBase:
        return variable_from(cls).base


@dataclass
class RoleDerivedA(Role[TDerivedA]):
    derived_a: TDerivedA = field(kw_only=True)

    @classmethod
    def role_taker_attribute(cls) -> TDerivedA:
        return variable_from(cls).derived_a


@dataclass
class RoleDerivedB(Role[TDerivedB]):
    derived_b: TDerivedB = field(kw_only=True)

    @classmethod
    def role_taker_attribute(cls) -> TDerivedB:
        return variable_from(cls).derived_b

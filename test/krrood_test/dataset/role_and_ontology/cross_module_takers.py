from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeVar

from krrood.entity_query_language.factories import variable_from
from krrood.patterns.role.role import Role

from .cross_module_shared_base import CrossModuleBase


@dataclass
class TakerX(CrossModuleBase):
    def taker_x_only_method(self) -> str: ...


@dataclass
class TakerY(CrossModuleBase):
    def taker_y_only_method(self) -> float: ...


TTakerX = TypeVar("TTakerX", bound=TakerX)
TTakerY = TypeVar("TTakerY", bound=TakerY)


@dataclass
class RoleX(Role[TTakerX]):
    taker_x: TTakerX = field(kw_only=True)

    @classmethod
    def role_taker_attribute(cls) -> TTakerX:
        return variable_from(cls).taker_x


@dataclass
class RoleY(Role[TTakerY]):
    taker_y: TTakerY = field(kw_only=True)

    @classmethod
    def role_taker_attribute(cls) -> TTakerY:
        return variable_from(cls).taker_y

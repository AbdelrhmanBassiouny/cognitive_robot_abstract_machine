from __future__ import annotations

from dataclasses import dataclass, field
from typing_extensions import TypeVar

from krrood.entity_query_language.factories import variable_from
from krrood.patterns.role.role import Role
from krrood.patterns.subclass_safe_generic import SubClassSafeGeneric


@dataclass(eq=False)
class BaseEntity:
    name: str = field(kw_only=True)


TBaseEntity = TypeVar("TBaseEntity", bound=BaseEntity)


@dataclass(eq=False)
class BaseHolder(SubClassSafeGeneric[TBaseEntity]):
    """First role taker — holds an entity of a parameterised type."""

    entity: TBaseEntity = field(kw_only=True)


TBaseHolder = TypeVar("TBaseHolder", bound=BaseHolder)


@dataclass(eq=False)
class BaseHolderRole(Role[TBaseHolder]):
    taker: TBaseHolder = field(kw_only=True)

    @classmethod
    def role_taker_attribute(cls) -> TBaseHolder:
        return variable_from(cls).taker


@dataclass(eq=False)
class SpecificEntity(BaseEntity):
    code: int = field(default=0, kw_only=True)


TSpecificEntity = TypeVar("TSpecificEntity", bound=SpecificEntity)


@dataclass(eq=False)
class DerivedHolder(BaseHolder[TSpecificEntity]):
    """Second role taker — narrows entity TypeVar to TSpecificEntity."""

    label: str = field(default="", kw_only=True)


TDerivedHolder = TypeVar("TDerivedHolder", bound=DerivedHolder)


@dataclass(eq=False)
class DerivedHolderRole(Role[TDerivedHolder]):
    taker: TDerivedHolder = field(kw_only=True)

    @classmethod
    def role_taker_attribute(cls) -> TDerivedHolder:
        return variable_from(cls).taker

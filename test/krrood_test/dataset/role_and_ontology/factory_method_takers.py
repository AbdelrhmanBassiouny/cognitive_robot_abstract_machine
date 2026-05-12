from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeVar

from typing_extensions import Self

from krrood.entity_query_language.factories import variable_from
from krrood.patterns.role.role import Role
from krrood.patterns.role import HasRoles
from test.krrood_test.dataset.role_and_ontology.role_mixins.factory_method_takers_role_mixins import (
    RoleForBaseWorker,
    RoleForDerivedWorker,
    RoleForPerson,
    RoleForPlainEntity,
)

# ── Simple: delegatee with one factory method ────────────────────────


@dataclass
class Person(HasRoles):
    name: str = field(kw_only=True)
    age: int = field(kw_only=True)

    @classmethod
    def create_adult(cls, name: str) -> Self:
        return cls(name=name, age=18)


TPerson = TypeVar("TPerson", bound=Person)


@dataclass
class PersonRole(Role[TPerson], RoleForPerson):
    person: TPerson = field(kw_only=True)

    @classmethod
    def role_taker_attribute(cls) -> TPerson:
        return variable_from(cls).person


# ── Delegatee with no factory methods ────────────────────────────────


@dataclass
class PlainEntity(HasRoles):
    value: str = field(kw_only=True)


TPlainEntity = TypeVar("TPlainEntity", bound=PlainEntity)


@dataclass
class PlainEntityRole(Role[TPlainEntity], RoleForPlainEntity):
    entity: TPlainEntity = field(kw_only=True)

    @classmethod
    def role_taker_attribute(cls) -> TPlainEntity:
        return variable_from(cls).entity


# ── Inheritance chain with factory methods ───────────────────────────


@dataclass
class BaseWorker(HasRoles):
    name: str = field(kw_only=True)

    @classmethod
    def create_intern(cls, name: str) -> Self:
        return cls(name=name)


TBaseWorker = TypeVar("TBaseWorker", bound=BaseWorker)


@dataclass
class DerivedWorker(BaseWorker):
    department: str = field(kw_only=True, default="engineering")

    @classmethod
    def create_manager(cls, name: str, department: str) -> Self:
        return cls(name=name, department=department)


TDerivedWorker = TypeVar("TDerivedWorker", bound=DerivedWorker)


@dataclass
class BaseWorkerRole(Role[TBaseWorker], RoleForBaseWorker):
    worker: TBaseWorker = field(kw_only=True)

    @classmethod
    def role_taker_attribute(cls) -> TBaseWorker:
        return variable_from(cls).worker


@dataclass
class DerivedWorkerRole(Role[TDerivedWorker], RoleForDerivedWorker):
    worker: TDerivedWorker = field(kw_only=True)

    @classmethod
    def role_taker_attribute(cls) -> TDerivedWorker:
        return variable_from(cls).worker

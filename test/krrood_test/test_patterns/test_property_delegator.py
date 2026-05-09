"""Tests for PropertyDelegator — standalone delegation without the Role pattern."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import pytest

from krrood.patterns.property_delegator import PropertyDelegator
from krrood.patterns.role.role import HasRoles


# ---------------------------------------------------------------------------
# Minimal hand-written mixin (simulates what the transformer generates)
# ---------------------------------------------------------------------------


@dataclass
class Engine:
    horsepower: int
    torque: float
    label: str = field(default="", kw_only=True)

    def rev(self) -> str:
        return f"{self.horsepower}hp"


@dataclass(eq=False)
class DelegatorForEngine(ABC):
    @property
    @abstractmethod
    def delegatee(self) -> Engine: ...

    @property
    def horsepower(self) -> int:
        return self.delegatee.horsepower

    @horsepower.setter
    def horsepower(self, value: int):
        self.delegatee.horsepower = value

    @property
    def torque(self) -> float:
        return self.delegatee.torque

    @torque.setter
    def torque(self, value: float):
        self.delegatee.torque = value

    @property
    def label(self) -> str:
        return self.delegatee.label

    @label.setter
    def label(self, value: str):
        self.delegatee.label = value

    def rev(self) -> str:
        return self.delegatee.rev()


@dataclass
class Car(PropertyDelegator[Engine], DelegatorForEngine):
    engine: Engine
    color: str

    @classmethod
    def delegatee_attribute_name(cls) -> str:
        return "engine"


# ---------------------------------------------------------------------------
# Delegation behaviour
# ---------------------------------------------------------------------------


def test_delegated_field_readable():
    car = Car(engine=Engine(200, 300.0), color="red")
    assert car.horsepower == 200
    assert car.torque == 300.0
    assert car.label == ""


def test_delegated_field_writable():
    car = Car(engine=Engine(200, 300.0), color="red")
    car.horsepower = 250
    assert car.engine.horsepower == 250


def test_delegated_method():
    car = Car(engine=Engine(200, 300.0), color="red")
    assert car.rev() == "200hp"


def test_own_field_not_shadowed():
    car = Car(engine=Engine(200, 300.0), color="red")
    assert car.color == "red"


def test_delegatee_property():
    engine = Engine(200, 300.0)
    car = Car(engine=engine, color="red")
    assert car.delegatee is engine


def test_get_delegatee_type():
    assert Car.get_delegatee_type() is Engine


# ---------------------------------------------------------------------------
# No Role-pattern extras
# ---------------------------------------------------------------------------


def test_no_identity_sharing_with_delegatee():
    engine = Engine(200, 300.0)
    car = Car(engine=engine, color="red")
    assert car is not engine
    assert car != engine


def test_no_has_roles_on_delegatee():
    engine = Engine(200, 300.0)
    Car(engine=engine, color="red")
    assert not isinstance(engine, HasRoles)
    assert not hasattr(engine, "roles")


# ---------------------------------------------------------------------------
# Transformer integration: PropertyDelegator modules generate DelegatorFor mixins
# ---------------------------------------------------------------------------


def test_transformer_generates_delegator_for_mixin():
    from krrood.patterns.role.role_transformer import RoleTransformer
    from test.krrood_test.dataset.property_delegator import simple_delegator

    transformer = RoleTransformer(simple_delegator)
    result = transformer.transform()

    mixin_source = list(result.values())[0][1]
    assert "DelegatorForEngine" in mixin_source
    assert "def delegatee" in mixin_source
    assert "def horsepower" in mixin_source
    assert "self.delegatee.horsepower" in mixin_source
    assert "role_taker" not in mixin_source


def test_transformer_does_not_inject_has_roles_into_delegatee():
    from krrood.patterns.role.role_transformer import RoleTransformer
    from test.krrood_test.dataset.property_delegator import simple_delegator

    transformer = RoleTransformer(simple_delegator)
    result = transformer.transform()

    transformed_source = list(result.values())[0][0]
    assert "HasRoles" not in transformed_source

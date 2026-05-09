"""Test dataset: a standalone PropertyDelegator (not a Role)."""
from __future__ import annotations

from dataclasses import dataclass, field

from krrood.entity_query_language.factories import variable_from
from krrood.patterns.property_delegator import PropertyDelegator


@dataclass
class Engine:
    horsepower: int
    torque: float
    label: str = field(default="", kw_only=True)

    def rev(self) -> str:
        return f"{self.horsepower}hp"


TEngine = __import__("typing").TypeVar("TEngine", bound=Engine)


@dataclass
class Car(PropertyDelegator[Engine]):
    engine: Engine
    color: str

    @classmethod
    def delegatee_attribute_name(cls) -> str:
        return "engine"

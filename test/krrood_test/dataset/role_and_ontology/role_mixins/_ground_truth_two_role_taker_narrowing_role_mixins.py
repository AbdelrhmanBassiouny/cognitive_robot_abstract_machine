from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from typing_extensions import TYPE_CHECKING

if TYPE_CHECKING:
    from test.krrood_test.dataset.role_and_ontology.two_role_taker_narrowing import (
        TBaseEntity,
        TBaseHolder,
        TDerivedHolder,
        TSpecificEntity,
    )


@dataclass(eq=False)
class RoleForBaseHolder(ABC):

    @property
    @abstractmethod
    def role_taker(self) -> TBaseHolder: ...

    @property
    def entity(self) -> TBaseEntity:
        return self.role_taker.entity

    @entity.setter
    def entity(self, value: TBaseEntity):
        self.role_taker.entity = value


@dataclass(eq=False)
class RoleForDerivedHolder(RoleForBaseHolder, ABC):

    @property
    @abstractmethod
    def role_taker(self) -> TDerivedHolder: ...

    @property
    def entity(self) -> TSpecificEntity:
        return self.role_taker.entity

    @entity.setter
    def entity(self, value: TSpecificEntity):
        self.role_taker.entity = value

    @property
    def label(self) -> str:
        return self.role_taker.label

    @label.setter
    def label(self, value: str):
        self.role_taker.label = value

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing_extensions import TYPE_CHECKING

if TYPE_CHECKING:
    from test.krrood_test.dataset.role_and_ontology.two_role_taker_narrowing import TBaseEntity, TBaseHolder, TDerivedHolder, TSpecificEntity


@dataclass(eq=False)
class DelegatorForBaseHolder(ABC):
    @property
    @abstractmethod
    def delegatee(self) -> TBaseHolder:
        ...
    @property
    def entity(self) -> TBaseEntity:
        return self.delegatee.entity
    @entity.setter
    def entity(self, value: TBaseEntity):
        self.delegatee.entity = value


@dataclass(eq=False)
class DelegatorForDerivedHolder(DelegatorForBaseHolder, ABC):
    @property
    @abstractmethod
    def delegatee(self) -> TDerivedHolder:
        ...
    @property
    def entity(self) -> TSpecificEntity:
        return self.delegatee.entity
    @entity.setter
    def entity(self, value: TSpecificEntity):
        self.delegatee.entity = value
    @property
    def label(self) -> str:
        return self.delegatee.label
    @label.setter
    def label(self, value: str):
        self.delegatee.label = value


@dataclass(eq=False)
class RoleForBaseHolder(DelegatorForBaseHolder, ABC):
    @property
    @abstractmethod
    def delegatee(self) -> TBaseHolder:
        ...


@dataclass(eq=False)
class RoleForDerivedHolder(DelegatorForDerivedHolder, RoleForBaseHolder, ABC):
    @property
    @abstractmethod
    def delegatee(self) -> TDerivedHolder:
        ...

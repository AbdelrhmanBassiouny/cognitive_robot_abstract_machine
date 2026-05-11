from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing_extensions import TYPE_CHECKING

if TYPE_CHECKING:
    from test.krrood_test.dataset.role_and_ontology.generic_typevar_takers import ConcreteEntity, GenericBaseMixin, TBase, TConcreteEntity, TConcreteTypeTaker, TNarrowedTypeVarTaker, TUnspecializedSubTaker


@dataclass(eq=False)
class DelegatorForGenericBaseMixin(ABC):
    @property
    @abstractmethod
    def delegatee(self) -> GenericBaseMixin:
        ...
    @property
    def entity(self) -> TBase:
        return self.delegatee.entity
    @entity.setter
    def entity(self, value: TBase):
        self.delegatee.entity = value
    @property
    def count(self) -> int:
        return self.delegatee.count
    @count.setter
    def count(self, value: int):
        self.delegatee.count = value


@dataclass(eq=False)
class DelegatorForNarrowedTypeVarTaker(DelegatorForGenericBaseMixin, ABC):
    @property
    @abstractmethod
    def delegatee(self) -> TNarrowedTypeVarTaker:
        ...
    @property
    def entity(self) -> TConcreteEntity:
        return self.delegatee.entity
    @entity.setter
    def entity(self, value: TConcreteEntity):
        self.delegatee.entity = value
    @property
    def label(self) -> str:
        return self.delegatee.label
    @label.setter
    def label(self, value: str):
        self.delegatee.label = value


@dataclass(eq=False)
class DelegatorForConcreteTypeTaker(DelegatorForGenericBaseMixin, ABC):
    @property
    @abstractmethod
    def delegatee(self) -> TConcreteTypeTaker:
        ...
    @property
    def entity(self) -> ConcreteEntity:
        return self.delegatee.entity
    @entity.setter
    def entity(self, value: ConcreteEntity):
        self.delegatee.entity = value
    @property
    def name(self) -> str:
        return self.delegatee.name
    @name.setter
    def name(self, value: str):
        self.delegatee.name = value


@dataclass(eq=False)
class DelegatorForUnspecializedSubTaker(DelegatorForGenericBaseMixin, ABC):
    @property
    @abstractmethod
    def delegatee(self) -> TUnspecializedSubTaker:
        ...
    @property
    def tag(self) -> str:
        return self.delegatee.tag
    @tag.setter
    def tag(self, value: str):
        self.delegatee.tag = value


@dataclass(eq=False)
class RoleForGenericBaseMixin(DelegatorForGenericBaseMixin, ABC):
    @property
    @abstractmethod
    def delegatee(self) -> GenericBaseMixin:
        ...


@dataclass(eq=False)
class RoleForNarrowedTypeVarTaker(DelegatorForNarrowedTypeVarTaker, RoleForGenericBaseMixin, ABC):
    @property
    @abstractmethod
    def delegatee(self) -> TNarrowedTypeVarTaker:
        ...


@dataclass(eq=False)
class RoleForConcreteTypeTaker(DelegatorForConcreteTypeTaker, RoleForGenericBaseMixin, ABC):
    @property
    @abstractmethod
    def delegatee(self) -> TConcreteTypeTaker:
        ...


@dataclass(eq=False)
class RoleForUnspecializedSubTaker(DelegatorForUnspecializedSubTaker, RoleForGenericBaseMixin, ABC):
    @property
    @abstractmethod
    def delegatee(self) -> TUnspecializedSubTaker:
        ...

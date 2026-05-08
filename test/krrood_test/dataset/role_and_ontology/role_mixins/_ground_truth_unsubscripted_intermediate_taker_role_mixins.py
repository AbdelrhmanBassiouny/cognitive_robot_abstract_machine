from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from typing_extensions import TYPE_CHECKING

if TYPE_CHECKING:
    from test.krrood_test.dataset.role_and_ontology.unsubscripted_intermediate_taker import (
        Box,
        Cargo,
        CargoCrate,
        TBoxItem,
        TRack,
        TRackSlot,
        TShelf,
        TShelfContent,
    )


@dataclass(eq=False)
class RoleForBox(ABC):

    @property
    @abstractmethod
    def role_taker(self) -> Box: ...

    @property
    def item(self) -> TBoxItem:
        return self.role_taker.item

    @item.setter
    def item(self, value: TBoxItem):
        self.role_taker.item = value


@dataclass(eq=False)
class RoleForCargoCrate(RoleForBox, ABC):

    @property
    @abstractmethod
    def role_taker(self) -> CargoCrate: ...

    @property
    def item(self) -> Cargo:
        return self.role_taker.item

    @item.setter
    def item(self, value: Cargo):
        self.role_taker.item = value


@dataclass(eq=False)
class RoleForShelf(RoleForCargoCrate, ABC):

    @property
    @abstractmethod
    def role_taker(self) -> TShelf: ...

    @property
    def slot(self) -> TShelfContent:
        return self.role_taker.slot

    @slot.setter
    def slot(self, value: TShelfContent):
        self.role_taker.slot = value


@dataclass(eq=False)
class RoleForRack(RoleForShelf, RoleForCargoCrate, ABC):

    @property
    @abstractmethod
    def role_taker(self) -> TRack: ...

    @property
    def slot(self) -> TRackSlot:
        return self.role_taker.slot

    @slot.setter
    def slot(self, value: TRackSlot):
        self.role_taker.slot = value

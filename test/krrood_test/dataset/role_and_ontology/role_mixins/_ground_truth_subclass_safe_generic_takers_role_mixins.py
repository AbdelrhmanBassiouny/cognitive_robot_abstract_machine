from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from typing_extensions import TYPE_CHECKING

if TYPE_CHECKING:
    from test.krrood_test.dataset.role_and_ontology.subclass_safe_generic_takers import (
        ItemHolder,
        SpecificItemTaker,
        TItem,
        TSpecificItem,
    )


@dataclass(eq=False)
class DelegatorForItemHolder(ABC):

    @property
    @abstractmethod
    def delegatee(self) -> ItemHolder: ...

    @property
    def item(self) -> TItem:
        return self.delegatee.item

    @item.setter
    def item(self, value: TItem):
        self.delegatee.item = value


@dataclass(eq=False)
class DelegatorForSpecificItemTaker(DelegatorForItemHolder, ABC):

    @property
    @abstractmethod
    def delegatee(self) -> SpecificItemTaker: ...

    @property
    def item(self) -> TSpecificItem:
        return self.delegatee.item

    @item.setter
    def item(self, value: TSpecificItem):
        self.delegatee.item = value

    @property
    def label(self) -> str:
        return self.delegatee.label

    @label.setter
    def label(self, value: str):
        self.delegatee.label = value

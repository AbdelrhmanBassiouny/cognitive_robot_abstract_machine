from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from typing_extensions import TYPE_CHECKING

if TYPE_CHECKING:
    from test.krrood_test.dataset.role_and_ontology.independent_typevar_takers import (
        ContentHolder,
        NarrowedRootHolder,
        RootHolder,
        TContent,
        TContent2,
        TMultiTaker,
        TRoot,
        TSpecificRoot,
    )


@dataclass(eq=False)
class DelegatorForRootHolder(ABC):

    @property
    @abstractmethod
    def delegatee(self) -> RootHolder: ...

    @property
    def root(self) -> TRoot:
        return self.delegatee.root

    @root.setter
    def root(self, value: TRoot):
        self.delegatee.root = value


@dataclass(eq=False)
class DelegatorForNarrowedRootHolder(DelegatorForRootHolder, ABC):

    @property
    @abstractmethod
    def delegatee(self) -> NarrowedRootHolder: ...

    @property
    def root(self) -> TSpecificRoot:
        return self.delegatee.root

    @root.setter
    def root(self, value: TSpecificRoot):
        self.delegatee.root = value


@dataclass(eq=False)
class DelegatorForContentHolder(DelegatorForNarrowedRootHolder, ABC):

    @property
    @abstractmethod
    def delegatee(self) -> ContentHolder: ...

    @property
    def content(self) -> TContent:
        return self.delegatee.content

    @content.setter
    def content(self, value: TContent):
        self.delegatee.content = value


@dataclass(eq=False)
class DelegatorForMultiTaker(DelegatorForContentHolder, ABC):

    @property
    @abstractmethod
    def delegatee(self) -> TMultiTaker: ...

    @property
    def content(self) -> TContent2:
        return self.delegatee.content

    @content.setter
    def content(self, value: TContent2):
        self.delegatee.content = value

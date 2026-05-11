from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from semantic_digital_twin.world_description.role_mixins.world_entity_role_mixins import (
    DelegatorForSemanticAnnotation,
    RoleForSemanticAnnotation,
)
from typing import Any, Dict, Self
from typing_extensions import TYPE_CHECKING

if TYPE_CHECKING:
    from semantic_digital_twin.semantic_annotations.semantic_annotations import (
        Floor,
        Room,
    )


@dataclass(eq=False)
class DelegatorForRoom(DelegatorForSemanticAnnotation, ABC):
    @property
    @abstractmethod
    def delegatee(self) -> Room: ...
    @property
    def floor(self) -> Floor:
        return self.delegatee.floor

    @floor.setter
    def floor(self, value: Floor):
        self.delegatee.floor = value


@dataclass(eq=False)
class RoleForRoom(DelegatorForRoom, RoleForSemanticAnnotation, ABC):
    @property
    @abstractmethod
    def delegatee(self) -> Room: ...
    @classmethod
    def from_json(cls, data: Dict[str, Any], **kwargs) -> Self:
        delegatee_type = cls.get_delegatee_type()
        role_taker = delegatee_type.from_json(data, kwargs)
        delegatee_attr = cls.delegatee_attribute_name()
        return cls(**{delegatee_attr: role_taker})

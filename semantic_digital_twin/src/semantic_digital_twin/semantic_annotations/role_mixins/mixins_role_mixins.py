from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from semantic_digital_twin.semantic_annotations.role_mixins.semantic_annotations_role_mixins import (
    RoleForHasRootBody,
)
from semantic_digital_twin.world_description.world_modification import (
    synchronized_attribute_modification,
)
from typing import List, Type
from typing_extensions import TYPE_CHECKING

if TYPE_CHECKING:
    from krrood.adapters.json_serializer import JSONAttributeDiff
    from semantic_digital_twin.semantic_annotations.mixins import (
        HasRootBody,
        HasStorageSpace,
        THasRootBody,
    )
    from semantic_digital_twin.world_description.world_entity import SemanticAnnotation


@dataclass(eq=False)
class RoleForHasStorageSpace(RoleForHasRootBody, ABC):
    @property
    @abstractmethod
    def role_taker(self) -> HasStorageSpace: ...
    @property
    def objects(self) -> List[THasRootBody]:
        return self.role_taker.objects

    @objects.setter
    def objects(self, value: List[THasRootBody]):
        self.role_taker.objects = value

    def _apply_diff(self, diff: JSONAttributeDiff, **kwargs) -> None:
        return self.role_taker._apply_diff(diff, kwargs)

    @synchronized_attribute_modification
    def add_object(self, object: HasRootBody):
        return self.role_taker.add_object(object)

    def get_objects_of_type(
        self, object_type: Type[SemanticAnnotation]
    ) -> List[HasRootBody]:
        return self.role_taker.get_objects_of_type(object_type)

    def update_from_json_diff(self, diffs: List[JSONAttributeDiff], **kwargs) -> None:
        return self.role_taker.update_from_json_diff(diffs, kwargs)

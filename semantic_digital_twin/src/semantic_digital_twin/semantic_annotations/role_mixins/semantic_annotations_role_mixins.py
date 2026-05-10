from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from semantic_digital_twin.semantic_annotations.role_mixins.mixins_role_mixins import (
    DelegatorForHasCaseAsRootBody,
    DelegatorForHasStorageSpace,
)
from semantic_digital_twin.world_description.role_mixins.world_entity_role_mixins import (
    DelegatorForSemanticAnnotation,
)
from typing_extensions import TYPE_CHECKING

if TYPE_CHECKING:
    from semantic_digital_twin.semantic_annotations.semantic_annotations import (
        Bottle,
        Cabinet,
        Floor,
        Furniture,
        Room,
        TLiquid,
        TinCan,
    )
    from semantic_digital_twin.spatial_types.spatial_types import (
        HomogeneousTransformationMatrix,
        Point3,
    )
    from semantic_digital_twin.world_description.geometry import Scale
    from semantic_digital_twin.world_description.world_entity import (
        Body,
        KinematicStructureEntity,
        Region,
    )


@dataclass(eq=False)
class DelegatorForFurniture(DelegatorForSemanticAnnotation, ABC):
    @property
    @abstractmethod
    def delegatee(self) -> Furniture: ...
    @property
    def bodies(self) -> list[Body]:
        return self.delegatee.bodies

    @property
    def kinematic_structure_entities(self) -> list[KinematicStructureEntity]:
        return self.delegatee.kinematic_structure_entities

    @property
    def regions(self) -> list[Region]:
        return self.delegatee.regions


@dataclass(eq=False)
class DelegatorForCabinet(DelegatorForFurniture, DelegatorForHasCaseAsRootBody, ABC):
    @property
    @abstractmethod
    def delegatee(self) -> Cabinet: ...
    @property
    def bodies(self) -> list[Body]:
        return self.delegatee.bodies

    @property
    def global_transform(self) -> HomogeneousTransformationMatrix:
        return self.delegatee.global_transform

    @property
    def kinematic_structure_entities(self) -> list[KinematicStructureEntity]:
        return self.delegatee.kinematic_structure_entities

    @property
    def min_max_points(self) -> tuple[Point3, Point3]:
        return self.delegatee.min_max_points

    @property
    def regions(self) -> list[Region]:
        return self.delegatee.regions

    @property
    def scale(self) -> Scale:
        return self.delegatee.scale


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

    @property
    def bodies(self) -> list[Body]:
        return self.delegatee.bodies

    @property
    def kinematic_structure_entities(self) -> list[KinematicStructureEntity]:
        return self.delegatee.kinematic_structure_entities

    @property
    def regions(self) -> list[Region]:
        return self.delegatee.regions


@dataclass(eq=False)
class DelegatorForBottle(
    DelegatorForHasCaseAsRootBody, DelegatorForHasStorageSpace, ABC
):
    @property
    @abstractmethod
    def delegatee(self) -> Bottle: ...
    @property
    def objects(self) -> list[TLiquid]:
        return self.delegatee.objects

    @objects.setter
    def objects(self, value: list[TLiquid]):
        self.delegatee.objects = value

    @property
    def bodies(self) -> list[Body]:
        return self.delegatee.bodies

    @property
    def global_transform(self) -> HomogeneousTransformationMatrix:
        return self.delegatee.global_transform

    @property
    def kinematic_structure_entities(self) -> list[KinematicStructureEntity]:
        return self.delegatee.kinematic_structure_entities

    @property
    def min_max_points(self) -> tuple[Point3, Point3]:
        return self.delegatee.min_max_points

    @property
    def regions(self) -> list[Region]:
        return self.delegatee.regions

    @property
    def scale(self) -> Scale:
        return self.delegatee.scale


@dataclass(eq=False)
class DelegatorForTinCan(DelegatorForHasStorageSpace, ABC):
    @property
    @abstractmethod
    def delegatee(self) -> TinCan: ...
    @property
    def bodies(self) -> list[Body]:
        return self.delegatee.bodies

    @property
    def global_transform(self) -> HomogeneousTransformationMatrix:
        return self.delegatee.global_transform

    @property
    def kinematic_structure_entities(self) -> list[KinematicStructureEntity]:
        return self.delegatee.kinematic_structure_entities

    @property
    def min_max_points(self) -> tuple[Point3, Point3]:
        return self.delegatee.min_max_points

    @property
    def regions(self) -> list[Region]:
        return self.delegatee.regions

    @property
    def scale(self) -> Scale:
        return self.delegatee.scale

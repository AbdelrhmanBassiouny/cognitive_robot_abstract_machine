from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from semantic_digital_twin.semantic_annotations.role_mixins.mixins_role_mixins import (
    RoleForHasStorageSpace,
)
from semantic_digital_twin.world_description.world_modification import (
    synchronized_attribute_modification,
)
from typing import List, Optional, Type
from typing_extensions import TYPE_CHECKING

if TYPE_CHECKING:
    from krrood.adapters.json_serializer import JSONAttributeDiff
    from probabilistic_model.probabilistic_circuit.rx.probabilistic_circuit import (
        ProbabilisticCircuit,
    )
    from random_events.product_algebra import Event
    from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
    from semantic_digital_twin.mixin import (
        HasSimulatorProperties,
        SimulatorAdditionalProperty,
    )
    from semantic_digital_twin.semantic_annotations.mixins import (
        HasRootBody,
        HasRootKinematicStructureEntity,
        HasSupportingSurface,
        TKinematicStructureEntity,
    )
    from semantic_digital_twin.semantic_annotations.semantic_annotations import (
        Bottle,
        Cabinet,
        Floor,
        Room,
        THasRootBody,
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
        SemanticAnnotation,
        WorldEntity,
        WorldEntityWithID,
    )
    from uuid import UUID


@dataclass(eq=False)
class RoleForHasSimulatorProperties(ABC):
    @property
    @abstractmethod
    def role_taker(self) -> HasSimulatorProperties: ...
    @property
    def simulator_additional_properties(self) -> list[SimulatorAdditionalProperty]:
        return self.role_taker.simulator_additional_properties

    @simulator_additional_properties.setter
    def simulator_additional_properties(self, value: list[SimulatorAdditionalProperty]):
        self.role_taker.simulator_additional_properties = value


@dataclass(eq=False)
class RoleForWorldEntity(ABC):
    @property
    @abstractmethod
    def role_taker(self) -> WorldEntity: ...
    @property
    def name(self) -> PrefixedName:
        return self.role_taker.name

    @name.setter
    def name(self, value: PrefixedName):
        self.role_taker.name = value


@dataclass(eq=False)
class RoleForWorldEntityWithID(RoleForWorldEntity, ABC):
    @property
    @abstractmethod
    def role_taker(self) -> WorldEntityWithID: ...
    @property
    def id(self) -> UUID:
        return self.role_taker.id

    @id.setter
    def id(self, value: UUID):
        self.role_taker.id = value


@dataclass(eq=False)
class RoleForSemanticAnnotation(RoleForWorldEntityWithID, ABC):
    @property
    @abstractmethod
    def role_taker(self) -> SemanticAnnotation: ...
    @property
    def kinematic_structure_entities(self) -> list[KinematicStructureEntity]:
        return self.role_taker.kinematic_structure_entities

    @property
    def regions(self) -> list[Region]:
        return self.role_taker.regions


@dataclass(eq=False)
class RoleForHasRootKinematicStructureEntity(RoleForSemanticAnnotation, ABC):
    @property
    @abstractmethod
    def role_taker(self) -> HasRootKinematicStructureEntity: ...
    @property
    def root(self) -> TKinematicStructureEntity:
        return self.role_taker.root

    @root.setter
    def root(self, value: TKinematicStructureEntity):
        self.role_taker.root = value

    @property
    def global_transform(self) -> HomogeneousTransformationMatrix:
        return self.role_taker.global_transform

    @property
    def min_max_points(self) -> tuple[Point3, Point3]:
        return self.role_taker.min_max_points

    @property
    def scale(self) -> Scale:
        return self.role_taker.scale


@dataclass(eq=False)
class RoleForHasRootBody(RoleForHasRootKinematicStructureEntity, ABC):
    @property
    @abstractmethod
    def role_taker(self) -> HasRootBody: ...
    @property
    def bodies(self) -> list[Body]:
        return self.role_taker.bodies


@dataclass(eq=False)
class RoleForHasSupportingSurface(RoleForHasRootBody, ABC):
    @property
    @abstractmethod
    def role_taker(self) -> HasSupportingSurface: ...
    @property
    def supporting_surface(self) -> Region:
        return self.role_taker.supporting_surface

    @supporting_surface.setter
    def supporting_surface(self, value: Region):
        self.role_taker.supporting_surface = value

    def _2d_gaussian_sampler_from_2d_sample_space(
        self,
        objects_of_interest: List[HasRootBody],
        variance: float,
        sample_space: Event,
    ) -> Optional[ProbabilisticCircuit]:
        return self.role_taker._2d_gaussian_sampler_from_2d_sample_space(
            objects_of_interest, variance, sample_space
        )

    def _2d_surface_sample_space_excluding_objects(self, object_bloat: float) -> Event:
        return self.role_taker._2d_surface_sample_space_excluding_objects(object_bloat)

    def _build_surface_sampler(
        self,
        category_of_interest: Optional[Type[SemanticAnnotation]] = None,
        object_bloat: float = 0.1,
    ):
        return self.role_taker._build_surface_sampler(
            category_of_interest, object_bloat
        )

    def _untruncated_2d_gaussian_sampler(
        self,
        objects_of_interest: List[HasRootBody],
        variance: float,
    ) -> ProbabilisticCircuit:
        return self.role_taker._untruncated_2d_gaussian_sampler(
            objects_of_interest, variance
        )

    @synchronized_attribute_modification
    def add_supporting_surface(self, region: Region):
        return self.role_taker.add_supporting_surface(region)

    def calculate_supporting_surface(
        self,
        upward_threshold: float = 0.95,
        clearance_threshold: float = 0.5,
        min_surface_area: float = 0.0225,  # 15cm x 15cm
    ) -> Optional[Region]:
        return self.role_taker.calculate_supporting_surface(
            upward_threshold, clearance_threshold, min_surface_area
        )

    def infer_objects_on_surface(self):
        return self.role_taker.infer_objects_on_surface()

    def sample_points_from_surface(
        self,
        body_to_sample_for: Optional[HasRootBody] = None,
        category_of_interest: Optional[Type[SemanticAnnotation]] = None,
        amount: int = 100,
    ) -> List[Point3]:
        return self.role_taker.sample_points_from_surface(
            body_to_sample_for, category_of_interest, amount
        )


@dataclass(eq=False)
class RoleForCabinet(RoleForHasSupportingSurface, ABC):
    @property
    @abstractmethod
    def role_taker(self) -> Cabinet: ...
    @property
    def objects(self) -> List[THasRootBody]:
        return self.role_taker.objects

    @objects.setter
    def objects(self, value: List[THasRootBody]):
        self.role_taker.objects = value


@dataclass(eq=False)
class RoleForRoom(RoleForSemanticAnnotation, ABC):
    @property
    @abstractmethod
    def role_taker(self) -> Room: ...
    @property
    def floor(self) -> Floor:
        return self.role_taker.floor

    @floor.setter
    def floor(self, value: Floor):
        self.role_taker.floor = value

    def _apply_diff(self, diff: JSONAttributeDiff, **kwargs) -> None:
        return self.role_taker._apply_diff(diff, kwargs)

    def update_from_json_diff(self, diffs: List[JSONAttributeDiff], **kwargs) -> None:
        return self.role_taker.update_from_json_diff(diffs, kwargs)


@dataclass(eq=False)
class RoleForBottle(RoleForHasStorageSpace, RoleForHasSupportingSurface, ABC):
    @property
    @abstractmethod
    def role_taker(self) -> Bottle: ...


@dataclass(eq=False)
class RoleForTinCan(RoleForHasStorageSpace, RoleForHasRootBody, ABC):
    @property
    @abstractmethod
    def role_taker(self) -> TinCan: ...

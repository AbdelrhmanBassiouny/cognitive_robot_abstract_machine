from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from semantic_digital_twin.semantic_annotations.role_mixins.mixins_role_mixins import (
    DelegatorForHasRootBody,
    DelegatorForHasStorageSpace,
    DelegatorForSemanticAnnotation,
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
    from semantic_digital_twin.semantic_annotations.mixins import (
        HasRootBody,
        HasSupportingSurface,
    )
    from semantic_digital_twin.semantic_annotations.semantic_annotations import (
        Bottle,
        Cabinet,
        Floor,
        Room,
        TLiquid,
        TinCan,
    )
    from semantic_digital_twin.spatial_types.spatial_types import Point3
    from semantic_digital_twin.world_description.world_entity import (
        Region,
        SemanticAnnotation,
    )


@dataclass(eq=False)
class DelegatorForHasSupportingSurface(DelegatorForHasStorageSpace, ABC):
    @property
    @abstractmethod
    def delegatee(self) -> HasSupportingSurface: ...
    @property
    def supporting_surface(self) -> Region:
        return self.delegatee.supporting_surface

    @supporting_surface.setter
    def supporting_surface(self, value: Region):
        self.delegatee.supporting_surface = value

    def _2d_gaussian_sampler_from_2d_sample_space(
        self,
        objects_of_interest: List[HasRootBody],
        variance: float,
        sample_space: Event,
    ) -> Optional[ProbabilisticCircuit]:
        return self.delegatee._2d_gaussian_sampler_from_2d_sample_space(
            objects_of_interest, variance, sample_space
        )

    def _2d_surface_sample_space_excluding_objects(self, object_bloat: float) -> Event:
        return self.delegatee._2d_surface_sample_space_excluding_objects(object_bloat)

    def _build_surface_sampler(
        self,
        category_of_interest: Optional[Type[SemanticAnnotation]] = None,
        object_bloat: float = 0.1,
    ):
        return self.delegatee._build_surface_sampler(category_of_interest, object_bloat)

    def _untruncated_2d_gaussian_sampler(
        self,
        objects_of_interest: List[HasRootBody],
        variance: float,
    ) -> ProbabilisticCircuit:
        return self.delegatee._untruncated_2d_gaussian_sampler(
            objects_of_interest, variance
        )

    @synchronized_attribute_modification
    def add_supporting_surface(self, region: Region):
        return self.delegatee.add_supporting_surface(region)

    def calculate_supporting_surface(
        self,
        upward_threshold: float = 0.95,
        clearance_threshold: float = 0.5,
        min_surface_area: float = 0.0225,  # 15cm x 15cm
    ) -> Optional[Region]:
        return self.delegatee.calculate_supporting_surface(
            upward_threshold, clearance_threshold, min_surface_area
        )

    def infer_objects_on_surface(self):
        return self.delegatee.infer_objects_on_surface()

    def sample_points_from_surface(
        self,
        body_to_sample_for: Optional[HasRootBody] = None,
        category_of_interest: Optional[Type[SemanticAnnotation]] = None,
        amount: int = 100,
    ) -> List[Point3]:
        return self.delegatee.sample_points_from_surface(
            body_to_sample_for, category_of_interest, amount
        )


@dataclass(eq=False)
class DelegatorForCabinet(DelegatorForHasSupportingSurface, ABC):
    @property
    @abstractmethod
    def delegatee(self) -> Cabinet: ...


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

    def _apply_diff(self, diff: JSONAttributeDiff, **kwargs) -> None:
        return self.delegatee._apply_diff(diff, kwargs)

    def update_from_json_diff(self, diffs: List[JSONAttributeDiff], **kwargs) -> None:
        return self.delegatee.update_from_json_diff(diffs, kwargs)


@dataclass(eq=False)
class DelegatorForBottle(DelegatorForHasSupportingSurface, ABC):
    @property
    @abstractmethod
    def delegatee(self) -> Bottle: ...
    @property
    def objects(self) -> list[TLiquid]:
        return self.delegatee.objects

    @objects.setter
    def objects(self, value: list[TLiquid]):
        self.delegatee.objects = value


@dataclass(eq=False)
class DelegatorForTinCan(DelegatorForHasStorageSpace, DelegatorForHasRootBody, ABC):
    @property
    @abstractmethod
    def delegatee(self) -> TinCan: ...

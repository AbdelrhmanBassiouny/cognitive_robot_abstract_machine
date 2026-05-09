from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Self, Tuple, Union
from typing_extensions import TYPE_CHECKING

if TYPE_CHECKING:
    from casadi.casadi import SX
    from collections.abc import Iterable
    from krrood.adapters.json_serializer import JSONAttributeDiff
    from krrood.symbolic_math.symbolic_math import (
        CompiledFunction,
        FloatVariable,
        GenericSymbolicType,
        Matrix,
        Scalar,
        VariableParameters,
        Vector,
    )
    from semantic_digital_twin.spatial_types.spatial_types import (
        HomogeneousTransformationMatrix,
        Point3,
        Pose,
        Quaternion,
        RotationMatrix,
        SpatialType,
        np,
    )
    from semantic_digital_twin.world_description.world_entity import (
        KinematicStructureEntity,
    )
    from types import ScalarData


@dataclass(eq=False)
class DelegatorForSpatialType(ABC):
    @property
    @abstractmethod
    def delegatee(self) -> SpatialType: ...
    @property
    def casadi_sx(self) -> SX:
        return self.delegatee.casadi_sx

    @casadi_sx.setter
    def casadi_sx(self, value: SX):
        self.delegatee.casadi_sx = value

    @property
    def reference_frame(self) -> Union[KinematicStructureEntity, None]:
        return self.delegatee.reference_frame

    @reference_frame.setter
    def reference_frame(self, value: Union[KinematicStructureEntity, None]):
        self.delegatee.reference_frame = value

    def __deepcopy__(self, memo) -> Self:
        return self.delegatee.__deepcopy__(memo)

    @staticmethod
    def _ensure_consistent_frame(
        spatial_objects: List[Optional[SpatialType]],
    ) -> Optional[KinematicStructureEntity]:
        from semantic_digital_twin.spatial_types.spatial_types import Pose

        return Pose._ensure_consistent_frame(spatial_objects)


@dataclass(eq=False, init=False, repr=False)
class DelegatorForPose(DelegatorForSpatialType, ABC):
    @property
    @abstractmethod
    def delegatee(self) -> Pose: ...
    @property
    def casadi_sx(self) -> SX:
        return self.delegatee.casadi_sx

    @casadi_sx.setter
    def casadi_sx(self, value: SX):
        self.delegatee.casadi_sx = value

    @property
    def shape(self) -> tuple[int, int]:
        return self.delegatee.shape

    @property
    def x(self) -> Scalar:
        return self.delegatee.x

    @x.setter
    def x(self, value: Scalar):
        self.delegatee.x = value

    @property
    def y(self) -> Scalar:
        return self.delegatee.y

    @y.setter
    def y(self, value: Scalar):
        self.delegatee.y = value

    @property
    def z(self) -> Scalar:
        return self.delegatee.z

    @z.setter
    def z(self, value: Scalar):
        self.delegatee.z = value

    def __abs__(self) -> Self:
        return self.delegatee.__abs__()

    def __array__(self):
        return self.delegatee.__array__()

    def __copy__(self) -> Self:
        return self.delegatee.__copy__()

    def __getitem__(
        self, item: np.ndarray | int | slice | Tuple[int | slice, int | slice]
    ) -> Scalar | Vector:
        return self.delegatee.__getitem__(item)

    def __hash__(self):
        return self.delegatee.__hash__()

    def __len__(self) -> int:
        return self.delegatee.__len__()

    def __neg__(self) -> Self:
        return self.delegatee.__neg__()

    def __repr__(self):
        return self.delegatee.__repr__()

    def __setitem__(
        self,
        key: int | slice | Tuple[int | slice, int | slice],
        value: ScalarData,
    ):
        return self.delegatee.__setitem__(key, value)

    def __str__(self):
        return self.delegatee.__str__()

    def _apply_diff(self, diff: JSONAttributeDiff, **kwargs) -> None:
        return self.delegatee._apply_diff(diff, kwargs)

    def _verify_type(self):
        return self.delegatee._verify_type()

    def compile(
        self,
        parameters: Optional[VariableParameters] = None,
        sparse: bool = False,
    ) -> CompiledFunction:
        return self.delegatee.compile(parameters, sparse)

    def equivalent(self, other: ScalarData) -> bool:
        return self.delegatee.equivalent(other)

    def evaluate(self) -> np.ndarray:
        return self.delegatee.evaluate()

    def flatten(self) -> Vector:
        return self.delegatee.flatten()

    def free_variables(self) -> List[FloatVariable]:
        return self.delegatee.free_variables()

    def is_constant(self) -> bool:
        return self.delegatee.is_constant()

    def is_scalar(self) -> bool:
        return self.delegatee.is_scalar()

    def jacobian(self, variables: Iterable[FloatVariable]) -> Matrix:
        return self.delegatee.jacobian(variables)

    def jacobian_ddot(
        self,
        variables: Iterable[FloatVariable],
        variables_dot: Iterable[FloatVariable],
        variables_ddot: Iterable[FloatVariable],
    ) -> Matrix:
        return self.delegatee.jacobian_ddot(variables, variables_dot, variables_ddot)

    def jacobian_dot(
        self,
        variables: Iterable[FloatVariable],
        variables_dot: Iterable[FloatVariable],
    ) -> Matrix:
        return self.delegatee.jacobian_dot(variables, variables_dot)

    def pretty_str(self) -> List[List[str]]:
        return self.delegatee.pretty_str()

    def safe_division(
        self,
        other: GenericSymbolicType,
        if_nan: Optional[ScalarData] = None,
    ) -> GenericSymbolicType:
        return self.delegatee.safe_division(other, if_nan)

    def second_order_total_derivative(
        self,
        variables: Iterable[FloatVariable],
        variables_dot: Iterable[FloatVariable],
        variables_ddot: Iterable[FloatVariable],
    ) -> Vector:
        return self.delegatee.second_order_total_derivative(
            variables, variables_dot, variables_ddot
        )

    def substitute(
        self,
        old_variables: List[FloatVariable],
        new_variables: List[ScalarData] | Vector,
    ) -> Self:
        return self.delegatee.substitute(old_variables, new_variables)

    def to_homogeneous_matrix(self) -> HomogeneousTransformationMatrix:
        return self.delegatee.to_homogeneous_matrix()

    def to_json(self) -> Dict[str, Any]:
        return self.delegatee.to_json()

    def to_list(self) -> list:
        return self.delegatee.to_list()

    def to_np(self) -> np.ndarray:
        return self.delegatee.to_np()

    def to_position(self) -> Point3:
        return self.delegatee.to_position()

    def to_quaternion(self) -> Quaternion:
        return self.delegatee.to_quaternion()

    def to_rotation_matrix(self) -> RotationMatrix:
        return self.delegatee.to_rotation_matrix()

    def total_derivative(
        self,
        variables: Iterable[FloatVariable],
        variables_dot: Iterable[FloatVariable],
    ) -> Vector:
        return self.delegatee.total_derivative(variables, variables_dot)

    def update_from_json_diff(self, diffs: List[JSONAttributeDiff], **kwargs) -> None:
        return self.delegatee.update_from_json_diff(diffs, kwargs)

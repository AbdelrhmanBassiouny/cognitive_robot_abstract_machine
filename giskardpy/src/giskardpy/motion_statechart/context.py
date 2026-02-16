from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from typing_extensions import Self, Dict, Type, TypeVar, TYPE_CHECKING

from krrood.symbolic_math.symbolic_math import FloatVariable
from semantic_digital_twin.collision_checking.collision_manager import CollisionManager
from semantic_digital_twin.world import World
from .variable_managers.auxiliary_variable_manager import AuxiliaryVariableManager
from krrood.symbolic_math.float_variable_data import FloatVariableData
from ..qp.qp_controller_config import QPControllerConfig

from .exceptions import MissingContextExtensionError


@dataclass
class ContextExtension:
    """
    Context extension for build context.
    Used together with require_extension to augment BuildContext with custom data.
    """


GenericContextExtension = TypeVar("GenericContextExtension", bound=ContextExtension)


@dataclass
class MotionStatechartContext:
    """
    Context used during the build phase of a MotionStatechartNode.
    """

    world: World
    """There world in which to execute the Motion Statechart."""
    control_cycle_variable: FloatVariable = field(init=False)
    """Auxiliary variable used to count control cycles, can be used my Motion StatechartNodes to implement time-dependent actions."""
    float_variable_data: FloatVariableData = field(default_factory=FloatVariableData)
    auxiliary_variable_manager: AuxiliaryVariableManager = field(init=False)
    """Auxiliary variable manager used by nodes to create auxiliary variables."""
    qp_controller_config: QPControllerConfig = field(
        default_factory=QPControllerConfig.create_with_simulation_defaults
    )
    """Optional configuration for the QP Controller. Is only needed when constraints are present in the motion statechart."""
    extensions: Dict[Type[ContextExtension], ContextExtension] = field(
        default_factory=dict, repr=False, init=False
    )
    """
    Dictionary of extensions used to augment the build context.
    Ros2 extensions are automatically added to the build context when using the Ros2Executor.
    """

    def __post_init__(self):
        self.auxiliary_variable_manager = AuxiliaryVariableManager(
            self.float_variable_data
        )

    @property
    def collision_manager(self) -> CollisionManager:
        return self.world.collision_manager

    def require_extension(
        self, extension_type: Type[GenericContextExtension]
    ) -> GenericContextExtension:
        """
        Return an extension instance or raise ``MissingContextExtensionError``.
        """
        extension = self.extensions.get(extension_type)
        if extension is None:
            raise MissingContextExtensionError(expected_extension=extension_type)
        return extension

    def add_extension(self, extension: GenericContextExtension):
        """
        Extend the build context with a custom extension.
        """
        extension_type = type(extension)
        if extension_type in self.extensions:
            raise ValueError(f"Extension of type {extension_type} already exists.")
        self.extensions[extension_type] = extension

    @classmethod
    def empty(cls) -> Self:
        return cls(
            world=World(),
            float_variable_data=None,
            qp_controller_config=None,
        )

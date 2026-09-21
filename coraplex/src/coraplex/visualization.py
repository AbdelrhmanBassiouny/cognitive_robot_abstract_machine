"""Optional world visualization selected without changing a robot plan."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from collections.abc import Callable
from contextlib import ExitStack
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from enum import StrEnum
from importlib.metadata import entry_points
from types import TracebackType

from typing_extensions import TYPE_CHECKING, ClassVar, Self

from coraplex.datastructures.enums import VisualizationBackend
from coraplex.plans.plan_node import PlanNode
from krrood.exceptions import DataclassException
from semantic_digital_twin.adapters.rerun import RerunAdapter, RerunMode

if TYPE_CHECKING:
    from rclpy.node import Node

    from coraplex.plans.plan import Plan
    from coraplex.plans.plan_callbacks import PlanCallback
    from semantic_digital_twin.world import World

try:
    import rclpy
    from semantic_digital_twin.adapters.ros.visualization.viz_marker import (
        VizMarkerPublisher,
    )
except ImportError:
    rclpy = None
    VizMarkerPublisher = None


# %% provider contract
@dataclass
class PlanVisualization(ABC):
    """A visualization provider observing a world and its executed plans."""

    world: World
    """The world presented by this provider."""

    @abstractmethod
    def start(self) -> Self:
        """Start serving this world and return the provider."""

    @abstractmethod
    def stop(self) -> None:
        """Stop serving and release resources owned by this provider."""

    @abstractmethod
    def plan_callback(self, plan: Plan) -> PlanCallback:
        """Create an execution observer for a plan.

        :param plan: The plan to observe.
        :return: A callback registered by the visualization owner.
        """


class VisualizationOption(StrEnum):
    """Configuration names for optional visualization providers."""

    BACKEND = "CORAPLEX_VISUALIZATION"
    """Environment setting selecting the renderer."""
    RERUN_MODE = "CORAPLEX_RERUN_MODE"
    """Environment setting selecting Rerun's output mode."""
    RERUN_TARGET = "CORAPLEX_RERUN_TARGET"
    """Environment setting selecting Rerun's file or server."""
    PROVIDER_GROUP = "coraplex.visualizations"
    """Installed entry points implementing PlanVisualization."""


@dataclass
class UnknownVisualizationOption(DataclassException):
    """A configuration value does not name a supported visualization option."""

    variable: VisualizationOption
    """The environment setting containing the unknown value."""
    value: str
    """The rejected value."""

    def error_message(self) -> str:
        """Identify the rejected environment setting and value."""
        return f"Unknown visualization option {self.variable}={self.value!r}."

    def suggest_correction(self) -> str:
        """Describe how to select a supported renderer configuration."""
        return "Choose a supported visualization backend or Rerun mode."


@dataclass
class VisualizationBackendUnavailable(DataclassException):
    """A selected renderer has no available provider."""

    backend: VisualizationBackend
    """The renderer that could not be started."""

    def error_message(self) -> str:
        """Identify the renderer whose provider could not be loaded."""
        return f"Visualization backend {self.backend.value!r} is unavailable."

    def suggest_correction(self) -> str:
        """Describe how to make the selected provider available."""
        return "Install the selected visualization provider or select another backend."


# %% visualization owner
@dataclass
class VisualizationSession:
    """Close visualizations acquired in a context when execution leaves that context."""

    _current: ClassVar[ContextVar[VisualizationSession | None]] = ContextVar(
        "visualization_session", default=None
    )
    """The cleanup scope active in the current execution context."""
    _cleanup: ExitStack = field(default_factory=ExitStack, init=False)
    """Resource cleanup callbacks in reverse acquisition order."""
    _token: Token[VisualizationSession | None] = field(init=False)
    """The previous scope restored when this context exits."""

    def __enter__(self) -> Self:
        """Make this session the owner of subsequently started visualizations."""
        self._token = self._current.set(self)
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close acquired resources and restore the enclosing session.

        :param exception_type: The exception type raised inside the scope, if any.
        :param exception: The original exception propagated after cleanup.
        :param traceback: The traceback associated with that exception.
        """
        try:
            self._cleanup.close()
        finally:
            self._current.reset(self._token)

    @classmethod
    def is_active(cls) -> bool:
        """Return whether the current context owns visualization cleanup."""
        return cls._current.get() is not None

    @classmethod
    def register(cls, cleanup: Callable[[], None]) -> None:
        """Register cleanup in the active session, if one exists.

        :param cleanup: Release an acquired resource without requiring its caller to retain it.
        """
        current = cls._current.get()
        if current is not None:
            current._cleanup.callback(cleanup)


@dataclass
class WorldVisualization:
    """Own a selected renderer and the execution observers attached to it."""

    world: World
    """The observed world."""
    backend: VisualizationBackend = VisualizationBackend.NONE
    """The explicitly selected renderer."""
    ros_node: Node | None = field(default=None, kw_only=True)
    """A borrowed ROS node, or a node created for an RViz renderer."""
    collision_visualization: bool = field(default=False, kw_only=True)
    """Whether the RViz renderer also publishes native collision results."""
    rerun_mode: RerunMode = field(default=RerunMode.SPAWN, kw_only=True)
    """Where the native Rerun adapter sends its recording."""
    rerun_target: str | None = field(default=None, kw_only=True)
    """The Rerun output file or server."""
    rviz_publisher: VizMarkerPublisher | None = field(default=None, init=False)
    """The owned RViz marker publisher."""
    rerun_adapter: RerunAdapter | None = field(default=None, init=False)
    """The owned native Rerun adapter."""
    cramera_visualization: PlanVisualization | None = field(default=None, init=False)
    """The optional installed browser visualization provider."""
    _callbacks: list[PlanCallback] = field(default_factory=list, init=False)
    """Plan callbacks registered by this owner."""
    _owns_node: bool = field(default=False, init=False)
    """Whether this owner created its ROS node."""
    _owns_context: bool = field(default=False, init=False)
    """Whether this owner initialized its ROS context."""

    @classmethod
    def from_environment(
        cls,
        world: World,
        default_backend: VisualizationBackend = VisualizationBackend.NONE,
        *,
        ros_node: Node | None = None,
        collision_visualization: bool = False,
    ) -> Self:
        """Read optional renderer settings while preserving the supplied default.

        :param world: The world to visualize.
        :param default_backend: Renderer used without an explicit setting.
        :param ros_node: An existing ROS node available for RViz publishing.
        :param collision_visualization: Whether to publish RViz collision results.
        """
        backend = (
            os.environ.get(VisualizationOption.BACKEND, default_backend.value)
            .strip()
            .lower()
        )
        mode = (
            os.environ.get(VisualizationOption.RERUN_MODE, RerunMode.SPAWN.value)
            .strip()
            .lower()
        )
        if backend not in {member.value for member in VisualizationBackend}:
            raise UnknownVisualizationOption(VisualizationOption.BACKEND, backend)
        if mode not in {member.value for member in RerunMode}:
            raise UnknownVisualizationOption(VisualizationOption.RERUN_MODE, mode)
        return cls(
            world=world,
            backend=VisualizationBackend(backend),
            ros_node=ros_node,
            collision_visualization=collision_visualization,
            rerun_mode=RerunMode(mode),
            rerun_target=os.environ.get(VisualizationOption.RERUN_TARGET),
        )

    @property
    def is_rendering(self) -> bool:
        """:return: Whether this owner has a started renderer."""
        return any(
            renderer is not None
            for renderer in (
                self.rviz_publisher,
                self.rerun_adapter,
                self.cramera_visualization,
            )
        )

    def start(self) -> Self:
        """Start the selected renderer once.

        :return: This visualization owner.
        """
        if self.is_rendering:
            return self
        match self.backend:
            case VisualizationBackend.RVIZ:
                self._start_rviz()
            case VisualizationBackend.RERUN:
                self.rerun_adapter = RerunAdapter(
                    _world=self.world,
                    mode=self.rerun_mode,
                    target=self.rerun_target,
                    state_history=True,
                )
            case VisualizationBackend.CRAMERA:
                providers = entry_points(
                    group=VisualizationOption.PROVIDER_GROUP, name=self.backend.value
                )
                if len(providers) != 1:
                    raise VisualizationBackendUnavailable(self.backend)
                provider_type = next(iter(providers)).load()
                if not issubclass(provider_type, PlanVisualization):
                    raise VisualizationBackendUnavailable(self.backend)
                self.cramera_visualization = provider_type(world=self.world).start()
        if self.is_rendering:
            VisualizationSession.register(self.stop)
        return self

    def _start_rviz(self) -> None:
        """Start native marker publishing, borrowing an existing ROS node if supplied."""
        if VizMarkerPublisher is None:
            raise VisualizationBackendUnavailable(self.backend)
        if self.ros_node is None:
            self._owns_context = not rclpy.ok()
            if self._owns_context:
                rclpy.init()
            self.ros_node = rclpy.create_node("coraplex_visualization")
            self._owns_node = True
        self.rviz_publisher = VizMarkerPublisher(_world=self.world, node=self.ros_node)
        if self.collision_visualization:
            self.rviz_publisher.with_collision_visualization()

    def attach_plan(self, plan: Plan | PlanNode) -> None:
        """Observe a plan through the running optional provider.

        :param plan: A plan or its root node.
        """
        if self.cramera_visualization is None:
            return
        observed_plan = plan.plan if isinstance(plan, PlanNode) else plan
        if any(callback.plan is observed_plan for callback in self._callbacks):
            return
        callback = self.cramera_visualization.plan_callback(observed_plan)
        observed_plan.node_callbacks.append(callback)
        self._callbacks.append(callback)

    def stop(self) -> None:
        """Remove owned observers and renderers, retaining borrowed ROS resources."""
        for callback in self._callbacks:
            callback.plan.node_callbacks[:] = [
                registered
                for registered in callback.plan.node_callbacks
                if registered is not callback
            ]
        self._callbacks.clear()
        if self.cramera_visualization is not None:
            self.cramera_visualization.stop()
            self.cramera_visualization = None
        if self.rerun_adapter is not None:
            self.rerun_adapter.stop()
            self.rerun_adapter = None
        if self.rviz_publisher is not None:
            self.rviz_publisher.stop()
            self.rviz_publisher = None
        if self._owns_node:
            self.ros_node.destroy_node()
            self.ros_node = None
            self._owns_node = False
        if self._owns_context:
            if rclpy.ok():
                rclpy.shutdown()
            self._owns_context = False

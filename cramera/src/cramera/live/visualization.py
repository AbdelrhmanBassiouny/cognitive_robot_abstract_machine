"""
The cramera backend of :class:`coraplex.visualization.WorldVisualization`.

Binds the live bridge to the world object itself: world state and model changes reach
the viewer through the world's own callbacks, and plan execution through a
:class:`~coraplex.plans.plan_callbacks.PlanCallback`. No parser or executor hooks are
involved — whatever world a demo builds, however it builds it, is what the viewer
shows.
"""

from __future__ import annotations

import atexit
from dataclasses import dataclass, field
from functools import partial

from typing_extensions import Any, Callable, Optional, TYPE_CHECKING

from coraplex.plans.plan_callbacks import PlanCallback
from coraplex.plans.plan_node import MotionNode, PlanNode
from coraplex.visualization import PlanVisualization, VisualizationSession
from semantic_digital_twin.callbacks.callback import (
    ModelChangeCallback,
    StateChangeCallback,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.geometry import MeshFileStorage

from cramera.live.bridge import Bridge
from cramera.live.http import DEFAULT_PORT, serve
from cramera.live.recording import Recording
from cramera.live.recording_bundle import finalize_recording
from cramera.live.ros_markers import RosMarkerListener
from cramera.logging_setup import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from coraplex.plans.plan import Plan
    from giskardpy.motion_statechart.motion_statechart import MotionStatechart

# %% world synchronization


@dataclass(eq=False)
class WorldStateSync(StateChangeCallback):
    """
    Publishes a world snapshot to the bridge whenever the world's state changes.
    """

    bridge: Bridge = field(kw_only=True)
    """
    The bridge the snapshots are published to.
    """

    def on_state_change(self, **kwargs: Any) -> None:
        """
        Publish and record the world's updated state.

        :param kwargs: Metadata provided by the native callback dispatcher.
        """
        self.bridge.snapshot()
        if self.bridge.recording is not None:
            self.bridge.recording.append(
                self.bridge.state,
                self.bridge.running_step(),
                self.bridge.executing_statechart(),
            )


@dataclass(eq=False)
class WorldModelSync(ModelChangeCallback):
    """
    Refreshes the bridge's body and geometry catalogs when the world model changes.
    """

    bridge: Bridge = field(kw_only=True)
    """
    The bridge whose catalogs are refreshed.
    """

    def on_model_change(self, **kwargs: Any) -> None:
        """
        Refresh the published model after a structural change.

        :param kwargs: Metadata provided by the native callback dispatcher.
        """
        self.bridge.observe_model_change()


# %% plan synchronization


@dataclass
class BridgePlanCallback(PlanCallback):
    """
    Feeds a plan's execution into the live bridge: per-node progress as its nodes start
    and end, and the executing motion statechart on every executor tick.
    """

    bridge: Bridge = field(kw_only=True)
    """
    The bridge the plan's execution is published to.
    """

    def on_start(self, node: PlanNode) -> None:
        """
        Publish execution of the started node.

        :param node: The plan node that started.
        """
        if isinstance(node, MotionNode):
            self.bridge.observe_motion_started(node)
            return
        self.bridge.snapshot_plan()

    def on_end(self, node: PlanNode) -> None:
        """
        Publish the completed node's final status.

        :param node: The plan node that completed.
        """
        if isinstance(node, MotionNode):
            self.bridge.observe_motion_ended(node)
            return
        self.bridge.snapshot_plan()

    def on_motion_tick(self, statechart: MotionStatechart) -> None:
        """
        Publish the motion executor's current chart.

        :param statechart: The chart being executed.
        """
        self.bridge.observe_motion_tick(statechart)


def _finalize_recording_at_exit(
    bridge: Bridge, recording: Optional[Recording] = None
) -> None:
    """
    Best-effort safety net: write the current recording to disk if the process is about
    to exit without the viewer ever sending ``/recording/stop``.

    A demo run directly (rather than through ``cramera-live``, which stays up for
    inspection after the demo finishes) has no long-lived process left for the browser
    to ask, so the recording would otherwise be lost the moment the script's main body
    returns.

    :param bridge: The bridge whose geometry belongs to the recording.
    :param recording: The session's capture, or the bridge's current capture.
    """
    if recording is None:
        recording = bridge.recording
    if recording is None:
        return
    try:
        finalize_recording(bridge, recording)
    except Exception:
        # boundary guard: the interpreter is tearing down and the world may be in a
        # partial state; losing the recording is better than a traceback on every exit
        logger.exception("could not finalize the live recording at exit")


# %% the backend


@dataclass
class LiveVisualization(PlanVisualization):
    """
    Serves a world to the cramera browser viewer while a demo runs.
    """

    world: World
    """
    The world served to the viewer.
    """

    port: int = DEFAULT_PORT
    """
    Port of the bridge's HTTP endpoints.
    """

    bridge: Bridge = field(default_factory=Bridge)
    """
    The bridge translating between the world and the viewer.
    """

    state_sync: Optional[WorldStateSync] = field(init=False, default=None)
    """
    The callback publishing state changes, while started.
    """

    model_sync: Optional[WorldModelSync] = field(init=False, default=None)
    """
    The callback refreshing the catalogs on model changes, while started.
    """

    marker_listener: Optional[RosMarkerListener] = field(init=False, default=None)
    """
    The ROS marker subscription feeding the debug overlay, when ROS is available.
    """

    _recording: Optional[Recording] = field(init=False, default=None)
    """
    The capture owned by this visualization session.
    """

    _exit_callback: Optional[Callable[[], None]] = field(init=False, default=None)
    """
    The registered finalizer for this session's capture.
    """

    def start(self) -> LiveVisualization:
        """
        Attach the bridge to the world and start serving the viewer.

        :return: This visualization.
        """
        if self.state_sync is not None:
            return self
        if self.bridge.recording is not None:
            finalize_recording(self.bridge, self.bridge.recording)
        try:
            self.bridge.attach(self.world)
            self._recording = Recording()
            self.bridge.recording = self._recording
            self._recording.start()
            MeshFileStorage()
            self._exit_callback = partial(
                _finalize_recording_at_exit, self.bridge, self._recording
            )
            atexit.register(self._exit_callback)
            self.bridge.snapshot()
            self.state_sync = WorldStateSync(_world=self.world, bridge=self.bridge)
            self.model_sync = WorldModelSync(_world=self.world, bridge=self.bridge)
            self.marker_listener = RosMarkerListener.start_if_available(self.bridge)
            self.bridge.marker_listener = self.marker_listener
            if self.bridge.live_server is None:
                self.bridge.live_server = serve(self.bridge, self.port)
        except BaseException:
            self.stop()
            raise
        VisualizationSession.register(self.stop)
        return self

    def plan_callback(self, plan: Plan) -> BridgePlanCallback:
        """
        The callback that publishes the plan's execution to the viewer.

        Also publishes the plan's tree immediately, so the viewer shows it before the
        first node runs.

        :param plan: The plan about to be performed.
        :return: The callback to append to the plan's ``node_callbacks``.
        """
        self.bridge.begin_plan(plan)
        return BridgePlanCallback(bridge=self.bridge, plan=plan)

    def stop(self) -> None:
        """
        Finalize this session's recording and release its callbacks and server.
        """
        if self._exit_callback is not None:
            atexit.unregister(self._exit_callback)
            self._exit_callback = None
        if self.state_sync is not None:
            self.state_sync.stop()
            self.state_sync = None
        if self.model_sync is not None:
            self.model_sync.stop()
            self.model_sync = None
        if self.marker_listener is not None:
            self.marker_listener.stop()
            self.marker_listener = None
            self.bridge.marker_listener = None
        if self.bridge.live_server is not None:
            self.bridge.live_server.shutdown()
            self.bridge.live_server.server_close()
            self.bridge.live_server = None
        if self._recording is not None:
            finalize_recording(self.bridge, self._recording)
            self._recording = None
            self.bridge.recording = None

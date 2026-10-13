"""
Publish native CRAM world and plan state to the browser viewer.

World callbacks publish geometry and poses. Plan callbacks and statechart histories
publish execution progress.
"""

from __future__ import annotations

import atexit
from dataclasses import dataclass, field
from functools import partial

from typing_extensions import Any, Callable, Optional

from coraplex.plans.designator import DesignatorParameters
from coraplex.visualization import PlanVisualization, VisualizationSession
from cramph.executor import Executor, ExecutorExtension
from cramph.statechart import StateHistory, StateHistoryObserver, Statechart
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
class StatechartPublishing(ExecutorExtension, StateHistoryObserver):
    """
    Publish the progress of the statecharts an executor runs, and of the plan each of
    them runs.
    """

    bridge: Bridge = field(kw_only=True)
    """
    The bridge the execution is published to.
    """

    _statechart: Optional[Statechart] = field(default=None, init=False, repr=False)
    """
    The statechart being published, whose history this observes.
    """

    def after_compile(self, executor: Executor) -> None:
        """
        Start publishing the statechart `executor` compiled, unless it already is.
        """
        if executor.statechart is self._statechart:
            return
        self.observe(executor.statechart)

    def after_run(self, executor: Executor) -> None:
        """
        Publish the statechart as the run left it, see :meth:`finish`.
        """
        self.finish()

    def finish(self) -> None:
        """
        Publish the observed statechart as its run left it, and stop observing it.
        """
        self.bridge.observe_chart(self._statechart)
        if self.bridge.recording is not None:
            self.bridge.recording.update_statechart(self.bridge.executing_statechart())
        self.stop()

    def observe(self, statechart: Statechart) -> None:
        """
        Publish the plan's trees and the statechart before its first node runs, and
        follow its history from then on.

        :param statechart: The statechart about to run.
        """
        self.stop()
        self._statechart = statechart
        statechart.history.add_observer(self)
        self.bridge.begin_plan(statechart)
        self.bridge.observe_chart(statechart)

    def on_state_change(self, history: StateHistory) -> None:
        """
        Publish the chart and the plan after a snapshot of the statechart changed,
        naming the chart after the action that started last.

        :param history: The subscribed history containing the changed state.
        """
        for node in history.nodes_started_in_latest_item():
            if isinstance(node, DesignatorParameters):
                self.bridge.observe_action_started(node)
        self.bridge.observe_chart(self._statechart)
        self.bridge.snapshot_plan()

    def stop(self) -> None:
        """
        Remove the subscription to the history of the published statechart.
        """
        if self._statechart is not None:
            self._statechart.history.remove_observer(self)


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

    _query_attachment: int | None = field(init=False, default=None, repr=False)
    """
    Automatic queries owned by this visualization's world attachment.
    """

    _exit_callback: Optional[Callable[[], None]] = field(init=False, default=None)
    """
    The registered finalizer for this session's capture.
    """

    _publishings: list[StatechartPublishing] = field(
        default_factory=list, init=False, repr=False
    )
    """
    The executor extensions whose history subscriptions belong to this session.
    """

    def start(self) -> LiveVisualization:
        """
        Start serving the world and its default live queries to the viewer.

        :return: This visualization.
        """
        if self.state_sync is not None:
            return self
        if self.bridge.recording is not None:
            finalize_recording(self.bridge, self.bridge.recording)
        try:
            self._query_attachment = self.bridge.attach(self.world)
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

    def executor_extension(self) -> StatechartPublishing:
        """
        The extension that publishes the statecharts an executor runs to the viewer,
        each plan's trees as soon as it is compiled.

        :return: The extension to add to the executor.
        """
        publishing = StatechartPublishing(bridge=self.bridge)
        self._publishings.append(publishing)
        return publishing

    def stop(self) -> None:
        """
        Finalize the recording and release this session's callbacks, server and queries.
        """
        for publishing in self._publishings:
            publishing.stop()
        self._publishings.clear()
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
        try:
            if self._recording is not None:
                finalize_recording(self.bridge, self._recording)
                self._recording = None
                self.bridge.recording = None
        finally:
            if self._query_attachment is not None:
                self.bridge.release_world_queries(self._query_attachment)
                self._query_attachment = None

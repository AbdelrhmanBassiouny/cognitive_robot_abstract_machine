"""
Publish native CRAM world and plan state to the browser viewer.

World callbacks publish geometry and poses. Plan callbacks and statechart histories
publish execution progress.
"""

from __future__ import annotations

import atexit
from contextlib import ExitStack
from dataclasses import dataclass, field
from functools import partial

from typing_extensions import TYPE_CHECKING, Any, Callable, Optional

from coraplex.robot_plans.actions.base import Action
from cramph.visualization import WorldVisualization
from cramph.state_history import StateHistory, StateHistoryObserver
from cramph.statechart import Statechart
from semantic_digital_twin.callbacks.callback import (
    ModelChangeCallback,
    StateChangeCallback,
)
from semantic_digital_twin.world_description.geometry import MeshFileStorage

from cramera.live.bridge import Bridge
from cramera.live.http import DEFAULT_PORT, serve
from cramera.live.recording import Recording
from cramera.live.recording_bundle import finalize_recording
from cramera.live.ros_markers import RosMarkerListener
from cramera.logging_setup import get_logger

if TYPE_CHECKING:
    from cramph.executor import Executor
    from semantic_digital_twin.world import World

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
class StatechartPublishing(StateHistoryObserver):
    """
    Publish the progress of a statechart, and of the plan it runs.
    """

    bridge: Bridge = field(kw_only=True)
    """
    The bridge the execution is published to.
    """

    _statechart: Statechart | None = field(default=None, init=False, repr=False)
    """
    The statechart being published, whose history this observes.
    """

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
        statechart.state_history.add_observer(self)
        self.bridge.begin_plan(statechart)
        self.bridge.observe_chart(statechart)

    def on_state_change(self, history: StateHistory) -> None:
        """
        Publish the chart and the plan after a snapshot of the statechart changed,
        naming the chart after the action that started last.

        :param history: The subscribed history containing the changed state.
        """
        for node in history.nodes_started_in_latest_item():
            if isinstance(node, Action):
                self.bridge.observe_action_started(node)
        self.bridge.observe_chart(self._statechart)
        self.bridge.snapshot_plan()

    def stop(self) -> None:
        """
        Remove the subscription to the history of the published statechart.
        """
        if self._statechart is not None:
            self._statechart.state_history.remove_observer(self)


def _finalize_recording_at_exit(
    bridge: Bridge, recording: Optional[Recording] = None
) -> None:
    """
    Best-effort safety net: write the current recording to disk if the process is about
    to exit without the viewer ever sending ``/recording/stop``.

    A demo has no long-lived process left for the browser to ask once it finished, so
    the recording would otherwise be lost the moment the script's main body returns.

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
class LiveVisualization(WorldVisualization):
    """
    Serves the world and the statechart of an executor to the cramera browser viewer
    while the executor runs it, and keeps what a run left inspectable until stopped.

    Every run of a later executor continues the same recording on the same server.
    """

    port: int = DEFAULT_PORT
    """
    Port of the bridge's HTTP endpoints.
    """

    bridge: Bridge = field(default_factory=Bridge)
    """
    The bridge translating between the world and the viewer.
    """

    publishing: StatechartPublishing = field(init=False)
    """
    Publishes the progress of the statechart the executor runs.
    """

    state_sync: WorldStateSync | None = field(init=False, default=None)
    """
    The callback publishing state changes, while started.
    """

    model_sync: WorldModelSync | None = field(init=False, default=None)
    """
    The callback refreshing the catalogs on model changes, while started.
    """

    marker_listener: RosMarkerListener | None = field(init=False, default=None)
    """
    The ROS marker subscription feeding the debug overlay, when ROS is available.
    """

    _recording: Recording | None = field(init=False, default=None)
    """
    The capture owned by this visualization while it runs.
    """

    _query_attachment: int | None = field(init=False, default=None, repr=False)
    """
    Automatic queries owned by this visualization's world attachment.
    """

    _exit_callback: Callable[[], None] | None = field(init=False, default=None)
    """
    The registered finalizer for the capture, in case the process exits before
    :meth:`stop`.
    """

    _session_cleanup: ExitStack = field(
        default_factory=ExitStack, init=False, repr=False
    )
    """
    Releases the server and the recording, which outlive a run, in reverse acquisition
    order.
    """

    def __post_init__(self) -> None:
        """
        Publish the statecharts through :attr:`bridge`.
        """
        self.publishing = StatechartPublishing(bridge=self.bridge)

    @property
    def is_rendering(self) -> bool:
        return self.state_sync is not None

    def _start(self, world: World, cleanup: ExitStack) -> None:
        """
        Serve `world` and its default live queries to the viewer, starting the server
        and a new recording unless they already run, and finalizing an earlier recording
        of :attr:`bridge` first.

        A failing start also releases the server and the recording it started.
        """
        with ExitStack() as session:
            if self._recording is None:
                self._start_recording(session)
            self._show(world, cleanup)
            if self.bridge.live_server is None:
                self.bridge.live_server = serve(self.bridge, self.port)
                session.callback(self._shut_down_server)
            self._session_cleanup.push(session.pop_all())

    def _show(self, world: World, cleanup: ExitStack) -> None:
        """
        Publish `world` and its default live queries through :attr:`bridge`.

        :param world: The world to show.
        :param cleanup: Releases what showing `world` acquired.
        """
        self._query_attachment = self.bridge.attach(world)
        cleanup.callback(self._release_world_queries)
        MeshFileStorage()
        self.bridge.snapshot()
        self.state_sync = WorldStateSync(_world=world, bridge=self.bridge)
        cleanup.callback(self._stop_state_sync)
        self.model_sync = WorldModelSync(_world=world, bridge=self.bridge)
        cleanup.callback(self._stop_model_sync)
        self.marker_listener = RosMarkerListener.start_if_available(self.bridge)
        self.bridge.marker_listener = self.marker_listener
        cleanup.callback(self._stop_marker_listener)

    def _start_recording(self, session: ExitStack) -> None:
        """
        Start a new recording of :attr:`bridge`, finalizing an earlier one first.

        :param session: Finalizes the recording.
        """
        if self.bridge.recording is not None:
            finalize_recording(self.bridge, self.bridge.recording)
        self._recording = Recording()
        self.bridge.recording = self._recording
        self._recording.start()
        session.callback(self._finalize_recording)
        self._exit_callback = partial(
            _finalize_recording_at_exit, self.bridge, self._recording
        )
        atexit.register(self._exit_callback)
        session.callback(self._unregister_exit_callback)

    def stop(self) -> None:
        """
        Differs from :meth:`~cramph.visualization.WorldVisualization.stop` in also
        unsubscribing from the history of the published statechart, finalizing the
        recording and closing the server of :attr:`bridge`.
        """
        self.publishing.stop()
        super().stop()
        self._session_cleanup.close()

    def after_compile(self, executor: Executor) -> None:
        """
        Differs from :meth:`~cramph.visualization.WorldVisualization.after_compile` in
        switching to the world of `executor` if another one is shown, and in also
        publishing the statechart `executor` compiled.
        """
        if self.is_rendering and self.bridge.world is not executor.context.world:
            self._cleanup.close()
        super().after_compile(executor)
        self.publishing.observe(executor.statechart)

    def after_run(self, executor: Executor) -> None:
        """
        Differs from :meth:`~cramph.visualization.WorldVisualization.after_run` in
        publishing the statechart as the run left it and keeping the world, the server
        and the recording until :meth:`stop`.
        """
        self.publishing.finish()

    def _release_world_queries(self) -> None:
        """
        Remove the automatic queries of the world attachment.
        """
        self.bridge.release_world_queries(self._query_attachment)
        self._query_attachment = None

    def _finalize_recording(self) -> None:
        """
        Write the capture of the run to disk.
        """
        finalize_recording(self.bridge, self._recording)
        self._recording = None
        self.bridge.recording = None

    def _unregister_exit_callback(self) -> None:
        """
        Withdraw the finalizer of the capture, which :meth:`_finalize_recording` takes
        over.
        """
        atexit.unregister(self._exit_callback)
        self._exit_callback = None

    def _stop_state_sync(self) -> None:
        """
        Stop publishing state changes.
        """
        self.state_sync.stop()
        self.state_sync = None

    def _stop_model_sync(self) -> None:
        """
        Stop refreshing the catalogs on model changes.
        """
        self.model_sync.stop()
        self.model_sync = None

    def _stop_marker_listener(self) -> None:
        """
        Stop feeding ROS markers to the debug overlay, if they were.
        """
        if self.marker_listener is not None:
            self.marker_listener.stop()
        self.marker_listener = None
        self.bridge.marker_listener = None

    def _shut_down_server(self) -> None:
        """
        Close the HTTP endpoints of :attr:`bridge`, if they are open.
        """
        if self.bridge.live_server is None:
            return
        self.bridge.live_server.shutdown()
        self.bridge.live_server.server_close()
        self.bridge.live_server = None

"""Execution callbacks preserve the native plan and motion lifecycle."""

from dataclasses import dataclass, field
from enum import StrEnum
from unittest.mock import Mock

import pytest

import coraplex.plans.executables as executables
from coraplex.datastructures.dataclasses import Context
from giskardpy.motion_statechart.graph_node import Goal, Task
from semantic_digital_twin.robots.minimal_robot import MinimalRobot

from coraplex.execution_environment import simulated_robot
from coraplex.plans.attachment_nodes import ReAttachNode
from coraplex.plans.executables import MotionPlanHistory
from coraplex.plans.factories import sequential
from coraplex.plans.failures import PlanFailure
from coraplex.plans.plan import Plan
from coraplex.plans.plan_callbacks import PlanCallback
from coraplex.plans.plan_node import MotionNode, PlanNode
from coraplex.robot_plans.actions.core.robot_body import MoveTorsoAction
from coraplex.robot_plans.motions.robot_body import MoveJointsMotion
from giskardpy.motion_statechart.data_types import LifeCycleValues
from giskardpy.motion_statechart.motion_statechart import (
    MotionStatechart,
    StateHistoryItem,
    StateHistoryObserver,
    StateHistory,
)
from semantic_digital_twin.datastructures.definitions import TorsoState


# %% observer records
class ExecutionEvent(StrEnum):
    """The execution boundary an observer received."""

    START = "start"
    """Execution began."""
    END = "end"
    """Execution ended."""


@dataclass(frozen=True)
class NodeEvent:
    """A node's status at the instant its execution boundary was reported."""

    event: ExecutionEvent
    """The reported boundary."""
    node: PlanNode
    """The node whose lifecycle changed."""
    status: LifeCycleValues
    """The native lifecycle state when the callback ran."""


@dataclass
class ExecutionRecorder(PlanCallback, StateHistoryObserver):
    """Keep execution boundaries and motion ticks in delivery order."""

    events: list[NodeEvent] = field(default_factory=list)
    """Observed node boundaries."""
    statecharts: list[MotionStatechart] = field(default_factory=list)
    """Motion charts delivered after executor ticks."""

    def on_start(self, node: PlanNode) -> None:
        """Remember the native start state.

        :param node: Node whose execution began.
        """
        self.events.append(NodeEvent(ExecutionEvent.START, node, node.status))
        if isinstance(node, MotionNode) and node.motion_statechart is not None:
            node.motion_statechart.history.add_observer(self)

    def on_end(self, node: PlanNode) -> None:
        """Remember the native terminal state.

        :param node: Node whose execution ended.
        """
        self.events.append(NodeEvent(ExecutionEvent.END, node, node.status))

    def on_state_change(self, history: StateHistory) -> None:
        """Remember a changed native chart snapshot.

        :param history: The chart's recorded states.
        """
        self.statecharts.append(history.history[-1].life_cycle_state.motion_statechart)


@dataclass
class RecordedMotion:
    """A task whose transitions are stored by the native history."""

    chart: MotionStatechart = field(default_factory=MotionStatechart)
    """The native motion chart."""
    task: Task = field(default_factory=Task)
    """The task whose states the test controls."""

    def __post_init__(self) -> None:
        """Register the task with its native state arrays."""
        self.chart.add_node(self.task)

    def record(self, state: LifeCycleValues) -> None:
        """Append the task's state through the production history API.

        :param state: The next native lifecycle state.
        """
        self.chart.life_cycle_state[self.task] = state
        self.chart.history.append(
            StateHistoryItem(
                control_cycle=len(self.chart.history),
                life_cycle_state=self.chart.life_cycle_state,
                observation_state=self.chart.observation_state,
            )
        )


# %% motion lifecycle
def test_native_history_drives_motion_events_without_executor_polling() -> None:
    """Native history updates publish motion boundaries without a second state cache."""
    node = MotionNode(designator=MoveJointsMotion(names=[], positions=[]))
    plan = Plan()
    plan.add_node(node)
    recorder = ExecutionRecorder(plan=plan)
    plan.node_callbacks.append(recorder)
    chart = MotionStatechart()
    task = Task()
    chart.add_node(task)
    observer = MotionPlanHistory(statechart=chart, motion_mappings={node: task})
    for state in (LifeCycleValues.RUNNING, LifeCycleValues.SUCCEEDED):
        chart.life_cycle_state[task] = state
        chart.history.append(
            StateHistoryItem(
                control_cycle=len(chart.history),
                life_cycle_state=chart.life_cycle_state,
                observation_state=chart.observation_state,
            )
        )

    assert recorder.events == [
        NodeEvent(ExecutionEvent.START, node, LifeCycleValues.RUNNING),
        NodeEvent(ExecutionEvent.END, node, LifeCycleValues.SUCCEEDED),
    ]


@pytest.fixture
def tracked_motion():
    """A native identity-hashable motion node registered with a plan."""
    node = MotionNode(designator=MoveJointsMotion(names=[], positions=[]))
    plan = Plan()
    plan.add_node(node)
    return node


@pytest.mark.parametrize("terminal", list(LifeCycleValues.terminal_states()))
def test_terminal_motion_reports_start_and_exact_outcome(
    terminal, tracked_motion
) -> None:
    """A short motion still starts before its successful, failed or interrupted end."""
    root = tracked_motion
    recorder = ExecutionRecorder(plan=root.plan)
    root.plan.node_callbacks.append(recorder)
    motion = RecordedMotion()
    observer = MotionPlanHistory(
        statechart=motion.chart, motion_mappings={root: motion.task}
    )

    motion.record(LifeCycleValues.NOT_STARTED)
    assert recorder.events == []
    motion.record(terminal)
    motion.record(terminal)

    assert recorder.events == [
        NodeEvent(ExecutionEvent.START, root, LifeCycleValues.RUNNING),
        NodeEvent(ExecutionEvent.END, root, terminal),
    ]
    assert root.status is terminal
    assert root.start_time <= root.end_time


def test_pausing_and_resuming_does_not_repeat_start(tracked_motion) -> None:
    """The plan state follows pauses while boundaries remain exactly once."""
    root = tracked_motion
    recorder = ExecutionRecorder(plan=root.plan)
    root.plan.node_callbacks.append(recorder)
    motion = RecordedMotion()
    observer = MotionPlanHistory(
        statechart=motion.chart, motion_mappings={root: motion.task}
    )

    for state in (
        LifeCycleValues.RUNNING,
        LifeCycleValues.PAUSED,
        LifeCycleValues.RUNNING,
    ):
        motion.record(state)
        assert root.status is state

    assert recorder.events == [
        NodeEvent(ExecutionEvent.START, root, LifeCycleValues.RUNNING)
    ]


def test_native_reset_starts_a_new_motion_execution(tracked_motion) -> None:
    """Resetting the native task clears the projected timestamps before another run."""
    node = tracked_motion
    recorder = ExecutionRecorder(plan=node.plan)
    node.plan.node_callbacks.append(recorder)
    motion = RecordedMotion()
    observer = MotionPlanHistory(motion.chart, {node: motion.task})
    motion.record(LifeCycleValues.RUNNING)
    motion.record(LifeCycleValues.SUCCEEDED)

    motion.record(LifeCycleValues.NOT_STARTED)

    assert node.status is LifeCycleValues.NOT_STARTED
    assert node.start_time is None
    assert node.end_time is None
    motion.record(LifeCycleValues.RUNNING)
    motion.record(LifeCycleValues.INTERRUPTED)
    assert recorder.events == [
        NodeEvent(ExecutionEvent.START, node, LifeCycleValues.RUNNING),
        NodeEvent(ExecutionEvent.END, node, LifeCycleValues.SUCCEEDED),
        NodeEvent(ExecutionEvent.START, node, LifeCycleValues.RUNNING),
        NodeEvent(ExecutionEvent.END, node, LifeCycleValues.INTERRUPTED),
    ]
    observer.stop()


def test_aborting_does_not_overwrite_a_completed_motion(tracked_motion) -> None:
    """Executor failures retain outcomes already recorded by the native chart."""
    node = tracked_motion
    recorder = ExecutionRecorder(plan=node.plan)
    node.plan.node_callbacks.append(recorder)
    motion = RecordedMotion()
    observer = MotionPlanHistory(motion.chart, {node: motion.task})
    motion.record(LifeCycleValues.RUNNING)
    motion.record(LifeCycleValues.SUCCEEDED)

    observer.end_active_motions(LifeCycleValues.FAILED)

    assert node.status is LifeCycleValues.SUCCEEDED
    assert recorder.events == [
        NodeEvent(ExecutionEvent.START, node, LifeCycleValues.RUNNING),
        NodeEvent(ExecutionEvent.END, node, LifeCycleValues.SUCCEEDED),
    ]
    observer.stop()


# %% performed native plans
def test_native_motion_reports_boundaries_and_ticks(immutable_model_world) -> None:
    """A real native torso plan reports its exact motion nodes and finished chart."""
    world, robot, context = immutable_model_world
    plan = sequential([MoveTorsoAction(TorsoState.HIGH)], context=context).plan
    recorder = ExecutionRecorder(plan=plan)
    plan.node_callbacks.append(recorder)

    with simulated_robot:
        plan.perform()

    assert recorder.events[0] == NodeEvent(
        ExecutionEvent.START, plan.root, LifeCycleValues.RUNNING
    )
    assert recorder.events[-1] == NodeEvent(
        ExecutionEvent.END, plan.root, LifeCycleValues.SUCCEEDED
    )
    motions = [node for node in plan.all_nodes if isinstance(node, MotionNode)]
    assert motions
    assert [
        event.node
        for event in recorder.events
        if event.event is ExecutionEvent.START and isinstance(event.node, MotionNode)
    ] == motions
    assert [
        event.node
        for event in recorder.events
        if event.event is ExecutionEvent.END and isinstance(event.node, MotionNode)
    ] == motions
    assert {motion.status for motion in motions} == {LifeCycleValues.SUCCEEDED}
    assert recorder.statecharts
    assert all(chart is recorder.statecharts[0] for chart in recorder.statecharts)
    assert recorder.statecharts[-1].is_end_motion()


def test_native_attachment_reports_its_own_completion(mutable_model_world) -> None:
    """A model change receives a lifecycle even when compiled below the plan root."""
    world, robot, context = mutable_model_world
    attachment = ReAttachNode(
        body=world.get_body_by_name("milk.stl"), new_parent=robot.root
    )
    plan = sequential([attachment], context=context).plan
    recorder = ExecutionRecorder(plan=plan)
    plan.node_callbacks.append(recorder)

    with simulated_robot:
        plan.perform()

    assert [event for event in recorder.events if event.node is attachment] == [
        NodeEvent(ExecutionEvent.START, attachment, LifeCycleValues.RUNNING),
        NodeEvent(ExecutionEvent.END, attachment, LifeCycleValues.SUCCEEDED),
    ]
    assert attachment.body.parent_connection.parent is robot.root


def test_failed_plan_reports_failure_before_end(monkeypatch) -> None:
    """Observers see the thrown native PlanFailure and its finished lifecycle."""
    root = sequential([])
    recorder = ExecutionRecorder(plan=root.plan)
    root.plan.node_callbacks.append(recorder)
    failure = PlanFailure()

    def fail_notify() -> None:
        """Fail at the native node's execution boundary."""
        raise failure

    monkeypatch.setattr(root, "notify", fail_notify)
    with pytest.raises(PlanFailure) as caught:
        root.perform()

    assert caught.value is failure
    assert root.reason is failure
    assert recorder.events == [
        NodeEvent(ExecutionEvent.START, root, LifeCycleValues.RUNNING),
        NodeEvent(ExecutionEvent.END, root, LifeCycleValues.FAILED),
    ]


def test_default_callback_accepts_native_history_events(tracked_motion) -> None:
    """A plan observer can omit every optional boundary method."""
    node = tracked_motion
    node.plan.node_callbacks.append(PlanCallback(plan=node.plan))
    motion = RecordedMotion()
    observer = MotionPlanHistory(
        statechart=motion.chart, motion_mappings={node: motion.task}
    )
    motion.record(LifeCycleValues.RUNNING)
    motion.record(LifeCycleValues.SUCCEEDED)
    assert node.status is LifeCycleValues.SUCCEEDED
    observer.stop()
    assert motion.chart.history.observers == []


# %% aborted execution
@dataclass
class AbortedExecution:
    """An executor whose native task history precedes an execution failure."""

    motion: RecordedMotion
    """The task exposed as running by compilation."""
    failure: BaseException | None
    """The original error raised by the executor tick, if any."""
    context: Mock = field(default_factory=Mock)
    """The native execution context's cleanup boundary."""
    stopped: bool = False
    """Whether motion commands were cleared."""

    @property
    def motion_statechart(self) -> MotionStatechart:
        """Return the chart provided to compilation."""
        return self.motion.chart

    def compile(self, statechart: MotionStatechart) -> None:
        """Expose a running task through its native history.

        :param statechart: The supplied motion chart.
        """
        assert statechart is self.motion.chart
        self.motion.record(LifeCycleValues.RUNNING)

    def tick(self) -> None:
        """Abort execution if a failure was configured."""
        if self.failure is not None:
            raise self.failure

    def set_velocity_acceleration_jerk_to_zero(self) -> None:
        """Record command cleanup after execution."""
        self.stopped = True


@pytest.mark.parametrize(
    "failure, outcome",
    [
        (RuntimeError("controller stopped"), LifeCycleValues.FAILED),
        (KeyboardInterrupt(), LifeCycleValues.INTERRUPTED),
    ],
)
def test_aborted_executor_ends_started_motion_observation(
    monkeypatch, tracked_motion, cylinder_bot_world, failure, outcome
) -> None:
    """A failed executor cannot leave an observed motion running indefinitely."""
    node = tracked_motion
    recorder = ExecutionRecorder(plan=node.plan)
    node.plan.node_callbacks.append(recorder)
    motion = RecordedMotion()
    aborted = AbortedExecution(motion, failure)
    monkeypatch.setattr(executables, "Ros2Executor", Mock(return_value=aborted))
    robot = cylinder_bot_world.get_semantic_annotations_by_type(MinimalRobot)[0]
    executable = executables.GiskardExecutable(
        context=Context(cylinder_bot_world, robot),
        root_node=Goal(),
        motion_state_chart=motion.chart,
        motion_mappings={node: motion.task},
    )

    with pytest.raises(type(failure)) as caught:
        executable._execute_simulation()

    assert caught.value is failure
    assert recorder.events == [
        NodeEvent(ExecutionEvent.START, node, LifeCycleValues.RUNNING),
        NodeEvent(ExecutionEvent.END, node, outcome),
    ]


def test_aborted_executor_releases_native_resources(
    monkeypatch, tracked_motion, cylinder_bot_world
) -> None:
    """Execution failure stops commands, cleans native nodes and detaches history."""
    node = tracked_motion
    motion = RecordedMotion()
    failure = RuntimeError("controller stopped")
    executor = AbortedExecution(motion, failure)
    monkeypatch.setattr(executables, "Ros2Executor", Mock(return_value=executor))
    cleanup = Mock(spec=motion.task.cleanup)
    monkeypatch.setattr(motion.task, "cleanup", cleanup)
    robot = cylinder_bot_world.get_semantic_annotations_by_type(MinimalRobot)[0]
    executable = executables.GiskardExecutable(
        context=Context(cylinder_bot_world, robot),
        root_node=Goal(),
        motion_state_chart=motion.chart,
        motion_mappings={node: motion.task},
    )

    with pytest.raises(RuntimeError) as caught:
        executable._execute_simulation()

    assert caught.value is failure
    assert executor.stopped
    cleanup.assert_called_once_with(context=executor.context)
    executor.context.cleanup.assert_called_once_with()
    assert motion.chart.history.observers == []


@pytest.mark.parametrize(
    "failure, outcome",
    [
        (RuntimeError("body stopped"), LifeCycleValues.FAILED),
        (KeyboardInterrupt(), LifeCycleValues.INTERRUPTED),
    ],
)
def test_aborted_plan_reports_terminal_outcome(monkeypatch, failure, outcome) -> None:
    """Unexpected errors and operator interruptions reach observers before propagating."""
    root = sequential([])
    recorder = ExecutionRecorder(plan=root.plan)
    root.plan.node_callbacks.append(recorder)

    def abort_notify() -> None:
        """Abort the running node with the original error."""
        raise failure

    monkeypatch.setattr(root, "notify", abort_notify)
    with pytest.raises(type(failure)) as caught:
        root.perform()

    assert caught.value is failure
    assert recorder.events[-1] == NodeEvent(ExecutionEvent.END, root, outcome)


def test_compilation_failure_preserves_error_without_starting_motion(
    monkeypatch, tracked_motion, cylinder_bot_world
) -> None:
    """Failed compilation propagates before any not-started motion gains an event."""
    node = tracked_motion
    recorder = ExecutionRecorder(plan=node.plan)
    node.plan.node_callbacks.append(recorder)
    failure = RuntimeError("cannot compile")
    motion = RecordedMotion()
    executor = Mock()
    executor.compile.side_effect = failure
    monkeypatch.setattr(executables, "Ros2Executor", Mock(return_value=executor))
    robot = cylinder_bot_world.get_semantic_annotations_by_type(MinimalRobot)[0]
    executable = executables.GiskardExecutable(
        context=Context(cylinder_bot_world, robot),
        root_node=Goal(),
        motion_state_chart=motion.chart,
        motion_mappings={node: motion.task},
    )
    with pytest.raises(RuntimeError) as caught:
        executable._execute_simulation()
    assert caught.value is failure
    assert recorder.events == []
    executor.tick.assert_not_called()


def test_exhausted_execution_ends_started_motion_observation(
    monkeypatch, tracked_motion, cylinder_bot_world
) -> None:
    """A motion that exhausts its native tick budget reports a failed observation."""
    node = tracked_motion
    recorder = ExecutionRecorder(plan=node.plan)
    node.plan.node_callbacks.append(recorder)
    motion = RecordedMotion()
    executor = AbortedExecution(motion, failure=None)
    monkeypatch.setattr(executables, "Ros2Executor", Mock(return_value=executor))
    robot = cylinder_bot_world.get_semantic_annotations_by_type(MinimalRobot)[0]
    executable = executables.GiskardExecutable(
        context=Context(cylinder_bot_world, robot, ticks_per_motion=1),
        root_node=Goal(),
        motion_state_chart=motion.chart,
        motion_mappings={node: motion.task},
    )
    with pytest.raises(executables.MotionDidNotFinish):
        executable._execute_simulation()
    assert recorder.events == [
        NodeEvent(ExecutionEvent.START, node, LifeCycleValues.RUNNING),
        NodeEvent(ExecutionEvent.END, node, LifeCycleValues.FAILED),
    ]


def test_start_observer_failure_releases_execution_scope(monkeypatch) -> None:
    """A failing start observer leaves the node retryable and reports its failure."""
    root = sequential([])
    recorder = ExecutionRecorder(plan=root.plan)
    root.plan.node_callbacks.append(recorder)
    failure = RuntimeError("observer stopped")
    start_observer = Mock(side_effect=failure)
    monkeypatch.setattr(recorder, "on_start", start_observer)
    with pytest.raises(RuntimeError) as caught:
        root.perform()
    assert caught.value is failure
    assert not root._execution_in_progress
    assert recorder.events == [
        NodeEvent(ExecutionEvent.END, root, LifeCycleValues.FAILED)
    ]

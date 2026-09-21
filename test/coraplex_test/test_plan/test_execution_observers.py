"""Execution callbacks preserve the native plan and motion lifecycle."""

from dataclasses import dataclass, field
from enum import StrEnum
from unittest.mock import Mock

import pytest

import coraplex.plans.executables as executables
from coraplex.datastructures.dataclasses import Context
from giskardpy.motion_statechart.graph_node import Goal
from semantic_digital_twin.robots.minimal_robot import MinimalRobot

from coraplex.execution_environment import simulated_robot
from coraplex.plans.attachment_nodes import ReAttachNode
from coraplex.plans.executables import MotionLifeCycleTracker
from coraplex.plans.factories import sequential
from coraplex.plans.failures import PlanFailure
from coraplex.plans.plan import Plan
from coraplex.plans.plan_callbacks import PlanCallback
from coraplex.plans.plan_node import MotionNode, PlanNode
from coraplex.robot_plans.actions.core.robot_body import MoveTorsoAction
from coraplex.robot_plans.motions.robot_body import MoveJointsMotion
from giskardpy.motion_statechart.data_types import LifeCycleValues
from giskardpy.motion_statechart.motion_statechart import MotionStatechart
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
class ExecutionRecorder(PlanCallback):
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

    def on_end(self, node: PlanNode) -> None:
        """Remember the native terminal state.

        :param node: Node whose execution ended.
        """
        self.events.append(NodeEvent(ExecutionEvent.END, node, node.status))

    def on_motion_tick(self, statechart: MotionStatechart) -> None:
        """Remember one executor observation.

        :param statechart: The chart that was ticked.
        """
        self.statecharts.append(statechart)


@dataclass
class TaskLifecycle:
    """The lifecycle state exposed by an executing task."""

    life_cycle_state: LifeCycleValues
    """The currently observed state."""


# %% motion lifecycle
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
    observer = ExecutionRecorder(plan=root.plan)
    root.plan.node_callbacks.append(observer)
    task = TaskLifecycle(LifeCycleValues.NOT_STARTED)
    tracker = MotionLifeCycleTracker(motion_mappings={root: task})

    tracker.emit_transitions()
    assert observer.events == []
    task.life_cycle_state = terminal
    tracker.emit_transitions()
    tracker.emit_transitions()

    assert observer.events == [
        NodeEvent(ExecutionEvent.START, root, LifeCycleValues.RUNNING),
        NodeEvent(ExecutionEvent.END, root, terminal),
    ]
    assert root.status is terminal
    assert root.start_time <= root.end_time


def test_pausing_and_resuming_does_not_repeat_start(tracked_motion) -> None:
    """The plan state follows pauses while boundaries remain exactly once."""
    root = tracked_motion
    observer = ExecutionRecorder(plan=root.plan)
    root.plan.node_callbacks.append(observer)
    task = TaskLifecycle(LifeCycleValues.NOT_STARTED)
    tracker = MotionLifeCycleTracker(motion_mappings={root: task})

    for state in (
        LifeCycleValues.RUNNING,
        LifeCycleValues.PAUSED,
        LifeCycleValues.RUNNING,
    ):
        task.life_cycle_state = state
        tracker.emit_transitions()
        assert root.status is state

    assert observer.events == [
        NodeEvent(ExecutionEvent.START, root, LifeCycleValues.RUNNING)
    ]


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


def test_default_callback_accepts_motion_ticks() -> None:
    """An existing observer may omit the new event without breaking execution."""
    plan = Plan()
    plan.node_callbacks.append(PlanCallback(plan=plan))
    assert plan.notify_motion_tick(MotionStatechart()) is None


# %% aborted execution
@dataclass
class AbortedExecution:
    """An executor whose active task is interrupted by a native execution failure."""

    task: TaskLifecycle
    """The task exposed as running by compilation."""
    failure: BaseException
    """The original error raised by the executor tick."""

    def compile(self, statechart: MotionStatechart) -> None:
        """Expose a running task at the executor observation boundary.

        :param statechart: The supplied motion chart.
        """
        self.task.life_cycle_state = LifeCycleValues.RUNNING

    def tick(self) -> None:
        """Abort the current execution."""
        raise self.failure


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
    task = TaskLifecycle(LifeCycleValues.NOT_STARTED)
    aborted = AbortedExecution(task, failure)
    monkeypatch.setattr(executables, "Ros2Executor", Mock(return_value=aborted))
    robot = cylinder_bot_world.get_semantic_annotations_by_type(MinimalRobot)[0]
    executable = executables.GiskardExecutable(
        context=Context(cylinder_bot_world, robot),
        root_node=Goal(),
        motion_mappings={node: task},
    )

    with pytest.raises(type(failure)) as caught:
        executable._execute_simulation()

    assert caught.value is failure
    assert recorder.events == [
        NodeEvent(ExecutionEvent.START, node, LifeCycleValues.RUNNING),
        NodeEvent(ExecutionEvent.END, node, outcome),
    ]


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
    executor = Mock()
    executor.compile.side_effect = failure
    monkeypatch.setattr(executables, "Ros2Executor", Mock(return_value=executor))
    robot = cylinder_bot_world.get_semantic_annotations_by_type(MinimalRobot)[0]
    executable = executables.GiskardExecutable(
        context=Context(cylinder_bot_world, robot),
        root_node=Goal(),
        motion_mappings={node: TaskLifecycle(LifeCycleValues.NOT_STARTED)},
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
    task = TaskLifecycle(LifeCycleValues.RUNNING)
    executor = Mock()
    executor.motion_statechart.is_end_motion.return_value = False
    monkeypatch.setattr(executables, "Ros2Executor", Mock(return_value=executor))
    robot = cylinder_bot_world.get_semantic_annotations_by_type(MinimalRobot)[0]
    executable = executables.GiskardExecutable(
        context=Context(cylinder_bot_world, robot, ticks_per_motion=1),
        root_node=Goal(),
        motion_mappings={node: task},
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

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from typing_extensions import List, Optional

from coraplex.plans.context_extensions import RobotAccess
from coraplex.plans.executors import PlanExecutor
from coraplex.robot_plans.actions.base import Action
from coraplex.robot_plans.actions.core.robot_body import (
    MoveTorsoAction,
)
from cramph.composites import Sequence
from cramph.data_types import LifeCycleValues, ObservationStateValues
from cramph.exceptions import (
    CompositeNodeWithoutChildrenError,
    NodesMissingContextExtensionsError,
)
from cramph.executor import StatechartExecutor
from cramph.node import EndStatechart, StatechartNode
from cramph.nodes_for_testing import (
    NodeFailingOnObservingFalse,
    NodeObservingAFixedValue,
    NodeSucceedingOnObservingTrue,
)
from cramph.statechart import Statechart
from krrood.patterns.field_metadata import ParameterMetadata
from semantic_digital_twin.datastructures.definitions import TorsoState
from ...plan_running import (
    simulated_executor,
    statechart_of,
)
from cramph.context import ContextExtension, StatechartContext

# %% a body handed in, so expansion is exercised without a robot


@dataclass(eq=False, repr=False)
class ActionRunningHandedInSteps(Action):
    """
    An action whose body is handed to it rather than derived from a robot, so that
    expanding and running an action can be exercised on its own.
    """

    steps: List[StatechartNode] = field(default_factory=list)
    """
    The nodes this action runs, in order.
    """

    def create_action_body(self) -> StatechartNode:
        return Sequence(list(self.steps))


def _succeeding(name: str) -> NodeSucceedingOnObservingTrue:
    """
    :return: A node that ends itself successfully as soon as it observes.
    """
    return NodeSucceedingOnObservingTrue(
        name=name, observation=ObservationStateValues.TRUE
    )


def _failing(name: str) -> NodeFailingOnObservingFalse:
    """
    :return: A node that declares itself failed as soon as it observes.
    """
    return NodeFailingOnObservingFalse(
        name=name, observation=ObservationStateValues.FALSE
    )


def _expanded(
    action: Action,
    extensions: List[ContextExtension],
    executor: Optional[PlanExecutor] = None,
) -> Statechart:
    """
    Adds `action` to a statechart, which expands it.

    :param executor: The executor whose context the statechart is built in, a simulated
        one by default.
    :return: The statechart holding the expanded action.
    """
    if executor is None:
        executor = simulated_executor(extensions)
    return statechart_of(executor, action)


def _run_until(statechart: Statechart, end: EndStatechart) -> None:
    """
    Compiles `statechart` and ticks it until `end` ends it.
    """
    statechart.add_node(end)
    executor = StatechartExecutor(context=statechart.context)
    executor.compile(statechart)
    executor.tick_until_end(timeout=100)


# %% an action is a statechart node


def test_action_runs_its_steps_as_one_sequence(simple_pr2_context):
    """
    An action's body is a sequence of exactly the nodes it names.
    """
    _, _, extensions = simple_pr2_context
    steps = [_succeeding("first"), _succeeding("second")]
    action = ActionRunningHandedInSteps(steps=steps)

    _expanded(action, extensions)

    [body] = action.children
    assert isinstance(body, Sequence)
    assert body.nodes == steps


@dataclass(eq=False, repr=False)
class ActionRunningOneNode(Action):
    """
    An action whose body is a single node rather than a sequence of steps.
    """

    node: StatechartNode
    """
    The node this action runs.
    """

    def create_action_body(self) -> StatechartNode:
        return self.node


def test_an_action_has_no_body_before_it_is_expanded():
    assert ActionRunningHandedInSteps(steps=[]).action_body is None


def test_an_action_needs_the_robot_performing_it(simple_pr2_context):
    world, _, _ = simple_pr2_context
    statechart = Statechart(context=StatechartContext(world=world))
    action = ActionRunningHandedInSteps(steps=[_succeeding("only")])

    with pytest.raises(NodesMissingContextExtensionsError) as raised:
        statechart.add_node(action)

    assert raised.value.nodes_by_missing_extension == {RobotAccess: [action]}


def test_an_action_runs_the_body_it_created(simple_pr2_context):
    _, _, extensions = simple_pr2_context
    action = ActionRunningHandedInSteps(steps=[_succeeding("only step")])

    _expanded(action, extensions)

    assert action.children == [action.action_body]


def test_an_action_body_can_be_a_single_node(simple_pr2_context):
    _, _, extensions = simple_pr2_context
    step = _succeeding("only step")
    action = ActionRunningOneNode(node=step)
    statechart = _expanded(action, extensions)

    _run_until(statechart, EndStatechart.when_true(action))

    assert action.action_body is step
    assert action.life_cycle_state == LifeCycleValues.SUCCEEDED


def test_an_action_whose_body_its_owner_decides_succeeds_once_the_body_arrives(
    simple_pr2_context,
):
    """
    A single task never ends on its own, so the action ends it once it is at its goal.
    """
    _, _, extensions = simple_pr2_context
    task = NodeObservingAFixedValue(
        name="task", observation=ObservationStateValues.TRUE
    )
    action = ActionRunningOneNode(node=task)
    statechart = _expanded(action, extensions)

    _run_until(statechart, EndStatechart.when_true(action))

    assert action.action_body is task
    assert task.life_cycle_state == LifeCycleValues.SUCCEEDED
    assert action.life_cycle_state == LifeCycleValues.SUCCEEDED


def test_an_action_whose_body_its_owner_decides_waits_while_the_body_is_away(
    simple_pr2_context,
):
    """
    A task that has not arrived yet observes False, which is not a failure of the
    action running it.
    """
    _, _, extensions = simple_pr2_context
    task = NodeObservingAFixedValue(
        name="task", observation=ObservationStateValues.FALSE
    )
    action = ActionRunningOneNode(node=task)
    statechart = _expanded(action, extensions)
    statechart.add_node(EndStatechart.when_true(action))
    executor = StatechartExecutor(context=statechart.context)
    executor.compile(statechart)

    for _ in range(3):
        executor.tick()

    assert action.life_cycle_state == LifeCycleValues.RUNNING


def test_action_succeeds_once_its_last_step_succeeded(simple_pr2_context):
    """
    An action ends successfully when the sequence it runs does.
    """
    _, _, extensions = simple_pr2_context
    action = ActionRunningHandedInSteps(steps=[_succeeding("only step")])
    statechart = _expanded(action, extensions)

    _run_until(statechart, EndStatechart.when_true(action))

    assert action.life_cycle_state == LifeCycleValues.SUCCEEDED


def test_action_fails_once_a_step_ended_without_succeeding(simple_pr2_context):
    """
    A step that cannot arrive fails the action rather than leaving it waiting.
    """
    _, _, extensions = simple_pr2_context
    action = ActionRunningHandedInSteps(steps=[_failing("step that gives up")])
    statechart = _expanded(action, extensions)

    _run_until(statechart, EndStatechart.when_failed(action))

    assert action.life_cycle_state == LifeCycleValues.FAILED


def test_action_without_steps_is_rejected(simple_pr2_context):
    """
    An action that names no node to run is a mistake, not an empty success.
    """
    _, _, extensions = simple_pr2_context
    statechart = _expanded(ActionRunningHandedInSteps(steps=[]), extensions)

    with pytest.raises(CompositeNodeWithoutChildrenError):
        statechart.compile()


def test_action_parameters_leave_out_statechart_machinery(simple_pr2_context):
    """
    Only what the action was parameterized with counts as its parameters.
    """
    action = MoveTorsoAction(TorsoState.HIGH)

    assert action.designator_parameter == {"torso_state": TorsoState.HIGH}


@dataclass(eq=False, repr=False)
class ActionWithKeywordOnlyParameter(ActionRunningHandedInSteps):
    """
    An action taking one of its parameters by keyword only.
    """

    speed: float = field(default=1.0, kw_only=True)
    """
    A parameter that can only be passed by keyword.
    """


@dataclass(eq=False, repr=False)
class ActionWithHelperField(ActionRunningHandedInSteps):
    """
    An action carrying a field its caller sets that is not one of its parameters.
    """

    helper: int = field(
        default=0, metadata=ParameterMetadata(is_parameter=False).as_dict()
    )
    """
    A value the action needs that does not describe what it does.
    """


def test_a_keyword_only_field_is_a_parameter():
    action = ActionWithKeywordOnlyParameter(speed=2.0)

    assert action.designator_parameter == {"steps": [], "speed": 2.0}


def test_the_name_of_an_action_is_not_a_parameter():
    action = MoveTorsoAction(TorsoState.HIGH, name="lift")

    assert action.designator_parameter == {"torso_state": TorsoState.HIGH}


def test_a_field_marked_as_no_parameter_is_left_out():
    action = ActionWithHelperField(helper=3)

    assert action.designator_parameter == {"steps": []}

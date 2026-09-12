from __future__ import annotations

import logging
import time
from datetime import datetime
from dataclasses import dataclass, field

from typing_extensions import List, Dict, ClassVar, Optional, Protocol, TYPE_CHECKING

from coraplex.datastructures.enums import ExecutionType
from coraplex.exceptions import (
    MotionDidNotFinish,
    ConditionNotSatisfied,
    UnknownExecutionType,
)
from giskardpy.motion_statechart.context import MotionStatechartContext
from giskardpy.motion_statechart.data_types import LifeCycleValues
from giskardpy.motion_statechart.goals.collision_avoidance import (
    ExternalCollisionAvoidance,
    SelfCollisionAvoidance,
)
from giskardpy.motion_statechart.graph_node import CancelMotion
from giskardpy.motion_statechart.graph_node import EndMotion, Goal, Task
from giskardpy.motion_statechart.motion_statechart import MotionStatechart
from giskardpy.executor import NoPacing, Pacer, RealTimePacer, SimulationTimePacer
from giskardpy.qp.qp_controller_config import QPControllerConfig
from giskardpy.ros_executor import Ros2Executor
from krrood.entity_query_language.factories import evaluate_condition
from krrood.symbolic_math.symbolic_math import Scalar, trinary_logic_not
from semantic_digital_twin.world_description.world_entity import Body

if TYPE_CHECKING:
    from coraplex.robot_plans.actions.base import ActionDescription

    from coraplex.plans.condition_nodes import ConditionNode
    from coraplex.plans.plan_node import MotionNode
    from coraplex.plans.underspecified import UnderspecifiedNode
    from coraplex.datastructures.dataclasses import Context

logger = logging.getLogger(__name__)

HELD_BY_THE_PLAN = (LifeCycleValues.PAUSED, LifeCycleValues.INTERRUPTED)
"""
The states a plan sets on its own nodes to steer the chart, which the chart's own life
cycles are not allowed to overwrite.
"""

ENDED = (
    LifeCycleValues.SUCCEEDED,
    LifeCycleValues.FAILED,
    LifeCycleValues.INTERRUPTED,
)
"""
The states a node does not run on from.
"""


# %% who is told about a motion that has run


class ReceivesExecutedMotions(Protocol):
    """
    Something told about each motion state chart an executable has run.
    """

    def receive(self, motion_state_chart: MotionStatechart, duration: float) -> None:
        """
        Take the chart of a motion that has just finished.

        :param motion_state_chart: The chart that ran, holding the history it wrote.
        :param duration: How long it ran, in seconds.
        """


# %% the executables


@dataclass
class Executable:
    """
    Base class for executable units.
    """

    execution_list: List[Executable] = field(default_factory=list)
    """
    List of executables that comprises this executable.
    """

    context: Context = field(kw_only=True)
    """
    Coraplex context which should be used to execute this executable.
    """

    @property
    def giskard_executables(self) -> List[GiskardExecutable]:
        """
        :return: The giskard executables this unit is made of, in execution order.
        """
        return [
            giskard_executable
            for executable in self.execution_list
            for giskard_executable in executable.giskard_executables
        ]

    def execute(self) -> None:
        """
        Executes the unit.
        """
        for executable in self.execution_list:
            executable.execute()


@dataclass
class GiskardExecutable(Executable):
    """
    Executable for everything that can be added to a motion state chart, this includes
    the motions and the pre- and postconditions.
    """

    root_node: Goal = field(kw_only=True)
    """
    The goal below which every motion of this executable lives.
    """

    motion_state_chart: MotionStatechart = field(
        default_factory=MotionStatechart, kw_only=True
    )
    """
    Giskard's motion state chart for this executable.

    It is created once and only ever extended, because a compiled chart can no longer
    grow: :meth:`~giskardpy.motion_statechart.motion_statechart.MotionStatechart.compile`
    binds its updaters to the state arrays that adding a node would replace.
    """

    motion_mappings: Dict[MotionNode, Task] = field(default_factory=dict, kw_only=True)
    """
    Mapping from the motion nodes of the plan to their giskard tasks, in execution
    order.
    """

    pre_condition_node: Optional[ConditionNode] = field(default=None, kw_only=True)
    """
    Optional pre-condition of the action this executable belongs to.

    Carried on the executable but not evaluated during execution at present, see
    :meth:`_add_condition_monitors`.
    """

    post_condition_node: Optional[ConditionNode] = field(default=None, kw_only=True)
    """
    Optional post-condition of the action this executable belongs to.

    Carried on the executable but not evaluated during execution at present, see
    :meth:`_add_condition_monitors`.
    """

    execution_type: ClassVar[Optional[ExecutionType]] = None
    """
    The execution type used for all giskard executables, managed by
    :py:class:`pycram.motion_executor.ExecutionEnvironment`.
    """

    collision_avoidance: ClassVar[bool] = False
    """
    Whether the robot avoids colliding with its surroundings and with itself, managed by
    :py:class:`pycram.motion_executor.ExecutionEnvironment`.

    Adds an
    :class:`~giskardpy.motion_statechart.goals.collision_avoidance.ExternalCollisionAvoidance`
    and a
    :class:`~giskardpy.motion_statechart.goals.collision_avoidance.SelfCollisionAvoidance`
    to the motion state chart.
    """

    real_time_pacing: ClassVar[bool] = False
    """
    Whether the simulated tick loop is paced to wall-clock time (via
    :class:`~giskardpy.executor.SimulationPacer`) instead of running as fast as the QP
    solve allows, managed by :py:class:`pycram.motion_executor.ExecutionEnvironment`.
    """

    real_time_factor: ClassVar[Optional[float]] = None
    """
    Paces :meth:`_execute_simulation`'s tick loop to run no faster than this multiple of
    real (wall-clock) time, managed by
    :py:class:`pycram.motion_executor.ExecutionEnvironment`.

    ``None`` (the default) ticks as fast as the QP solver allows, which is what every
    existing test relies on; set this only for demos meant to be watched.
    """

    prediction_horizon: ClassVar[int] = 4
    """
    Prediction horizon passed to :meth:`_execute_simulation`'s
    :class:`~giskardpy.qp.qp_controller_config.QPControllerConfig`, managed by
    :py:class:`pycram.motion_executor.ExecutionEnvironment`.

    4 (the default, and the minimum the QP formulation accepts) is what every existing
    robot's tuning assumes. Raise it only for robots with real, tight jerk limits (a
    short horizon can make reaching their velocity limit mathematically infeasible
    within it) - raising it for everyone regressed other robots' plans in testing.
    """

    _current_motion_state_chart: MotionStatechart = field(init=False, default=None)
    """
    The motion state chart this executable most recently compiled, for a future caller
    to inspect what is currently running.
    """

    @property
    def giskard_executables(self) -> List[GiskardExecutable]:
        """
        :return: This executable, which is the only giskard executable it is made of.
        """
        return [self]

    def prepare_for_execution(self) -> None:
        """
        Extend the motion state chart with the nodes that terminate it.

        This runs just before compilation rather than during parsing, because the
        execution type is only known once an
        :py:class:`~coraplex.execution_environment.ExecutionEnvironment` is entered.
        """
        end_trigger = self.root_node.goal_reached
        if GiskardExecutable.collision_avoidance:
            self.motion_state_chart.add_node(ExternalCollisionAvoidance())
            self.motion_state_chart.add_node(SelfCollisionAvoidance())

        end_motion = EndMotion()
        end_motion.start_condition = end_trigger
        self.motion_state_chart.add_node(end_motion)

    def _add_condition_monitors(self, end_trigger: Scalar) -> Scalar:
        """
        Add the pre- and post-condition nodes to the motion state chart and wire them to
        the root node and the end trigger of the motion state chart.

        The pre-condition gates the start of the motions, the post-condition gates the
        successful end of the motion, and a
        :class:`~giskardpy.motion_statechart.graph_node.CancelMotion` aborts the motion if
        either is observed to be false.

        .. note:: Currently unused. Conditions are kept out of the chart while evaluating
            them inside it is being reworked; this stays so they can be wired back in.

        :param end_trigger: The trigger which ends the motion state chart.
        :return: The end trigger, gated by the post-condition when there is one.
        """
        from coraplex.plans.condition_nodes import condition_monitor

        if self.pre_condition_node is not None and self.context.evaluate_conditions:
            pre_monitor = condition_monitor(self.pre_condition_node)
            self.motion_state_chart.add_node(pre_monitor)
            # only start the motion once the pre-condition holds
            self.root_node.start_condition = pre_monitor.observation_variable
            # abort if the pre-condition is observed to be false
            pre_cancel = CancelMotion(
                exception=self._condition_not_satisfied(
                    self.pre_condition_node,
                    action_node=self.pre_condition_node.action_node.action,
                )
            )
            pre_cancel.start_condition = trinary_logic_not(
                pre_monitor.observation_variable
            )
            self.motion_state_chart.add_node(pre_cancel)

        if self.post_condition_node is not None and self.context.evaluate_conditions:
            post_monitor = condition_monitor(self.post_condition_node)
            # only evaluate the post-condition once the motion is done
            post_monitor.start_condition = end_trigger
            self.motion_state_chart.add_node(post_monitor)
            end_trigger = post_monitor.observation_variable
            # abort if the post-condition is observed to be false
            post_cancel = CancelMotion(
                exception=self._condition_not_satisfied(
                    self.post_condition_node,
                    action_node=self.post_condition_node.action_node.action,
                )
            )
            post_cancel.start_condition = trinary_logic_not(
                post_monitor.observation_variable
            )
            self.motion_state_chart.add_node(post_cancel)
        return end_trigger

    @staticmethod
    def _condition_not_satisfied(
        condition_node: ConditionNode,
        action_node: ActionDescription,
    ) -> ConditionNotSatisfied:
        return ConditionNotSatisfied(
            pre_condition=condition_node.pre_condition,
            action=action_node.__class__,
            condition=condition_node.condition,
        )

    @property
    def is_interrupted(self) -> bool:
        return any(node.is_interrupted for node in self.motion_mappings)

    @property
    def is_paused(self) -> bool:
        return any(node.is_paused for node in self.motion_mappings)

    def execute(self) -> None:
        """
        Completes the motion state chart and executes it according to the execution
        type, then tells the context's listener about the chart that ran.
        """
        if len(self.motion_mappings) == 0:
            return
        if GiskardExecutable.execution_type == ExecutionType.NO_EXECUTION:
            return
        self.prepare_for_execution()

        started_at = time.monotonic()
        match GiskardExecutable.execution_type:
            case ExecutionType.SIMULATED:
                self._execute_simulation()
            case ExecutionType.REAL:
                self._execute_real()
            case _:
                raise UnknownExecutionType(GiskardExecutable.execution_type)
        self._hand_over_the_chart_that_ran(time.monotonic() - started_at)

    def _hand_over_the_chart_that_ran(self, duration: float) -> None:
        """
        Hand the chart that has just run to whoever the context says listens.

        The chart itself is handed over rather than a copy of it, so what the listener
        keeps is the history the controller wrote into it.

        :param duration: How long the chart ran, in seconds.
        """
        if self.context.motion_listener is None:
            return
        self.context.motion_listener.receive(self.motion_state_chart, duration)

    def _build_pacer(self) -> Pacer:
        """
        The pacer for the control loop: simulated time when the context knows how to
        read a simulation clock, otherwise wall-clock time if ``real_time_pacing`` is on
        and no pacing at all if it is not.

        Pacing against a simulation that cannot hold real time keeps one control cycle
        of simulation between commands, rather than letting the controller outrun the
        plant by however far the simulation happens to be lagging.
        """
        if self.context.simulation_clock is not None:
            return SimulationTimePacer(simulation_clock=self.context.simulation_clock)
        if GiskardExecutable.real_time_pacing:
            return RealTimePacer()
        return NoPacing()

    def _execute_simulation(self) -> None:
        """
        Compiles the motion state chart and ticks it in the world of the context until
        it is done.
        """
        target_frequency = 50
        executor = Ros2Executor(
            context=MotionStatechartContext(
                world=self.context.world,
                qp_controller_config=QPControllerConfig(
                    target_frequency=target_frequency,
                    prediction_horizon=GiskardExecutable.prediction_horizon,
                    verbose=False,
                ),
            ),
            ros_node=self.context.ros_node,
            pacer=self._build_pacer(),
        )
        motion_state_chart = self.motion_state_chart
        executor.compile(motion_state_chart)

        # None (the default) ticks as fast as the QP solver allows; set via
        # ExecutionEnvironment(real_time_factor=...) to pace ticks to (a multiple of)
        # real time instead, so a demo plays out at a watchable speed rather than
        # teleporting through every intermediate joint configuration.
        tick_period = (
            1.0 / (target_frequency * GiskardExecutable.real_time_factor)
            if GiskardExecutable.real_time_factor
            else None
        )

        counter = 0
        while counter < len(self.motion_mappings) * self.context.ticks_per_motion:
            # Interrupting and pausing are handled inside the motion state chart by
            # per-task monitors (see motion_state_chart): an interrupt ends the
            # motion via EndMotion, a pause holds the active task via its
            # pause_condition. While paused we simply do not tick, so the pause does
            # not consume the tick budget.
            if self.is_paused:
                time.sleep(0.01)
                continue

            tick_start_time = time.time()
            executor.tick()
            ticked_at = datetime.now()
            self.keep_the_motions_in_step(started_at=ticked_at, ended_at=ticked_at)
            executor.pacer.sleep()
            counter += 1
            if tick_period is not None:
                remaining = tick_period - (time.time() - tick_start_time)
                if remaining > 0:
                    time.sleep(remaining)
            if executor.motion_statechart.is_end_motion():
                break

        executor.set_velocity_acceleration_jerk_to_zero()
        executor.motion_statechart.cleanup_nodes(context=executor.context)
        executor.context.cleanup()

        if not executor.motion_statechart.is_end_motion():
            unfinished_nodes = [
                node
                for node in motion_state_chart.nodes
                if node.life_cycle_state
                not in [LifeCycleValues.SUCCEEDED, LifeCycleValues.NOT_STARTED]
            ]
            motion_did_not_finish = MotionDidNotFinish(unfinished_nodes)
            logger.error(motion_did_not_finish.error_message())
            raise motion_did_not_finish

    def _execute_real(self) -> None:
        """
        Executes the motion state chart on the real robot via giskard while monitoring
        for interrupts.

        The chart runs inside Giskard, which reports back once it is done, so every
        motion of it is stamped with the stretch the whole chart ran over.
        """
        began = datetime.now()
        self.context.giskard_wrapper.execute(self.motion_state_chart)
        self.keep_the_motions_in_step(started_at=began, ended_at=datetime.now())

    def keep_the_motions_in_step(
        self, started_at: datetime, ended_at: datetime
    ) -> None:
        """
        Bring each motion's own record up to date with the life cycle its task is in.

        A plan's nodes are not performed one by one: the whole plan runs as one motion
        statechart, so what a motion node knows of its own run is read off its task
        after every tick. A node the plan itself holds paused or interrupted is left as
        the plan set it.

        :param started_at: When a task first seen running now is taken to have started.
        :param ended_at: When a task first seen ended now is taken to have ended.
        """
        for motion, task in self.motion_mappings.items():
            state = task.life_cycle_state
            if state is motion.status or motion.status in HELD_BY_THE_PLAN:
                continue
            if motion.status is LifeCycleValues.NOT_STARTED:
                motion.start_time = started_at
            if state in ENDED:
                motion.end_time = ended_at
            motion.status = state


@dataclass
class ConditionExecutable(Executable):
    """
    An executable unit for a condition node.
    """

    condition_node: ConditionNode = field(kw_only=True)
    """
    The condition node to execute.
    """

    def execute(self) -> None:
        """
        Executes the condition node.
        """
        if evaluate_condition(self.condition_node.condition):
            return True
        raise ConditionNotSatisfied(
            pre_condition=self.condition_node.pre_condition,
            action=self.condition_node.__class__,
            condition=self.condition_node.condition,
        )


@dataclass
class MoveBranchExecutable(Executable):
    """
    Executable that moves a body under a new parent, keeping the body's own connection
    so an actively driven body stays drivable afterwards.
    """

    body: Body = field(kw_only=True)
    """
    The root of the branch in the kinematic structure that is moved.
    """

    new_parent: Body = field(kw_only=True)
    """
    The new parent to which the branch is moved.
    """

    def execute(self) -> None:
        self.context.world.move_branch(self.body, self.new_parent)


@dataclass
class UnderspecifiedExecutable(Executable):
    """
    Executable for an underspecified node whose resolution is deferred to execution
    time.

    Because it is not a :class:`GiskardExecutable`, it acts as a boundary in the
    execution list: every preceding executable runs (and mutates the world) before it
    is reached. Only then is the underspecified statement grounded, so the query sees
    the correct world state (e.g. the torso already raised, the object already in the
    gripper). Candidates are tried in order until one executes without raising a
    :class:`~pycram.plans.failures.PlanFailure`; if the generator is exhausted,
    :class:`~pycram.plans.failures.EmptyUnderspecified` is raised.
    """

    node: UnderspecifiedNode = field(kw_only=True)
    """
    The underspecified node that is grounded when this executable is reached.
    """

    def execute(self) -> None:
        from coraplex.plans.failures import PlanFailure, EmptyUnderspecified

        while self.node.advance():
            try:
                self.node.current_candidate.parse().execute()
                self.node.stop_grounding()
                return
            except PlanFailure:
                continue
        raise EmptyUnderspecified()

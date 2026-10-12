from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import timedelta

from rclpy.node import Node
from typing_extensions import List, Optional

from coraplex.exceptions import (
    MotionDidNotFinish,
    PlanNotCompiled,
)
from coraplex.plans.context_extensions import (
    ExecutionMode,
    MotionToleranceConfig,
    StatementGrounding,
)
from coraplex.plans.failures import (
    CandidateLimitReached,
    EmptyUnderspecified,
    MotionExceededSimulationTimeLimit,
    MotionMadeNoProgress,
    MotionViolatedCollisionAvoidance,
)
from coraplex.plans.plan_transformation import PlanRewriting
from coraplex.plans.underspecified import (
    UnderspecifiedChildChooser,
    UnderspecifiedNode,
)
from cramph.composites import ChildChooserAccess
from cramph.context import ContextExtension, StatechartContext
from cramph.data_types import LifeCycleValues
from cramph.exceptions import EmptyStatechartError
from cramph.executor import Executor, ExecutorExtension, StatechartExecutor
from cramph.node import StatechartNode, TerminalNode
from cramph.statechart import Statechart
from giskardpy.motion_control import MotionControl
from giskardpy.motion_statechart.exceptions import (
    CollisionViolatedError,
    NoProgressError,
)
from giskardpy.motion_statechart.goals.collision_avoidance import (
    ExternalCollisionAvoidance,
    SelfCollisionAvoidance,
)
from giskardpy.motion_statechart.graph_node import ConvergingTask, EndMotion
from giskardpy.motion_statechart.monitors.progress_monitors import StillProgressing
from giskardpy.middleware.ros2.python_interface import GiskardClientExecutor
from giskardpy.motion_statechart.ros_context import RosNodeAccess
from krrood.ormatic.utils import classproperty
from krrood.symbolic_math.symbolic_math import logic_or
from semantic_digital_twin.world import World

logger = logging.getLogger(__name__)


# %% executing a plan


@dataclass
class PlanExecutor(Executor, ABC):
    """
    Executes a plan: the top-level nodes of a statechart built in :attr:`context`.

    The executor builds that context over :attr:`world` from the extensions it is given,
    which are what describes the robot and how the plan is grounded, so the same
    extensions can configure the executors of several plans. :meth:`compile` adds what a
    plan runs with: the collision avoidance if asked for, one
    :class:`~giskardpy.motion_statechart.graph_node.EndMotion` once every plan node
    succeeded or one of them ended without succeeding, and the stall detection.
    Underspecified actions are grounded while it runs, see
    :class:`~coraplex.plans.underspecified.UnderspecifiedChildChooser`.
    """

    context: StatechartContext = field(init=False)
    """
    The context the plan's statechart is built and run in, built from
    :attr:`context_extensions`.
    """

    world: World
    """
    The world the plan is executed in.
    """

    context_extensions: List[ContextExtension] = field(
        default_factory=list, kw_only=True
    )
    """
    What the plan's nodes read from the context, such as the
    :class:`~coraplex.plans.context_extensions.RobotAccess` of the robot performing it.

    A :class:`~coraplex.plans.context_extensions.StatementGrounding`, a
    :class:`~coraplex.plans.context_extensions.MotionToleranceConfig` and a
    :class:`~coraplex.plans.plan_transformation.PlanRewriting` with default values are
    added unless one is given; the latter holds the transformations rewriting the plan
    once it is expanded, and every action that joins it while it runs.
    """

    ros_node: Optional[Node] = field(default=None, kw_only=True)
    """
    The ROS node the plan communicates through, if any.
    """

    collision_avoidance: bool = field(default=False, kw_only=True)
    """
    Whether the robot avoids colliding with its surroundings and with itself.
    """

    debug: bool = field(default=False, kw_only=True)
    """
    Whether debug messages are logged and every copy of the world a candidate is tried
    in is published to RViz, which needs :attr:`ros_node`.
    """

    child_chooser: UnderspecifiedChildChooser = field(init=False)
    """
    Grounds the underspecified actions of the plan while it runs.
    """

    plan_nodes: List[StatechartNode] = field(default_factory=list, init=False)
    """
    The top-level nodes of the plan compiled last.
    """

    @classproperty
    def simulated(cls) -> bool:
        """
        :return: Whether this executor runs plans against a simulated robot.
        """
        return issubclass(cls, SimulatedPlanExecutor)

    def __post_init__(self):
        if self.debug and self.ros_node is None:
            raise ValueError("Debug mode requires a ROS node")
        logging.getLogger("coraplex").setLevel(
            logging.DEBUG if self.debug else logging.INFO
        )
        self.context = StatechartContext(world=self.world)
        for extension in self.context_extensions:
            self.context.add_extension(extension)
        self.context.add_extension(
            ExecutionMode(
                simulated=self.simulated,
                collision_avoidance=self.collision_avoidance,
            )
        )
        self.child_chooser = UnderspecifiedChildChooser(
            executor=self, trial_executor_type=SimulatedPlanExecutor
        )
        self.context.add_extension(ChildChooserAccess(chooser=self.child_chooser))
        super().__post_init__()

    def default_context_extensions(self) -> list[ContextExtension]:
        return [StatementGrounding(), MotionToleranceConfig(), PlanRewriting()]

    def prepare(self, statechart: Statechart) -> None:
        """
        Add what the plan in `statechart` runs with, and rewrite it with the plan
        transformations, without compiling it.

        :param statechart: The statechart holding the plan, built in :attr:`context`.
        :raises StatechartOfDifferentContextError: If `statechart` was not built in
            :attr:`context`.
        :raises EmptyStatechartError: If `statechart` holds no node.
        """
        Executor.compile(self, statechart)
        self.plan_nodes = list(statechart.top_level_nodes)
        if not self.plan_nodes:
            raise EmptyStatechartError()
        rewriting = self.context.require_extension(PlanRewriting)
        for plan_node in self.plan_nodes:
            rewriting.rewrite(plan_node)
        if self.collision_avoidance:
            statechart.add_node(ExternalCollisionAvoidance())
            statechart.add_node(SelfCollisionAvoidance())
        self._add_end_of_plan(statechart)
        self._add_stall_detection(statechart)

    def _add_end_of_plan(self, statechart: Statechart) -> None:
        """
        End the statechart once every plan node succeeded, or one of them ended without
        succeeding, so the plan no longer can.

        :param statechart: The statechart the plan was added to.
        """
        end_of_plan = EndMotion.when_all_true(self.plan_nodes)
        end_of_plan.start_condition = logic_or(
            end_of_plan.start_condition,
            *[plan_node.is_failed_or_interrupted for plan_node in self.plan_nodes],
        )
        statechart.add_node(end_of_plan)

    def _add_stall_detection(self, statechart: Statechart) -> None:
        """
        Cancel the statechart once a plan node stops approaching its goal.

        Only the motions a plan node holds when it is compiled are watched; an action an
        underspecified node chooses later is watched by its own stall monitor. A plan
        node holding no motion yet is not watched at all, since it would read as stalled
        from its first tick.

        :param statechart: The statechart the plan was added to, which expanded it.
        """
        for plan_node in self.plan_nodes:
            if not any(
                isinstance(node, ConvergingTask)
                for node in [plan_node, *plan_node.descendants]
            ):
                continue
            still_progressing = StillProgressing(monitored_node=plan_node)
            statechart.add_node(still_progressing)
            statechart.add_node(still_progressing.cancel_motion())

    def compile(self, statechart: Statechart) -> None:
        """
        Prepare the plan in `statechart`, see :meth:`prepare`, and compile it, so that
        :meth:`execute` can run it.

        :param statechart: The statechart holding the plan, built in :attr:`context`.
        """
        self.prepare(statechart)
        super().compile(statechart)

    def execute(self) -> None:
        """
        Run the compiled plan until every plan node succeeded.

        :raises PlanNotCompiled: If no plan was compiled.
        :raises MotionDidNotFinish: If the plan did not succeed.
        :raises EmptyUnderspecified: If an underspecified action ran out of actions to
            try.
        :raises CandidateLimitReached: If an underspecified action tried as many actions
            as it may.
        :raises MotionMadeNoProgress: When the plan stops approaching its goal.
        :raises MotionExceededSimulationTimeLimit: When a simulated plan runs for longer
            than :attr:`SimulatedPlanExecutor.simulation_time_limit`.
        :raises MotionViolatedCollisionAvoidance: When the plan brings bodies closer to
            each other than collision avoidance allows.
        """
        if self.statechart is None:
            raise PlanNotCompiled()
        try:
            self._run()
        except NoProgressError as stalled:
            raise MotionMadeNoProgress(stalled) from stalled
        except CollisionViolatedError as violation:
            raise MotionViolatedCollisionAvoidance(violation) from violation
        self._raise_if_plan_failed()

    @abstractmethod
    def _run(self) -> None:
        """
        Run the compiled plan until it ended, leaving every node in the life cycle state
        it ended in.
        """

    def close(self) -> None:
        """
        Release what this executor acquired to run its plans, once no further plan is
        run with it.
        """

    def _plan_failed(self) -> bool:
        """
        :return: Whether a plan node ended without succeeding, so the plan no longer
            can succeed.
        """
        return any(
            plan_node.life_cycle_state.is_terminal
            and plan_node.life_cycle_state != LifeCycleValues.SUCCEEDED
            for plan_node in self.plan_nodes
        )

    def _raise_if_plan_failed(self) -> None:
        """
        :raises CandidateLimitReached: If an underspecified node tried as many actions
            as it may, which is why the plan failed.
        :raises EmptyUnderspecified: If an underspecified node ran out of actions to
            try, which is why the plan failed.
        :raises MotionDidNotFinish: If the plan failed for any other reason.
        """
        if not self._plan_failed():
            return
        self._raise_if_out_of_candidates()
        motion_did_not_finish = MotionDidNotFinish(
            [
                node
                for node in self.statechart.nodes
                if not isinstance(node, TerminalNode)
                and node.life_cycle_state
                not in [LifeCycleValues.SUCCEEDED, LifeCycleValues.NOT_STARTED]
            ]
        )
        logger.error(motion_did_not_finish.error_message())
        raise motion_did_not_finish

    def _raise_if_out_of_candidates(self) -> None:
        """
        :raises CandidateLimitReached: If an underspecified node tried as many actions
            as it may.
        :raises EmptyUnderspecified: If an underspecified node ran out of actions to
            try.
        """
        for node in self.statechart.get_nodes_by_type(UnderspecifiedNode):
            if not node.ran_out_of_children:
                continue
            if node.reached_candidate_limit:
                raise CandidateLimitReached(
                    node=node, candidate_limit=node.candidate_limit
                )
            raise EmptyUnderspecified(node=node)


@dataclass
class SimulatedPlanExecutor(PlanExecutor, StatechartExecutor):
    """
    Ticks the plan's statechart in :attr:`world`, driving the robot's motions with the
    :class:`~giskardpy.motion_control.MotionControl` among its :attr:`extensions`, which
    is added with its default controller unless one is given.
    """

    simulation_time_limit: timedelta = field(default=timedelta(minutes=2), kw_only=True)
    """
    The simulated time after which a plan is given up on, however it is progressing.
    """

    def default_executor_extensions(self) -> list[ExecutorExtension]:
        return [RosNodeAccess(self.ros_node), MotionControl()]

    def _run(self) -> None:
        """
        Tick the statechart until it or the plan ended, waiting for :attr:`pacer` after
        every tick.

        The statechart's own stall monitor decides when a plan is hopeless, so a plan
        that keeps converging is never cut off for taking many ticks.

        :raises NoProgressError: When the plan stops approaching its goal.
        :raises MotionExceededSimulationTimeLimit: When the plan runs for longer than
            :attr:`simulation_time_limit`.
        """
        maximum_ticks = (
            self.simulation_time_limit.total_seconds()
            / self.context.require_tick_duration()
        )
        try:
            while not self._is_over():
                if self.tick_count >= maximum_ticks:
                    raise MotionExceededSimulationTimeLimit(self.simulation_time_limit)
                self.tick()
                self.pacer.sleep()
        finally:
            MotionControl.set_velocity_acceleration_jerk_to_zero(self.world)
            self.finish_run()

    def _is_over(self) -> bool:
        """
        :return: Whether the statechart ended, every plan node succeeded or the plan
            failed.
        """
        return (
            self.statechart.is_ended()
            or self._plan_failed()
            or all(
                plan_node.life_cycle_state == LifeCycleValues.SUCCEEDED
                for plan_node in self.plan_nodes
            )
        )


@dataclass
class RealRobotPlanExecutor(PlanExecutor):
    """
    Sends the plan's statechart to Giskard, grounding every underspecified action
    Giskard reaches against the world as it is then.

    Giskard compiles the statechart once it receives it.
    """

    _giskard: Optional[GiskardClientExecutor] = field(
        default=None, init=False, repr=False
    )
    """
    The connection to Giskard every plan is sent through, None until the first plan
    runs.
    """

    def _run(self) -> None:
        """
        Send the statechart to Giskard and wait until it ended there.
        """
        if self._giskard is None:
            self._giskard = GiskardClientExecutor(self.ros_node, context=self.context)
        self._giskard.compile(self.statechart)
        self._giskard.execute()

    def close(self) -> None:
        if self._giskard is None:
            return
        self._giskard.close()
        self._giskard = None

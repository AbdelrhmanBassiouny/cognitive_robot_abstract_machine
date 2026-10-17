from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from typing_extensions import (
    List,
    Optional,
)

from coraplex.plans.context_extensions import RobotAccess, StatementGrounding
from coraplex.plans.designator import DesignatorParameters
from coraplex.plans.plan_transformation import PlanRewriting
from krrood.ormatic.utils import classproperty
from cramph.node import SucceedsOnObservingTrue, FailsOnObservingFalse
from cramph.composites import Parallel, Sequence, TryAll
from cramph.context import ContextExtension, StatechartContext
from cramph.node import CompositeNode, NodeArtifacts, StatechartNode
from giskardpy.motion_statechart.graph_node import MotionStatechartNode
from giskardpy.motion_statechart.tasks.cartesian_tasks import HoldPose
from krrood.symbolic_math.symbolic_math import Scalar, trinary_if_cases
from semantic_digital_twin.robots.robot_part_mixins import HasMobileBase
from semantic_digital_twin.robots.robot_parts import AbstractRobot
from semantic_digital_twin.world_description.world_entity import (
    KinematicStructureEntity,
)

logger = logging.getLogger(__name__)


@dataclass(eq=False, repr=False, kw_only=True)
class Action(
    SucceedsOnObservingTrue,
    CompositeNode,
    DesignatorParameters,
    ABC,
):
    """
    Something a robot does, described by the parameters it is given and run as a node of
    a statechart.

    It ends itself once it did what it does, so an action can be a step of another one.
    What it does takes one of a few shapes: a :class:`GoalAction` reaches a single goal,
    while a :class:`SequentialAction`, :class:`ParallelAction` or :class:`TryAllAction`
    is the plan language node of the steps it creates.

    .. note:: :class:`~coraplex.plans.designator.DesignatorParameters` is the last
        base, because ORMatic resolves a data access object's parent by walking the
        method resolution order and taking the first mapped class, and an action is
        stored as the statechart node it is.
    """

    @classproperty
    def context_extensions_required_to_expand(
        cls,
    ) -> tuple[type[ContextExtension], ...]:
        return super().context_extensions_required_to_expand + (RobotAccess,)

    @property
    def robot(self) -> AbstractRobot:
        """
        :return: The robot performing this action.
        """
        return self.context.require_extension(RobotAccess).robot

    @property
    def sampling_seed(self) -> Optional[int]:
        """
        :return: The seed for the locations this action samples, so a run can be
            repeated; ``None`` samples afresh each run.
        """
        return self.context.require_extension(StatementGrounding).sampling_seed

    @property
    def controlled_root(self) -> KinematicStructureEntity:
        """
        :return: The topmost entity this action's motions may move the robot relative
            to, which its Cartesian goals are expressed in.
        """
        return self.context.require_extension(RobotAccess).controlled_root

    def keep_base_still(self) -> List[MotionStatechartNode]:
        """
        :return: The task holding the robot's base where it stands, empty when the robot
            has no mobile base or may move its whole body.

        A goal relative to the robot is bound when it starts, so a base that moves
        afterwards, which collision avoidance does to buy clearance, carries the goal
        away from its target.
        """
        robot = self.robot
        if (
            not isinstance(robot, HasMobileBase)
            or robot.mobile_base.full_body_controlled
        ):
            return []
        return [
            HoldPose(name="hold base", root_link=self.world.root, tip_link=robot.root)
        ]

    def expand(self, context: StatechartContext) -> None:
        """
        Creates what this action does below it, once the
        :class:`~coraplex.plans.plan_transformation.PlanRewriting` of `context`, if any,
        configured this action.
        """
        rewriting = context.get_extension(PlanRewriting)
        if rewriting is not None:
            rewriting.configure(self)
        self._create_what_it_does(context)

    @abstractmethod
    def _create_what_it_does(self, context: StatechartContext) -> None:
        """
        Puts the nodes doing what this action does below it, in the shape of its kind of
        action.
        """


@dataclass(eq=False, repr=False, kw_only=True)
class GoalAction(Action, FailsOnObservingFalse, ABC):
    """
    An action reaching a single goal, the node :meth:`create_goal` creates, which stays a
    node of its own below the action.

    The action reaches its goal once that node did, and declares itself failed as soon
    as the node failed. A goal whose owner decides its success, such as a single task,
    is ended by the action once it observes True.
    """

    @abstractmethod
    def create_goal(self) -> StatechartNode:
        """
        :return: A new node reaching the goal of this action. Called once, when the
            action is expanded.
        """

    @property
    def goal(self) -> Optional[StatechartNode]:
        """
        :return: The child reaching the goal of this action, None until the action was
            expanded.
        """
        if not self.children:
            return None
        return self.children[0]

    def _create_what_it_does(self, context: StatechartContext) -> None:
        """
        Puts the goal below this action and ends it once it is at its goal, unless it
        decides its own success.
        """
        goal = self.create_goal()
        self._add_child_to_statechart(goal)
        self._succeed_at_its_goal(goal)

    def build_artifacts(self, context: StatechartContext) -> NodeArtifacts:
        """
        Report how the goal ended, or nothing while it has not.
        """
        return NodeArtifacts(
            observation=trinary_if_cases(
                cases=[
                    (self.goal.is_succeeded, Scalar.const_true()),
                    (self.goal.is_failed_or_interrupted, Scalar.const_false()),
                ],
                else_result=Scalar.const_trinary_unknown(),
            )
        )


@dataclass(eq=False, repr=False, kw_only=True)
class ActionOfSteps(Action, ABC):
    """
    An action that is the plan language node of its own steps, the nodes
    :meth:`create_steps` creates, so the steps are its children and the language node
    it also is decides how they run and when they are done.

    .. note:: The language node comes after :class:`Action` in the method resolution
        order of every shape, so that the action ends itself once its steps are done,
        even where the language node alone would leave that to its owner.
    """

    nodes: List[StatechartNode] = field(default_factory=list, init=False, repr=False)
    """
    The steps of this action, which :meth:`create_steps` creates when the action is
    expanded, and which plan transformations may add to.
    """

    @abstractmethod
    def create_steps(self) -> List[StatechartNode]:
        """
        :return: New nodes doing what this action does, in order. Called once, when the
            action is expanded.
        """

    def _create_what_it_does(self, context: StatechartContext) -> None:
        """
        Puts the steps below this action and lets the language node wire them.
        """
        self.nodes = [self._as_node(step) for step in self.create_steps()]
        super(Action, self).expand(context)


@dataclass(eq=False, repr=False, kw_only=True)
class SequentialAction(ActionOfSteps, Sequence, ABC):
    """
    An action running its steps one after another, done once the last one succeeded.
    """


@dataclass(eq=False, repr=False, kw_only=True)
class ParallelAction(ActionOfSteps, Parallel, ABC):
    """
    An action running its steps side by side, done once all of them are at their goals
    together.
    """

    minimum_success: Optional[int] = field(default=None, init=False, repr=False)
    """
    None, so every step has to be at its goal; how many have to be is up to the action,
    not a parameter it is described by.
    """


@dataclass(eq=False, repr=False, kw_only=True)
class TryAllAction(ActionOfSteps, TryAll, ABC):
    """
    An action running its steps side by side as alternatives, done once one of them
    succeeded.
    """

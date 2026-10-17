from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

from typing_extensions import (
    List,
    Optional,
)

from coraplex.exceptions import ActionNotExpanded
from coraplex.plans.context_extensions import RobotAccess, StatementGrounding
from coraplex.plans.designator import DesignatorParameters
from coraplex.plans.plan_transformation import PlanRewriting
from krrood.ormatic.utils import classproperty
from cramph.node import SucceedsOnObservingTrue, FailsOnObservingFalse
from cramph.composites import CramLanguageNode
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
    FailsOnObservingFalse,
    CompositeNode,
    DesignatorParameters,
    ABC,
):
    """
    Something a robot does, described by the parameters it is given and run as a node of
    a statechart.

    What it does is its :attr:`action_body`, the node :meth:`create_action_body`
    creates. The action reaches its goal once its body did, and declares itself failed
    as soon as the body failed, so an action can be a step of another one. A body whose
    owner decides its success, such as a single task, is ended by the action once it
    observes True.

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

    @abstractmethod
    def create_action_body(self) -> StatechartNode:
        """
        :return: A new node running what this action does: a single goal, or a
            :class:`~cramph.composites.Sequence` of its steps. Called once, when the
            action is expanded.
        """

    @property
    def action_body(self) -> Optional[StatechartNode]:
        """
        :return: The child running what this action does, which is the node
            :meth:`create_action_body` created. None until the action was expanded.
        """
        if not self.children:
            return None
        return self.children[0]

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
        Puts the node this action creates below it, once the
        :class:`~coraplex.plans.plan_transformation.PlanRewriting` of `context`, if any,
        configured this action.
        """
        rewriting = context.get_extension(PlanRewriting)
        if rewriting is not None:
            rewriting.configure(self)
        self._put_below_as_action_body(self.create_action_body())

    def replace_action_body(self, node: StatechartNode) -> None:
        """
        Puts `node` in place of :attr:`action_body`, as what this action does.

        If `node` is a plan language node that has the action body among its children,
        the action body stays in the statechart as that child, and the conditions this
        action wired for it are cleared, so that `node` wires them. Otherwise the action
        body leaves the statechart together with everything below it.

        :param node: The node to put in its place, which belongs to no statechart yet.
        :raises ActionNotExpanded: If this action was not expanded yet.
        :raises StatechartAlreadyCompiledError: If the statechart of this action is
            compiled.
        """
        replaced = self.action_body
        if replaced is None:
            raise ActionNotExpanded(self)
        if isinstance(node, CramLanguageNode) and node._has_child(replaced):
            self._check_accepts_children()
            node._join_statechart_keeping_child(
                replaced, lambda: self._put_in_place_of_action_body(node)
            )
            return
        self.statechart.remove_node(replaced)
        self._put_below_as_action_body(node)

    def _put_in_place_of_action_body(self, node: StatechartNode) -> None:
        """
        Puts `node` in the statechart as :attr:`action_body`, in place of the current
        one, which stays in the statechart.
        """
        self.nodes[self.nodes.index(self.action_body)] = node
        self._put_below_as_action_body(node)

    def _put_below_as_action_body(self, node: StatechartNode) -> None:
        """
        Puts `node` below this action and ends it once it is at its goal, unless it
        decides its own success.
        """
        self._add_child_to_statechart(node)
        self._succeed_at_its_goal(node)

    def build_artifacts(self, context: StatechartContext) -> NodeArtifacts:
        """
        Report how the body ended, or nothing while it has not.
        """
        return NodeArtifacts(
            observation=trinary_if_cases(
                cases=[
                    (self.action_body.is_succeeded, Scalar.const_true()),
                    (self.action_body.is_failed_or_interrupted, Scalar.const_false()),
                ],
                else_result=Scalar.const_trinary_unknown(),
            )
        )

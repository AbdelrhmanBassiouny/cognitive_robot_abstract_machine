"""
What a robot did, as something a query can range over.

A plan's action nodes are compiled into motion state charts and run there, so an
action's own node never records that it ran; its motions do. Each action whose motions
ran is flattened to the names and the moments a question about the robot's past asks
for.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime

from typing_extensions import Any, List, Optional, Type

from krrood.entity_query_language.factories import an, entity, variable

from coraplex.plans.plan import Plan
from coraplex.plans.plan_node import ActionNode, MotionNode, PlanNode
from giskardpy.motion_statechart.data_types import LifeCycleValues
from semantic_digital_twin.grasping.grasp_candidates import GraspCandidate
from semantic_digital_twin.robots.robot_parts import AbstractRobotPart
from semantic_digital_twin.semantic_annotations.mixins import HasRootBody
from semantic_digital_twin.world_description.world_entity import Body

# %% the object an action is about


@dataclass(frozen=True)
class ActedOnObject:
    """
    Finds the object of the world an action is about, such as the milk a pick up lifts.

    An action names its object among its parameters, directly or through a nested action
    or a grasp; the robot's own parts are parameters too but never what the action is
    about.
    """

    node: ActionNode
    """
    The action node whose object is looked for.
    """

    def body(self) -> Optional[Body]:
        """
        The body the action is about: what it grasps if it grasps anything, such as the
        spoon fetched from a drawer rather than the drawer's handle pulled on the way,
        and otherwise the first object its parameters name.
        """
        parameters = [
            value
            for action_node in [self.node, *self._sub_actions()]
            for value in action_node.designator.designator_parameter.values()
        ]
        grasped = [
            value.graspable.root
            for value in parameters
            if isinstance(value, GraspCandidate)
        ]
        if grasped:
            return grasped[0]
        named = [body for value in parameters if (body := self._body_of(value))]
        return named[0] if named else None

    def _sub_actions(self) -> List[ActionNode]:
        """
        The actions this one was carried out by, in the order the plan lists them.
        """
        return [
            descendant
            for descendant in self.node.descendants
            if isinstance(descendant, ActionNode)
        ]

    @staticmethod
    def _body_of(value: Any) -> Optional[Body]:
        """
        The body a parameter value stands for, or None for a value that names no object
        of the world or names a part of the robot.

        :param value: The parameter value to read.
        """
        if isinstance(value, Body):
            return value
        if isinstance(value, HasRootBody) and not isinstance(value, AbstractRobotPart):
            return value.root
        return None


# %% one performed action


@dataclass(frozen=True)
class PerformedAction:
    """
    One action the robot carried out, flattened to what a question about it asks.
    """

    name: str
    """
    The action's label, e.g. ``"Milk PickUpAction"``.
    """

    action_type: str
    """
    The kind of action, e.g. ``"PickUpAction"``.
    """

    timestamp: datetime
    """
    When the action's first motion began.
    """

    seconds: float
    """
    How long the action took, from its first motion's start to its last motion's end.
    """

    acted_on: Optional[str] = None
    """
    Name of the body the action was about, or None for an action about no object, such
    as parking the arms.
    """

    part_of: Optional[str] = None
    """
    The kind of action this one was carried out for, or None for a step of the plan
    itself.
    """

    def related_highlight_ids(self) -> List[str]:
        """
        The body the action was about, so an answer naming the action lights it up.
        """
        return [self.acted_on] if self.acted_on is not None else []

    @classmethod
    def of_node(cls, node: ActionNode) -> Optional[PerformedAction]:
        """
        The record of an action node, or None for an action none of whose motions ran,
        such as an alternative that was never tried.

        :param node: The action node to flatten.
        """
        motions = [
            descendant
            for descendant in node.descendants
            if isinstance(descendant, MotionNode)
            and descendant.status == LifeCycleValues.SUCCEEDED
        ]
        if not motions:
            return None
        start = min(motion.start_time for motion in motions)
        end = max(motion.end_time for motion in motions)
        action_type = type(node.designator).__name__
        body = ActedOnObject(node).body()
        acted_on = str(body.name) if body is not None else None
        parent = node.parent_action_node
        return cls(
            name=f"{body.name.name} {action_type}" if body else action_type,
            action_type=action_type,
            timestamp=start,
            seconds=(end - start).total_seconds(),
            acted_on=acted_on,
            part_of=type(parent.designator).__name__ if parent is not None else None,
        )


# %% one finished run


@dataclass
class RecordedRun:
    """
    One run a demonstration finished: when it began and every action the robot carried
    out in it.
    """

    demonstration: str
    """
    The name of the demonstration that ran.
    """

    started: datetime
    """
    When the run's first action began.
    """

    actions: List[PerformedAction] = field(default_factory=list)
    """
    Every action the robot carried out in the run, in the order they began.
    """

    @property
    def name(self) -> str:
        """
        The run's label, e.g. ``"place setting at 15:27:09"``.
        """
        return f"{self.demonstration} at {self.started:%H:%M:%S}"

    @classmethod
    def of_actions(
        cls, demonstration: str, actions: List[PerformedAction]
    ) -> RecordedRun:
        """
        The run that carried out the given actions.

        :param demonstration: The name of the demonstration that ran.
        :param actions: The run's actions, in the order they began.
        """
        return cls(
            demonstration=demonstration,
            started=actions[0].timestamp,
            actions=actions,
        )


# %% every performed action of a demonstration


@dataclass
class PerformedActions:
    """
    Every action of the plans a demonstration has performed, read afresh each time it is
    iterated so a question sees what the robot has done by the time it is asked.
    """

    plans: List[Plan] = field(default_factory=list)
    """
    The plans performed so far, in the order they were performed.
    """

    def running(self, node_type: Type[PlanNode] = PlanNode) -> List[PlanNode]:
        """
        :param node_type: The kind of node asked for.
        :return: The nodes of the kind running right now in the plans, deepest first.
        """
        node = variable(
            node_type, [node for plan in self.plans for node in plan.all_nodes]
        )
        running = an(entity(node).where(node.status == LifeCycleValues.RUNNING))
        return sorted(running.tolist(), key=lambda found: -found.depth)

    def __iter__(self) -> Iterator[PerformedAction]:
        """
        Iterate over the performed actions in the order they began.
        """
        records = [
            record
            for plan in self.plans
            for node in plan.plan_graph.nodes()
            if isinstance(node, ActionNode)
            and (record := PerformedAction.of_node(node)) is not None
        ]
        return iter(sorted(records, key=lambda record: record.timestamp))

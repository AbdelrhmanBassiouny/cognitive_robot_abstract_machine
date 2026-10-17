from __future__ import annotations

from dataclasses import dataclass, field

from cramph.composites import Parallel
from cramph.context import StatechartContext
from cramph.node import StatechartNode
from giskardpy.motion_statechart.goals.collision_avoidance import (
    UpdateTemporaryCollisionRules,
)
from giskardpy.motion_statechart.monitors.monitors import LocalMinimumReached
from giskardpy.motion_statechart.tasks.joint_tasks import (
    JointPositionList,
    JointVelocityLimit,
)
from semantic_digital_twin.datastructures.definitions import GripperState
from semantic_digital_twin.datastructures.joint_state import JointState
from semantic_digital_twin.robots.robot_parts import EndEffector
from typing_extensions import List, Optional


@dataclass(eq=False, repr=False, kw_only=True)
class MoveGripper(Parallel):
    """
    Drive a gripper to one of the states its end effector defines.

    Fingers that close on an object stop short of the position they were commanded, so
    the goal can be told to settle for fingers that have stopped moving instead.
    """

    end_effector: EndEffector
    """
    The gripper to drive.
    """

    state: GripperState
    """
    The state to drive it to, read off the end effector as a joint state.
    """

    tolerate_stall: bool = False
    """
    Whether fingers that have stopped moving count as done, even short of their
    commanded position.
    """

    stall_minimum_time: Optional[float] = None
    """
    How long the fingers must stand still before a stall counts, in seconds.

    None keeps :attr:`~giskardpy.motion_statechart.monitors.monitors.LocalMinimumReached.minimum_time`.
    """

    finger_velocity: Optional[float] = None
    """
    Maximum speed of the finger joints, in meters per second.

    None leaves the speed capped only by the joints' own limits.
    """

    allow_gripper_collision: bool = False
    """
    Whether this end effector, and whatever it holds, may touch its surroundings while
    the fingers move.
    """

    nodes: List[StatechartNode] = field(default_factory=list, init=False)
    """
    The finger goal, together with the speed cap and collision allowance that were asked
    for.
    """

    def expand(self, context: StatechartContext) -> None:
        """
        Create the finger goal, the speed cap and the collision allowance, then adopt
        them as :meth:`~cramph.composites.CramLanguageNode.expand` does.
        """
        goal_state = self.end_effector.get_joint_state_by_type(self.state)
        self.nodes.append(self._finger_goal(goal_state))
        if self.finger_velocity is not None:
            self.nodes.append(
                JointVelocityLimit(
                    connections=list(goal_state.connections),
                    max_velocity=self.finger_velocity,
                )
            )
        if self.allow_gripper_collision:
            self.nodes.append(
                UpdateTemporaryCollisionRules.for_end_effector(self.end_effector)
            )
        super().expand(context)

    def _finger_goal(self, goal_state: JointState) -> StatechartNode:
        """
        :param goal_state: The joint state the fingers are driven to.
        :return: The node that is done once the fingers arrived, which with
            :attr:`tolerate_stall` is also done once they stopped moving short of it.

        The stall monitor sits beside the joint goal rather than replacing its
        observation, because fingers standing still does not mean the commanded position
        was reached.
        """
        joint_goal = JointPositionList(goal_state=goal_state)
        if not self.tolerate_stall:
            return joint_goal
        return Parallel(
            nodes=[joint_goal, self._stall_monitor(goal_state)], minimum_success=1
        )

    def _stall_monitor(self, goal_state: JointState) -> LocalMinimumReached:
        """
        :param goal_state: The joint state whose degrees of freedom are watched.
        :return: A monitor that observes the commanded fingers, and only those, standing
            still for long enough.
        """
        return LocalMinimumReached(
            degrees_of_freedom=[
                connection.raw_dof for connection in goal_state.connections
            ],
            minimum_time=(
                LocalMinimumReached.minimum_time
                if self.stall_minimum_time is None
                else self.stall_minimum_time
            ),
            measure_from_own_start=True,
        )

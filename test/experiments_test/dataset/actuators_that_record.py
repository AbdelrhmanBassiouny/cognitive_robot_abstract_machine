"""
Stand-ins for the physical robot's arm and fingers, which record what they were asked to
do instead of doing it.

They let the actions that drive Tracy be asserted without a robot, a Giskard or a ROS
node: the plans the arm would have been driven through and the commands the fingers
would have been sent are kept, in the order they were issued.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import List

from coraplex.datastructures.enums import Arms
from coraplex.plans.plan_node import PlanNode
from experiments.tracy_experiments.pick_and_place_action_real import TracyActuators
from semantic_digital_twin.datastructures.definitions import GripperState
from semantic_digital_twin.spatial_types.spatial_types import Quaternion
from semantic_digital_twin.world import World


@dataclass
class EndEffectorFacingAWay:
    """
    An end effector described only by which way it faces, which is all a grasp reads off
    it to work out the poses a reach and a lift are aimed at.
    """

    _world: World
    """
    The world the grasp's poses are worked out in.
    """

    front_facing_orientation: Quaternion = field(
        default_factory=lambda: Quaternion(0, 0, 0, 1)
    )
    """
    Which way the end effector faces, in its own world's root frame.
    """


@dataclass
class FingerCommand:
    """
    One command sent to the fingers.
    """

    arm: Arms
    """
    Which hand it was sent to.
    """

    setpoint: float
    """
    How far the fingers were told to close, as the knuckle's own position.
    """


@dataclass
class FingersThatRecord:
    """
    The Robotiq controller's own interface, keeping each command rather than sending it.
    """

    commands: List[FingerCommand] = field(default_factory=list)
    """
    Every command sent, in the order it was sent.
    """

    def move(self, arm: Arms, state: GripperState) -> None:
        """
        :param arm: Which hand to move.
        :param state: The state to move it to.
        """
        self.commands.append(FingerCommand(arm, float(state is GripperState.CLOSE)))

    def close_to(self, arm: Arms, setpoint: float) -> None:
        """
        :param arm: Which hand to close.
        :param setpoint: How far to close it.
        """
        self.commands.append(FingerCommand(arm, setpoint))


@dataclass
class ActuatorsThatRecord(TracyActuators):
    """
    Tracy's actuators, with the arm's plans recorded rather than performed.

    A member of :class:`~experiments.tracy_experiments.pick_and_place_action_real.
    TracyActuators` rather than a look-alike, since which actions drive a lab is decided
    by the type of the lab itself.
    """

    driven: List[PlanNode] = field(default_factory=list)
    """
    Every plan the arm would have been driven through, in order.
    """

    def perform_and_record(self, plan: PlanNode) -> None:
        """
        Keep the plan instead of performing it.

        :param plan: The plan the arm would have been driven through.
        """
        self.driven.append(plan)

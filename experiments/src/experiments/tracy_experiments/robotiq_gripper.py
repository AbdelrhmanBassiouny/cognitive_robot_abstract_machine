"""
Drive Tracy's Robotiq parallel grippers directly through their
``control_msgs/action/ParallelGripperCommand`` action servers.

Giskard's Tracy interface only subscribes to the gripper joint states and never
publishes a command for the fingers, so a plan's ``MoveGripperMotion`` leaves the
physical gripper where it is and blocks forever waiting for fingers that cannot move.
This bypasses Giskard and talks to the ``robotiq_gripper_controller`` action the real
robot exposes.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum

from typing_extensions import Dict, List

from control_msgs.action import ParallelGripperCommand
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.task import Future
from sensor_msgs.msg import JointState

from coraplex.datastructures.enums import Arms
from semantic_digital_twin.datastructures.definitions import GripperState

logger = logging.getLogger(__name__)

# %% failures


class RobotiqGripperError(Exception):
    """
    Base class for failures while driving a Robotiq gripper action.
    """


@dataclass
class GripperActionServerUnavailable(RobotiqGripperError):
    """
    The gripper action server was not reachable within the wait budget.
    """

    arm: Arms
    """
    Arm whose gripper action server was missing.
    """

    action_name: str
    """
    Fully qualified name of the action that was waited on.
    """

    def __str__(self) -> str:
        return (
            f"Robotiq gripper action server {self.action_name!r} for {self.arm} did "
            f"not become available"
        )


@dataclass
class GripperCommandTimedOut(RobotiqGripperError):
    """
    The gripper action accepted the goal but did not finish in time.
    """

    arm: Arms
    """
    Arm whose gripper command did not finish.
    """

    action_name: str
    """
    Fully qualified name of the action that was waited on.
    """

    def __str__(self) -> str:
        return (
            f"Robotiq gripper command for {self.arm} on {self.action_name!r} timed out"
        )


@dataclass
class GripperCommandRejected(RobotiqGripperError):
    """
    The gripper action server rejected the goal, or the motion stopped without either
    reaching the commanded position or stalling against something.
    """

    arm: Arms
    """
    Arm whose gripper command was not completed.
    """

    reached_goal: bool
    """
    Whether the controller reported the commanded position as reached.
    """

    stalled: bool
    """
    Whether the controller reported the fingers as stalled.
    """

    def __str__(self) -> str:
        return (
            f"Robotiq gripper command for {self.arm} was not completed "
            f"(reached_goal={self.reached_goal}, stalled={self.stalled})"
        )


# %% setpoints


class FingerSetpoint(float, Enum):
    """
    Commanded finger position for a Robotiq parallel gripper, in the controller's own
    units where ``0`` is fully open.
    """

    OPEN = 0.0
    """
    Fully open.
    """

    CLOSED = 0.5
    """
    Fully closed.
    """

    @classmethod
    def for_state(cls, state: GripperState) -> "FingerSetpoint":
        """:return: The finger setpoint that realises ``state``."""
        return _STATE_SETPOINTS[state]


_STATE_SETPOINTS: Dict[GripperState, FingerSetpoint] = {
    GripperState.OPEN: FingerSetpoint.OPEN,
    GripperState.CLOSE: FingerSetpoint.CLOSED,
}
"""
Finger setpoint realising each :class:`GripperState` this controller supports.
"""

_ARM_SIDES: Dict[Arms, str] = {Arms.LEFT: "left", Arms.RIGHT: "right"}
"""
Body-side token in the action name for each single-arm :class:`Arms` member.
"""

GRIPPER_ACTION_TEMPLATE = "/{side}_gripper/robotiq_gripper_controller/gripper_cmd"
"""
Action name of a Robotiq gripper controller, parameterised by body side.
"""


# %% controller


@dataclass
class RobotiqGripperController:
    """
    Opens and closes Tracy's Robotiq grippers over their ``ParallelGripperCommand``
    action servers, blocking until each command finishes.

    ..note:: The node must be spun by an executor (for example a background
        :class:`~rclpy.executors.MultiThreadedExecutor`) while a command is in flight.
    """

    node: Node
    """
    ROS node that owns the action clients.
    """

    server_timeout: float = 10.0
    """
    Seconds to wait for a gripper action server before raising.
    """

    command_timeout: float = 15.0
    """
    Seconds to wait for an accepted gripper command to finish before raising.
    """

    _clients: Dict[Arms, ActionClient] = field(
        default_factory=dict, init=False, repr=False
    )
    """
    Action client per single arm, created on first use.
    """

    def move(self, arm: Arms, state: GripperState) -> None:
        """
        Move the given arm's gripper to the position realising ``state``.

        Stalling against an object counts as done: closing onto something to grasp it
        never reaches the fully closed position.

        :param arm: Arm whose gripper to move; :attr:`Arms.BOTH` moves both.
        :param state: Target gripper state.
        :raises GripperActionServerUnavailable: If a gripper action server is missing.
        :raises GripperCommandTimedOut: If an accepted command does not finish in time.
        :raises GripperCommandRejected: If a command is rejected, or stops without
            reaching the commanded position and without stalling.
        """
        setpoint = FingerSetpoint.for_state(state)
        for single_arm in self._single_arms(arm):
            self._send(single_arm, setpoint)

    def close_to(self, arm: Arms, setpoint: float) -> None:
        """
        Drive the given arm's gripper to a raw finger ``setpoint``.

        Unlike :meth:`move`, the setpoint is used as given rather than taken from the
        two-step :class:`FingerSetpoint`, so a grasp can be sized to the piece it is
        about to hold. As with :meth:`move`, stalling against an object counts as done.

        :param arm: Arm whose gripper to move; :attr:`Arms.BOTH` moves both.
        :param setpoint: Target finger position in the controller's own units, where
            ``0`` is fully open.
        :raises GripperActionServerUnavailable: If a gripper action server is missing.
        :raises GripperCommandTimedOut: If an accepted command does not finish in time.
        :raises GripperCommandRejected: If a command is rejected, or stops without
            reaching the commanded position and without stalling.
        """
        for single_arm in self._single_arms(arm):
            self._send(single_arm, setpoint)

    @staticmethod
    def _single_arms(arm: Arms) -> List[Arms]:
        """:return: The single-arm members ``arm`` stands for."""
        if arm == Arms.BOTH:
            return [Arms.LEFT, Arms.RIGHT]
        return [arm]

    def _client(self, arm: Arms) -> ActionClient:
        """:return: The cached action client for ``arm``, creating it on first use."""
        if arm not in self._clients:
            self._clients[arm] = ActionClient(
                self.node, ParallelGripperCommand, self._action_name(arm)
            )
        return self._clients[arm]

    @staticmethod
    def _action_name(arm: Arms) -> str:
        """:return: The gripper action name for a single arm."""
        return GRIPPER_ACTION_TEMPLATE.format(side=_ARM_SIDES[arm])

    def _send(self, arm: Arms, setpoint: float) -> None:
        """
        Send one finger-position command to a single arm and wait for its result.
        """
        client = self._client(arm)
        action_name = self._action_name(arm)
        if not client.wait_for_server(timeout_sec=self.server_timeout):
            raise GripperActionServerUnavailable(arm, action_name)

        goal = ParallelGripperCommand.Goal()
        goal.command = JointState(position=[float(setpoint)], effort=[0.0])

        goal_handle = self._wait(client.send_goal_async(goal), arm, action_name)
        if not goal_handle.accepted:
            raise GripperCommandRejected(arm, reached_goal=False, stalled=False)

        result = self._wait(goal_handle.get_result_async(), arm, action_name).result
        if not result.reached_goal and not result.stalled:
            raise GripperCommandRejected(
                arm, reached_goal=result.reached_goal, stalled=result.stalled
            )
        if result.stalled and not result.reached_goal:
            logger.info(
                "%s gripper stalled before the commanded position -- grasped an object "
                "or hit a stop.",
                arm,
            )

    def _wait(self, future: Future, arm: Arms, action_name: str) -> object:
        """
        Block until ``future`` completes, letting the spinning executor drive it.

        :raises GripperCommandTimedOut: If :attr:`command_timeout` elapses first.
        """
        deadline = time.monotonic() + self.command_timeout
        while not future.done():
            if time.monotonic() > deadline:
                raise GripperCommandTimedOut(arm, action_name)
            time.sleep(0.02)
        return future.result()

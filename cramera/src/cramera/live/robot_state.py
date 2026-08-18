"""
The running demo's own state, as something the viewer can ask questions about.

Everything here is read off what the bridge already publishes for the viewer's panels,
so asking a question observes the run rather than touching it.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Dict, List, Optional, Tuple

from cramera.knowledge.entity import NamedEntity
from cramera.knowledge.enums import PlanNodeGroup
from cramera.knowledge.presets import Preset
from cramera.knowledge.query_domain import QueryDomain
from cramera.live.bridge import Bridge, PlanNodeEntry, TaskStatusName
from cramera.live.held_objects import HeldObject
from cramera.live.query import LiveQuerySource

# %% what the robot is doing


@dataclass
class RobotAction(NamedEntity):
    """
    One action of the plan the robot is performing, as it stands right now.
    """

    status: str
    """
    The action's execution status, mirroring coraplex's own ``TaskStatus`` names.
    """

    depth: int
    """
    How deeply the action is nested in the plan tree; the root is at zero.
    """

    is_goal: bool = False
    """
    Whether this is the outermost action still running: what the robot is trying to
    achieve at this moment.
    """

    is_current_step: bool = False
    """
    Whether this is the innermost action running: what the robot is doing at this
    moment.
    """

    arm: Optional[str] = None
    """
    The arm the action's designator names, if any.
    """

    target: Optional[str] = None
    """
    The object the action's designator acts on, if any.
    """

    @classmethod
    def of_plan(cls, nodes: List[PlanNodeEntry]) -> List[RobotAction]:
        """
        The actions of one plan snapshot, with the running ones marked.

        :param nodes: The plan tree's entries, in traversal order.
        """
        actions = []
        depths: Dict[str, int] = {}
        for node in nodes:
            depths[node.id] = 0 if node.parent is None else depths[node.parent] + 1
            if node.group is not PlanNodeGroup.ACTION:
                continue
            actions.append(
                cls(
                    name=node.label,
                    status=node.status,
                    depth=depths[node.id],
                    arm=node.arm,
                    target=node.target,
                )
            )
        cls._mark_running(actions)
        return actions

    @staticmethod
    def _mark_running(actions: List[RobotAction]) -> None:
        """
        Mark the goal and the current step among ``actions``.

        A plan is walked parent before child, so the first running action is the
        outermost one and the last is the innermost.

        :param actions: The plan's actions in traversal order, marked in place.
        """
        running = [
            action for action in actions if action.status == TaskStatusName.RUNNING
        ]
        if not running:
            return
        running[0].is_goal = True
        running[-1].is_current_step = True


# %% the questions the panel offers


def actions_in_status(status: TaskStatusName) -> str:
    """
    The query selecting every action of the plan that is in one status.

    :param status: The status the selected actions report.
    """
    return "an(entity(action).where(action.status == %r))" % status.value


ROBOT_STATE_PRESETS: Tuple[Preset, ...] = (
    Preset("what are you holding right now?", "an(entity(held_object))"),
    Preset(
        "what is your current action?",
        "an(entity(action).where(action.is_current_step == True))",
    ),
    Preset(
        "what is your current goal?",
        "an(entity(action).where(action.is_goal == True))",
    ),
    Preset("what have you done so far?", actions_in_status(TaskStatusName.SUCCEEDED)),
    Preset("what has failed?", actions_in_status(TaskStatusName.FAILED)),
    Preset("what is still to come?", actions_in_status(TaskStatusName.CREATED)),
    Preset("every action and its status", "set_of(action.name, action.status)"),
)
"""
The ready-made questions about the running demo, as the panel's buttons.
"""


@dataclass
class RobotStateQuerySource(LiveQuerySource):
    """
    A running demo's robot, as something the viewer can ask questions of.
    """

    bridge: Bridge
    """
    The bridge whose published plan and world state the answers are read from.
    """

    def title(self) -> str:
        """
        What the panel names this source: the robot answering, while one is bound.
        """
        robot = self.bridge.robot
        if robot is None:
            return "the running demo"
        return "%s (live)" % type(robot).__name__

    def domains(self) -> List[QueryDomain]:
        """
        What a question about the running demo may range over: the actions of the plan
        being performed, and the objects the robot is holding.

        Read fresh on every call, so an answer describes the run as it stands now.
        """
        return [
            QueryDomain(
                "action", RobotAction, RobotAction.of_plan(self.bridge.plan_nodes())
            ),
            QueryDomain("held_object", HeldObject, self.bridge.get_held_objects()),
        ]

    def presets(self) -> List[Preset]:
        """
        The ready-made questions the panel offers as buttons.
        """
        return list(ROBOT_STATE_PRESETS)

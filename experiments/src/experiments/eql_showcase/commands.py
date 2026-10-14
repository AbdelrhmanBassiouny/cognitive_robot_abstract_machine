"""
Telling the robot what to do from the viewer, and asking afterwards how it worked out
what was left open.

A command names what is to happen and leaves the rest open: which grasp, where to stand.
The robot resolves those parts while it runs, trying each candidate its query backend
offers against a copy of the world first, and every candidate tried is kept so a
question can ask how a command was resolved.
"""

from __future__ import annotations

import logging
import queue
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

import numpy as np
from typing_extensions import Callable, ContextManager, Dict, List, Optional, Type

from coraplex.datastructures.dataclasses import Context
from krrood.entity_query_language.utils import camel_case_to_words
from coraplex.execution_environment import ExecutionEnvironment
from coraplex.plans.factories import execute_single
from coraplex.plans.failures import PlanFailure
from coraplex.plans.plan import Plan
from coraplex.plans.underspecified import CandidateTrial, UnderspecifiedNode
from coraplex.robot_plans.actions.base import ActionDescription
from coraplex.robot_plans.actions.composite.transporting import TransportAction
from semantic_digital_twin.grasping.grasp_candidates import GraspCandidate
from semantic_digital_twin.robots.robot_parts import AbstractRobotPart, Arm
from semantic_digital_twin.semantic_annotations.mixins import HasRootBody
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world import World

logger = logging.getLogger(__name__)

PUT_BACK = "put the {} back"
"""
What a command to return an object to where it started is called.
"""

APPROACH_DIRECTIONS = {
    (2, -1): "from above",
    (2, 1): "from below",
    (0, 1): "from behind",
    (0, -1): "from the front",
    (1, 1): "from the left",
    (1, -1): "from the right",
}
"""
How a grasp approaches its object, keyed by the axis of the object's own frame the
gripper's approach axis lies along most, and which way along it.
"""


# %% a command and its state


class CommandState(StrEnum):
    """
    Where a command is in being carried out.
    """

    QUEUED = "queued"
    """
    Waiting for the robot to finish what it is doing.
    """

    RUNNING = "running"
    """
    Being carried out.
    """

    DONE = "done"
    """
    Carried out.
    """

    FAILED = "failed"
    """
    Given up on.
    """


@dataclass
class RobotCommand:
    """
    One thing the robot was told to do, and how far it got.
    """

    name: str
    """
    What the command asks, e.g. ``"put the milk back"``.
    """

    timestamp: datetime
    """
    When the command was given.
    """

    state: CommandState = CommandState.QUEUED
    """
    How far the robot got with it.
    """

    failure: Optional[str] = None
    """
    Why the robot gave up on it, if it did.
    """


# %% one step of resolving what a command left open


@dataclass(frozen=True)
class ResolutionStep:
    """
    One candidate the robot considered for a part of a command that was left open, and
    what became of it.
    """

    name: str
    """
    The step's label, e.g. ``"Milk MoveAndPickUpAction candidate 2"``.
    """

    open_part: str
    """
    The kind of action that was left open, e.g. ``"MoveAndPickUpAction"``.
    """

    candidate: int
    """
    Which of the candidates the backend offered this was, counting from one.
    """

    outcome: str
    """
    Whether a trial in a copy of the world rejected it or it was accepted.
    """

    choice: str
    """
    What the candidate chose for the open part, e.g. where to stand and how to grasp.
    """

    timestamp: datetime
    """
    When its trial ended.
    """

    reason: Optional[str] = None
    """
    Why the trial rejected it, or None for an accepted candidate.
    """

    acted_on: Optional[str] = None
    """
    Name of the body the action is about, so an answer naming the step lights it up.
    """

    def related_highlight_ids(self) -> List[str]:
        """
        The body the step's action is about.
        """
        return [self.acted_on] if self.acted_on is not None else []

    @classmethod
    def of_trial(
        cls, node: UnderspecifiedNode, index: int, trial: CandidateTrial
    ) -> ResolutionStep:
        """
        The step one candidate trial of an underspecified node was.

        :param node: The node that left the action open.
        :param index: Which candidate it was, counting from zero.
        :param trial: The candidate and what became of it.
        """
        choice = CandidateChoice(trial.action)
        body = choice.grasped_body()
        open_part = node.designator_type.__name__
        prefix = f"{body.name.name} " if body is not None else ""
        return cls(
            name=f"{prefix}{open_part} candidate {index + 1}",
            open_part=open_part,
            candidate=index + 1,
            outcome=str(trial.outcome),
            choice=choice.describe(),
            timestamp=trial.tried_at,
            reason=(
                f"{type(trial.failure).__name__}: {str(trial.failure).splitlines()[0]}"
                if trial.failure is not None
                else None
            ),
            acted_on=str(body.name) if body is not None else None,
        )


@dataclass(frozen=True)
class CandidateChoice:
    """
    What one candidate action chose for the parts its command left open.
    """

    action: ActionDescription
    """
    The candidate action.
    """

    def values(self) -> List[object]:
        """
        Every parameter value of the action and of the actions it is made of.
        """
        found: List[object] = []
        pending = [self.action]
        while pending:
            current = pending.pop(0)
            if not isinstance(current, ActionDescription):
                found.append(current)
                continue
            pending.extend(current.designator_parameter.values())
        return found

    def grasped_body(self):
        """
        The body the candidate is about: what it grasps, else the first object it names
        that is not a part of the robot, or None for one about no object.
        """
        grasps = [value for value in self.values() if isinstance(value, GraspCandidate)]
        if grasps:
            return grasps[0].graspable.root
        named = [
            value.root
            for value in self.values()
            if isinstance(value, HasRootBody)
            and not isinstance(value, AbstractRobotPart)
        ]
        return named[0] if named else None

    def describe(self) -> str:
        """
        Where the candidate stands and how it grasps, as it is said.
        """
        parts = []
        for value in self.values():
            if isinstance(value, GraspCandidate):
                parts.append(f"grasp {self.approach_of(value.grasp_pose)}")
            elif isinstance(value, Arm):
                parts.append(f"with the {camel_case_to_words(type(value).__name__)}")
            elif isinstance(value, Pose):
                x, y = value.position.to_np()[:2]
                parts.append(f"at ({x:.2f}, {y:.2f})")
        return ", ".join(dict.fromkeys(parts))

    @staticmethod
    def approach_of(grasp_pose: Pose) -> str:
        """
        Which side a grasp approaches its object from.

        :param grasp_pose: The gripper's pose in the object's own frame.
        """
        approach_axis = grasp_pose.rotation_matrix.to_np()[:3, 0]
        axis = int(np.argmax(np.abs(approach_axis)))
        return APPROACH_DIRECTIONS[(axis, int(np.sign(approach_axis[axis])))]


@dataclass
class ResolutionSteps:
    """
    Every candidate considered for every open part of the plans performed so far, read
    afresh each time it is iterated.
    """

    plans: List[Plan] = field(default_factory=list)
    """
    The plans performed so far.
    """

    def __iter__(self) -> Iterator[ResolutionStep]:
        """
        Iterate over the steps in the order their trials ended.
        """
        steps = [
            ResolutionStep.of_trial(node, index, trial)
            for plan in self.plans
            for node in plan.plan_graph.nodes()
            if isinstance(node, UnderspecifiedNode)
            for index, trial in enumerate(node.candidate_trials)
        ]
        return iter(sorted(steps, key=lambda step: step.timestamp))


# %% commanding the robot


@dataclass
class RobotCommander:
    """
    Takes commands from the viewer and has the robot carry them out one after another.
    """

    context: Context
    """
    The context the robot's plans run in, whose gate pauses and resumes it.
    """

    execution_environment: Callable[[], ContextManager]
    """
    Builds the environment a command is performed in.
    """

    observe_plan: Callable[[Plan], None]
    """
    Told about every plan a command becomes, before it is performed.
    """

    homes: Dict[Type[HasRootBody], Pose] = field(default_factory=dict)
    """
    Where each object started out, which putting it back returns it to.
    """

    commands: List[RobotCommand] = field(default_factory=list)
    """
    Every command given so far, in order.
    """

    _waiting: queue.Queue = field(default_factory=queue.Queue, init=False, repr=False)
    """
    The commands not yet started, each with what it asks the robot to do.
    """

    @property
    def world(self) -> World:
        """
        The world the robot acts in.
        """
        return self.context.world

    def remember_homes(self, kinds: List[Type[HasRootBody]]) -> None:
        """
        Remember where objects of the given kinds stand now, as where putting them back
        returns them to.

        :param kinds: The kinds of object to remember.
        """
        for kind in kinds:
            [annotation] = self.world.get_semantic_annotations_by_type(kind)
            self.homes[kind] = annotation.root.global_pose

    # %% the commands the viewer gives

    def put_back(self, kind: Type[HasRootBody]) -> RobotCommand:
        """
        Have the robot return an object to where it started, leaving open how to grasp
        it and where to stand.

        :param kind: The kind of object to put back.
        :return: The command, queued.
        """
        [annotation] = self.world.get_semantic_annotations_by_type(kind)
        transport = TransportAction.from_graspable_by_closest_grasps(
            annotation,
            self.homes[kind],
            self.context.robot.all_arms[0],
            self.context,
        )
        return self.do(transport, PUT_BACK.format(kind.__name__.lower()))

    def do(self, action: object, name: str) -> RobotCommand:
        """
        Queue an action, specified as far as the command says and open beyond that.

        :param action: The action to carry out.
        :param name: What the command is called.
        :return: The command, queued.
        """
        command = RobotCommand(name=name, timestamp=datetime.now())
        self.commands.append(command)
        self._waiting.put((command, action))
        return command

    def pause(self) -> RobotCommand:
        """
        Hold the robot still where it is.

        :return: The command being carried out, or the last one given.
        """
        self.context.execution_gate.pause()
        return self.commands[-1] if self.commands else None

    def resume(self) -> RobotCommand:
        """
        Let the robot carry on from where it was held.

        :return: The command being carried out, or the last one given.
        """
        self.context.execution_gate.resume()
        return self.commands[-1] if self.commands else None

    # %% carrying the commands out

    def serve_forever(self) -> None:
        """
        Carry out every command given, one after another, for as long as the process
        runs.
        """
        while True:
            command, action = self._waiting.get()
            self.carry_out(command, action)

    def carry_out(self, command: RobotCommand, action: object) -> None:
        """
        Carry out one command.

        :param command: The command to carry out.
        :param action: What it asks the robot to do.
        """
        plan = execute_single(action_like=action, context=self.context).plan
        self.observe_plan(plan)
        command.state = CommandState.RUNNING
        # a command the robot gives up on is reported on, not allowed to end the
        # robot's service of every command after it
        try:
            with self.execution_environment():
                plan.perform()
        except PlanFailure as failure:
            command.state = CommandState.FAILED
            command.failure = str(failure)
            logger.warning("gave up on %s: %s", command.name, failure)
            return
        command.state = CommandState.DONE

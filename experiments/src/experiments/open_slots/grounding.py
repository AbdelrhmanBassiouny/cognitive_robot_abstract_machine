"""
The figure's plan, answered against one look at a lab.

What a lab is -- a simulated one or the physical robot -- makes no difference here: a
look stands the board and the pieces in the world the robot plans in, the backends are
asked in the order :mod:`~experiments.open_slots.choice` prefers them, and the plan
:mod:`~experiments.open_slots.plan` writes is handed to them. The answers come back the
same way in both, which is what lets a run on the robot be compared with a run in
simulation slot by slot.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from typing_extensions import List, Self

from coraplex.datastructures.enums import Arms
from coraplex.robot_plans.actions.base import ActionDescription
from coraplex.view_manager import ViewManager
from experiments.montessori.perception.backend import MontessoriPerceptionBackend
from experiments.montessori.perception.scene_publishing import PerceivedScene
from experiments.open_slots.choice import backends_for
from experiments.open_slots.plan import sorting_plan
from krrood.entity_query_language.backends import BackendChoice
from semantic_digital_twin.robots.tracy import Tracy

logger = logging.getLogger(__name__)


@dataclass
class GroundedPlan:
    """
    The figure's plan with every slot it leaves open closed, and a record of which
    backend closed which.
    """

    scene: PerceivedScene
    """
    The board and the pieces as the look found them, stood in the world the robot plans
    in.
    """

    answered_by: BackendChoice
    """
    The backends that answered, which keep which of them answered which slot.
    """

    actions: List[ActionDescription]
    """
    What the plan came to, in the order it runs.
    """

    @classmethod
    def grounded_against(cls, scene: PerceivedScene, arm: Arms, robot: Tracy) -> Self:
        """
        Ground the figure's plan against a scene that has already been looked at.

        :param scene: The scene, once :meth:`~experiments.montessori.perception.
            scene_publishing.PerceivedScene.perceive` has run.
        :param arm: The arm that picks the piece up and carries it.
        :param robot: The robot the plan is for, whose hand the grasp is described for.
        :return: The plan, answered.
        """
        answered_by = backends_for(
            MontessoriPerceptionBackend(source=scene.last_look), scene.world
        )
        plan = sorting_plan(
            scene.board,
            scene.look.pipeline.lid.entity,
            scene.piece_set,
            arm,
            ViewManager.get_end_effector_view(arm, robot),
        )
        return cls(
            scene=scene,
            answered_by=answered_by,
            actions=next(plan.grounded_by(answered_by)),
        )

    @property
    def slots_and_their_backends(self) -> List[str]:
        """
        One line per slot the plan left open, naming the backend that closed it.

        The same lines in any lab, so a run on the robot is compared with a run in
        simulation by reading them against one another.
        """
        return [
            f"{type(answered.backend).__name__} answered {answered.statement}"
            for answered in self.answered_by.answered
        ]

    def report(self) -> None:
        """
        Log which backend answered which slot, and what the plan came to.
        """
        for line in self.slots_and_their_backends:
            logger.info("%s.", line)
        for action in self.actions:
            logger.info("Resolved to %s.", action)

"""
Resolve the framework figure's plan in the simulated lab: every slot it leaves open
closed by the backend that can answer it.

The lab is the pickup demo's own -- Tracy on its table, the board and the loose pieces,
seen through the camera hung on Tracy's ``camera_link``. What runs against it is the
plan as :mod:`~experiments.open_slots.plan` writes it: the piece to pick up is looked
for, how to take hold of it is sampled, and the hole it goes through is concluded by
rules. Nothing here says who supplies any of it.

The plan is resolved rather than performed. What it resolves to is the piece the belief
holds, standing where the look found it, so a reach can be planned against it; what is
missing is a way to carry a resolved ``PickUpAction`` out in this lab, since Giskard's
own closed loop races the physics thread and the actions that do drive the actuators --
:mod:`~experiments.tracy_experiments.pick_and_place_action` -- are separate classes that
read no grasp description.

Usage:
    python3 framework_demo.py [--execution simulated] [--headless]

Needs MuJoCo and Tracy's description, like the pickup demo whose lab it builds;
``--execution`` takes only ``simulated`` today, and is spelled out so a run against the
real lab can be asked for by name once there is one.
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass

from typing_extensions import List

from coraplex.robot_plans.actions.base import ActionDescription
from coraplex.view_manager import ViewManager
from experiments.montessori.perception.backend import MontessoriPerceptionBackend
from experiments.montessori.perception.recorded_setup import lab_board
from experiments.montessori.perception.scene_publishing import PerceivedScene
from experiments.montessori.pieces import SMALLER_PIECES
from experiments.open_slots.choice import backends_for
from experiments.open_slots.plan import sorting_plan
from experiments.tracy_experiments.pickup.pickup_demo_mujoco import (
    PICK_ARM,
    SimulatedLab,
    SimulatedLook,
)
from experiments.tracy_experiments.real_time_simulation import RealTimeSimulation
from krrood.entity_query_language.backends import BackendChoice
from semantic_digital_twin.adapters.multi_sim import RegionAppearance

logger = logging.getLogger(__name__)

EXECUTION_SIMULATED = "simulated"
"""
The one lab this plan can be resolved in today.
"""

# %% resolving the plan in the lab


@dataclass(frozen=True)
class ResolvedPlan:
    """
    What the plan came to, and who answered it.
    """

    actions: List[ActionDescription]
    """
    The grounded actions, in the order the plan runs them.
    """

    answered_by: BackendChoice
    """
    The backends that answered the plan, which keep which of them answered which slot.
    """


def resolved_in_the_simulated_lab(headless: bool) -> ResolvedPlan:
    """
    Look at the simulated lab and ground the figure's plan against what was found.

    :param headless: Whether the simulation runs without a viewer window.
    :return: What the plan came to, and who answered it.
    """
    lab = SimulatedLab.build()
    simulation = RealTimeSimulation(
        world=lab.reality,
        headless=headless,
        paced_to_the_wall_clock=not headless,
        region_appearance=RegionAppearance.HIDDEN,
        followers=[lab.belief],
    )
    lab.camera.drawn_by = simulation.multi_sim
    look = SimulatedLook(
        pipeline=lab.perception_pipeline(SMALLER_PIECES), camera=lab.camera
    )
    with simulation, lab.camera:
        lab.hold_the_parked_pose(simulation)
        scene = PerceivedScene(world=lab.belief, look=look, described_board=lab_board())
        scene.perceive()
        backends = backends_for(
            MontessoriPerceptionBackend(source=scene.last_look), lab.belief
        )
        plan = sorting_plan(
            scene.board,
            look.pipeline.lid.entity,
            PICK_ARM,
            ViewManager.get_end_effector_view(PICK_ARM, lab.believed_robot),
        )
        return ResolvedPlan(
            actions=next(plan.grounded_by(backends)), answered_by=backends
        )


# %% running it


def parse_arguments() -> argparse.Namespace:
    """
    :return: This demo's own command line arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execution",
        choices=[EXECUTION_SIMULATED],
        default=EXECUTION_SIMULATED,
        help="the lab the plan is resolved in",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="run without opening MuJoCo's viewer window, as fast as the machine allows",
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    resolved = resolved_in_the_simulated_lab(arguments.headless)
    for answered in resolved.answered_by.answered:
        logger.info(
            "%s answered %s.", type(answered.backend).__name__, answered.statement
        )
    for action in resolved.actions:
        logger.info("Resolved to %s.", action)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()

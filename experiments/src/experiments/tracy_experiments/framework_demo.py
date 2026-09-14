"""
Run the framework figure's plan in the simulated lab: every slot it leaves open closed
by the backend that can answer it, and then the plan carried out on the robot.

The lab is the pickup demo's own -- Tracy on its table, the board and the loose pieces,
seen through the camera hung on Tracy's ``camera_link``. What runs against it is the
plan as :mod:`~experiments.open_slots.plan` writes it: the piece to pick up is looked
for, which side of it the hand comes at is sampled, and the hole it goes through is
concluded by rules. Nothing here says who supplies any of it.

What the plan resolves to is carried out by the actions that drive this lab's actuators
(:class:`~experiments.tracy_experiments.pick_and_place_action.ActuatorDrivenAction`), so
the arm is driven at the piece the look found, turned the way the grasp was sampled. Two
films are taken of the run: what the robot's own camera saw, and the table from in front
of it.

Usage:
    python -m experiments.tracy_experiments.framework_demo \
        [--film-directory DIRECTORY] [--headless] [--watch]

Needs MuJoCo and Tracy's description, like the pickup demo whose lab it builds.
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from typing_extensions import List

from coraplex.datastructures.dataclasses import Context
from coraplex.plans.factories import sequential
from coraplex.robot_plans.actions.base import ActionDescription
from coraplex.view_manager import ViewManager
from experiments.episodes.trace import FilmBeingTaken
from experiments.montessori.perception.backend import MontessoriPerceptionBackend
from experiments.montessori.perception.recorded_setup import lab_board
from experiments.montessori.perception.scene_publishing import PerceivedScene
from experiments.montessori.pieces import SMALLER_PIECES, KnownPieceSet
from experiments.open_slots.choice import backends_for
from experiments.open_slots.plan import SORTED_PIECE, sorting_plan
from experiments.tracy_experiments.pick_and_place_action import ActuatorDrivenAction
from experiments.tracy_experiments.pickup.pickup_demo_mujoco import (
    CAMERA_NAME,
    FRAMES_PER_SECOND,
    PICK_ARM,
    SimulatedLab,
    SimulatedLook,
    SimulationFilm,
    camera_looking_at,
)
from experiments.tracy_experiments.real_time_simulation import RealTimeSimulation
from semantic_digital_twin.adapters.multi_sim import RegionAppearance
from semantic_digital_twin.adapters.mujoco_video_recording import VideoResolution
from semantic_digital_twin.spatial_types.spatial_types import Point3
from krrood.entity_query_language.backends import BackendChoice

logger = logging.getLogger(__name__)

# %% the camera watching the table from in front of it

FRONT_CAMERA_NAME = "front_camera"
"""
What the camera filming the table from in front of it is called.
"""

FRONT_CAMERA_STANDS_AT = Point3(1.7, 0.12, 1.38)
"""
Where that camera stands, in the reality's root frame: beyond the board, facing back
along the table towards the robot, and high enough over the table top to see the board's
lid rather than only its side.
"""

FRONT_CAMERA_LOOKS_AT = Point3(0.7, 0.12, 0.95)
"""
What it looks at: the stretch of table top between the loose pieces and the board, which
is where everything the plan does happens.
"""

VIDEO_RESOLUTION = VideoResolution(width=960, height=544)
"""
The size of both films: a film is watched rather than measured, so the robot's own
camera is filmed at half the width of the picture it takes.

Both sides are a multiple of sixteen, which is the block size the codec encodes without
resizing the frames first.
"""

SETTLING_TIME = 1.0
"""
Seconds of simulated time the run goes on for after the plan has finished, so the piece
is filmed coming to rest.
"""


class DemoFilm(StrEnum):
    """
    What the run leaves behind, by the file each film is written to.
    """

    FROM_THE_FRONT = "table_from_the_front.mp4"
    ROBOT_CAMERA = "robot_camera.mp4"


# %% the run


@dataclass
class FrameworkDemo:
    """
    The figure's plan, resolved against a look at the simulated lab and then carried out
    there, filmed from in front of the table and through the robot's own camera.
    """

    films_directory: Path
    """
    Where the two films are written.
    """

    headless: bool = True
    """
    Whether the simulation runs without a viewer window.
    """

    paced_to_the_wall_clock: bool = False
    """
    Whether the motion runs at life speed, for watching, or as fast as it can.
    """

    pieces: KnownPieceSet = SMALLER_PIECES
    """
    The set of loose pieces on the table: what the lab stands, what the look is fitted
    with, and what says the colour the piece sorted wears.
    """

    lab: SimulatedLab = field(init=False)
    """
    The two worlds the run is performed in, once :meth:`perform` has built them.
    """

    resolved: List[ActionDescription] = field(init=False)
    """
    What the plan came to, in the order it runs, once :meth:`perform` has resolved it.
    """

    answered_by: BackendChoice = field(init=False)
    """
    The backends that answered the plan, which keep which of them answered which slot.
    """

    carried_out: List[ActionDescription] = field(init=False)
    """
    The actions that drove the actuators through the resolved plan, once :meth:`perform`
    has run.
    """

    films: List[SimulationFilm] = field(init=False)
    """
    The films taken of the run, once :meth:`perform` has run.
    """

    def perform(self) -> None:
        """
        Look at the lab, ground the figure's plan against what was found, and drive the
        robot through it, filming all of it.
        """
        self.lab = SimulatedLab.build(self.pieces)
        camera_looking_at(
            self.lab.reality,
            FRONT_CAMERA_NAME,
            FRONT_CAMERA_STANDS_AT,
            FRONT_CAMERA_LOOKS_AT,
            VIDEO_RESOLUTION,
        )
        simulation = RealTimeSimulation(
            world=self.lab.reality,
            headless=self.headless,
            paced_to_the_wall_clock=self.paced_to_the_wall_clock,
            region_appearance=RegionAppearance.HIDDEN,
            followers=[self.lab.belief],
        )
        self.films = [
            self._film(simulation, camera_name, film)
            for camera_name, film in (
                (FRONT_CAMERA_NAME, DemoFilm.FROM_THE_FRONT),
                (CAMERA_NAME, DemoFilm.ROBOT_CAMERA),
            )
        ]
        simulation.observers.extend(self.films)
        self.lab.camera.drawn_by = simulation.multi_sim
        look = SimulatedLook(
            pipeline=self.lab.perception_pipeline(self.pieces),
            camera=self.lab.camera,
        )
        with simulation, self.lab.camera:
            self.lab.hold_the_parked_pose(simulation)
            scene = PerceivedScene(
                world=self.lab.belief, look=look, described_board=lab_board()
            )
            scene.perceive()
            self.answered_by = backends_for(
                MontessoriPerceptionBackend(source=scene.last_look), self.lab.belief
            )
            plan = sorting_plan(
                scene.board,
                look.pipeline.lid.entity,
                self.pieces,
                PICK_ARM,
                ViewManager.get_end_effector_view(PICK_ARM, self.lab.believed_robot),
            )
            self.resolved = next(plan.grounded_by(self.answered_by))
            self._carry_out(simulation)
            simulation.advance(SETTLING_TIME)
            for film in self.films:
                film.close()

    def _film(
        self, simulation: RealTimeSimulation, camera_name: str, film: DemoFilm
    ) -> SimulationFilm:
        """
        :param simulation: The simulation to film.
        :param camera_name: The camera to film through.
        :param film: Which of the run's films this is.
        :return: The film, writing into this run's own directory.
        """
        return SimulationFilm(
            simulation,
            camera_name,
            VIDEO_RESOLUTION,
            FilmBeingTaken(
                path=self.films_directory / film,
                frames_per_second=FRAMES_PER_SECOND,
            ),
            clock=lambda: simulation.simulated_time,
        )

    def _carry_out(self, simulation: RealTimeSimulation) -> None:
        """
        Drive the robot through the resolved plan, each action carried out by the one
        that commands this lab's actuators.

        :param simulation: The running simulation whose actuators are driven.
        """
        context = Context(
            self.lab.belief, self.lab.believed_robot, evaluate_conditions=False
        )
        self.carried_out = ActuatorDrivenAction.performing(
            self.resolved, simulation, self.lab.actuators
        )
        sequential(self.carried_out, context).plan.perform()

    @property
    def sorted_piece_is_through_its_hole(self) -> float:
        """
        How much of the piece the plan sorted stands in the space under its own hole:
        one once it has gone through, zero while it still rests on the lid.
        """
        return self.lab.containment_in_its_hole(SORTED_PIECE)


# %% running it


def parse_arguments() -> argparse.Namespace:
    """
    :return: This demo's own command line arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--film-directory",
        type=Path,
        default=Path.cwd(),
        help="where the run's two films are written",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="run without opening MuJoCo's viewer window",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="run the motion at life speed rather than as fast as the machine allows",
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    arguments.film_directory.mkdir(parents=True, exist_ok=True)
    demo = FrameworkDemo(
        films_directory=arguments.film_directory,
        headless=arguments.headless,
        paced_to_the_wall_clock=arguments.watch,
    )
    demo.perform()
    for answered in demo.answered_by.answered:
        logger.info(
            "%s answered %s.", type(answered.backend).__name__, answered.statement
        )
    for action in demo.resolved:
        logger.info("Resolved to %s.", action)
    for film in demo.films:
        logger.info("Filmed %s.", film.film.path)
    logger.info(
        "%s of the piece ended up through its hole.",
        f"{demo.sorted_piece_is_through_its_hole:.0%}",
    )


if __name__ == "__main__":
    # A package imported along the way configures the root logger for itself, and leaves
    # it at its own level, so the run's own report has to take it over to be seen.
    logging.basicConfig(level=logging.INFO, format="%(message)s", force=True)
    main()

"""
Tracy sorts the Montessori pieces its camera saw into the holes cut for them, and the
cramera viewer asks it how it worked out everything the plan left open.

Run it through the viewer's demo wrapper, then open ``http://localhost:8711``::

    cramera-live experiments/src/experiments/eql_showcase/montessori_demo.py

A capture taken off Tracy's real camera is looked at by the perception pipeline and
committed into Tracy's twin, so the robot works on the pieces and holes it saw. The
sorting plan names only what is to happen: each piece is picked up and put into a hole
of its shape. Which arm, which grasp and which hole are left open; the query backend
offers candidates for each, a trial in a copy of the world rejects the ones that fail,
and every candidate considered can be asked about while the robot works or after.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass, field

from typing_extensions import Dict, List, Type

from coraplex.datastructures.dataclasses import Context
from coraplex.plans.factories import sequential
from coraplex.plans.plan_node import PlanNode
from coraplex.robot_plans.actions.core.pick_up import PickUpAction
from coraplex.robot_plans.actions.core.placing import PlaceAction
from coraplex.robot_plans.actions.core.robot_body import ParkArmsAction
from cramera.paths import data_directory
from krrood.entity_query_language.factories import a, variable
from segmind.detectors.agent_event_detector_nodes import GraspDetector
from segmind.detectors.coarse_event_detector_nodes import (
    PickUpDetector,
    PlacingDetector,
)
from segmind.event_segmentation import Segmind
from semantic_digital_twin.grasping.grasp_candidates import GraspCandidate
from semantic_digital_twin.robots.robot_parts import Arm
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world import World

from experiments.eql_showcase.demo import ShowcasedDemonstration
from experiments.eql_showcase.episodic_memory import RunDatabase
from experiments.eql_showcase.perceived_twin import PerceivedTwin, SeenHole, SeenPiece
from experiments.eql_showcase.perception_demo import PerceptionShowcase
from experiments.eql_showcase.showcase import QUESTIONS_FILE, ShowcaseQuestions

MONTESSORI_QUESTIONS_FILE = QUESTIONS_FILE.with_name("montessori_questions.yaml")
"""
The file the Montessori showcase's questions are read from.
"""

SORTING_LABEL = "montessori sorting"
"""
What a run of the sorting demonstration is called among the finished runs.
"""

DEFAULT_CAPTURE = "stuck_cube_in_hole"
"""
The capture the robot looks at unless told otherwise.
"""

RELEASE_CLEARANCE = 0.003
"""
How far above the lid a piece is released over its hole, in metres.
"""

# %% the sorting plan


@dataclass
class MontessoriSorting:
    """
    Builds plans that put the pieces the camera saw into the holes cut for them, leaving
    the arm, the grasp and the hole open.
    """

    twin: PerceivedTwin
    """
    The twin holding what the camera saw.
    """

    robot: Tracy
    """
    The robot doing the sorting.
    """

    homes: Dict[SeenPiece, Pose] = field(default_factory=dict)
    """
    Where each piece lay when the camera saw it, which taking it out returns it to.
    """

    def __post_init__(self) -> None:
        self.homes = {
            piece: piece.root.global_pose
            for piece in self.twin.world.get_semantic_annotations_by_type(SeenPiece)
        }

    def pieces(self) -> List[SeenPiece]:
        """
        The pieces the camera saw that a hole of their shape was seen for.
        """
        return [
            piece
            for piece in self.twin.world.get_semantic_annotations_by_type(SeenPiece)
            if self.holes_for(piece)
        ]

    def holes_for(self, piece: SeenPiece) -> List[SeenHole]:
        """
        The holes seen that are cut for the piece's kind.

        :param piece: The piece to find holes for.
        """
        return [hole for hole in self.twin.holes if hole.kind is piece.kind]

    def sort_all(self) -> PlanNode:
        """
        Put every piece that has a hole of its shape into one.
        """
        steps: List[object] = [ParkArmsAction(self.robot.all_arms)]
        for piece in self.pieces():
            steps.extend(self._insertion_steps(piece))
        return sequential(steps)

    def insert(self, kind: Type) -> PlanNode:
        """
        Put the first seen piece of a kind into a hole of its shape.

        :param kind: The kind of piece to insert.
        """
        [piece, *_] = [piece for piece in self.pieces() if piece.kind is kind]
        return sequential(
            [ParkArmsAction(self.robot.all_arms), *self._insertion_steps(piece)]
        )

    def take_out(self, kind: Type) -> PlanNode:
        """
        Take the first seen piece of a kind back to where the camera saw it, leaving
        open which arm and which grasp; placing it is resolved only once it is held.

        :param kind: The kind of piece to take out.
        """
        [piece, *_] = [piece for piece in self.pieces() if piece.kind is kind]
        return sequential(
            [
                ParkArmsAction(self.robot.all_arms),
                self._pick_up(piece),
                a(PlaceAction)(
                    object_designator=piece,
                    target_location=variable(Pose, domain=[self.homes[piece]]),
                ),
                ParkArmsAction(self.robot.all_arms),
            ]
        )

    def _pick_up(self, piece: SeenPiece) -> object:
        """
        Pick a piece up, leaving open which arm and which grasp.

        :param piece: The piece to pick up.
        """
        return a(PickUpAction)(
            grasp=variable(GraspCandidate, domain=piece.grasp_candidates()),
            arm=variable(Arm, domain=self.robot.all_arms),
        )

    def _insertion_steps(self, piece: SeenPiece) -> List[object]:
        """
        Pick a piece up and release it over a hole of its shape, leaving open which arm,
        which grasp and which hole.

        :param piece: The piece to insert.
        """
        return [
            self._pick_up(piece),
            a(PlaceAction)(
                object_designator=piece,
                target_location=variable(Pose, domain=self.release_poses(piece)),
            ),
            ParkArmsAction(self.robot.all_arms),
        ]

    def release_poses(self, piece: SeenPiece) -> List[Pose]:
        """
        Where the piece can be released to rest over each hole of its shape.

        :param piece: The piece to release.
        """
        [box] = piece.root.collision.shapes
        return [
            Pose.from_xyz_rpy(
                *hole.region.global_pose.position.to_np()[:2],
                hole.lid_height + box.scale.z / 2 + RELEASE_CLEARANCE,
                reference_frame=self.twin.world.root,
            )
            for hole in self.holes_for(piece)
        ]


# %% the demonstration


@dataclass(kw_only=True)
class TracyMontessoriDemonstration(ShowcasedDemonstration):
    """
    Tracy looks at a real capture of the Montessori board and sorts the pieces it saw
    into their holes, with the EQL showcase listening in.
    """

    used_robot: Type = Tracy
    """
    The robot doing the sorting.
    """

    capture_name: str = DEFAULT_CAPTURE
    """
    The capture taken off the real camera that the robot looks at.
    """

    look: PerceptionShowcase = field(init=False)
    """
    What looks at the capture and holds the twin it is committed into.
    """

    sorting: MontessoriSorting = field(init=False)
    """
    What builds the sorting plans.
    """

    def build_simulated_world(self) -> World:
        self.look = PerceptionShowcase(bridge=None)
        self.look.commit(self.capture_name)
        return self.look.twin.world

    def is_scene_populated(self, world: World) -> bool:
        return True

    def populate_scene(self, world: World) -> None:
        pass

    def build_context(self, world: World) -> Context:
        [robot] = world.get_semantic_annotations_by_type(Tracy)
        self.sorting = MontessoriSorting(twin=self.look.twin, robot=robot)
        self.extra_names[SORTING_NAME] = self.sorting
        self.extra_names.update(PerceptionShowcase.piece_kinds())
        return Context(
            world,
            robot,
            ros_node=self.ros_node,
            sampling_seed=0,
            _debug=self.debug,
        )

    def build_plan(self, context: Context) -> PlanNode:
        built = sequential([self.sorting.sort_all()], context=context).plan
        self.showcase.observe_plan(built)
        return built

    def segment_events(self, world: World) -> AbstractContextManager:
        segmentation = Segmind.create_for_semantic_annotation_types(
            world,
            (SeenPiece,),
            detector_types=(PickUpDetector, PlacingDetector, GraspDetector),
        )
        self.showcase.observe_events(segmentation.event_logger)
        self._offer_showcase()
        return segmentation


SORTING_NAME = "montessori"
"""
The name the sorting plans are built through in a command, e.g.
``robot.do(montessori.insert(CubeShape), "insert the cube")``.
"""


def main(capture_name: str = DEFAULT_CAPTURE, takes_commands: bool = True) -> None:
    """
    Have Tracy sort what it saw in a capture, then let the viewer command it.

    :param capture_name: The capture the robot looks at.
    :param takes_commands: Whether the robot takes commands once the sorting is done.
    """
    TracyMontessoriDemonstration(
        capture_name=capture_name,
        run_label=SORTING_LABEL,
        run_database=RunDatabase(data_directory() / "eql_showcase_runs.sqlite"),
        questions=ShowcaseQuestions.from_file(MONTESSORI_QUESTIONS_FILE),
        takes_commands=takes_commands,
        collision_avoidance=False,
    ).run()


if __name__ == "__main__":
    main()

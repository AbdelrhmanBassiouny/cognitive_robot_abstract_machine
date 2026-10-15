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

from typing_extensions import Dict, Iterator, List, Type

from coraplex.datastructures.dataclasses import Context
from coraplex.plans.factories import sequential
from coraplex.plans.plan_node import PlanNode
from coraplex.visualization import PluginVisualization
from cramera.live.visualization import LiveVisualization
from coraplex.querying.predicates import GripperHolds
from coraplex.robot_plans.actions.core.pick_up import PickUpAction
from coraplex.robot_plans.actions.core.placing import PlaceAction
from coraplex.robot_plans.actions.core.robot_body import ParkArmsAction
from cramera.paths import data_directory
from experiments.montessori.semantics import MontessoriShape
from krrood.entity_query_language.factories import a, an, variable
from segmind.detectors.agent_event_detector_nodes import GraspDetector
from segmind.detectors.coarse_event_detector_nodes import (
    PickUpDetector,
    PlacingDetector,
)
from segmind.event_segmentation import Segmind
from semantic_digital_twin.grasping.grasp_candidates import GraspCandidate
from semantic_digital_twin.reasoning.predicates import InsideRegion, SupportedBy
from semantic_digital_twin.robots.robot_parts import Arm
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world import World

from experiments.eql_showcase.demo import ShowcasedDemonstration
from experiments.eql_showcase.episodic_memory import RunDatabase
from experiments.eql_showcase.falling import FallIntoHolesNode
from experiments.eql_showcase.open_slots import (
    AnsweredWhenAsked,
    Faculty,
    SlotAnswer,
    GraspSamplingBackend,
    HoleRulesBackend,
    Insertion,
    OpenSlotAnswerer,
    PerceptionBackend,
    SideGrasp,
    WorkingMemoryBackend,
)
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
    open which piece, whether it still rests on the table, which side to take it from,
    which arm and which hole -- each answered, when its step comes, by the backend that
    declares it can.
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

    answerer: OpenSlotAnswerer = field(init=False)
    """
    What answers the parts the plans leave open, and keeps what each backend answered.
    """

    def __post_init__(self) -> None:
        self.homes = {
            piece: piece.root.global_pose
            for piece in self.twin.world.get_semantic_annotations_by_type(SeenPiece)
        }
        self.answerer = OpenSlotAnswerer(
            backends=[
                PerceptionBackend(twin=self.twin),
                WorkingMemoryBackend(world=self.twin.world),
                HoleRulesBackend(
                    twin=self.twin, rule_order=MontessoriShape.__subclasses__()
                ),
                GraspSamplingBackend(),
            ]
        )

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

    def kinds_to_sort(self) -> List[Type[MontessoriShape]]:
        """
        The kinds of piece seen that a hole of their shape was seen for, each once.
        """
        return list(dict.fromkeys(piece.kind for piece in self.pieces()))

    def sort_all(self) -> PlanNode:
        """
        Put a piece of every kind that has a hole of its shape into one.
        """
        steps: List[object] = [ParkArmsAction(self.robot.all_arms)]
        for kind in self.kinds_to_sort():
            steps.extend(self._insertion_steps(kind))
        return sequential(steps)

    def insert(self, kind: Type) -> PlanNode:
        """
        Put a seen piece of a kind into a hole of its shape.

        :param kind: The kind of piece to insert.
        """
        return sequential(
            [ParkArmsAction(self.robot.all_arms), *self._insertion_steps(kind)]
        )

    def take_out(self, kind: Type) -> PlanNode:
        """
        Take the first seen piece of a kind back to where the camera saw it, leaving
        open which arm and which grasp; placing it is resolved only once it is held.

        :param kind: The kind of piece to take out.
        """
        [piece, *_] = [piece for piece in self.pieces() if piece.kind is kind]
        step = f"take the {self.twin.kind_of(kind)} back out"
        return sequential(
            [
                ParkArmsAction(self.robot.all_arms),
                self._pick_up(kind, step, still_on_the_table=False),
                a(PlaceAction)(
                    object_designator=piece,
                    target_location=variable(Pose, domain=[self.homes[piece]]),
                ),
                ParkArmsAction(self.robot.all_arms),
            ]
        )

    def _insertion_steps(self, kind: Type[MontessoriShape]) -> List[object]:
        """
        Pick a piece of a kind up off the table and release it over the hole the rules
        say it goes into, where it falls in.

        :param kind: The kind of piece to insert.
        """
        step = f"put the {self.twin.kind_of(kind)} into its hole"
        held: List[SeenPiece] = []

        def piece_held() -> Iterator[SeenPiece]:
            # asked once, when the place is resolved; its target is released over the
            # hole of the very piece answered here
            if not held:
                held.extend(self._held(step))
            return iter(held)

        return [
            self._pick_up(kind, step, still_on_the_table=True),
            a(PlaceAction)(
                object_designator=variable(
                    SeenPiece, domain=AnsweredWhenAsked(piece_held)
                ),
                target_location=variable(
                    Pose,
                    domain=AnsweredWhenAsked(
                        lambda: self._over_its_hole(step, piece_held())
                    ),
                ),
            ),
            FallIntoHolesNode(twin=self.twin),
            ParkArmsAction(self.robot.all_arms),
        ]

    def _pick_up(
        self, kind: Type[MontessoriShape], step: str, still_on_the_table: bool
    ) -> object:
        """
        Pick up a piece of a kind, leaving open which piece, which side to take it from
        and which arm.

        :param kind: The kind of piece to pick up.
        :param step: The step the pick-up belongs to, as said to a person.
        :param still_on_the_table: Whether the piece must still rest on the table.
        """
        return a(PickUpAction)(
            grasp=variable(
                GraspCandidate,
                domain=AnsweredWhenAsked(
                    lambda: self._grasps(kind, step, still_on_the_table)
                ),
            ),
            arm=variable(
                Arm,
                domain=AnsweredWhenAsked(
                    lambda: iter(self.answerer.answer(step, "which arm", an(Arm)))
                ),
            ),
        )

    def _grasps(
        self, kind: Type[MontessoriShape], step: str, still_on_the_table: bool
    ) -> Iterator[GraspCandidate]:
        """
        The grasps on a piece of a kind, asking the camera which pieces there are, the
        twin which of them still rest on the table, and the grasp model which side to
        take each from.

        :param kind: The kind of piece.
        :param step: The step the grasp belongs to, as said to a person.
        :param still_on_the_table: Whether the piece must still rest on the table.
        """
        pieces = self.answerer.answer(step, "which piece", a(SeenPiece)(kind=kind))
        if still_on_the_table:
            resting = a(SeenPiece)(kind=kind).from_(pieces)
            resting.where(SupportedBy(resting.root, self.twin.table))
            pieces = self.answerer.answer(step, "does it rest on the table", resting)
        for piece in pieces:
            sides = self.answerer.answer(
                step, "which side to take it from", a(SideGrasp)(side=..., piece=piece)
            )
            for side in sides:
                yield side.candidate_on(piece)

    def _held(self, step: str) -> Iterator[SeenPiece]:
        """
        The piece the robot holds, as the twin says.

        :param step: The step it is asked in, as said to a person.
        """
        held = a(SeenPiece)()
        arm = variable(Arm, domain=self.robot.all_arms)
        held.where(GripperHolds(arm.end_effector, held.root))
        yield from self.answerer.answer(step, "which piece is held", held)

    def _over_its_hole(self, step: str, pieces: Iterator[SeenPiece]) -> Iterator[Pose]:
        """
        Where a held piece is released, over each hole the rules say it goes into.

        :param step: The step it is asked in, as said to a person.
        :param pieces: The pieces held.
        """
        for piece in pieces:
            insertions = self.answerer.answer(
                step, "which hole", an(Insertion)(piece=piece, hole=...)
            )
            for insertion in insertions:
                yield self.release_pose(piece, insertion.hole)

    def release_poses(self, piece: SeenPiece) -> List[Pose]:
        """
        Where the piece can be released to rest over each hole of its shape.

        :param piece: The piece to release.
        """
        return [self.release_pose(piece, hole) for hole in self.holes_for(piece)]

    def release_pose(self, piece: SeenPiece, hole: SeenHole) -> Pose:
        """
        Where the piece is released to rest just over a hole.

        :param piece: The piece to release.
        :param hole: The hole it is released over.
        """
        [box] = piece.root.collision.shapes
        return Pose.from_xyz_rpy(
            *hole.region.global_pose.position.to_np()[:2],
            hole.lid_height + box.scale.z / 2 + RELEASE_CLEARANCE,
            reference_frame=self.twin.world.root,
        )


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

    sorting: MontessoriSorting | None = field(init=False, default=None)
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
        # a command is built against a context of its own, but its open parts are
        # answered by the same backends, and kept with the sorting's answers
        if self.sorting is None:
            self.sorting = MontessoriSorting(twin=self.look.twin, robot=robot)
            self.sorting.answerer.on_answer = self._publish_slot_answers
            self._publish_slot_answers(self.sorting.answerer)
        self.extra_names[SORTING_NAME] = self.sorting
        self.extra_names[ANSWERER_NAME] = self.sorting.answerer
        self.extra_names.update(
            {kind.__name__: kind for kind in (SlotAnswer, Faculty, InsideRegion)}
        )
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

    def _publish_slot_answers(self, answerer: OpenSlotAnswerer) -> None:
        """
        Show the viewer how the parts the plan left open were answered so far, if this
        run is shown in one.

        :param answerer: What answered them.
        """
        if not isinstance(self.visualization, PluginVisualization):
            return
        if not isinstance(self.visualization.provider, LiveVisualization):
            return
        self.visualization.provider.bridge.publish_slot_answers(answerer.to_payload())

    def segment_events(self, world: World) -> AbstractContextManager:
        segmentation = Segmind.create_for_semantic_annotation_types(
            world,
            (SeenPiece,),
            detector_types=(PickUpDetector, PlacingDetector, GraspDetector),
        )
        self.showcase.observe_events(segmentation.event_logger)
        self._offer_showcase()
        return segmentation


ANSWERER_NAME = "backends"
"""
The name what answered the plans' open parts goes by in a question, e.g.
``backends.answered``.
"""

SORTING_NAME = "montessori"
"""
The name the sorting plans are built through in a command, e.g.
``robot.do(montessori.insert(CubeShape), "insert the cube")``.
"""


def main(
    capture_name: str = DEFAULT_CAPTURE,
    takes_commands: bool = True,
    real_time_factor: float = 1.0,
) -> None:
    """
    Have Tracy sort what it saw in a capture, then let the viewer command it.

    :param capture_name: The capture the robot looks at.
    :param takes_commands: Whether the robot takes commands once the sorting is done.
    :param real_time_factor: How much faster than the clock Tracy moves.
    """
    TracyMontessoriDemonstration(
        capture_name=capture_name,
        run_label=SORTING_LABEL,
        run_database=RunDatabase(data_directory() / "eql_showcase_runs.sqlite"),
        questions=ShowcaseQuestions.from_file(MONTESSORI_QUESTIONS_FILE),
        takes_commands=takes_commands,
        collision_avoidance=False,
        real_time_factor=real_time_factor,
    ).run()


if __name__ == "__main__":
    main()

"""
Tracy sorts the Montessori pieces its camera saw into the holes cut for them, and the
cramera viewer shows how every part the plan left open was resolved before it moved.

Run it through the viewer's demo wrapper, then open ``http://localhost:8711``::

    cramera-live experiments/src/experiments/eql_showcase/montessori_demo.py

A capture taken off Tracy's real camera is looked at by the perception pipeline and
committed into Tracy's twin, so the robot works on the pieces and holes it saw. The
sorting plan names only what is to happen: a piece of a kind, still on the table, is put
into a hole of its shape. Which piece, which side to take it from, which arm and which
hole are left open; before the robot moves, each is answered by the backend that
declares it can -- perception, working memory, ripple-down rules or a probabilistic
model -- and the viewer shows each backend's reasoning. Any statement, or a whole
sorting plan, can be resolved the same way from the viewer, and a resolved plan carried
out.
"""

from __future__ import annotations

import time
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass, field
from enum import StrEnum

from typing_extensions import Any, Callable, Dict, List, Type

from coraplex.datastructures.dataclasses import Context
from coraplex.plans.factories import sequential
from coraplex.plans.plan_node import PlanNode
from coraplex.querying.predicates import GripperIsFree
from coraplex.robot_plans.actions.base import ActionDescription
from coraplex.robot_plans.actions.core.pick_up import PickUpAction
from coraplex.robot_plans.actions.core.robot_body import ParkArmsAction
from coraplex.visualization import PluginVisualization
from cramera.live.visualization import LiveVisualization
from cramera.paths import data_directory
from experiments.montessori.perception.overlay import RectifiedView
from experiments.montessori.semantics import MontessoriShape
from krrood.entity_query_language.factories import a, an, entity, exists, the, variable
from krrood.entity_query_language.query.query import Query
from krrood.entity_query_language.query.match import Match
from segmind.detectors.agent_event_detector_nodes import GraspDetector
from segmind.detectors.coarse_event_detector_nodes import (
    PickUpDetector,
    PlacingDetector,
)
from segmind.event_segmentation import Segmind
from semantic_digital_twin.datastructures.definitions import StaticJointState
from semantic_digital_twin.reasoning.predicates import InsideRegion, SupportedBy
from semantic_digital_twin.robots.robot_parts import Arm
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world import World

from experiments.eql_showcase.demo import ShowcasedDemonstration
from experiments.eql_showcase.episodic_memory import RunDatabase
from experiments.eql_showcase.insertion import InsertAction
from experiments.eql_showcase.open_slots import (
    CodeLine,
    Faculty,
    GraspSamplingBackend,
    GraspSide,
    HoleRulesBackend,
    Insertion,
    OpenSlotAnswerer,
    PerceptionBackend,
    PlanResolution,
    SideGrasp,
    SlotAnswer,
    SlotMarker,
    WorkingMemoryBackend,
)
from experiments.eql_showcase.perceived_twin import PerceivedTwin, SeenHole, SeenPiece
from experiments.eql_showcase.perception_demo import PerceptionShowcase
from experiments.eql_showcase.query_steps import (
    EnclosingStatement,
    Phase,
    QueryStepper,
    StepSituation,
)
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

# %% the sorting action


class SortingPart(StrEnum):
    """
    The parts a sorting plan leaves open, by the id each goes by in the plan's lines.
    """

    PIECE = "piece"
    PIECE_ON_THE_TABLE = "piece-where"
    SIDE = "side"
    ARM = "arm"
    HOLE = "hole"


class QuestionName(StrEnum):
    """
    The names the demonstration's own objects go by in a question or command.
    """

    ANSWERER = "backends"
    """
    What answered the plans' open parts, e.g. ``backends.answered``.
    """

    SORTING = "montessori"
    """
    What resolves the sorting plans, e.g.
    ``robot.do(montessori.insert(CubeShape), "insert the cube")``.
    """

    RESOLVE = "resolve"
    """
    Resolves a statement or plan, e.g. ``resolve(a(SeenPiece)(kind=CubeShape))``.
    """

    STEPS = "steps"
    """
    The queries Tracy asked, e.g. ``steps.steps``.
    """


class TracyActivity(StrEnum):
    """
    What Tracy is said to be doing when it asks a query outside any plan.
    """

    SETTING_UP = "setting up the twin"
    """
    It builds the twin it acts in, before any plan.
    """

    PLANNING = "planning what to sort"
    """
    It neither resolves a plan nor carries one out.
    """


@dataclass
class SortPieceAction(ActionDescription):
    """
    Puts a piece into a hole: the hand comes down onto it from above, closing from the
    given side, lifts it, lowers it just over the hole and lets go.
    """

    piece: SeenPiece
    """
    The piece to sort.
    """

    side: GraspSide
    """
    The side the hand closes on the piece from.
    """

    arm: Arm
    """
    The arm that does it.
    """

    hole: SeenHole
    """
    The hole the piece goes into.
    """

    release_clearance: float = field(default=0.003, kw_only=True)
    """
    How far above the lid the piece is let go, in metres.
    """

    @property
    def _action_plan(self) -> PlanNode:
        return sequential(
            [
                PickUpAction(
                    grasp=SideGrasp(self.side).candidate_on(self.piece), arm=self.arm
                ),
                InsertAction(
                    object_designator=self.piece,
                    target_location=self.release_pose(),
                    hole=self.hole,
                ),
                ParkArmsAction(self.robot.all_arms),
            ],
            self.context,
        )

    def release_pose(self) -> Pose:
        """
        :return: Where the piece is let go, its bottom just over the hole's lid.
        """
        [box] = self.piece.root.collision.shapes
        over_the_hole = self.hole.region.global_pose
        return Pose.from_xyz_rpy(
            *over_the_hole.position.to_np()[:2],
            self.hole.lid_height + box.scale.z / 2 + self.release_clearance,
            reference_frame=over_the_hole.reference_frame,
        )


# %% resolving the sorting before the robot moves


@dataclass
class MontessoriSorting:
    """
    Resolves plans that put the pieces the camera saw into the holes cut for them: which
    piece, which side to take it from, which arm and which hole are answered by the
    backends before the robot moves.
    """

    twin: PerceivedTwin
    """
    The twin holding what the camera saw.
    """

    robot: Tracy
    """
    The robot doing the sorting.
    """

    answerer: OpenSlotAnswerer = field(init=False)
    """
    What answers the parts the plans leave open, and keeps every resolution.
    """

    perception_view: RectifiedView | None = None
    """
    The camera's top-down view of the table in the last look, or None.
    """

    on_resolved: Callable[[PlanResolution], None] | None = None
    """
    Called once a plan or statement is resolved.
    """

    observing: Callable[[], AbstractContextManager] = nullcontext
    """
    Opens the block whose queries are observed while a plan or statement is resolved.
    """

    def __post_init__(self) -> None:
        self.answerer = OpenSlotAnswerer(
            backends=[
                PerceptionBackend(twin=self.twin, view=self.perception_view),
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
        return self.pieces_with_their_hole().tolist()

    def kinds_to_sort(self) -> List[Type[MontessoriShape]]:
        """
        The kinds of piece seen that a hole of their shape was seen for, each once.
        """
        piece = variable(SeenPiece, self.twin.world.semantic_annotations)
        hole = variable(SeenHole, self.twin.holes)
        return (
            an(entity(piece.kind).where(exists(hole, hole.kind == piece.kind)))
            .distinct()
            .tolist()
        )

    def pieces_with_their_hole(self) -> Query:
        """
        :return: The query for the pieces the camera saw that a hole of their shape was
            seen for.
        """
        piece = variable(SeenPiece, self.twin.world.semantic_annotations)
        hole = variable(SeenHole, self.twin.holes)
        return an(entity(piece).where(exists(hole, hole.kind == piece.kind)))

    def statement_to_sort(self, kind: Type[MontessoriShape]) -> Match:
        """
        :param kind: The kind of piece to sort.
        :return: The plan to put a piece of the kind that still rests on the table into
            a hole, leaving open which piece, side, arm and hole.
        """
        piece = a(SeenPiece)(kind=kind)
        piece.where(SupportedBy(piece.root, self.twin.table))
        return a(SortPieceAction)(piece=piece, side=..., arm=..., hole=...)

    def sort(self, kinds: List[Type[MontessoriShape]]) -> PlanNode:
        """
        Resolve a sorting of each kind, then put a piece of each into a hole of its
        shape; a kind whose sorting has a part without an answer is left out.

        :param kinds: The kinds of piece to sort.
        """
        plans = [self.resolve_sorting(self.statement_to_sort(kind)) for kind in kinds]
        return sequential(
            [
                ParkArmsAction(self.robot.all_arms),
                *[plan for plan in plans if plan is not None],
            ]
        )

    def insert(self, kind: Type[MontessoriShape]) -> SortPieceAction | None:
        """
        :param kind: The kind of piece to insert.
        :return: The resolved plan to put a piece of the kind into a hole of its shape,
            or None if a part of it has no answer.
        """
        return self.resolve_sorting(self.statement_to_sort(kind))

    def resolve(self, statement: Match) -> List[Any]:
        """
        Resolve a statement with parts left open, or a whole sorting plan, through the
        backends and show how in the viewer.

        :param statement: The statement or sorting plan.
        :return: What answers it, most preferred first; the resolved plan for a sorting
            plan.
        """
        if statement._type_ is SortPieceAction:
            return [self.resolve_sorting(statement)]
        with self.observing():
            answers = self.answerer.resolve(statement)
        if self.on_resolved is not None:
            self.on_resolved(self.answerer.resolutions[-1])
        return answers

    def resolve_sorting(self, statement: Match) -> SortPieceAction | None:
        """
        Answer each part a sorting plan leaves open, in the order its steps need them.

        :param statement: The sorting plan, each open part given as ``...`` or as a
            statement; any part given as a value is kept.
        :return: The sorting plan with every part answered, or None if a part has no
            answer.
        """
        resolution = self.answerer.begin(
            self.title_of(statement._kwargs_["piece"]),
            self.underspecified_lines(statement),
            self.resolved_lines(),
            statement,
        )
        with self.observing():
            plan = self._answer_parts(resolution, statement._kwargs_)
        resolution.plan = plan
        resolution.executable = plan is not None
        self._resolved(resolution)
        return plan

    def _answer_parts(
        self, resolution: PlanResolution, stated: Dict[str, Any]
    ) -> SortPieceAction | None:
        """
        :param resolution: The resolution the parts are answered in.
        :param stated: The sorting plan's parts as stated.
        :return: The sorting plan with every part answered, or None as soon as a part
            has no answer.
        """
        pieces = self.answerer.answer_with_conditions(
            resolution, SortingPart.PIECE, "which piece", stated["piece"]
        )
        if not pieces:
            return None
        piece = pieces[0]
        side = self._given_or_answered(
            stated["side"],
            resolution,
            SortingPart.SIDE,
            "which side to take it from",
            a(SideGrasp)(side=..., piece=piece),
        )
        arm = self._given_or_answered(
            stated["arm"],
            resolution,
            SortingPart.ARM,
            "which arm",
            self.free_arm_nearest(piece),
        )
        hole = self._given_or_answered(
            stated["hole"],
            resolution,
            SortingPart.HOLE,
            "which hole",
            an(Insertion)(piece=piece, hole=...),
        )
        if None in (side, arm, hole):
            return None
        return SortPieceAction(
            piece=piece,
            side=side.side if isinstance(side, SideGrasp) else side,
            arm=arm,
            hole=hole.hole if isinstance(hole, Insertion) else hole,
        )

    def _given_or_answered(
        self,
        given: Any,
        resolution: PlanResolution,
        part: SortingPart,
        slot: str,
        statement: Match,
    ) -> Any | None:
        """
        :param given: The part as stated.
        :param resolution: The resolution the part is answered in.
        :param part: The open part.
        :param slot: What the part asks for.
        :param statement: The statement the part is asked as, if it is open.
        :return: The part as stated if it was given, else the most preferred answer,
            or None if there is none.
        """
        if given is not ...:
            return given
        answers = self.answerer.answer(resolution, part, slot, statement)
        return answers[0] if answers else None

    def _resolved(self, resolution: PlanResolution) -> None:
        """
        Mark a resolution complete and tell whoever listens.

        :param resolution: The complete resolution.
        """
        self.answerer.finish(resolution)
        if self.on_resolved is not None:
            self.on_resolved(resolution)

    def free_arm_nearest(self, piece: SeenPiece) -> Match:
        """
        :param piece: The piece to be taken hold of.
        :return: The statement asking for an arm whose gripper is free, the arms nearest
            the piece considered first.
        """
        position = piece.root.global_pose.position.to_np()[:3]
        arm = an(Arm).from_(self.robot.all_arms)
        arm.where(GripperIsFree(arm.end_effector))
        arm.ordered_by(
            arm.root,
            key=lambda root: float(
                sum((root.global_pose.position.to_np()[:3] - position) ** 2)
            ),
        )
        return arm

    def title_of(self, piece_statement: Match) -> str:
        """
        :param piece_statement: The statement asking for the piece to sort.
        :return: What sorting it is called, e.g. ``"put the cylinder into its hole"``.
        """
        kind = piece_statement._kwargs_.get("kind")
        named = self.twin.kind_of(kind) if isinstance(kind, type) else "piece"
        return f"put the {named} into its hole"

    def underspecified_lines(self, statement: Match) -> List[CodeLine]:
        """
        :param statement: The sorting plan as stated.
        :return: Its lines, each open part marked.
        """
        piece_statement = statement._kwargs_["piece"]
        piece_lines = [
            CodeLine(
                "  piece="
                + self.answerer.code_of(
                    a(piece_statement._type_)(**piece_statement._kwargs_)
                ),
                slot_id=SortingPart.PIECE,
            )
        ]
        if piece_statement._where_conditions_:
            piece_lines.append(
                CodeLine(
                    "        .where(SupportedBy(piece.root, table)),",
                    slot_id=SortingPart.PIECE_ON_THE_TABLE,
                )
            )
        return [
            CodeLine("a(SortPieceAction)("),
            *piece_lines,
            self._open_line(
                "side", SortingPart.SIDE, "a(SideGrasp)(side=..., piece=piece)"
            ),
            self._open_line(
                "arm", SortingPart.ARM, "an(Arm).where(GripperIsFree(arm.end_effector))"
            ),
            self._open_line(
                "hole", SortingPart.HOLE, "an(Insertion)(piece=piece, hole=...)"
            ),
            CodeLine(")"),
        ]

    @staticmethod
    def _open_line(name: str, part: SortingPart, asked_as: str) -> CodeLine:
        """
        :param name: The argument the part is.
        :param part: The open part.
        :param asked_as: The statement the part is asked as.
        :return: The line stating the part open.
        """
        return CodeLine(
            f"  {name}={SlotMarker.around(part)},   # {asked_as}", slot_id=part
        )

    @staticmethod
    def resolved_lines() -> List[CodeLine]:
        """
        :return: The lines of a resolved sorting plan, each open part marked where its
            answer goes, followed by the steps it is carried out as.
        """
        piece = SlotMarker.around(SortingPart.PIECE_ON_THE_TABLE)
        side = SlotMarker.around(SortingPart.SIDE)
        arm = SlotMarker.around(SortingPart.ARM)
        hole = SlotMarker.around(SortingPart.HOLE)
        return [
            CodeLine("SortPieceAction("),
            CodeLine(f"  piece={piece},"),
            CodeLine(f"  side={side},"),
            CodeLine(f"  arm={arm},"),
            CodeLine(f"  hole={hole},"),
            CodeLine(")"),
            CodeLine(f"  ↳ PickUpAction(arm={arm}, grasp=from above, {side})"),
            CodeLine(f"  ↳ InsertAction(piece={piece}, hole={hole})"),
            CodeLine("  ↳ ParkArmsAction()"),
        ]


# %% showing a resolution before the robot moves


@dataclass
class ResolutionPresentation:
    """
    How long the viewer takes to show a resolution, which the robot waits out before it
    carries the resolved plan out.
    """

    seconds_per_part: float = 4.2
    """
    How long one answered part is shown.
    """

    seconds_before: float = 1.6
    """
    How long the plan as stated is shown before its first part is answered.
    """

    seconds_after: float = 2.4
    """
    How long the resolved plan is shown before the robot carries it out.
    """

    real_time_factor: float = 1.0
    """
    How much faster than the clock the demonstration runs; the viewer slows down by as
    much.
    """

    def seconds_for(self, resolution: PlanResolution) -> float:
        """
        :param resolution: A complete resolution.
        :return: How long the viewer takes to show it.
        """
        shown = (
            self.seconds_before
            + self.seconds_per_part * len(resolution.parts)
            + self.seconds_after
        )
        return shown / self.real_time_factor

    def to_payload(self) -> dict:
        """
        :return: The timing as JSON for the viewer, in milliseconds of the clock.
        """
        return {
            "partMilliseconds": 1000 * self.seconds_per_part / self.real_time_factor,
            "beforeMilliseconds": 1000 * self.seconds_before / self.real_time_factor,
            "afterMilliseconds": 1000 * self.seconds_after / self.real_time_factor,
        }


# %% the demonstration


@dataclass(kw_only=True)
class TracyMontessoriDemonstration(ShowcasedDemonstration):
    """
    Tracy looks at a real capture of the Montessori board, resolves how to sort the
    pieces it saw into their holes, and sorts them, with the EQL showcase listening in.
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
    What resolves the sorting plans.
    """

    presentation: ResolutionPresentation = field(default_factory=ResolutionPresentation)
    """
    How long the viewer takes to show a resolution.
    """

    kinds_sorted_by_the_plan: int = 1
    """
    How many kinds of piece the demonstration's own plan sorts; the others are left for
    the viewer to resolve and command.
    """

    stepper: QueryStepper = field(init=False)
    """
    Keeps every query Tracy asks, and holds it at each while the viewer steps through
    them.
    """

    steps_through_queries: bool = False
    """
    Whether Tracy starts held at every query it asks until the viewer moves on.
    """

    def __post_init__(self) -> None:
        self.stepper = QueryStepper(
            situation_of=self.situation,
            publish=self._publish_query_steps,
            is_stepping=self.steps_through_queries,
        )

    def run(self) -> World:
        with self.stepper.observing():
            return super().run()

    def build_simulated_world(self) -> World:
        self.look = PerceptionShowcase(bridge=None)
        self.look.commit(self.capture_name)
        world = self.look.twin.world
        robot = self.robot_in(world)
        # Tracy starts with its arms parked, as it stands before a task
        for arm in robot.all_arms:
            for connection, position in arm.get_joint_state_by_type(
                StaticJointState.PARK
            ).items():
                connection.position = position
        return world

    def is_scene_populated(self, world: World) -> bool:
        return True

    def populate_scene(self, world: World) -> None:
        pass

    @staticmethod
    def robot_in(world: World) -> Tracy:
        """
        :param world: The world Tracy stands in.
        :return: Tracy.
        """
        return the(entity(variable(Tracy, world.semantic_annotations))).first()

    def build_context(self, world: World) -> Context:
        robot = self.robot_in(world)
        # a command is built against a context of its own, but its open parts are
        # answered by the same backends, and kept with the sorting's answers
        if self.sorting is None:
            self.presentation.real_time_factor = self.real_time_factor or 1.0
            self.sorting = MontessoriSorting(
                twin=self.look.twin,
                robot=robot,
                perception_view=self.look.view,
                on_resolved=self._show_resolution,
                observing=self.stepper.observing,
            )
            self.sorting.answerer.on_answer = self._publish_resolutions
            self._publish_resolutions(self.sorting.answerer)
        self.extra_names[QuestionName.SORTING] = self.sorting
        self.extra_names[QuestionName.ANSWERER] = self.sorting.answerer
        self.extra_names[QuestionName.RESOLVE] = self.sorting.resolve
        self.extra_names[QuestionName.STEPS] = self.stepper
        self.extra_names.update(
            {
                kind.__name__: kind
                for kind in (
                    SlotAnswer,
                    PlanResolution,
                    Faculty,
                    InsideRegion,
                    SortPieceAction,
                    SeenPiece,
                    SideGrasp,
                    GraspSide,
                    Insertion,
                    Arm,
                    GripperIsFree,
                )
            }
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
        kinds = self.sorting.kinds_to_sort()[: self.kinds_sorted_by_the_plan]
        built = sequential([self.sorting.sort(kinds)], context=context).plan
        self.showcase.observe_plan(built)
        return built

    def _publish_resolutions(self, answerer: OpenSlotAnswerer) -> None:
        """
        Show the viewer every resolution so far, if this run is shown in one.

        :param answerer: What resolved them.
        """
        if not isinstance(self.visualization, PluginVisualization):
            return
        if not isinstance(self.visualization.provider, LiveVisualization):
            return
        payload = answerer.to_payload()
        payload["presentation"] = self.presentation.to_payload()
        self.visualization.provider.bridge.publish_slot_answers(payload)

    def situation(self) -> StepSituation:
        """
        :return: What Tracy is doing at the moment: setting up, resolving a plan,
            expanding or carrying out a plan, or planning what to sort.
        """
        if self.sorting is None:
            return StepSituation(Phase.SETUP, TracyActivity.SETTING_UP)
        resolution = variable(PlanResolution, self.sorting.answerer.resolutions)
        resolving = an(entity(resolution).where(resolution.done == False)).tolist()
        if resolving:
            return StepSituation(
                Phase.RESOLUTION,
                resolving[-1].name,
                EnclosingStatement.of_resolution(resolving[-1]),
            )
        performing = (
            None
            if self.showcase is None
            else StepSituation.of_performance(self.showcase.performed_actions)
        )
        return performing or StepSituation(Phase.RESOLUTION, TracyActivity.PLANNING)

    def _publish_query_steps(self, steps: Dict[str, Any]) -> bool:
        """
        Show the viewer the queries Tracy asked and let it step through them, if this
        run is shown in one.

        :param steps: The steps, as JSON.
        :return: Whether a viewer was shown them.
        """
        if not isinstance(self.visualization, PluginVisualization):
            return False
        if not isinstance(self.visualization.provider, LiveVisualization):
            return False
        bridge = self.visualization.provider.bridge
        bridge.query_step_control = self.stepper
        bridge.publish_query_steps(steps)
        return True

    def _show_resolution(self, resolution: PlanResolution) -> None:
        """
        Let the viewer show a complete resolution before the robot carries it out, if
        this run is shown in one.

        :param resolution: The complete resolution.
        """
        if not isinstance(self.visualization, PluginVisualization):
            return
        if not isinstance(self.visualization.provider, LiveVisualization):
            return
        self._publish_resolutions(self.sorting.answerer)
        time.sleep(self.presentation.seconds_for(resolution))

    def segment_events(self, world: World) -> AbstractContextManager:
        segmentation = Segmind.create_for_semantic_annotation_types(
            world,
            (SeenPiece,),
            detector_types=(PickUpDetector, PlacingDetector, GraspDetector),
        )
        self.showcase.observe_events(segmentation.event_logger)
        self._offer_showcase()
        return segmentation


def main(
    capture_name: str = DEFAULT_CAPTURE,
    takes_commands: bool = True,
    real_time_factor: float = 1.0,
    steps_through_queries: bool = False,
) -> None:
    """
    Have Tracy sort what it saw in a capture, then let the viewer command it.

    :param capture_name: The capture the robot looks at.
    :param takes_commands: Whether the robot takes commands once the sorting is done.
    :param real_time_factor: How much faster than the clock Tracy moves.
    :param steps_through_queries: Whether Tracy starts held at every query it asks
        until the viewer moves on.
    """
    TracyMontessoriDemonstration(
        capture_name=capture_name,
        run_label=SORTING_LABEL,
        run_database=RunDatabase(data_directory() / "eql_showcase_runs.sqlite"),
        questions=ShowcaseQuestions.from_file(MONTESSORI_QUESTIONS_FILE),
        takes_commands=takes_commands,
        collision_avoidance=False,
        real_time_factor=real_time_factor,
        steps_through_queries=steps_through_queries,
    ).run()


if __name__ == "__main__":
    main()

"""
The framework figure's plan, run on the physical Tracy.

The plan is the one :mod:`~experiments.open_slots.plan` writes and
:mod:`~experiments.tracy_experiments.framework_demo` runs in simulation -- pick the cube
off the board's lid and put it through the hole it belongs in -- with every slot it
leaves open closed by the same backends, in the same order. What differs is the lab:
the world is the one the robot publishes, the look is the robot's own camera, and the
resolved plan is carried out by the actions that drive Tracy's arm through Giskard and
its fingers through their Robotiq action server (see
:mod:`~experiments.tracy_experiments.pick_and_place_action_real`).

The run is wired the way
:mod:`~experiments.tracy_experiments.pickup.pickup_demo_real` wires the physical robot,
and records the same kind of episode: the person at the console places the cube and says
what they placed, the plan is carried out as one trial, the working-memory question set
is asked about the cube once it has come to rest, and the trial is recorded to the
results database with its transcript, its joint trace and the bag if one was recorded.

Which backend answered which slot is reported exactly as the simulated run reports it,
so the two are read against one another line by line. A slot answered by a different
backend here is a finding about the two labs, not something for this demo to correct.

Run with (the Giskard stack, the camera and the robot must be up)::

    python -m experiments.tracy_experiments.framework_demo --execution real [--record]
"""

from __future__ import annotations

import argparse
import contextlib
import logging
from dataclasses import dataclass, field
from pathlib import Path

from typing_extensions import TYPE_CHECKING, List, Optional, Sequence

logging.basicConfig(level=logging.INFO, format="%(message)s")

import rclpy

from coraplex.datastructures.dataclasses import Context
from coraplex.datastructures.enums import Arms, ExecutionType
from coraplex.execution_environment import ExecutionEnvironment
from coraplex.plans.factories import sequential
from coraplex.robot_plans.actions.base import ActionDescription
from coraplex.robot_plans.actions.core.robot_body import ParkArmsAction
from coraplex.view_manager import ViewManager
from experiments.episodes.artifacts import ArtifactDirectory, EpisodeArtifacts
from experiments.episodes.episode import Episode, RecordedTrial
from experiments.episodes.observer import EpisodeObserver, ObserverMotionListener
from experiments.episodes.trace import JointTraceRecorder
from experiments.montessori.perception.recorded_setup import lab_board
from experiments.montessori.perception.scene_publishing import (
    LOOKS_FOR_THE_BOARD,
    PerceivedScene,
)
from experiments.montessori.results_database import ResultsDatabase
from experiments.montessori.semantics import MontessoriShape, MontessoriShapeCategory
from experiments.montessori.watched_run import SceneThePersonSetUp
from experiments.open_slots.grounding import GroundedPlan
from experiments.open_slots.plan import SORTED_PIECE
from experiments.questions.after_the_move import QuestionAfterTheMove
from experiments.questions.question_set import QuestionSet
from experiments.questions.question import SceneAsSetUp
from experiments.montessori.scenarios import SortingScene
from experiments.scenarios.scenario import Person, PersonAtTheConsole
from experiments.scenarios.trial import TrialOutcome
from experiments.tracy_experiments.live_tracy import LiveTracy
from experiments.tracy_experiments.montessori.event_dashboard import (
    EventFeed,
    run_dashboard,
)
from experiments.tracy_experiments.montessori.event_monitoring import build_pick_monitor
from experiments.tracy_experiments.montessori.gripper_feedback import (
    GraspVerdict,
    GripperJointStateListener,
    GripperSlipEvent,
)
from experiments.tracy_experiments.pick_and_place_action import ActuatorDrivenAction
from experiments.tracy_experiments.pick_and_place_action_real import TracyActuators
from experiments.tracy_experiments.pickup.pickup_demo_real import (
    DemoOption,
    bag_asked_for,
    database_asked_for,
    keep_the_episode,
    outcome_of,
    piece_asked_about,
    question_set_about,
)
from experiments.tracy_experiments.robotiq_gripper import RobotiqGripperController
from experiments.tracy_experiments.rosbag_recording import (
    DECIMATED_TOPICS,
    DEFAULT_BAG_DIRECTORY,
    DEFAULT_KEEP_EVERY_NTH_FRAME,
    RosbagRecorder,
    RosbagRecordingProcess,
)
from segmind.datastructures.events import DetectionEvent
from segmind.detectors.base import SegmindContext
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body

if TYPE_CHECKING:
    from experiments.montessori.perception.camera import RgbdFrame

logger = logging.getLogger(__name__)

NODE_NAME = "tracy_framework_demo_real"
"""
The name this demo's node registers under.
"""

PICK_ARM = Arms.LEFT
"""
Which arm carries the plan out.
"""

SCENARIO_NAME = "the robot carries out the plan the framework figure shows"
"""
What the episode a run records calls its scenario.
"""

BAG_NAME_PREFIX = "tracy_framework_demo"
"""
Leading part of the recorded bag's directory name, completed with a timestamp so
consecutive runs do not collide.
"""

PLACE_THE_PIECE = (
    "Put the light-blue %s on the board's lid, on the far side of the lid from the "
    "square hole, then press enter."
)
"""
What the person at the console is asked to do before the look, with the kind of piece
the plan sorts.

The plan states that the piece it picks up rests on the lid (``SupportedBy(piece,
lid)``), so a piece anywhere else answers nothing and the run has no plan to carry out.
Starting it away from its own hole is what leaves the insertion something to do.
"""

CHECK_THE_SCENE = (
    "Board and %d perceived piece(s) in rviz. Check they line up with the real objects "
    "before the plan runs."
)
"""
What the person at the console is asked to check once the camera has stood the scene,
with how many pieces it found.
"""

# %% the one trial a run records


@dataclass
class FrameworkTrial:
    """
    The one trial a run of this demo records: the account of the table the person at it
    gives, the figure's plan carried out on the robot, and the question set asked once
    the piece has come to rest.
    """

    grounded: GroundedPlan
    """
    The figure's plan as the look answered it, and which backend answered which slot.
    """

    lab: TracyActuators
    """
    What the plan is carried out on, and what observes everything the trial records.
    """

    robot: Tracy
    """
    The robot carrying it out, which the questions are put to.
    """

    person: Person
    """
    The person at the table, who says what they placed.
    """

    asked_about: MontessoriShapeCategory = SORTED_PIECE
    """
    The kind of piece the question set is asked about, the one the plan sorts.
    """

    carried_out: List[ActionDescription] = field(init=False, default_factory=list)
    """
    The actions that drove the robot through the resolved plan, once it has run.
    """

    stated_scene: Optional[SceneAsSetUp] = field(init=False, default=None)
    """
    The table as the person at it states it, once asked, or None where nobody can say.
    """

    joints: Optional[JointTraceRecorder] = field(init=False, default=None)
    """
    What traces where every joint stands while the trial runs, once it has begun.
    """

    asks: Optional[QuestionAfterTheMove] = field(init=False, default=None)
    """
    What asks the question set once the piece has come to rest, once the trial runs.
    """

    @property
    def world(self) -> World:
        """
        The world the robot plans in.
        """
        return self.lab.context.world

    def episode(self) -> Episode:
        """
        The episode this trial is the one trial of, keeping the world it runs in.
        """
        return Episode(
            scenario_name=SCENARIO_NAME,
            execution_type=ExecutionType.REAL,
            perturbation_names=[],
            world=self.world,
        )

    def begin(self) -> None:
        """
        Start the trial's clock and trace the joints against it.

        Every moment the trial records is seconds from now, and the trial says when now
        was on the wall clock, which is the clock the bag stamps its messages on.
        """
        self.lab.observer.restart()
        self.joints = JointTraceRecorder(
            _world=self.world, clock=lambda: self.lab.observer.elapsed_seconds
        )
        # A still robot changes no joint, so where the joints stand is read once here or
        # a trial that moves nothing would keep no trace at all.
        self.joints.trace.sample(self.world, self.lab.observer.elapsed_seconds)

    def state_the_scene(self) -> None:
        """
        Ask the person at the table which pieces they placed, and keep the table as they
        state it.
        """
        self.stated_scene = SceneThePersonSetUp(self.person).stated_over(
            SortingScene(self.world)
        )

    @property
    def piece_asked_about(self) -> MontessoriShape:
        """
        The piece the question set is asked about, as the look found it.

        :raises PieceNotSeenError: If the look found no piece of the kind asked about.
        """
        return piece_asked_about(self.grounded.scene, self.asked_about)

    def question_set(self) -> QuestionSet:
        """
        The working-memory question set about the piece the plan sorts, scored against
        the table as the person states it.

        :raises PieceNotSeenError: If the look found no piece of the kind asked about.
        """
        return question_set_about(
            self.grounded.scene, self.piece_asked_about, self.robot, self.stated_scene
        )

    def perform(self) -> None:
        """
        Run the trial: take the person's account, carry the resolved plan out on the
        robot while a monitor watches the piece, and ask the question set once the piece
        has come to rest -- or at the end, if it never does.

        :raises PieceNotSeenError: If the look found no piece of the kind asked about.
        :raises NoActionCarriesItOut: If the plan states an action nothing drives Tracy
            with.
        """
        self.state_the_scene()
        piece = self.piece_asked_about
        self.asks = QuestionAfterTheMove(
            observer=self.lab.observer,
            asked_about=piece.root,
            question_set=self.question_set,
            robot=self.robot,
        )
        self.carried_out = ActuatorDrivenAction.performing(
            self.grounded.actions, self.lab
        )
        monitor = build_pick_monitor(
            world=self.world, tracked_body=piece.root, robot=self.robot, arm=PICK_ARM
        )
        monitor.context.require_extension(SegmindContext).logger.add_callback(
            DetectionEvent, self.note_event
        )
        monitor.start()
        try:
            sequential(self.carried_out, context=self.lab.context).plan.perform()
        finally:
            monitor.stop()
        self.asks.ask_if_not_yet()

    def note_event(self, event: DetectionEvent) -> None:
        """
        Keep one event a monitor reported as a tick of the trial, stamped with the
        moment it arrived, and let whatever is waiting on the piece hear it.

        :param event: The event.
        """
        self.lab.observer.tick(self.lab.observer.elapsed_seconds, [event])
        if self.asks is not None:
            self.asks.receive([event])

    @property
    def outcome(self) -> TrialOutcome:
        """
        Whether the run picked the piece it was asked about up, as its monitor saw it.
        """
        return outcome_of(
            [event for tick in self.lab.observer.ticks for event in tick.events],
            self.piece_asked_about.root,
        )

    def finish(self, episode: Episode) -> RecordedTrial:
        """
        Stop tracing the joints and record the trial with everything observed in it.

        :param episode: The episode the trial belongs to.
        :return: The trial, carrying when it began, its ticks, queries, plans and
            motions.
        """
        self.joints.stop()
        return self.lab.observer.into(
            RecordedTrial(
                episode=episode,
                outcome=self.outcome,
                duration=self.lab.observer.elapsed_seconds,
            )
        )


# %% the run


@dataclass
class FrameworkDemoOnTracy:
    """
    The run of this demo over a connected Tracy: have the person place the piece, look
    once, ground the figure's plan against what was found, carry it out on the robot as
    one recorded trial, and keep the episode.
    """

    tracy: LiveTracy
    """
    The robot, connected.
    """

    person: Person
    """
    The person at the console and the table.
    """

    database: Optional[ResultsDatabase]
    """
    The database the episode is recorded to, or None for a run that keeps no episode.
    """

    bag: Optional[RosbagRecorder] = None
    """
    The bag the run records for as long as the plan runs, or None to record none.
    """

    artifact_directory: ArtifactDirectory = field(default_factory=ArtifactDirectory)
    """
    Where the episode's artifacts are kept.
    """

    feed: EventFeed = field(default_factory=EventFeed)
    """
    Where the events the trial's monitor reports are streamed to.
    """

    grounded: Optional[GroundedPlan] = field(init=False, default=None)
    """
    The figure's plan as this run answered it, once it has looked.
    """

    def run(self) -> Optional[EpisodeArtifacts]:
        """
        Carry the figure's plan out on the robot, recording the episode.

        The bag opens before the trial's clock starts and closes after it has stopped,
        so the recording spans the whole trial.

        :return: The artifacts the episode kept, or None for a run that keeps no
            episode.
        :raises NoBoardInView: If the camera cannot find the board.
        :raises PieceNotSeenError: If the look found no piece of the kind the plan
            sorts.
        """
        tracy = self.tracy
        context = Context(
            world=tracy.world,
            robot=tracy.robot,
            ros_node=tracy.node,
            evaluate_conditions=False,
        )
        observer = EpisodeObserver()
        context.motion_listener = ObserverMotionListener(observer=observer)
        lab = TracyActuators(
            context=context,
            gripper=RobotiqGripperController(tracy.node),
            gripper_listener=GripperJointStateListener(node=tracy.node, arm=PICK_ARM),
            tool_frame=ViewManager.get_end_effector_view(
                PICK_ARM, tracy.robot
            ).tool_frame,
            observer=observer,
            slipped=self.report_slip,
        )

        self.person.carry_out(PLACE_THE_PIECE % SORTED_PIECE.value)
        scene = PerceivedScene(
            world=tracy.world,
            look=tracy.look,
            described_board=lab_board(),
            looks_for_board=LOOKS_FOR_THE_BOARD,
        )
        scene.perceive()
        looked_at = tracy.look.wait_for_frame()
        self.person.carry_out(CHECK_THE_SCENE % len(scene.pieces))

        self.grounded = GroundedPlan.grounded_against(scene, PICK_ARM, tracy.robot)
        self.grounded.report()

        trial = FrameworkTrial(
            grounded=self.grounded, lab=lab, robot=tracy.robot, person=self.person
        )
        episode = trial.episode()
        recorder = (
            contextlib.nullcontext()
            if self.bag is None
            else RosbagRecordingProcess(self.bag)
        )
        with (
            recorder as bag,
            ExecutionEnvironment(
                execution_type=ExecutionType.REAL, collision_avoidance=False
            ),
        ):
            trial.begin()
            lab.perform_and_record(
                sequential([ParkArmsAction(PICK_ARM)], context=context).plan
            )
            trial.perform()
            recorded = trial.finish(episode)
        logger.info("The plan finished; the trial %s.", recorded.outcome)
        # Keeping the episode rewrites where the world's meshes are read from, which a
        # look still copying the world would read half-written.
        tracy.look.stop_looking()
        return self.keep(
            recorded,
            trial,
            None if bag is None else Path(bag.output_directory),
            looked_at,
        )

    def report_slip(self, body: Body, verdict: GraspVerdict) -> None:
        """
        Stream a slip the carry's watch reported to the dashboard.

        :param body: The piece being carried.
        :param verdict: The poll's held-or-slipped verdict.
        """
        if verdict is GraspVerdict.OBJECT_SLIPPED:
            self.feed.publish(body.name.name, GripperSlipEvent(tracked_object=body))

    def keep(
        self,
        recorded: RecordedTrial,
        trial: FrameworkTrial,
        bag_directory: Optional[Path],
        looked_at: RgbdFrame,
    ) -> Optional[EpisodeArtifacts]:
        """
        Keep the episode of the finished trial, unless this run keeps none, with the
        pictures of the plan's statement about the piece read one condition at a time
        over the frame the look was taken from.

        :param recorded: The trial the run recorded.
        :param trial: The trial it was recorded from, which holds the joint trace.
        :param bag_directory: The bag the run recorded, or None for a run that recorded
            none.
        :param looked_at: The frame the camera took when the scene was looked at.
        :return: The artifacts that were kept, or None for a run that keeps no episode.
        """
        if self.database is None:
            logger.info("No episode kept, as asked.")
            return None
        # Read before the episode is kept: reading a statement copies the world, and
        # keeping the episode rewrites where that world's meshes are read from.
        narrowing = self.grounded.narrowing_over(looked_at)
        artifacts = keep_the_episode(
            recorded,
            trial.joints.trace,
            bag_directory,
            self.database,
            self.artifact_directory,
        )
        artifacts.trial(recorded.number).keep_narrowing(narrowing)
        return artifacts


# %% running it


def parse_arguments(argument_list: Optional[Sequence[str]]) -> argparse.Namespace:
    """
    The real run's own command line, spelling the recording and database options the way
    :mod:`~experiments.tracy_experiments.pickup.pickup_demo_real` spells them.

    The perturbation and piece options that demo offers are left out: this one carries
    out the plan the figure states, which names the piece it sorts itself.

    :param argument_list: Arguments to read; the process's own when None.
    """
    parser = argparse.ArgumentParser(
        description="Carry the framework figure's plan out on the physical Tracy."
    )
    parser.add_argument(
        DemoOption.RECORD,
        action="store_true",
        help=(
            "Record a rosbag of the camera, depth camera, joint states and transforms "
            "for the duration of the run."
        ),
    )
    parser.add_argument(
        DemoOption.BAG_DIRECTORY,
        default=DEFAULT_BAG_DIRECTORY,
        help=(
            f"Directory the recorded bag is placed in. Default: "
            f"{DEFAULT_BAG_DIRECTORY}."
        ),
    )
    parser.add_argument(
        DemoOption.KEEP_EVERY_NTH_FRAME,
        type=int,
        default=DEFAULT_KEEP_EVERY_NTH_FRAME,
        metavar="N",
        help=(
            f"Record only one in every N frames of the heavy camera streams "
            f"({', '.join(DECIMATED_TOPICS)}). Joint states and transforms are always "
            f"recorded whole. Pass 1 to record every frame. Default: "
            f"{DEFAULT_KEEP_EVERY_NTH_FRAME}."
        ),
    )
    parser.add_argument(
        DemoOption.DATABASE_URI,
        default=None,
        help=(
            "Database the episode is recorded to; the MONTESSORI_SORTING_DATABASE_URI "
            "environment variable or the built-in default otherwise. A database that "
            "cannot be reached or would live only in memory is refused before the "
            "robot moves."
        ),
    )
    parser.add_argument(
        DemoOption.NO_EPISODE,
        action="store_true",
        help=(
            "Keep no episode: nothing is written to a database or beside it, and no "
            "database is checked. A bag asked for with --record is still recorded."
        ),
    )
    parser.add_argument("--execution", default=None, help=argparse.SUPPRESS)
    return parser.parse_args(argument_list)


def main(argument_list: Optional[Sequence[str]] = None) -> None:
    """
    Carry the figure's plan out on the physical Tracy, recording the episode.

    :param argument_list: Arguments to read; the process's own when omitted.
    :raises InMemoryDatabaseRefused: If the episode would be recorded to a database that
        dies with the run, before anything on the robot is touched.
    """
    arguments = parse_arguments(argument_list)
    database = database_asked_for(arguments)
    bag = bag_asked_for(arguments, BAG_NAME_PREFIX)

    feed = EventFeed()
    run_dashboard(feed)

    rclpy.init()
    with LiveTracy.connected(NODE_NAME) as tracy:
        FrameworkDemoOnTracy(
            tracy=tracy,
            person=PersonAtTheConsole(),
            database=database,
            bag=bag,
            feed=feed,
        ).run()


if __name__ == "__main__":
    main()

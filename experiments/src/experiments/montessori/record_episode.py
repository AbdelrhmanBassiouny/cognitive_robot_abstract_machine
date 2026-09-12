"""
Record one episode of a Montessori sorting scenario: the scenario, its layout, the
perturbation applied to it, where it runs and where its scene comes from are chosen on
the command line, the run is watched by the event monitor and asked the question set,
and its trials, its video, its transcript and its bag are kept under the episode's
identifier.

The scene is either built from Tracy's description, for a run in simulation, or
perceived: the world is fetched from the robot and the board and the pieces are stood in
it by the robot's own camera, which is what a run on the robot is set among. A perceived
scene is laid out by nobody here, so its layout is read off what the camera found.

The identifier is printed before anything else, so a run that dies can still be found in
the database and asked about.
"""

from __future__ import annotations

import argparse
import contextlib
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from coraplex.datastructures.enums import ExecutionType
from krrood.exceptions import DataclassException
from semantic_digital_twin.spatial_types.spatial_types import Vector3
from typing_extensions import TYPE_CHECKING, Iterator, List, Optional, Sequence, Type

from experiments.episodes.artifacts import ArtifactDirectory
from experiments.episodes.episode import Episode
from experiments.episodes.recording import open_recording
from experiments.montessori import results_database
from experiments.montessori.perception.recorded_setup import lab_board
from experiments.montessori.perception.scene_publishing import (
    LOOKS_FOR_THE_BOARD,
    PerceivedScene,
)
from experiments.montessori.results_database import (
    DATABASE_URI_ENVIRONMENT_VARIABLE,
    ConfiguredDatabase,
    ReadOnlyResultsDatabase,
    ResultsDatabase,
    UnreachableResultsDatabase,
    database_label,
    is_in_memory,
    verify_writable,
)
from experiments.montessori.scenarios import (
    DetectionRelabelled,
    HOW_FAR_A_MOVED_HOLE_GOES,
    Layout,
    LayoutAsFound,
    MontessoriSortingScenario,
    MontessoriWorldBuilder,
    PerceivedPoseOffset,
    Perturbation,
    PieceLayout,
    PieceShoved,
    SortingStep,
    TargetHoleMoved,
    TracyHoldsAPiece,
    TracyIsIdleWhileAPieceIsPushed,
    TracyLooksAtTheScene,
    TracySortsAPiece,
    TracyWatchesTheSceneStandStill,
)
from experiments.montessori.semantics import MontessoriShapeCategory
from experiments.montessori.watched_run import WatchedSortingRun
from experiments.scenarios.scenario import PersonAtTheConsole
from experiments.tracy_experiments.montessori.scene_builder import (
    TracyLookingAtItsOwnTable,
    TracyOnItsOwnTable,
    WHERE_TRACY_LOOKS_FROM,
    layout_area_on_tracys_table,
)

if TYPE_CHECKING:
    from experiments.tracy_experiments.rosbag_recording import RosbagRecorder

# %% what the command line offers


class ScenarioChoice(StrEnum):
    """
    The scenarios a run can record, named for what happens in them.
    """

    SCENE_STANDS_STILL = "scene-stands-still"
    ROBOT_SORTS_A_PIECE = "robot-sorts-a-piece"
    PIECE_PUSHED_WHILE_IDLE = "piece-pushed-while-idle"
    PIECE_HELD_WHEN_ASKED = "piece-held-when-asked"
    ROBOT_LOOKS_AT_THE_SCENE = "robot-looks-at-the-scene"


class LayoutChoice(StrEnum):
    """
    How the pieces come to stand on the table.
    """

    RANDOMIZED = "randomized"
    NEARLY_AMBIGUOUS = "nearly-ambiguous"
    AS_FOUND = "as-found"


class SceneChoice(StrEnum):
    """
    Where the board and the pieces the run is set among come from.
    """

    BUILT = "built"
    PERCEIVED = "perceived"

    @property
    def default_layout(self) -> LayoutChoice:
        """
        How the pieces come to stand unless the command line says otherwise: a built
        scene stands them by a seeded draw, a perceived scene finds them where they are.
        """
        if self is SceneChoice.PERCEIVED:
            return LayoutChoice.AS_FOUND
        return LayoutChoice.RANDOMIZED


class PerturbationChoice(StrEnum):
    """
    The changes a run can apply to its trials, named for what they change.
    """

    TARGET_HOLE_MOVED = "target-hole-moved"
    PIECE_SHOVED = "piece-shoved"
    PERCEIVED_POSE_OFFSET = "perceived-pose-offset"
    DETECTION_RELABELLED = "detection-relabelled"


class ExecutionChoice(StrEnum):
    """
    Where the run happens.
    """

    SIMULATED = "simulated"
    REAL = "real"

    @property
    def execution_type(self) -> ExecutionType:
        """
        The execution type a scenario is built with for this choice.
        """
        if self is ExecutionChoice.REAL:
            return ExecutionType.REAL
        return ExecutionType.SIMULATED

    @property
    def default_scene(self) -> SceneChoice:
        """
        Where the scene comes from unless the command line says otherwise: a run on the
        robot is set in the scene its camera finds, a simulated run in a built one.
        """
        if self is ExecutionChoice.REAL:
            return SceneChoice.PERCEIVED
        return SceneChoice.BUILT


class RecordingOption(StrEnum):
    """
    The command line options, as they are spelled.
    """

    SCENARIO = "--scenario"
    SCENE = "--scene"
    LAYOUT = "--layout"
    PERTURBATION = "--perturbation"
    PERTURBATION_STEP = "--perturbation-step"
    EXECUTION = "--execution"
    PIECE = "--piece"
    SEED = "--seed"
    REPETITIONS = "--repetitions"
    RECORD_BAG = "--record-bag"
    HEADLESS = "--headless"
    DATABASE_URI = "--database-uri"


DEFAULT_REPETITIONS = 1
"""
How many trials a run records unless told otherwise.
"""

DEFAULT_SEED = 0
"""
The seed a layout is drawn from unless told otherwise.
"""

DEFAULT_PIECE = MontessoriShapeCategory.CUBE
"""
The piece the script acts on and the perturbation is aimed at unless told otherwise.
"""

HOW_FAR_A_PERTURBATION_MOVES_SOMETHING = Vector3(HOW_FAR_A_MOVED_HOLE_GOES, 0.0, 0.0)
"""
The displacement every perturbation of this script that moves something applies,
straight along x.

Stated once, at the distance the moved-hole perturbation was specified at, so every
perturbation a run records was applied at one known distance.
"""

BAG_NAME_PREFIX = "montessori_episode"
"""
Leading part of the name of the bag a run records.
"""

NODE_NAME = "montessori_episode_recording"
"""
The name a run on the robot registers its node under.
"""

RECORDED_EXIT_CODE = 0
"""
What the process exits with once the episode is recorded.
"""

DATABASE_REFUSED_EXIT_CODE = 1
"""
What the process exits with when the episode's database cannot be recorded to.
"""

CHOICES_CLASH_EXIT_CODE = 2
"""
What the process exits with when the choices made on the command line contradict each
other, as a parser exits on a usage error.
"""

# %% refusing a database that would be lost with the run


@dataclass
class InMemoryDatabaseRefused(DataclassException):
    """
    Raised when the database a run would record to lives only in memory, so the episode
    would be lost with the process that recorded it.
    """

    database: ConfiguredDatabase
    """
    The database that was resolved.
    """

    def error_message(self) -> str:
        if self.database.fell_back_from is None:
            return "Refusing to record an episode to %s, which lives in memory." % (
                database_label(self.database.uri)
            )
        return (
            "Refusing to record an episode to a database in memory, stood in for one "
            "that cannot be reached: %s"
        ) % self.database.fell_back_from.error_message()

    def suggest_correction(self) -> str:
        return (
            "An episode is recorded so that it can be asked about later, which a "
            "database that dies with the run cannot serve. Start the database, or "
            "point the run at one that lasts with %s or %s (for a throwaway one, "
            "sqlite:///montessori.db)."
        ) % (RecordingOption.DATABASE_URI.value, DATABASE_URI_ENVIRONMENT_VARIABLE)


# %% refusing choices that contradict each other


@dataclass
class PerceivedSceneNeedsTheRobot(DataclassException):
    """
    Raised when the scene is to be perceived but the run is not on the robot: the world
    a perceived scene is stood in is the one the robot publishes, and no simulation can
    carry that.
    """

    execution: ExecutionChoice
    """
    Where the run was asked to happen.
    """

    def error_message(self) -> str:
        return (
            "A perceived scene is the world the robot publishes with what its camera "
            "finds stood in it, which cannot be run %s." % self.execution
        )

    def suggest_correction(self) -> str:
        return "Pass %s %s, or record a %s scene." % (
            RecordingOption.EXECUTION.value,
            ExecutionChoice.REAL,
            SceneChoice.BUILT,
        )


@dataclass
class PerceivedSceneCannotBeLaidOut(DataclassException):
    """
    Raised when a perceived scene is asked to stand its pieces by a layout: nothing here
    moves the real pieces, so where they stand is read off the look rather than chosen.
    """

    layout: LayoutChoice
    """
    The layout that was asked for.
    """

    def error_message(self) -> str:
        return "A perceived scene cannot stand its pieces %s." % self.layout

    def suggest_correction(self) -> str:
        return (
            "Leave %s out, or pass %s %s: the pieces stand where the camera finds them."
            % (
                RecordingOption.LAYOUT.value,
                RecordingOption.LAYOUT.value,
                LayoutChoice.AS_FOUND,
            )
        )


@dataclass
class BuiltSceneCannotRunOnTheRobot(DataclassException):
    """
    Raised when a run on the robot is asked for a built scene: what the person at the
    table changes reaches the world only through the robot's camera, and a built scene
    has nothing to look with.
    """

    def error_message(self) -> str:
        return (
            "A run on the robot is set in the scene its camera finds, not a built one."
        )

    def suggest_correction(self) -> str:
        return "Leave %s out, or pass %s %s." % (
            RecordingOption.SCENE.value,
            RecordingOption.SCENE.value,
            SceneChoice.PERCEIVED,
        )


# %% what one run is asked to do


@dataclass(frozen=True)
class RecordingArguments:
    """
    Everything the command line settles for one recorded episode.
    """

    scenario: ScenarioChoice
    """
    Which scenario runs.
    """

    scene: SceneChoice
    """
    Where the board and the pieces come from.
    """

    layout: LayoutChoice
    """
    How its pieces come to stand.
    """

    perturbation: Optional[PerturbationChoice]
    """
    The change applied to every trial, or None for an unperturbed run.
    """

    perturbation_step: SortingStep
    """
    The step the perturbation strikes before.
    """

    execution: ExecutionChoice
    """
    Where the run happens.
    """

    piece: MontessoriShapeCategory
    """
    The piece the script acts on and the perturbation is aimed at.
    """

    seed: int
    """
    What the layout is drawn from.
    """

    repetitions: int
    """
    How many trials are recorded.
    """

    record_bag: bool
    """
    Whether a bag of the run's topics is recorded and kept with the episode.
    """

    headless: bool
    """
    Whether the simulation goes without a viewer window.
    """

    database_uri: Optional[str]
    """
    The database asked for on the command line, or None to use the configured one.
    """

    def __post_init__(self) -> None:
        if self.scene is not SceneChoice.PERCEIVED:
            if self.execution is ExecutionChoice.REAL:
                raise BuiltSceneCannotRunOnTheRobot()
            return
        if self.execution is not ExecutionChoice.REAL:
            raise PerceivedSceneNeedsTheRobot(execution=self.execution)
        if self.layout is not LayoutChoice.AS_FOUND:
            raise PerceivedSceneCannotBeLaidOut(layout=self.layout)

    @property
    def needs_ros(self) -> bool:
        """
        Whether the run talks to ROS at all: a perceived scene comes from the robot, and
        a bag is recorded off its topics.
        """
        return self.scene is SceneChoice.PERCEIVED or self.record_bag

    @property
    def scenario_type(self) -> Type[MontessoriSortingScenario]:
        """
        The kind of scenario this run records.
        """
        if self.scenario is ScenarioChoice.ROBOT_SORTS_A_PIECE:
            return TracySortsAPiece
        if self.scenario is ScenarioChoice.PIECE_PUSHED_WHILE_IDLE:
            return TracyIsIdleWhileAPieceIsPushed
        if self.scenario is ScenarioChoice.PIECE_HELD_WHEN_ASKED:
            return TracyHoldsAPiece
        if self.scenario is ScenarioChoice.ROBOT_LOOKS_AT_THE_SCENE:
            return TracyLooksAtTheScene
        return TracyWatchesTheSceneStandStill

    def scenario_instance(
        self, world_builder: MontessoriWorldBuilder
    ) -> MontessoriSortingScenario:
        """
        The scenario this run records, set in the given scene.

        A simulated run is filmed; a run on the robot cannot be.

        :param world_builder: What builds the scene each trial runs in.
        """
        scene = dict(
            layout=self.piece_layout(),
            world_builder=world_builder,
            filmed=self.execution is ExecutionChoice.SIMULATED,
            headless=self.headless,
            execution_type=self.execution.execution_type,
        )
        if self.scenario is ScenarioChoice.ROBOT_SORTS_A_PIECE:
            return TracySortsAPiece(sorted_category=self.piece, **scene)
        if self.scenario is ScenarioChoice.PIECE_PUSHED_WHILE_IDLE:
            return TracyIsIdleWhileAPieceIsPushed(pushed_category=self.piece, **scene)
        if self.scenario is ScenarioChoice.PIECE_HELD_WHEN_ASKED:
            return TracyHoldsAPiece(held_category=self.piece, **scene)
        if self.scenario is ScenarioChoice.ROBOT_LOOKS_AT_THE_SCENE:
            return TracyLooksAtTheScene(**scene)
        return TracyWatchesTheSceneStandStill(**scene)

    def piece_layout(self) -> Layout:
        """
        How this run's pieces come to stand.
        """
        if self.layout is LayoutChoice.AS_FOUND:
            return LayoutAsFound()
        area = layout_area_on_tracys_table()
        if self.layout is LayoutChoice.NEARLY_AMBIGUOUS:
            return PieceLayout.nearly_ambiguous(
                seed=self.seed, area=area, viewpoint=WHERE_TRACY_LOOKS_FROM
            )
        return PieceLayout.randomized(seed=self.seed, area=area)

    def perturbations(self) -> List[Perturbation]:
        """
        The perturbations applied to every trial: the one asked for, or none.
        """
        if self.perturbation is None:
            return []
        return [self._perturbation_instance()]

    def _perturbation_instance(self) -> Perturbation:
        """
        The perturbation asked for, aimed at the piece the run acts on.
        """
        step = self.perturbation_step
        if self.perturbation is PerturbationChoice.TARGET_HOLE_MOVED:
            return TargetHoleMoved(
                step=step,
                category=self.piece,
                displacement=HOW_FAR_A_PERTURBATION_MOVES_SOMETHING,
            )
        if self.perturbation is PerturbationChoice.PIECE_SHOVED:
            return PieceShoved(
                step=step,
                category=self.piece,
                displacement=HOW_FAR_A_PERTURBATION_MOVES_SOMETHING,
            )
        if self.perturbation is PerturbationChoice.PERCEIVED_POSE_OFFSET:
            return PerceivedPoseOffset(
                step=step,
                category=self.piece,
                offset=HOW_FAR_A_PERTURBATION_MOVES_SOMETHING,
            )
        return DetectionRelabelled(
            step=step, category=self.piece, reported_as=another_piece_than(self.piece)
        )


def another_piece_than(piece: MontessoriShapeCategory) -> MontessoriShapeCategory:
    """
    The piece a relabelled detection reports instead: the next one of the set.

    :param piece: The piece that is actually there.
    """
    categories = list(MontessoriShapeCategory)
    return categories[(categories.index(piece) + 1) % len(categories)]


def parse_arguments(
    argument_list: Optional[Sequence[str]] = None,
) -> RecordingArguments:
    """
    Read what one run is asked to do off the command line.

    :param argument_list: Arguments to read; the process's own when omitted.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        RecordingOption.SCENARIO,
        type=ScenarioChoice,
        choices=list(ScenarioChoice),
        default=ScenarioChoice.SCENE_STANDS_STILL,
    )
    parser.add_argument(
        RecordingOption.SCENE,
        type=SceneChoice,
        choices=list(SceneChoice),
        default=None,
    )
    parser.add_argument(
        RecordingOption.LAYOUT,
        type=LayoutChoice,
        choices=list(LayoutChoice),
        default=None,
    )
    parser.add_argument(
        RecordingOption.PERTURBATION,
        type=PerturbationChoice,
        choices=list(PerturbationChoice),
        default=None,
    )
    parser.add_argument(
        RecordingOption.PERTURBATION_STEP,
        type=SortingStep,
        choices=list(SortingStep),
        default=SortingStep.SETTLE,
    )
    parser.add_argument(
        RecordingOption.EXECUTION,
        type=ExecutionChoice,
        choices=list(ExecutionChoice),
        default=ExecutionChoice.SIMULATED,
    )
    parser.add_argument(
        RecordingOption.PIECE,
        type=MontessoriShapeCategory,
        choices=list(MontessoriShapeCategory),
        default=DEFAULT_PIECE,
    )
    parser.add_argument(RecordingOption.SEED, type=int, default=DEFAULT_SEED)
    parser.add_argument(
        RecordingOption.REPETITIONS, type=int, default=DEFAULT_REPETITIONS
    )
    parser.add_argument(RecordingOption.RECORD_BAG, action="store_true")
    parser.add_argument(RecordingOption.HEADLESS, action="store_true")
    parser.add_argument(RecordingOption.DATABASE_URI, default=None)
    parsed = parser.parse_args(argument_list)
    scene = parsed.execution.default_scene if parsed.scene is None else parsed.scene
    return RecordingArguments(
        scenario=parsed.scenario,
        scene=scene,
        layout=scene.default_layout if parsed.layout is None else parsed.layout,
        perturbation=parsed.perturbation,
        perturbation_step=parsed.perturbation_step,
        execution=parsed.execution,
        piece=parsed.piece,
        seed=parsed.seed,
        repetitions=parsed.repetitions,
        record_bag=parsed.record_bag,
        headless=parsed.headless,
        database_uri=parsed.database_uri,
    )


# %% the run itself


def resolve_lasting_database(database_uri: Optional[str]) -> ResultsDatabase:
    """
    The database the run records to, insisting it outlives the run.

    :param database_uri: The database asked for on the command line, or None.
    :raises InMemoryDatabaseRefused: If the run would record to memory.
    """
    configured = ConfiguredDatabase.resolve_reachable(database_uri)
    if configured.fell_back_from is not None or is_in_memory(configured.uri):
        raise InMemoryDatabaseRefused(database=configured)
    return ResultsDatabase(uri=configured.uri)


def record_episode(arguments: RecordingArguments, episode: Episode) -> Path:
    """
    Run the scenario as asked and keep everything it leaves behind.

    :param arguments: What the run is asked to do.
    :param episode: The episode the run makes.
    :return: The directory the episode's artifacts were kept in.
    """
    database = resolve_lasting_database(arguments.database_uri)
    verify_writable(database.uri)
    artifacts = ArtifactDirectory().open_for(episode)
    recording = open_recording(database)
    bag = recorded_bag() if arguments.record_bag else contextlib.nullcontext()
    try:
        with (
            ros_running(arguments.needs_ros),
            scene_of(arguments) as world_builder,
            bag as bag_directory,
        ):
            scenario = arguments.scenario_instance(world_builder)
            run = WatchedSortingRun(
                repetitions=arguments.repetitions,
                person=PersonAtTheConsole(),
                episode=episode,
                records_trials=recording,
                artifacts=artifacts,
                film=scenario if scenario.filmed else None,
            )
            run.run(scenario, perturbations=arguments.perturbations())
    finally:
        recording.close()
    if bag_directory is not None:
        artifacts.keep_directory(bag_directory)
    return artifacts.directory


@contextlib.contextmanager
def ros_running(needed: bool) -> Iterator[None]:
    """
    Keep ROS initialised for as long as the block runs, if the run needs it at all.

    Imported here rather than at the top, so a run that needs no ROS needs none
    installed.

    :param needed: Whether the run talks to ROS.
    """
    if not needed:
        yield
        return
    import rclpy

    rclpy.init()
    try:
        yield
    finally:
        rclpy.shutdown()


@contextlib.contextmanager
def scene_of(arguments: RecordingArguments) -> Iterator[MontessoriWorldBuilder]:
    """
    What builds the scene the run is set in, for as long as the block runs: Tracy's
    table as its description builds it, or, connected to the robot for the block's
    duration, Tracy's table as its own camera finds it.

    Imported here rather than at the top, so a run whose scene is built needs no ROS.

    :param arguments: What the run is asked to do.
    """
    if arguments.scene is SceneChoice.BUILT:
        yield TracyOnItsOwnTable()
        return
    from experiments.tracy_experiments.live_tracy import LiveTracy

    with LiveTracy.connected(NODE_NAME) as tracy:
        yield TracyLookingAtItsOwnTable(
            scene=PerceivedScene(
                world=tracy.world,
                look=tracy.look,
                described_board=lab_board(),
                looks_for_board=LOOKS_FOR_THE_BOARD,
            )
        )


def episode_bag_recorder(parent_directory: Optional[str] = None) -> RosbagRecorder:
    """
    The recorder of an episode's bag: the run's topics, keeping one camera frame in :dat
    a:`~experiments.tracy_experiments.rosbag_recording.DEFAULT_KEEP_EVERY_NTH_FRAME`.

    Imported here rather than at the top, so a run that records no bag needs no ROS.

    :param parent_directory: Where the bag is placed; the recorder's own default when
        None.
    """
    from experiments.tracy_experiments.rosbag_recording import (
        DEFAULT_BAG_DIRECTORY,
        DEFAULT_KEEP_EVERY_NTH_FRAME,
        RosbagRecorder,
    )

    return RosbagRecorder.timestamped(
        BAG_NAME_PREFIX,
        DEFAULT_BAG_DIRECTORY if parent_directory is None else parent_directory,
        keep_every_nth_frame=DEFAULT_KEEP_EVERY_NTH_FRAME,
    )


@contextlib.contextmanager
def recorded_bag() -> Iterator[Path]:
    """
    Record a bag of the run's topics for as long as the block runs, and hand over the
    bag's directory once it is closed.
    """
    with episode_bag_recorder() as recorder:
        yield Path(recorder.output_directory)


def main(argument_list: Optional[Sequence[str]] = None) -> int:
    """
    Record one episode as the command line asks.

    :param argument_list: Arguments to read; the process's own when omitted.
    :return: 0 once the episode is recorded, 1 if its database cannot be recorded to, 2
        if the choices made on the command line contradict each other.
    """
    try:
        arguments = parse_arguments(argument_list)
    except (
        PerceivedSceneNeedsTheRobot,
        PerceivedSceneCannotBeLaidOut,
        BuiltSceneCannotRunOnTheRobot,
    ) as clash:
        print(clash, file=sys.stderr)
        return CHOICES_CLASH_EXIT_CODE
    episode = Episode.planned(
        arguments.scenario_type,
        arguments.execution.execution_type,
        perturbations=arguments.perturbations(),
    )
    print(episode.identifier, flush=True)
    results_database.main(list(argument_list) if argument_list is not None else None)
    try:
        kept_in = record_episode(arguments, episode)
    except (UnreachableResultsDatabase, ReadOnlyResultsDatabase) as error:
        print(error, file=sys.stderr)
        return DATABASE_REFUSED_EXIT_CODE
    print("Episode %s recorded; artifacts in %s" % (episode.identifier, kept_in))
    return RECORDED_EXIT_CODE


if __name__ == "__main__":
    sys.exit(main())

"""
Record one episode of a Montessori sorting scenario: the scenario, its layout, the
perturbation applied to it and where it runs are chosen on the command line, the run is
watched by the event monitor and asked the question set, and its trials, its video, its
transcript and its bag are kept under the episode's identifier.

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
from typing_extensions import Iterator, List, Optional, Sequence

from experiments.episodes.artifacts import ArtifactDirectory
from experiments.episodes.episode import Episode
from experiments.episodes.recording import open_recording
from experiments.montessori import results_database
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
    MontessoriSortingScenario,
    PerceivedPoseOffset,
    Perturbation,
    PieceLayout,
    PieceShoved,
    SortingStep,
    TargetHoleMoved,
    TracyHoldsAPiece,
    TracyIsIdleWhileAPieceIsPushed,
    TracySortsAPiece,
    TracyWatchesTheSceneStandStill,
)
from experiments.montessori.semantics import MontessoriShapeCategory
from experiments.montessori.watched_run import WatchedSortingRun
from experiments.scenarios.runner import ConsoleOperatorPrompt
from experiments.tracy_experiments.montessori.scene_builder import (
    TracyOnItsOwnTable,
    WHERE_TRACY_LOOKS_FROM,
    layout_area_on_tracys_table,
)

# %% what the command line offers


class ScenarioChoice(StrEnum):
    """
    The scenarios a run can record, named for what happens in them.
    """

    SCENE_STANDS_STILL = "scene-stands-still"
    ROBOT_SORTS_A_PIECE = "robot-sorts-a-piece"
    PIECE_PUSHED_WHILE_IDLE = "piece-pushed-while-idle"
    PIECE_HELD_WHEN_ASKED = "piece-held-when-asked"


class LayoutChoice(StrEnum):
    """
    How the pieces are stood on the table.
    """

    RANDOMIZED = "randomized"
    NEARLY_AMBIGUOUS = "nearly-ambiguous"


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


class RecordingOption(StrEnum):
    """
    The command line options, as they are spelled.
    """

    SCENARIO = "--scenario"
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

    layout: LayoutChoice
    """
    How its pieces are stood.
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

    def scenario_instance(self) -> MontessoriSortingScenario:
        """
        The scenario this run records, built on Tracy's own table.
        """
        scene = dict(
            layout=self.piece_layout(),
            world_builder=TracyOnItsOwnTable(),
            filmed=True,
            headless=self.headless,
            execution_type=self.execution.execution_type,
        )
        if self.scenario is ScenarioChoice.ROBOT_SORTS_A_PIECE:
            return TracySortsAPiece(sorted_category=self.piece, **scene)
        if self.scenario is ScenarioChoice.PIECE_PUSHED_WHILE_IDLE:
            return TracyIsIdleWhileAPieceIsPushed(pushed_category=self.piece, **scene)
        if self.scenario is ScenarioChoice.PIECE_HELD_WHEN_ASKED:
            return TracyHoldsAPiece(held_category=self.piece, **scene)
        return TracyWatchesTheSceneStandStill(**scene)

    def piece_layout(self) -> PieceLayout:
        """
        The layout this run stands its pieces in.
        """
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
        RecordingOption.LAYOUT,
        type=LayoutChoice,
        choices=list(LayoutChoice),
        default=LayoutChoice.RANDOMIZED,
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
    return RecordingArguments(
        scenario=parsed.scenario,
        layout=parsed.layout,
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
    scenario = arguments.scenario_instance()
    artifacts = ArtifactDirectory().open_for(episode)
    recording = open_recording(database)
    run = WatchedSortingRun(
        repetitions=arguments.repetitions,
        operator_prompt=ConsoleOperatorPrompt(),
        episode=episode,
        records_trials=recording,
        artifacts=artifacts,
        film=scenario,
    )
    bag = recorded_bag() if arguments.record_bag else contextlib.nullcontext()
    try:
        with bag as bag_directory:
            run.run(scenario, perturbations=arguments.perturbations())
    finally:
        recording.close()
    if bag_directory is not None:
        artifacts.keep_directory(bag_directory)
    return artifacts.directory


@contextlib.contextmanager
def recorded_bag() -> Iterator[Path]:
    """
    Record a bag of the run's topics for as long as the block runs, on a ROS context of
    the run's own, and hand over the bag's directory once it is closed.

    Imported here rather than at the top, so a run that records no bag needs no ROS.
    """
    import rclpy

    from experiments.tracy_experiments.rosbag_recording import RosbagRecorder

    rclpy.init()
    try:
        with RosbagRecorder.timestamped(BAG_NAME_PREFIX) as recorder:
            yield Path(recorder.output_directory)
    finally:
        rclpy.shutdown()


def main(argument_list: Optional[Sequence[str]] = None) -> int:
    """
    Record one episode as the command line asks.

    :param argument_list: Arguments to read; the process's own when omitted.
    :return: 0 once the episode is recorded, 1 if its database cannot be recorded to.
    """
    arguments = parse_arguments(argument_list)
    episode = Episode.from_run(
        arguments.scenario_instance(), perturbations=arguments.perturbations()
    )
    print(episode.identifier, flush=True)
    results_database.main(list(argument_list) if argument_list is not None else None)
    try:
        kept_in = record_episode(arguments, episode)
    except (UnreachableResultsDatabase, ReadOnlyResultsDatabase) as error:
        print(error, file=sys.stderr)
        return 1
    print("Episode %s recorded; artifacts in %s" % (episode.identifier, kept_in))
    return 0


if __name__ == "__main__":
    sys.exit(main())

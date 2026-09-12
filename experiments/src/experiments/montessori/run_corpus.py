"""
Record the whole corpus the paper's tables are computed over, and ask every episode of
it back.

One episode per scenario, layout and perturbation the corpus covers, each recorded
headless through the machinery one episode is recorded with, and each asked the long-
term-memory question set several times once the corpus stands. Asked afterwards rather
than as each episode finishes, because the questions that span the corpus are answered
from every episode there is: asking one while the corpus was still growing would answer
it from half a corpus, and asking it again later would answer it differently.

The identifier of every episode is written to a manifest as it is recorded, so a corpus
that dies halfway still names what it recorded.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from enum import StrEnum
from itertools import product
from pathlib import Path

from krrood.exceptions import DataclassException
from segmind.datastructures.events import EventWithTrackedObjects
from semantic_digital_twin.world_description.world_entity import Body
from typing_extensions import List, Optional, Protocol, Sequence, Tuple

from experiments.episodes.artifacts import configured_artifact_directory
from experiments.episodes.episode import Episode, RecordedTrial
from experiments.episodes.long_term_memory import LongTermMemory
from experiments.montessori.ask_episode import ask_episode, keep_with_the_trial
from experiments.montessori.record_episode import (
    DATABASE_REFUSED_EXIT_CODE,
    DEFAULT_PIECE,
    DEFAULT_SEED,
    ExecutionChoice,
    LayoutChoice,
    PerturbationChoice,
    RECORDED_EXIT_CODE,
    RecordingArguments,
    ScenarioChoice,
    SceneChoice,
    record_episode,
)
from experiments.montessori.results_database import (
    ReadOnlyResultsDatabase,
    ResultsDatabase,
    UnreachableResultsDatabase,
    database_label,
    resolve_lasting_database,
)
from experiments.montessori.scenarios import SortingStep
from experiments.montessori.semantics import MontessoriShapeCategory

# %% what the corpus covers

SCENARIOS_RECORDED: Tuple[ScenarioChoice, ...] = tuple(ScenarioChoice)
"""
Every scenario the corpus records, which is every one the command line offers.
"""

LAYOUTS_RECORDED: Tuple[LayoutChoice, ...] = (
    LayoutChoice.RANDOMIZED,
    LayoutChoice.PARTIAL,
    LayoutChoice.NEARLY_AMBIGUOUS,
)
"""
The layouts a built scene stands its pieces by.

:attr:`~experiments.montessori.record_episode.LayoutChoice.AS_FOUND` is not among them:
it reads where the pieces already stand, which only a scene the robot's camera finds
has to say.
"""

PERTURBATIONS_RECORDED: Tuple[Optional[PerturbationChoice], ...] = (None,) + tuple(
    PerturbationChoice
)
"""
The unperturbed run and each perturbation a run can apply, so every scenario is recorded
both undisturbed and once per way of disturbing it.
"""

DEFAULT_REPETITIONS = 3
"""
How many trials each episode of the corpus records unless told otherwise.
"""

ASKINGS_PER_QUESTION = 5
"""
How often each episode is asked the long-term-memory set.

More than once, because whether a question answered twice answers the same way is one of
the things the paper reports, and a question asked once always agrees with itself.
"""

MANIFEST_NAME = "corpus_episodes.txt"
"""
What the manifest naming every recorded episode is called, inside the directory episodes
keep their artifacts in.
"""


def default_manifest_path() -> Path:
    """
    Where the manifest goes when the command line asks for no other place: beside the
    artifacts the episodes it names keep.
    """
    return configured_artifact_directory() / MANIFEST_NAME


# %% an episode that watched nothing


@dataclass
class EpisodeWatchedNothing(DataclassException):
    """
    Raised when an episode of the corpus is to be asked about the piece it watched, but
    recorded no event naming one.
    """

    episode_identifier: str
    """
    The episode nothing was watched in.
    """

    def error_message(self) -> str:
        return (
            "Episode %s recorded no event, so there is no piece to ask it about."
            % self.episode_identifier
        )

    def suggest_correction(self) -> str:
        return (
            "The event monitor watches one piece for the whole trial, so an episode "
            "without a single event is a run whose monitor never reported. Record that "
            "episode again on its own and check what its monitor detected."
        )


# %% what the command line offers


class CorpusOption(StrEnum):
    """
    The command line options, as they are spelled.
    """

    REPETITIONS = "--repetitions"
    PIECE = "--piece"
    SEED = "--seed"
    MANIFEST = "--manifest"
    DATABASE_URI = "--database-uri"


@dataclass(frozen=True)
class CorpusArguments:
    """
    Everything the command line settles for one recorded corpus.
    """

    repetitions: int = DEFAULT_REPETITIONS
    """
    How many trials each episode of the corpus records.
    """

    piece: MontessoriShapeCategory = DEFAULT_PIECE
    """
    The piece every scenario acts on and every perturbation is aimed at.
    """

    seed: int = DEFAULT_SEED
    """
    What every layout of the corpus is drawn from, so the same corpus builds the same
    scenes.
    """

    manifest_path: Path = field(default_factory=default_manifest_path)
    """
    Where the identifiers of the recorded episodes are written.
    """

    database_uri: Optional[str] = None
    """
    The database asked for on the command line, or None to use the configured one.
    """

    scenarios: Tuple[ScenarioChoice, ...] = SCENARIOS_RECORDED
    """
    The scenarios the corpus covers.
    """

    layouts: Tuple[LayoutChoice, ...] = LAYOUTS_RECORDED
    """
    The layouts it covers.
    """

    perturbations: Tuple[Optional[PerturbationChoice], ...] = PERTURBATIONS_RECORDED
    """
    The perturbations it covers, the unperturbed run among them.
    """

    askings_per_question: int = ASKINGS_PER_QUESTION
    """
    How often each episode is asked the long-term-memory set.
    """

    def recordings(self) -> List[RecordingArguments]:
        """
        What each episode of this corpus is asked to record, one per scenario, layout
        and perturbation, in that order.
        """
        return [
            self.recording(scenario, layout, perturbation)
            for scenario, layout, perturbation in product(
                self.scenarios, self.layouts, self.perturbations
            )
        ]

    def recording(
        self,
        scenario: ScenarioChoice,
        layout: LayoutChoice,
        perturbation: Optional[PerturbationChoice],
    ) -> RecordingArguments:
        """
        What one episode of this corpus is asked to record: a built scene, run headless
        in simulation, filmed as any simulated run is.

        :param scenario: The scenario that episode runs.
        :param layout: How its pieces come to stand.
        :param perturbation: The change applied to every trial, or None for an
            unperturbed episode.
        """
        return RecordingArguments(
            scenario=scenario,
            scene=SceneChoice.BUILT,
            layout=layout,
            perturbation=perturbation,
            perturbation_step=SortingStep.SETTLE,
            execution=ExecutionChoice.SIMULATED,
            piece=self.piece,
            seed=self.seed,
            repetitions=self.repetitions,
            record_bag=False,
            headless=True,
            database_uri=self.database_uri,
        )


def parse_arguments(
    argument_list: Optional[Sequence[str]] = None,
) -> CorpusArguments:
    """
    Read what one corpus is asked to record off the command line.

    :param argument_list: Arguments to read; the process's own when omitted.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(CorpusOption.REPETITIONS, type=int, default=DEFAULT_REPETITIONS)
    parser.add_argument(
        CorpusOption.PIECE,
        type=MontessoriShapeCategory,
        choices=list(MontessoriShapeCategory),
        default=DEFAULT_PIECE,
    )
    parser.add_argument(CorpusOption.SEED, type=int, default=DEFAULT_SEED)
    parser.add_argument(
        CorpusOption.MANIFEST, type=Path, default=default_manifest_path()
    )
    parser.add_argument(CorpusOption.DATABASE_URI, default=None)
    parsed = parser.parse_args(argument_list)
    return CorpusArguments(
        repetitions=parsed.repetitions,
        piece=parsed.piece,
        seed=parsed.seed,
        manifest_path=parsed.manifest,
        database_uri=parsed.database_uri,
    )


# %% where the corpus names what it recorded


@dataclass
class EpisodeManifest:
    """
    The file naming every episode a corpus recorded, one identifier per line.
    """

    path: Path
    """
    Where the identifiers are written.
    """

    def start(self) -> None:
        """
        Begin a manifest, replacing whatever the file held before.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("")

    def append(self, episode: Episode) -> None:
        """
        Name one recorded episode, written as the episode is recorded so that a corpus
        which dies halfway still names what it got through.

        :param episode: The episode that was recorded.
        """
        with self.path.open("a") as manifest:
            manifest.write("%s\n" % episode.identifier)


# %% how an episode of the corpus is recorded


class RecordsEpisodes(Protocol):
    """
    Something that records one episode of a sorting scenario.
    """

    def record(self, arguments: RecordingArguments, episode: Episode) -> Path:
        """
        Record one episode as the given arguments ask.

        :param arguments: What that episode is asked to record.
        :param episode: The episode being recorded.
        :return: The directory the episode's artifacts were kept in.
        """


@dataclass
class SimulatedEpisodeRecorder:
    """
    Records each episode by running its scenario, the way the single-episode script
    does.
    """

    def record(self, arguments: RecordingArguments, episode: Episode) -> Path:
        """
        Run the scenario and keep everything it leaves behind.

        :param arguments: What that episode is asked to record.
        :param episode: The episode being recorded.
        :return: The directory the episode's artifacts were kept in.
        """
        return record_episode(arguments, episode)


# %% the corpus itself


@dataclass
class RecordedCorpus:
    """
    Every episode of one corpus, recorded and then asked the long-term-memory set.
    """

    arguments: CorpusArguments
    """
    What this corpus is asked to record.
    """

    database: ResultsDatabase
    """
    The database every episode is recorded to and asked back from.
    """

    recorder: RecordsEpisodes = field(default_factory=SimulatedEpisodeRecorder)
    """
    What records each episode.
    """

    @property
    def memory(self) -> LongTermMemory:
        """
        The episodes recorded so far, as the questions reach them.
        """
        return LongTermMemory(self.database)

    def record(self) -> List[Episode]:
        """
        Record every episode of this corpus, naming each in the manifest as it is
        recorded.

        :return: The episodes, in the order they were recorded.
        """
        manifest = EpisodeManifest(path=self.arguments.manifest_path)
        manifest.start()
        episodes: List[Episode] = []
        for recording in self.arguments.recordings():
            episode = Episode.planned(
                recording.scenario_type,
                recording.execution.execution_type,
                perturbations=recording.perturbations(),
            )
            print(episode.identifier, flush=True)
            self.recorder.record(recording, episode)
            manifest.append(episode)
            episodes.append(episode)
        return episodes

    def ask(self, episodes: Sequence[Episode]) -> int:
        """
        Ask every recorded episode the long-term-memory set as often as this corpus
        asks, keeping every scored row with the trial it asked about.

        :param episodes: The episodes to ask, which this corpus has recorded.
        :return: How many scored rows were kept.
        """
        kept = 0
        for episode in episodes:
            object_name = self.object_watched_in(episode)
            for _ in range(self.arguments.askings_per_question):
                rows = ask_episode(self.memory, episode.identifier, object_name)
                keep_with_the_trial(self.database, episode.identifier, rows)
                kept += len(rows)
        return kept

    def object_watched_in(self, episode: Episode) -> str:
        """
        What the piece one episode's monitor watched was called, which is what the
        questions about one object ask that episode about.

        :param episode: The episode to read.
        :raises EpisodeWatchedNothing: If it recorded no event naming a piece.
        """
        for trial in self.memory.recall_trials(episode.identifier):
            watched = self.watched_object(trial)
            if watched is not None:
                return watched.name.name
        raise EpisodeWatchedNothing(episode_identifier=episode.identifier)

    @staticmethod
    def watched_object(trial: RecordedTrial) -> Optional[Body]:
        """
        The object one trial's events are about.

        The monitor watches one piece for the whole trial, so the first event that names
        an object names the watched one.

        :param trial: The recorded trial to read.
        :return: The watched object, or None if the trial recorded no event naming one.
        """
        for tick in trial.ticks:
            for event in tick.events:
                if isinstance(event, EventWithTrackedObjects):
                    return event.tracked_object
        return None


# %% the whole command


def main(argument_list: Optional[Sequence[str]] = None) -> int:
    """
    Record the corpus the command line asks for and ask every episode of it back.

    :param argument_list: Arguments to read; the process's own when omitted.
    :return: 0 once the corpus is recorded and asked, 1 if its database cannot be
        recorded to.
    """
    arguments = parse_arguments(argument_list)
    try:
        database = resolve_lasting_database(arguments.database_uri)
    except (UnreachableResultsDatabase, ReadOnlyResultsDatabase) as error:
        print(error, file=sys.stderr)
        return DATABASE_REFUSED_EXIT_CODE
    print("Recording the corpus to %s." % database_label(database.uri))
    corpus = RecordedCorpus(arguments=arguments, database=database)
    episodes = corpus.record()
    kept = corpus.ask(episodes)
    print(
        "Recorded %d episode(s), named in %s, and kept %d scored row(s)."
        % (len(episodes), arguments.manifest_path, kept)
    )
    return RECORDED_EXIT_CODE


if __name__ == "__main__":
    sys.exit(main())

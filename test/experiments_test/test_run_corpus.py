"""
Recording a corpus of episodes and asking every one of them back.

The corpus's own work is which episodes it covers, that each is named in the manifest,
and that every episode is asked the long-term-memory set as often as the corpus asks --
not the simulation each episode runs, which the single-episode script's own tests cover.
So the episodes here are recorded by a recorder that keeps a trial without simulating
anything, and the corpus is recorded to a database in memory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest
from segmind.datastructures.events import PickUpEvent, TranslationEvent
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.world_description.world_entity import Body
from typing_extensions import List

from experiments.episodes.episode import Episode, RecordedTrial, Tick
from experiments.episodes.long_term_memory import LongTermMemory
from experiments.episodes.recording import RecordsTrials, open_recording
from experiments.montessori.record_episode import (
    ExecutionChoice,
    LayoutChoice,
    PerturbationChoice,
    RecordingArguments,
    SceneChoice,
    ScenarioChoice,
)
from experiments.montessori.results_database import (
    IN_MEMORY_DATABASE_URI,
    ResultsDatabase,
)
from experiments.montessori.run_corpus import (
    ASKINGS_PER_QUESTION,
    CorpusArguments,
    CorpusOption,
    DEFAULT_REPETITIONS,
    EpisodeManifest,
    EpisodeWatchedNothing,
    LAYOUTS_RECORDED,
    PERTURBATIONS_RECORDED,
    RecordedCorpus,
    SCENARIOS_RECORDED,
    parse_arguments,
)
from experiments.scenarios.trial import TrialOutcome

WATCHED_PIECE = "cube"
"""
The piece every stood-in episode's monitor watches, which is what the questions about
one object then ask each episode about.
"""

TRIAL_DURATION = 3.0
"""
How long each stood-in trial took, which none of these questions reads.
"""

FIRST_TICK = 1.0
"""
When each stood-in trial's only tick was taken, in seconds from the start of the trial.
"""

ONE_REPETITION = 1
"""
How many trials each episode of the corpus under test records.
"""

TWO_SCENARIOS = SCENARIOS_RECORDED[:2]
"""
The two scenarios the corpus under test covers, which is enough for it to cover more
than one.
"""

ONE_LAYOUT = (LayoutChoice.PARTIAL,)
"""
The one layout it stands its pieces by.
"""

# %% a recorder that keeps a trial without simulating one


@dataclass
class EpisodeRecorderWithoutASimulation:
    """
    Records each episode as trials that watched one piece move and be picked up, in
    place of the simulation the real recorder runs.
    """

    records_trials: RecordsTrials
    """
    Where each stood-in trial goes.
    """

    directory: Path
    """
    What stands in for the directory an episode's artifacts are kept in.
    """

    recorded: List[RecordingArguments] = field(default_factory=list)
    """
    What each episode was asked to record, in the order the corpus asked.
    """

    def record(self, arguments: RecordingArguments, episode: Episode) -> Path:
        """
        Keep one trial per repetition the arguments ask for.

        :param arguments: What that episode was asked to record.
        :param episode: The episode being recorded.
        :return: Where its artifacts would have been kept.
        """
        self.recorded.append(arguments)
        watched = Body(name=PrefixedName(WATCHED_PIECE))
        for _ in range(arguments.repetitions):
            self.records_trials.record(
                RecordedTrial(
                    episode=episode,
                    outcome=TrialOutcome.SUCCEEDED,
                    duration=TRIAL_DURATION,
                    ticks=[
                        Tick(
                            moment=FIRST_TICK,
                            events=[
                                TranslationEvent(tracked_object=watched),
                                PickUpEvent(tracked_object=watched),
                            ],
                        )
                    ],
                )
            )
        return self.directory


# %% the corpus under test


@pytest.fixture()
def results_database() -> ResultsDatabase:
    """
    A results database of this test's own, living in memory: one connection is shared
    across it, so what the corpus records is what the questions then read.
    """
    return ResultsDatabase(uri=IN_MEMORY_DATABASE_URI)


@pytest.fixture()
def corpus_arguments(tmp_path) -> CorpusArguments:
    """
    Two scenarios, one layout and every perturbation, recorded once each.
    """
    return CorpusArguments(
        repetitions=ONE_REPETITION,
        manifest_path=tmp_path / "corpus_episodes.txt",
        database_uri=IN_MEMORY_DATABASE_URI,
        scenarios=TWO_SCENARIOS,
        layouts=ONE_LAYOUT,
    )


@pytest.fixture()
def corpus(
    corpus_arguments: CorpusArguments, results_database: ResultsDatabase, tmp_path
) -> RecordedCorpus:
    """
    That corpus, recorded by a recorder that simulates nothing.
    """
    return RecordedCorpus(
        arguments=corpus_arguments,
        database=results_database,
        recorder=EpisodeRecorderWithoutASimulation(
            records_trials=open_recording(results_database),
            directory=tmp_path / "artifacts",
        ),
    )


# %% which episodes the corpus covers


def test_the_paper_corpus_covers_every_scenario_layout_and_perturbation():
    arguments = CorpusArguments()

    recordings = arguments.recordings()

    assert len(recordings) == len(SCENARIOS_RECORDED) * len(LAYOUTS_RECORDED) * len(
        PERTURBATIONS_RECORDED
    )
    assert {recording.scenario for recording in recordings} == set(SCENARIOS_RECORDED)
    assert {recording.layout for recording in recordings} == set(LAYOUTS_RECORDED)
    assert {recording.perturbation for recording in recordings} == set(
        PERTURBATIONS_RECORDED
    )


def test_an_unperturbed_episode_is_recorded_beside_the_perturbed_ones():
    assert None in PERTURBATIONS_RECORDED
    assert set(PERTURBATIONS_RECORDED) - {None} == set(PerturbationChoice)


def test_every_episode_of_the_corpus_is_a_built_scene_run_headless():
    for recording in CorpusArguments().recordings():
        assert recording.scene is SceneChoice.BUILT
        assert recording.execution is ExecutionChoice.SIMULATED
        assert recording.headless is True
        assert recording.record_bag is False


def test_the_corpus_records_as_many_trials_per_episode_as_it_is_asked_for(
    corpus: RecordedCorpus, corpus_arguments: CorpusArguments
):
    corpus.record()

    assert {recording.repetitions for recording in corpus.recorder.recorded} == {
        ONE_REPETITION
    }
    assert len(corpus.recorder.recorded) == len(corpus_arguments.recordings())


# %% the manifest


def test_every_recorded_episode_is_named_in_the_manifest(
    corpus: RecordedCorpus, corpus_arguments: CorpusArguments
):
    episodes = corpus.record()

    assert corpus_arguments.manifest_path.read_text().split() == [
        episode.identifier for episode in episodes
    ]


def test_a_manifest_replaces_what_it_held_before(tmp_path):
    manifest = EpisodeManifest(path=tmp_path / "corpus_episodes.txt")
    manifest.path.write_text("an-episode-of-an-earlier-corpus\n")

    manifest.start()

    assert manifest.path.read_text() == ""


# %% asking every episode back


def test_each_episode_is_asked_every_question_once_per_asking(corpus: RecordedCorpus):
    episodes = corpus.record()

    kept = corpus.ask(episodes)

    memory = LongTermMemory(corpus.database)
    for episode in episodes:
        [trial] = memory.recall_trials(episode.identifier)
        askings = {}
        for query in trial.queries:
            askings.setdefault(query.text, []).append(query)
        assert askings
        assert {len(asked) for asked in askings.values()} == {ASKINGS_PER_QUESTION}
    assert kept == sum(
        len(memory.recall_trials(episode.identifier)[0].queries) for episode in episodes
    )


def test_every_kept_row_is_scored_against_the_frozen_set(corpus: RecordedCorpus):
    episodes = corpus.record()

    corpus.ask(episodes)

    memory = LongTermMemory(corpus.database)
    for episode in episodes:
        [trial] = memory.recall_trials(episode.identifier)
        assert all(query.answered_correctly is not None for query in trial.queries)


def test_the_questions_about_one_object_ask_about_the_watched_piece(
    corpus: RecordedCorpus,
):
    [episode, *rest] = corpus.record()

    assert corpus.object_watched_in(episode) == WATCHED_PIECE


def test_an_episode_that_watched_nothing_cannot_be_asked_about_a_piece(
    corpus: RecordedCorpus, results_database: ResultsDatabase
):
    episode = Episode.planned(
        CorpusArguments().recordings()[0].scenario_type,
        ExecutionChoice.SIMULATED.execution_type,
    )
    recording = open_recording(results_database)
    recording.record(
        RecordedTrial(
            episode=episode, outcome=TrialOutcome.SUCCEEDED, duration=TRIAL_DURATION
        )
    )

    with pytest.raises(EpisodeWatchedNothing):
        corpus.object_watched_in(episode)


# %% the command line


def test_the_corpus_records_three_trials_per_episode_unless_told_otherwise():
    assert parse_arguments([]).repetitions == DEFAULT_REPETITIONS


def test_the_repetitions_and_the_manifest_are_read(tmp_path):
    arguments = parse_arguments(
        [
            CorpusOption.REPETITIONS,
            str(ONE_REPETITION),
            CorpusOption.MANIFEST,
            str(tmp_path / "named_here.txt"),
        ]
    )

    assert arguments.repetitions == ONE_REPETITION
    assert arguments.manifest_path == tmp_path / "named_here.txt"


def test_the_repetitions_asked_for_reach_every_episode():
    arguments = parse_arguments([CorpusOption.REPETITIONS, str(ONE_REPETITION)])

    assert {recording.repetitions for recording in arguments.recordings()} == {
        ONE_REPETITION
    }

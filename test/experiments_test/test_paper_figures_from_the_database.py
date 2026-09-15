"""
The paper's tables regenerated from the recorded episodes rather than from the trials a
run is still holding.

The item's claim is that one script regenerates every table from the episode database,
which is only true if the corpus recalled from it says exactly what the corpus that was
recorded said.
"""

from __future__ import annotations

import pytest

from experiments.episodes.episode import RecordedTrial
from experiments.episodes.long_term_memory import LongTermMemory
from experiments.episodes.recording import open_recording
from experiments.montessori.results_database import ResultsDatabase
from experiments.paper.figure import FigureName
from experiments.paper.figure_set import FigureSet

from .test_paper_figures import recorded_corpus


@pytest.fixture()
def results_database(tmp_path) -> ResultsDatabase:
    """
    A results database of this test's own, on disk so recording and recalling reach it
    through sessions of their own.
    """
    return ResultsDatabase(uri="sqlite:///%s" % (tmp_path / "results.db"))


@pytest.fixture()
def recorded_trials() -> list[RecordedTrial]:
    """
    The corpus, as the run that made it still holds it.
    """
    return recorded_corpus()


@pytest.fixture()
def recalled_trials(results_database, recorded_trials) -> list[RecordedTrial]:
    """
    The same corpus, recorded the way a run records it and read back out again.
    """
    recording = open_recording(results_database)
    for trial in recorded_trials:
        recording.record(trial)
    recording.close()
    return LongTermMemory(results_database).recall_every_trial()


# %% the corpus itself survives the round trip


def test_every_recorded_trial_is_recalled(recalled_trials, recorded_trials):
    """
    A table over part of the corpus is a table of the wrong numbers, so recalling has to
    reach every episode's trials rather than one episode's.
    """
    assert len(recalled_trials) == len(recorded_trials)


# %% every table says the same thing over either corpus


@pytest.mark.parametrize("figure_name", list(FigureName))
def test_a_table_regenerated_from_the_database_says_what_the_run_said(
    figure_name, recalled_trials, recorded_trials
):
    """
    Every figure is computed from what an episode recorded, so what the database gives
    back has to carry everything the figure reads: the conditions of the run, the
    outcome of each trial, the failures each attempt predicted and observed, and the
    latency and routing of each query.
    """
    figure = FigureSet.for_the_paper().figure_named(figure_name)

    assert figure.render(recalled_trials) == figure.render(recorded_trials)


def test_the_rows_behind_a_table_survive_the_round_trip(
    recalled_trials, recorded_trials, tmp_path
):
    """
    The manifest is what makes a number in the paper traceable, so it has to be the same
    manifest whichever corpus the table was computed from.
    """
    figure = FigureSet.for_the_paper().figure_named(
        FigureName.FAILURE_TYPE_BY_CONDITION
    )

    from_the_database = figure.write(recalled_trials, tmp_path / "recalled")
    from_the_run = figure.write(recorded_trials, tmp_path / "recorded")

    assert (
        from_the_database.row_manifest_path.read_text()
        == from_the_run.row_manifest_path.read_text()
    )

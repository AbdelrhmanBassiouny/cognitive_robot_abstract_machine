"""
The command that takes one search a step, and leaves it to be read back.

Each call is a decision read on its own: the state lives in the document rather than in
the process, so a caller that wants to wait asks again. What a concluded search produces
is the same finding a local one does, reported to the same pull request and blocking the
branch with the same label.
"""

from __future__ import annotations

import json
from pathlib import Path

import bastler.integration_failure
from bastler.integration_exit_codes import IntegrationExitCode
from bastler.integration_localisation import Localisation, LocalisationStage

from .test_maintenance import (
    ForkCheckout,
    fork_checkout,  # noqa: F401  (imported so pytest finds the fixture by name)
)

from .integration_fixtures import FIRST_TIP, SECOND_TIP
from .localisation_fixtures import (
    A_LIBRARY,
    LocalisingRun,
    RecordingFork,
    a_failing_check,
    a_run,
    assemble,
    check_name_for,
    locate,
    published,
    three_tips,
)


def test_a_candidate_whose_failures_name_no_library_is_answered_rather_than_probed(
    fork_checkout: ForkCheckout, tmp_path: Path
):
    """
    A tooling check is already localised by the local search - faster, and before a build
    is pushed - and a check that is a property of one tree is not about a combination at
    all. Probing either would spend a round of matrix runs to say nothing.
    """
    fork = RecordingFork(checks=[a_failing_check("test_claude_dev_tooling")])
    run = LocalisingRun(fork_checkout, three_tips(fork_checkout), fork)

    status = locate(run, tmp_path / "state.json")

    assert status is IntegrationExitCode.NO_LIBRARY_CHECK_FAILED
    assert fork.dispatched == []
    assert not (tmp_path / "state.json").exists()


def test_the_first_call_publishes_the_prefixes_and_leaves_the_search_to_be_read_back(
    fork_checkout: ForkCheckout, tmp_path: Path
):
    """
    A dispatch is only the start of a probe, so the first call has nothing to conclude
    from - it leaves the round in the document a later call picks up, and a status saying
    to ask again.
    """
    fork = RecordingFork(checks=[a_failing_check(check_name_for(A_LIBRARY))])
    run = LocalisingRun(fork_checkout, three_tips(fork_checkout), fork)
    state = tmp_path / "state.json"

    status = locate(run, state)

    assert status is IntegrationExitCode.PROBES_STILL_RUNNING
    assert len(fork.dispatched) == 3
    assert Localisation.from_json(json.loads(state.read_text())).library == A_LIBRARY


def test_a_prefix_round_that_answers_opens_the_narrowing_round(
    fork_checkout: ForkCheckout, tmp_path: Path
):
    """
    Which earlier tip the suspect fails against alone is what the report claims when it
    names one - and claims the absence of when it names none, so the round that settles
    it is opened rather than skipped.
    """
    fork = RecordingFork(checks=[a_failing_check(check_name_for(A_LIBRARY))])
    run = LocalisingRun(fork_checkout, three_tips(fork_checkout), fork)
    state = tmp_path / "state.json"
    locate(run, state)
    prefixes = Localisation.from_json(json.loads(state.read_text())).probes
    fork.runs.extend(
        [
            a_run(prefixes[0].branch),
            a_run(prefixes[1].branch, conclusion="failure"),
            a_run(prefixes[2].branch, conclusion="failure"),
        ]
    )
    fork.dispatched.clear()

    status = locate(run, state)

    assert status is IntegrationExitCode.PROBES_STILL_RUNNING
    assert Localisation.from_json(json.loads(state.read_text())).stage is (
        LocalisationStage.NARROWING
    )
    assert len(fork.dispatched) == 1


def test_a_concluded_search_blocks_the_branch_in_the_same_words_a_local_one_does(
    fork_checkout: ForkCheckout, tmp_path: Path
):
    """
    What a localisation finds is the same kind of thing either way, so it produces the.

    same finding, reports it to the same pull request, and holds the branch out of
    promotion with the same label - there is one place that decides what happens to a
    branch that breaks another.
    """
    fork = RecordingFork(checks=[a_failing_check(check_name_for(A_LIBRARY))])
    run = LocalisingRun(fork_checkout, three_tips(fork_checkout), fork)
    state = tmp_path / "state.json"
    locate(run, state)
    prefixes = Localisation.from_json(json.loads(state.read_text())).probes
    fork.runs.extend(
        [
            a_run(prefixes[0].branch),
            a_run(prefixes[1].branch, conclusion="failure"),
            a_run(prefixes[2].branch, conclusion="failure"),
        ]
    )
    locate(run, state)
    narrowing = Localisation.from_json(json.loads(state.read_text())).probes
    fork.runs.append(a_run(narrowing[0].branch, conclusion="failure"))

    status = locate(run, state)

    assert status is IntegrationExitCode.TESTS_FAILED
    assert fork.comments[0].body.startswith(bastler.integration_failure.FAILURE_COMMENT_PREFIX)
    assert SECOND_TIP in fork.comments[0].body and FIRST_TIP in fork.comments[0].body
    assert not state.exists()
    assert published(fork_checkout, prefixes + narrowing) == []


def test_the_two_rounds_of_one_search_never_publish_under_the_same_name(
    fork_checkout: ForkCheckout,
):
    """
    Both rounds are opened by calls that can land in the same second, and a narrowing.

    probe reusing a prefix probe's name would be answered by the run that judged a
    different tree - the search would read its own stale answer as this round's.
    """
    assembly = assemble(fork_checkout, three_tips(fork_checkout))

    assert assembly.branch_name(LocalisationStage.PREFIXES, 0) != assembly.branch_name(
        LocalisationStage.NARROWING, 0
    )

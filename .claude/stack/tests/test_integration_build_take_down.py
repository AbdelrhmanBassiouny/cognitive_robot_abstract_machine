"""
What becomes of a build branch once nothing is judging it.

A build is assembled onto a branch of its own so a candidate has something to be opened
against, and publishing drops that branch because the pointer then holds the same
commit. Every other outcome left one behind - eight had accumulated on the fork by the
time anyone counted - so the rule is here rather than on the one path that already got
it right.
"""

from __future__ import annotations

import argparse
import json

import pytest

from git_commands import BranchPublication, ProposedPush

from integration_candidate_commands import TakeDownUnreferencedBuildsCommand
from integration_constants import POINTER_BRANCH, PROBE_BRANCH_PREFIX, ReportKey
from integration_exit_codes import IntegrationExitCode

from integration_fixtures import A_BUILD_BRANCH, RunAgainstAGivenFork
from test_integration_verdict import RecordingCandidates, an_open_pull_request
from test_maintenance import (
    ForkCheckout,
    UPSTREAM_BASE,
    fork_checkout,  # noqa: F401  (imported so pytest finds the fixture by name)
    make_configuration,
)

ANOTHER_BUILD_BRANCH = "integration-20260811-090000"
"""
A second build, so a test can say which of two was taken down.
"""

A_PROBE_BRANCH = f"{PROBE_BRANCH_PREFIX}20260810-120000"
"""
A localisation's own published tree, which opens with the pointer's name and is not a
build.
"""

A_CANDIDATE_NUMBER = 213
"""
The pull request judging whichever build a test says is still being judged.
"""

A_HEAD = "aaaa"
"""
What a judged build's branch points at, which the take-down never reads.
"""


def publish_branch(checkout: ForkCheckout, branch: str) -> None:
    """
    :param checkout: The checkout to publish from.
    :param branch: The branch to put on the fork, pointing at the base.
    """
    checkout.run_git("branch", "--force", branch, UPSTREAM_BASE)
    checkout.git.push(
        ProposedPush(
            remote="origin", publication=BranchPublication.under_its_own_name(branch)
        )
    ).raise_if_failed()


def take_down(checkout: ForkCheckout, fork: RecordingCandidates) -> None:
    """
    Run one take-down, failing the test if it did not answer success.

    :param checkout: The checkout holding the fork remote.
    :param fork: The open pull requests to judge the published branches against.
    """
    run = RunAgainstAGivenFork(
        configuration=make_configuration(), git=checkout.git, given=fork
    )
    status = TakeDownUnreferencedBuildsCommand().run(run, argparse.Namespace(json=True))
    assert status is IntegrationExitCode.SUCCESS


def branches_left(checkout: ForkCheckout) -> set[str]:
    """
    :param checkout: The checkout to ask the fork through.
    :return: Every branch on the fork opening with the pointer's own name.
    """
    return set(checkout.git.remote_branch_names("origin", f"{POINTER_BRANCH}*"))


def reported(captured: pytest.CaptureFixture) -> list[str]:
    """
    :param captured: What the run printed.
    :return: The branches its own report says it took down.
    """
    return json.loads(captured.readouterr().out)[ReportKey.TAKEN_DOWN]


# %% which builds a run takes down


def test_a_build_no_open_pull_request_refers_to_is_taken_down(
    fork_checkout: ForkCheckout, capsys: pytest.CaptureFixture
):
    """
    The defect this closes: a candidate closed without publishing left its build on the
    fork for good, and a rebuild runs four times a day.
    """
    publish_branch(fork_checkout, A_BUILD_BRANCH)

    take_down(fork_checkout, RecordingCandidates())

    assert reported(capsys) == [A_BUILD_BRANCH]
    assert branches_left(fork_checkout) == set()


def test_the_build_a_candidate_is_still_judging_is_kept(
    fork_checkout: ForkCheckout, capsys: pytest.CaptureFixture
):
    """
    A rebuild takes down what earlier ones left before settling the candidate it
    inherited, so the build that candidate is about is published at that moment.
    """
    publish_branch(fork_checkout, A_BUILD_BRANCH)
    judging = RecordingCandidates(
        pull_requests=[
            an_open_pull_request(
                A_CANDIDATE_NUMBER, A_BUILD_BRANCH, POINTER_BRANCH, A_HEAD
            )
        ]
    )

    take_down(fork_checkout, judging)

    assert reported(capsys) == []
    assert branches_left(fork_checkout) == {A_BUILD_BRANCH}


def test_a_build_is_told_from_another_by_the_pull_request_rather_than_by_age(
    fork_checkout: ForkCheckout, capsys: pytest.CaptureFixture
):
    """
    What makes a build worth keeping is something still reading it - a candidate, or a
    filtered build somebody asked for and is working from - and neither is a matter of
    which was assembled last.
    """
    publish_branch(fork_checkout, A_BUILD_BRANCH)
    publish_branch(fork_checkout, ANOTHER_BUILD_BRANCH)
    judging = RecordingCandidates(
        pull_requests=[
            an_open_pull_request(
                A_CANDIDATE_NUMBER, ANOTHER_BUILD_BRANCH, POINTER_BRANCH, A_HEAD
            )
        ]
    )

    take_down(fork_checkout, judging)

    assert reported(capsys) == [A_BUILD_BRANCH]
    assert branches_left(fork_checkout) == {ANOTHER_BUILD_BRANCH}


def test_a_probe_is_not_a_build_and_is_left_where_it_is(
    fork_checkout: ForkCheckout, capsys: pytest.CaptureFixture
):
    """
    A probe's branch opens with the pointer's own name too, and a search still running
    is what would lose its trees - a localisation takes its own down when it concludes.
    """
    publish_branch(fork_checkout, A_PROBE_BRANCH)

    take_down(fork_checkout, RecordingCandidates())

    assert reported(capsys) == []
    assert branches_left(fork_checkout) == {A_PROBE_BRANCH}


def test_a_run_with_nothing_to_take_down_reports_that_rather_than_failing(
    fork_checkout: ForkCheckout, capsys: pytest.CaptureFixture
):
    """
    A rebuild carries on past this, so a fork already tidy has to be an answer rather
    than a status somebody has to look at.
    """
    take_down(fork_checkout, RecordingCandidates())

    assert reported(capsys) == []

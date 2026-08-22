"""
Integration tests for fast-forward-default-branch.sh, the session-start step that keeps
the base every session starts from level with the upstream repository the fork tracks.

The defect it exists for: a fork's default branch drifts behind its upstream, every
session is cloned from it, and the whole session plans and implements against a base
that is already stale.

The three copies of the default branch these run against - this clone's, the fork's and
the upstream's - are built by :mod:`forked_scratch_repository`, so the hook performs
real fetches and pushes with no network access.
"""

from __future__ import annotations

import subprocess

import pytest

from forked_scratch_repository import (
    DEFAULT_BRANCH,
    FORK_REMOTE,
    ForkedScratchRepository,
    SHARED_FILE,
    STACK_CONFIGURATION_PATH,
    UPSTREAM_REPOSITORY,
)
from scratch_repository import ScratchRepository
from session_start_summary import SummaryMessage, summary_message, summary_value

SUMMARY_LABEL = "default branch"

FOLLOW_UP_ROW_INDENT = "    "

COMMITS_THE_UPSTREAM_IS_AHEAD = 3


def reported_outcome(result: subprocess.CompletedProcess[str]) -> str:
    """
    Read the outcome the hook reports, which session-start.sh prints as its summary
    line's value.

    :param result: The finished hook process.
    :return: The first line of its output.
    """
    return result.stdout.splitlines()[0]


def follow_up_rows(result: subprocess.CompletedProcess[str]) -> list[str]:
    """
    Read the indented rows the hook prints under its outcome, naming what is left for
    the session to do.

    :param result: The finished hook process.
    :return: The rows, with their indent stripped.
    """
    return [
        row.removeprefix(FOLLOW_UP_ROW_INDENT) for row in result.stdout.splitlines()[1:]
    ]


def fork_pushed_row() -> str:
    """
    :return: The row reporting that the fork's copy of the default branch was behind and
        has been pushed.
    """
    return summary_message(SummaryMessage.FORK_PUSHED, FORK_REMOTE)


def current_branch_behind_row(commit_count: int) -> str:
    """
    :param commit_count: How far behind the default branch the checked-out branch is.
    :return: The row reporting it.
    """
    return summary_message(
        SummaryMessage.CURRENT_BRANCH_BEHIND, DEFAULT_BRANCH, str(commit_count)
    )


@pytest.fixture
def forked_repository(scratch_repository: ScratchRepository) -> ForkedScratchRepository:
    """
    A scratch clone of a fork whose default branch, fork and upstream all match.

    :param scratch_repository: The initialized scratch repository and notes remote.
    :return: The laid-out fork.
    """
    return ForkedScratchRepository.laid_out_in(scratch_repository)


# %% a default branch behind its upstream


def test_fast_forwards_the_default_branch_to_the_upstream_tip(
    forked_repository: ForkedScratchRepository,
):
    upstream_tip = forked_repository.advance_upstream(COMMITS_THE_UPSTREAM_IS_AHEAD)

    result = forked_repository.run_hook()

    assert result.returncode == 0, result.stderr
    assert forked_repository.local_default_branch_tip() == upstream_tip


def test_pushes_the_fast_forwarded_default_branch_to_the_fork(
    forked_repository: ForkedScratchRepository,
):
    upstream_tip = forked_repository.advance_upstream(COMMITS_THE_UPSTREAM_IS_AHEAD)

    result = forked_repository.run_hook()

    assert forked_repository.fork.branch_tip(DEFAULT_BRANCH) == upstream_tip
    assert fork_pushed_row() in follow_up_rows(result)


def test_reports_how_far_the_default_branch_was_behind(
    forked_repository: ForkedScratchRepository,
):
    forked_repository.advance_upstream(COMMITS_THE_UPSTREAM_IS_AHEAD)

    result = forked_repository.run_hook()

    assert reported_outcome(result) == summary_message(
        SummaryMessage.DEFAULT_BRANCH_FAST_FORWARDED,
        DEFAULT_BRANCH,
        str(COMMITS_THE_UPSTREAM_IS_AHEAD),
        UPSTREAM_REPOSITORY,
    )


def test_reports_how_far_the_current_branch_is_behind_the_moved_default_branch(
    forked_repository: ForkedScratchRepository,
):
    forked_repository.advance_upstream(COMMITS_THE_UPSTREAM_IS_AHEAD)

    result = forked_repository.run_hook()

    assert current_branch_behind_row(COMMITS_THE_UPSTREAM_IS_AHEAD) in follow_up_rows(
        result
    )


def test_fast_forwards_the_default_branch_while_it_is_checked_out(
    forked_repository: ForkedScratchRepository,
):
    upstream_tip = forked_repository.advance_upstream(COMMITS_THE_UPSTREAM_IS_AHEAD)
    forked_repository.check_out_default_branch()

    result = forked_repository.run_hook()

    assert result.returncode == 0, result.stderr
    assert forked_repository.checked_out_commit() == upstream_tip


def test_says_nothing_about_the_current_branch_when_it_is_the_default_branch(
    forked_repository: ForkedScratchRepository,
):
    forked_repository.advance_upstream(COMMITS_THE_UPSTREAM_IS_AHEAD)
    forked_repository.check_out_default_branch()

    result = forked_repository.run_hook()

    assert follow_up_rows(result) == [fork_pushed_row()]


def test_fetches_from_the_upstream_remote_when_the_clone_already_has_one(
    forked_repository: ForkedScratchRepository,
):
    upstream_tip = forked_repository.advance_upstream(COMMITS_THE_UPSTREAM_IS_AHEAD)
    forked_repository.reach_the_upstream_only_through_its_remote()

    result = forked_repository.run_hook()

    assert result.returncode == 0, result.stderr
    assert forked_repository.local_default_branch_tip() == upstream_tip


# %% a default branch that needs nothing done to it


def test_reports_the_default_branch_as_current_when_nothing_has_moved(
    forked_repository: ForkedScratchRepository,
):
    result = forked_repository.run_hook()

    assert result.returncode == 0, result.stderr
    assert reported_outcome(result) == summary_message(
        SummaryMessage.DEFAULT_BRANCH_CURRENT, DEFAULT_BRANCH, UPSTREAM_REPOSITORY
    )


def test_leaves_nothing_to_do_when_nothing_has_moved(
    forked_repository: ForkedScratchRepository,
):
    result = forked_repository.run_hook()

    assert follow_up_rows(result) == []


# %% a fork left behind by an earlier session


def test_pushes_to_the_fork_when_this_clone_is_already_current(
    forked_repository: ForkedScratchRepository,
):
    upstream_tip = forked_repository.advance_upstream(COMMITS_THE_UPSTREAM_IS_AHEAD)
    forked_repository.set_local_default_branch_to(upstream_tip)

    result = forked_repository.run_hook()

    assert forked_repository.fork.branch_tip(DEFAULT_BRANCH) == upstream_tip
    assert reported_outcome(result) == summary_message(
        SummaryMessage.DEFAULT_BRANCH_CURRENT, DEFAULT_BRANCH, UPSTREAM_REPOSITORY
    )
    assert fork_pushed_row() in follow_up_rows(result)


# %% states a fast-forward must not resolve


def test_leaves_a_diverged_default_branch_alone(
    forked_repository: ForkedScratchRepository,
):
    forked_repository.advance_upstream(COMMITS_THE_UPSTREAM_IS_AHEAD)
    diverged_tip = forked_repository.advance_local_default_branch()

    result = forked_repository.run_hook()

    assert result.returncode == 0, result.stderr
    assert forked_repository.local_default_branch_tip() == diverged_tip
    assert reported_outcome(result) == summary_message(
        SummaryMessage.DEFAULT_BRANCH_DIVERGED, DEFAULT_BRANCH, UPSTREAM_REPOSITORY
    )


def test_leaves_the_fork_alone_when_the_default_branch_has_diverged(
    forked_repository: ForkedScratchRepository,
):
    shared_base = forked_repository.shared_base
    forked_repository.advance_upstream(COMMITS_THE_UPSTREAM_IS_AHEAD)
    forked_repository.advance_local_default_branch()

    forked_repository.run_hook()

    assert forked_repository.fork.branch_tip(DEFAULT_BRANCH) == shared_base


def test_leaves_a_checked_out_default_branch_alone_when_git_refuses_to_move_it(
    forked_repository: ForkedScratchRepository,
):
    shared_base = forked_repository.shared_base
    forked_repository.advance_upstream(COMMITS_THE_UPSTREAM_IS_AHEAD)
    forked_repository.check_out_default_branch()
    forked_repository.repository.write(SHARED_FILE, "work in progress\n")

    result = forked_repository.run_hook()

    assert result.returncode == 0, result.stderr
    assert forked_repository.local_default_branch_tip() == shared_base
    assert reported_outcome(result) == summary_message(
        SummaryMessage.DEFAULT_BRANCH_LOCAL_UPDATE_REFUSED,
        DEFAULT_BRANCH,
        UPSTREAM_REPOSITORY,
    )


# %% an upstream this clone cannot resolve or reach


def test_reports_an_unreachable_upstream_without_touching_the_default_branch(
    forked_repository: ForkedScratchRepository,
):
    shared_base = forked_repository.shared_base
    forked_repository.make_the_upstream_unreachable()

    result = forked_repository.run_hook()

    assert result.returncode == 0, result.stderr
    assert forked_repository.local_default_branch_tip() == shared_base
    assert reported_outcome(result) == summary_message(
        SummaryMessage.DEFAULT_BRANCH_UPSTREAM_UNREACHABLE,
        DEFAULT_BRANCH,
        UPSTREAM_REPOSITORY,
    )


def test_reports_a_clone_that_names_no_upstream_at_all(
    forked_repository: ForkedScratchRepository,
):
    forked_repository.forget_the_stack_configuration()

    result = forked_repository.run_hook()

    assert result.returncode == 0, result.stderr
    assert reported_outcome(result) == summary_message(
        SummaryMessage.DEFAULT_BRANCH_NOT_CONFIGURED, STACK_CONFIGURATION_PATH
    )


def test_reports_a_refused_upstream_resolution_in_the_words_it_was_refused_with(
    forked_repository: ForkedScratchRepository,
):
    forked_repository.forget_the_fork_remote()

    result = forked_repository.run_hook()

    assert result.returncode == 0, result.stderr
    assert reported_outcome(result) == summary_message(
        SummaryMessage.DEFAULT_BRANCH_UPSTREAM_UNRESOLVED,
        forked_repository.stack_configuration_refusal(),
    )


# %% the line session-start.sh prints


def test_session_start_reports_the_default_branch_it_fast_forwarded(
    forked_repository: ForkedScratchRepository,
):
    forked_repository.advance_upstream(COMMITS_THE_UPSTREAM_IS_AHEAD)

    result = forked_repository.run_session_start()

    assert result.returncode == 0, result.stderr
    assert summary_value(result.stdout, SUMMARY_LABEL) == summary_message(
        SummaryMessage.DEFAULT_BRANCH_FAST_FORWARDED,
        DEFAULT_BRANCH,
        str(COMMITS_THE_UPSTREAM_IS_AHEAD),
        UPSTREAM_REPOSITORY,
    )
    assert f"{FOLLOW_UP_ROW_INDENT}{fork_pushed_row()}" in result.stdout


def test_a_clone_that_names_no_upstream_does_not_fail_session_start(
    forked_repository: ForkedScratchRepository,
):
    forked_repository.forget_the_stack_configuration()

    result = forked_repository.run_session_start()

    assert result.returncode == 0, result.stderr
    assert summary_value(result.stdout, SUMMARY_LABEL) == summary_message(
        SummaryMessage.DEFAULT_BRANCH_NOT_CONFIGURED, STACK_CONFIGURATION_PATH
    )


def test_session_start_stamps_the_notes_branch_it_read_not_the_upstream_it_fetched(
    forked_repository: ForkedScratchRepository,
):
    """
    Catching the default branch up leaves the upstream's tip in ``FETCH_HEAD``, so the
    recheck baseline has to be read from what was recorded rather than from whichever
    fetch happened to run last.
    """
    forked_repository.advance_upstream(COMMITS_THE_UPSTREAM_IS_AHEAD)

    result = forked_repository.run_session_start()

    assert summary_value(result.stdout, "plan state SHA").startswith(
        forked_repository.notes_branch_tip()
    )

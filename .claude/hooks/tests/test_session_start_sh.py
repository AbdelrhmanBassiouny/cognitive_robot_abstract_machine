"""
Integration tests for session-start.sh's summary report.

Cover the two guards the report exists for: naming which situation a branch with no plan
item is actually in, and surfacing check-setup.sh's verdict rather than leaving it to be
remembered. Both stay invisible to anyone who uses neither plans nor personal notes.

Run against a scratch project root with a local bare repository standing in for the
personal-notes remote - no network access or real personal-notes branch involved.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path

import pytest

from scratch_repository import (
    HOOKS_SOURCE_DIRECTORY,
    NOTES_BRANCH,
    WORK_BRANCH,
    ScratchRepository,
)

MESSAGES_SCRIPT = HOOKS_SOURCE_DIRECTORY / "session-start-messages.sh"

FIXTURES_DIRECTORY = Path(__file__).parent / "fixtures"

PLAN_MANIFEST = (FIXTURES_DIRECTORY / "plan.yaml").read_text()

PLAN_MANIFEST_WITH_TRACKING_ISSUE = (
    FIXTURES_DIRECTORY / "plan-with-tracking-issue.yaml"
).read_text()

TRACKING_ISSUE = "55"

PLAN_IDENTIFIER = "test-plan"

NOTES_PATH = ".claude/personal/cram-notes.md"

BRANCH_INDEX_PATH = ".claude/personal/plans/_generated/branch-index.tsv"

MANIFEST_PATH = f".claude/personal/plans/{PLAN_IDENTIFIER}/plan.yaml"

CLAUDE_LOCAL_MD = "CLAUDE.local.md"


class SummaryMessage(StrEnum):
    """
    The situations session-start.sh reports, each carrying the session-start-messages.sh
    function that renders its line.

    Named for the situation rather than for that function: a test reads as the case it
    exercises, while the shell file keeps grouping its own definitions by which summary
    line they belong to.
    """

    PLAN_NOT_APPLICABLE = "plan_line_not_applicable"
    """
    The branch is one no plan item could ever track.
    """

    NO_PLANS_TRACKED = "plan_line_no_plans_tracked"
    """
    The notes branch tracks no plans at all.
    """

    NO_PLAN_ITEM_TRACKS_BRANCH = "plan_line_no_item_tracks_branch"
    """
    Plans are tracked, and none holds an item for this branch.
    """

    PLAN_MANIFEST_MISSING = "plan_line_manifest_missing"
    """
    The index names a plan whose manifest is not on the notes branch.
    """

    BRANCH_TRACKED_IN_PLAN = "plan_line_tracked"
    """
    The branch is a tracked item of a plan that resolved.
    """

    SETUP_SCRIPT_MISSING = "setup_line_not_checked"
    """
    The check-setup.sh script is not in this checkout, so there is no verdict.
    """

    SETUP_OK = "setup_line_ok"
    """
    Every setup check passed.
    """

    CHECKS_NEED_SETUP = "setup_line_needs_setup"
    """
    The heading above the indented rows naming each check that needs setup.
    """


def summary_message(message: SummaryMessage, *arguments: str) -> str:
    """
    Render one summary line from the same definitions session-start.sh prints it from,
    so an assertion is never a second copy of the wording.

    :param message: The summary line to render.
    :param arguments: That message's arguments, in order.
    :return: The rendered line.
    """
    result = subprocess.run(
        [
            "bash",
            "-c",
            'source "$1"; shift; "$@"',
            "_",
            str(MESSAGES_SCRIPT),
            message,
            *arguments,
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def branch_index(plan_identifier_by_branch: Mapping[str, str]) -> str:
    """
    Build a branch index mapping each branch to the plan that tracks it.

    :param plan_identifier_by_branch: Plan ids, keyed by the branch each one tracks.
    :return: The index's tab-separated content.
    """
    return "".join(
        f"{branch}\t{plan_identifier}\n"
        for branch, plan_identifier in plan_identifier_by_branch.items()
    )


def summary_value(output: str, label: str) -> str:
    """
    Extract one line's value from the summary report.

    :param output: session-start.sh's standard output.
    :param label: The summary line's label, such as ``plan``.
    :return: Everything after the label, stripped.
    :raises AssertionError: If the report has no such line.
    """
    prefix = f"  {label}:"
    for line in output.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    raise AssertionError(f"no '{label}' line in this summary report:\n{output}")


# %% the scratch layout


@pytest.fixture
def session_start_repository(
    scratch_repository: ScratchRepository,
) -> ScratchRepository:
    """
    A scratch repository carrying the real session-start.sh and everything else a set up
    clone has, with nothing published to the notes remote yet.

    :param scratch_repository: The initialized scratch repository and notes remote.
    :return: The same repository, ready to publish a notes branch and run the hook.
    """
    scratch_repository.install_hook_scripts(
        "resolve-personal-notes-config.sh",
        "session-start-messages.sh",
        "session-start.sh",
        "check-setup.sh",
    )
    scratch_repository.write_setup_prerequisites()
    scratch_repository.commit_everything("initial commit")
    scratch_repository.resolve_notes_remote_to()
    return scratch_repository


def run_session_start(
    repository: ScratchRepository,
) -> subprocess.CompletedProcess[str]:
    """
    Run the scratch layout's session-start.sh.

    Every ``CLAUDE_PERSONAL_NOTES_*`` variable is stripped from the inherited
    environment first, so a value that happens to be set in whoever's shell is running
    the tests can never change what they assert.

    :param repository: A fixture-built scratch repository.
    :return: The finished subprocess.
    """
    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith("CLAUDE_PERSONAL_NOTES_")
    }
    return subprocess.run(
        [
            "bash",
            str(repository.project_root / ".claude" / "hooks" / "session-start.sh"),
        ],
        cwd=repository.project_root,
        capture_output=True,
        text=True,
        env=environment,
    )


def publish_and_run(
    repository: ScratchRepository, notes_branch_files: Mapping[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """
    Publish the notes file plus *notes_branch_files* to the notes branch, then run
    session-start.sh against it.

    :param repository: The fixture-built scratch repository.
    :param notes_branch_files: Extra file contents, keyed by path relative to the
        project root.
    :return: The finished session-start.sh process.
    """
    repository.publish_notes_branch(
        {NOTES_PATH: "personal notes\n", **(notes_branch_files or {})}
    )
    return run_session_start(repository)


# %% someone who uses neither plans nor personal notes


def test_reports_nothing_when_no_notes_branch_exists(
    session_start_repository: ScratchRepository,
):
    session_start_repository.run_git("checkout", "--quiet", "-b", WORK_BRANCH)

    result = run_session_start(session_start_repository)

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert not (session_start_repository.project_root / CLAUDE_LOCAL_MD).exists()


# %% the plan line


def test_reports_no_plans_when_none_are_tracked(
    session_start_repository: ScratchRepository,
):
    result = publish_and_run(session_start_repository)

    assert result.returncode == 0, result.stderr
    assert summary_value(result.stdout, "plan") == summary_message(
        SummaryMessage.NO_PLANS_TRACKED, NOTES_BRANCH
    )


def test_names_the_missing_item_when_other_plans_are_tracked(
    session_start_repository: ScratchRepository,
):
    result = publish_and_run(
        session_start_repository,
        {
            BRANCH_INDEX_PATH: branch_index(
                {
                    "some-other-branch": PLAN_IDENTIFIER,
                    "a-third-branch": "another-plan",
                }
            ),
            MANIFEST_PATH: PLAN_MANIFEST,
        },
    )

    assert result.returncode == 0, result.stderr
    assert summary_value(result.stdout, "plan") == summary_message(
        SummaryMessage.NO_PLAN_ITEM_TRACKS_BRANCH, WORK_BRANCH, "2"
    )


def test_reports_the_plan_that_tracks_this_branch(
    session_start_repository: ScratchRepository,
):
    result = publish_and_run(
        session_start_repository,
        {
            BRANCH_INDEX_PATH: branch_index({WORK_BRANCH: PLAN_IDENTIFIER}),
            MANIFEST_PATH: PLAN_MANIFEST_WITH_TRACKING_ISSUE,
        },
    )

    assert result.returncode == 0, result.stderr
    assert summary_value(result.stdout, "plan") == summary_message(
        SummaryMessage.BRANCH_TRACKED_IN_PLAN, PLAN_IDENTIFIER, TRACKING_ISSUE
    )


def test_reports_a_tracked_plan_that_has_no_tracking_issue(
    session_start_repository: ScratchRepository,
):
    result = publish_and_run(
        session_start_repository,
        {
            BRANCH_INDEX_PATH: branch_index({WORK_BRANCH: PLAN_IDENTIFIER}),
            MANIFEST_PATH: PLAN_MANIFEST,
        },
    )

    assert result.returncode == 0, result.stderr
    assert summary_value(result.stdout, "plan") == summary_message(
        SummaryMessage.BRANCH_TRACKED_IN_PLAN, PLAN_IDENTIFIER, "none"
    )


def test_reports_a_tracked_branch_whose_manifest_is_missing(
    session_start_repository: ScratchRepository,
):
    result = publish_and_run(
        session_start_repository,
        {BRANCH_INDEX_PATH: branch_index({WORK_BRANCH: PLAN_IDENTIFIER})},
    )

    assert result.returncode == 0, result.stderr
    assert summary_value(result.stdout, "plan") == summary_message(
        SummaryMessage.PLAN_MANIFEST_MISSING,
        PLAN_IDENTIFIER,
        MANIFEST_PATH,
        NOTES_BRANCH,
    )


# %% branches no plan item can ever track


def test_reports_plan_as_not_applicable_on_the_default_branch(
    session_start_repository: ScratchRepository,
):
    session_start_repository.publish_notes_branch(
        {
            NOTES_PATH: "personal notes\n",
            BRANCH_INDEX_PATH: branch_index({WORK_BRANCH: PLAN_IDENTIFIER}),
            MANIFEST_PATH: PLAN_MANIFEST,
        }
    )
    session_start_repository.run_git("checkout", "--quiet", "-b", "main")

    result = run_session_start(session_start_repository)

    assert result.returncode == 0, result.stderr
    assert summary_value(result.stdout, "plan") == summary_message(
        SummaryMessage.PLAN_NOT_APPLICABLE
    )


def test_reports_plan_as_not_applicable_on_the_notes_branch(
    session_start_repository: ScratchRepository,
):
    session_start_repository.publish_notes_branch(
        {
            NOTES_PATH: "personal notes\n",
            BRANCH_INDEX_PATH: branch_index({WORK_BRANCH: PLAN_IDENTIFIER}),
            MANIFEST_PATH: PLAN_MANIFEST,
        }
    )
    session_start_repository.run_git("checkout", "--quiet", NOTES_BRANCH)

    result = run_session_start(session_start_repository)

    assert result.returncode == 0, result.stderr
    assert summary_value(result.stdout, "plan") == summary_message(
        SummaryMessage.PLAN_NOT_APPLICABLE
    )


# %% the setup line


def test_reports_setup_as_ok_when_every_check_passes(
    session_start_repository: ScratchRepository,
):
    result = publish_and_run(session_start_repository)

    assert result.returncode == 0, result.stderr
    assert summary_value(result.stdout, "setup") == summary_message(
        SummaryMessage.SETUP_OK
    )


def test_names_every_check_that_needs_setup(
    session_start_repository: ScratchRepository,
):
    (session_start_repository.project_root / ".claude" / "settings.json").unlink()
    session_start_repository.commit_everything("unregister the SessionStart hook")

    result = publish_and_run(session_start_repository)

    failing_check = "session_start_hook"
    detail = next(
        row.split("\t")[2]
        for row in session_start_repository.run_hook_script(
            "check-setup.sh"
        ).stdout.splitlines()
        if row.split("\t")[0] == failing_check
    )
    assert summary_value(result.stdout, "setup") == summary_message(
        SummaryMessage.CHECKS_NEED_SETUP, "1"
    )
    assert f"    {failing_check}: {detail}" in result.stdout


def test_a_failing_setup_check_does_not_fail_the_hook(
    session_start_repository: ScratchRepository,
):
    (session_start_repository.project_root / ".claude" / "settings.json").unlink()
    session_start_repository.commit_everything("unregister the SessionStart hook")

    result = publish_and_run(session_start_repository)

    assert result.returncode == 0, result.stderr
    assert (session_start_repository.project_root / CLAUDE_LOCAL_MD).exists()


# %% every message renders


def test_every_summary_message_renders_something():
    """
    Check that every message this module can name resolves to a shell function that
    prints something.

    Deliberately not an assertion about the wording: every other assertion here renders
    its expectation from session-start-messages.sh, so a reword moves both sides at once
    and none of them fail. What is still worth catching is a member naming a function
    that does not exist, or one that prints nothing - neither of which survives here.

    Three placeholder arguments cover the widest message; a shell function ignores the
    ones it does not read.
    """
    for message in SummaryMessage:
        assert summary_message(message, "first", "second", "third").strip() != ""

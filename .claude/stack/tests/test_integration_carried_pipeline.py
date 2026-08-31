"""
Whether a build carries the rebuild that would produce the next one.

Publishing moves this fork's default branch onto a build, and a schedule registers from
the default branch - so a build that does not itself carry the rebuild takes the
schedule down with it and leaves nothing able to publish a later build. Measured on
2026-08-30: a build assembled from nine branches came back green on all 23 of its checks
and carried neither of the two branches the pipeline lives on, so publishing it would
have ended the automation with nothing left to restore it.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import date
from pathlib import Path
from typing import Mapping

import pytest
import yaml

from git_commands import GitCommandRunner

import integration_candidate_commands
from integration_candidate_commands import PublishRecordedPassCommand, tree_of
from integration_carried_pipeline import (
    PIPELINE_PATHS,
    REFRESH_WORKFLOW_PATH,
    pipeline_carried_by,
)
from integration_constants import POINTER_BRANCH, ReportKey
from integration_exit_codes import IntegrationExitCode
from integration_pass_record import PassedChecks, RecordedSubject
from integration_verdict import ChecksVerdict, VerdictReportKey
from workflow_document import REPOSITORY_ROOT, TriggerEvent

from integration_fixtures import (
    A_BUILD_BRANCH,
    RunAgainstAGivenFork,
    the_pipeline_this_checkout_carries,
    write_into,
)
from test_integration_verdict import (
    RecordingCandidates,
    RecordingGit,
    a_check,
    settle,
)
from test_maintenance import (
    ForkCheckout,
    UPSTREAM_BASE,
    fork_checkout,  # noqa: F401  (imported so pytest finds the fixture by name)
    make_configuration,
)


def without(files: Mapping[str, str], dropped: str) -> dict[str, str]:
    """
    :param files: What a tree would carry.
    :param dropped: The one path to leave out of it.
    :return: The rest.
    """
    return {path: content for path, content in files.items() if path != dropped}


def without_its_schedule(workflow: str) -> str:
    """
    :param workflow: The refresh workflow as this checkout carries it.
    :return: The same workflow with nothing left that starts it unasked.
    """
    declared = yaml.safe_load(workflow)
    declared[True] = without(declared[True], str(TriggerEvent.SCHEDULE))
    return yaml.safe_dump(declared)


class ScratchBuild:
    """
    A repository whose commits stand in for the trees a build is judged as.
    """

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        for arguments in (
            ("init", "--quiet"),
            ("config", "user.name", "Scratch Build"),
            ("config", "user.email", "scratch-build@example.com"),
        ):
            subprocess.run(["git", *arguments], cwd=self.root, check=True)

    @property
    def git(self) -> GitCommandRunner:
        """:return: The runner the guard reads this repository through."""
        return GitCommandRunner(working_directory=self.root)

    def holding(self, files: Mapping[str, str]) -> str:
        """
        :param files: What the tree carries, by path.
        :return: The commit holding exactly that.
        """
        write_into(self.root, files)
        self.git.run("add", "--all")
        self.git.run("commit", "--quiet", "--allow-empty", "-m", "a build")
        return self.git.run("rev-parse", "HEAD")


@pytest.fixture
def scratch_build(tmp_path: Path) -> ScratchBuild:
    """
    :param tmp_path: pytest's per-test temporary directory.
    :return: A repository to commit the trees under test into.
    """
    return ScratchBuild(tmp_path / "build")


# %% what a tree has to carry


def test_the_pipeline_is_looked_for_where_this_checkout_keeps_it():
    """
    The paths are derived from the enums naming the workflow and the entry points it
    drives, so a file that moved would be looked for where it used to be - and the guard
    would then refuse every build over a file nothing is actually missing.
    """
    assert PIPELINE_PATHS
    assert [
        path for path in PIPELINE_PATHS if not (REPOSITORY_ROOT / path).is_file()
    ] == []


def test_a_tree_carrying_the_whole_pipeline_can_rebuild(scratch_build: ScratchBuild):
    """
    The ordinary build: everything a later rebuild needs is in it, so publishing leaves
    the pipeline where it was.
    """
    head = scratch_build.holding(the_pipeline_this_checkout_carries())

    carried = pipeline_carried_by(scratch_build.git, head)

    assert carried.missing == () and carried.can_rebuild


def test_a_tree_without_the_workflow_a_schedule_starts_cannot_rebuild(
    scratch_build: ScratchBuild,
):
    """
    The build of 2026-08-30, which is what this guard exists for: green, and carrying no
    refresh workflow at all.

    Published, the schedule that registers from the default branch goes with it.
    """
    head = scratch_build.holding(
        without(the_pipeline_this_checkout_carries(), REFRESH_WORKFLOW_PATH)
    )

    carried = pipeline_carried_by(scratch_build.git, head)

    assert carried.missing == (REFRESH_WORKFLOW_PATH,)
    assert not carried.can_rebuild


def test_a_tree_without_the_entry_point_the_workflow_drives_cannot_rebuild(
    scratch_build: ScratchBuild,
):
    """
    A workflow with nothing to call is a scheduled run that fails every time, which
    costs the pipeline exactly what a missing workflow costs it.
    """
    dropped = next(path for path in PIPELINE_PATHS if path != REFRESH_WORKFLOW_PATH)
    head = scratch_build.holding(without(the_pipeline_this_checkout_carries(), dropped))

    carried = pipeline_carried_by(scratch_build.git, head)

    assert carried.missing == (dropped,) and not carried.can_rebuild


def test_a_rebuild_nothing_would_start_is_not_a_pipeline_that_survived(
    scratch_build: ScratchBuild,
):
    """
    Every file present and nothing left that starts them.

    A dispatch somebody remembers to press is not what publishing must not cost: it is the rebuild that happens
    without being asked.
    """
    carried_files = the_pipeline_this_checkout_carries()
    carried_files[REFRESH_WORKFLOW_PATH] = without_its_schedule(
        carried_files[REFRESH_WORKFLOW_PATH]
    )
    head = scratch_build.holding(carried_files)

    carried = pipeline_carried_by(scratch_build.git, head)

    assert carried.missing == ()
    assert not carried.starts_on_a_schedule and not carried.can_rebuild


# %% what the candidate's own path does about it


def pointer_moved(run) -> bool:
    """
    Asked of the pushes rather than of the report, since the report is the other half of
    what is under test here.

    :param run: A settling that has happened.
    :return: Whether it moved the branch a developer works from.
    """
    return any(
        command[0] == "push"
        and any(part.endswith(f"refs/heads/{POINTER_BRANCH}") for part in command)
        for command in run.git.commands
    )


def test_a_green_build_that_would_take_the_rebuild_down_is_not_published():
    """
    The verdict is honest and beside the point: green says the branches in the build are
    healthy, not that the pointer is safe to move onto them.
    """
    run = settle([a_check()], git=RecordingGit(carried={}))

    assert not pointer_moved(run)


def test_the_refusal_says_which_of_the_pipeline_s_files_are_missing(
    capsys: pytest.CaptureFixture,
):
    """
    A refusal that said nothing would read as a rebuild that quietly did nothing, and
    what a reader acts on is which of the pipeline the build left behind.
    """
    settle([a_check()], git=RecordingGit(carried={}))

    document = json.loads(capsys.readouterr().out)
    assert document[VerdictReportKey.PUBLISHED] is False
    assert document[VerdictReportKey.MISSING_PIPELINE] == list(PIPELINE_PATHS)


def test_a_build_that_carries_the_pipeline_is_still_published(
    capsys: pytest.CaptureFixture,
):
    """
    The guard refuses one thing rather than gating publication: an ordinary green build
    reaches the pointer exactly as it did.
    """
    run = settle([a_check()])

    assert pointer_moved(run)
    assert json.loads(capsys.readouterr().out)[VerdictReportKey.PUBLISHED] is True


def test_a_refused_publication_leaves_its_own_status_rather_than_the_verdict_s():
    """
    A rebuild acts on the status rather than on the document, so a refusal answered with
    the success the checks earned is a run reporting a build published that is not.
    """
    assert (
        integration_candidate_commands._verdict_exit_code(
            ChecksVerdict.PASSED, published=False
        )
        is IntegrationExitCode.PIPELINE_WOULD_BE_REMOVED
    )


# %% what the recorded-pass path does about it


def a_build_on_the_fork(checkout: ForkCheckout, files: Mapping[str, str]) -> str:
    """
    Put a build carrying those files on the fork, as a rebuild would leave one.

    :param checkout: The checkout holding the fork remote.
    :param files: What the build's tree carries beyond the base's own file.
    :return: The build's head commit.
    """
    checkout.run_git("checkout", "--quiet", "-B", A_BUILD_BRANCH, UPSTREAM_BASE)
    write_into(checkout.project_root, files)
    checkout.run_git("add", "--all")
    checkout.run_git("commit", "--quiet", "--allow-empty", "-m", "a build")
    checkout.run_git("push", "--quiet", "origin", f"{A_BUILD_BRANCH}:{A_BUILD_BRANCH}")
    checkout.run_git("fetch", "--quiet", "origin")
    return checkout.run_git("rev-parse", A_BUILD_BRANCH)


def publish_a_recorded_pass(checkout: ForkCheckout) -> IntegrationExitCode:
    """
    Record that this build's tree passed, and ask for it to be published.

    :param checkout: The checkout the build is on.
    :return: The status publishing answered with.
    """
    run = RunAgainstAGivenFork(
        configuration=make_configuration(),
        git=checkout.git,
        given=RecordingCandidates(),
    )
    PassedChecks(records=(), read_on=date.today()).record(
        checkout.git,
        "origin",
        RecordedSubject.BUILD_TREE,
        tree_of(run, A_BUILD_BRANCH),
        checkout.run_git("rev-parse", A_BUILD_BRANCH),
    )
    return PublishRecordedPassCommand().run(
        run, argparse.Namespace(build=A_BUILD_BRANCH, json=True)
    )


def pointer_on_the_fork(checkout: ForkCheckout) -> str:
    """
    :param checkout: The checkout holding the fork remote.
    :return: The commit the fork has the pointer at, empty when it has no such branch.
    """
    return checkout.run_git("ls-remote", "origin", f"refs/heads/{POINTER_BRANCH}")


def test_a_recorded_pass_over_a_build_without_the_pipeline_is_refused(
    fork_checkout: ForkCheckout, capsys: pytest.CaptureFixture
):
    """
    The second way a build reaches the pointer skips the candidate entirely - it is what
    publishes on the ordinary day, when nothing has moved - so a guard on the judged
    path alone is one this walks straight past.
    """
    a_build_on_the_fork(fork_checkout, {})

    status = publish_a_recorded_pass(fork_checkout)

    assert status is IntegrationExitCode.PIPELINE_WOULD_BE_REMOVED
    assert pointer_on_the_fork(fork_checkout) == ""
    document = json.loads(capsys.readouterr().out)
    assert document[ReportKey.PUBLISHED] is False
    assert document[ReportKey.MISSING_PIPELINE] == list(PIPELINE_PATHS)


def test_a_recorded_pass_over_a_build_carrying_the_pipeline_publishes(
    fork_checkout: ForkCheckout,
):
    """
    What the guard must not cost: the day nothing moved, the recorded pass still moves
    the pointer without spending a matrix.
    """
    head = a_build_on_the_fork(fork_checkout, the_pipeline_this_checkout_carries())

    status = publish_a_recorded_pass(fork_checkout)

    assert status is IntegrationExitCode.SUCCESS
    assert pointer_on_the_fork(fork_checkout).split()[0] == head

"""
Integration tests for check-setup.sh's per-check reporting and exit code.

Run against a scratch project root with a local bare repository standing in for the
personal-notes remote - no network access or real personal-notes branch involved.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import pytest

import missing_requirements
from scratch_repository import (
    NOTES_BRANCH,
    PERSONAL_GIT_IDENTITY_PATH,
    SCRATCH_IDENTITY,
    ScratchRepository,
    SetupPrerequisiteFile,
    StackConfigurationPath,
    initialize_bare_repository,
    stack_configuration,
)

NOTES_PATH = ".claude/personal/cram-notes.md"


# %% what a report is made of


class SetupCheck(StrEnum):
    """
    The checks check-setup.sh reports on, in the order it prints them.
    """

    TOOLING_FILES = "tooling_files"
    SESSION_START_HOOK = "session_start_hook"
    CLAUDE_LOCAL_MD_IGNORED = "claude_local_md_ignored"
    NOTES_REMOTE = "notes_remote"
    NOTES_REMOTE_URL = "notes_remote_url"
    NOTES_BRANCH_NAME = "notes_branch_name"
    NOTES_PATH = "notes_path"
    NOTES_BRANCH = "notes_branch"
    NOTES_FILE = "notes_file"
    GIT_IDENTITY = "git_identity"
    BRANCH_BASE = "branch_base"
    DASHBOARD_DEPENDENCIES = "dashboard_dependencies"
    CLAUDE_LOCAL_MD = "claude_local_md"


class CheckStatus(StrEnum):
    """
    The status check-setup.sh reports for a single check.
    """

    OK = "ok"
    NEEDS_SETUP = "needs-setup"
    INFORMATIONAL = "info"


@dataclass
class CheckResult:
    """
    What check-setup.sh reported for one check.
    """

    status: CheckStatus
    """
    Whether the check passed, needs setup, or is context rather than a verdict.
    """

    detail: str
    """
    The human-readable explanation printed alongside the status.
    """


@dataclass
class SetupReport:
    """
    One parsed run of check-setup.sh: what it reported, and how it exited.
    """

    exit_code: int
    """
    The script's exit code: 0 when nothing needs setup, 1 otherwise.
    """

    results: dict[SetupCheck, CheckResult]
    """
    Every reported check, keyed by the check it reports on.
    """

    @classmethod
    def from_completed_process(
        cls, process: subprocess.CompletedProcess[str]
    ) -> SetupReport:
        """
        Parse a finished check-setup.sh run.

        Raises if a row names a check this test module doesn't know about, so a new
        check has to be declared here rather than silently going unasserted.

        :param process: The finished check-setup.sh subprocess.
        :return: The parsed report.
        """
        results = {}
        for line in process.stdout.splitlines():
            check, status, detail = line.split("\t")
            results[SetupCheck(check)] = CheckResult(CheckStatus(status), detail)
        return cls(process.returncode, results)


# %% the scratch layout


@pytest.fixture
def check_setup_repository(scratch_repository: ScratchRepository) -> ScratchRepository:
    """
    A scratch repository set up so every check-setup.sh check passes: the real check-
    setup.sh and resolve-personal-notes-config.sh, placeholder tooling files, a
    registered SessionStart hook, a gitignored CLAUDE.local.md, and a notes branch
    carrying a notes file and the identity this repository's own commits are authored
    with.

    Individual tests break exactly one of those conditions to assert the matching check
    reports it.

    :param scratch_repository: The initialized scratch repository and notes remote.
    :return: The same repository, fully set up.
    """
    scratch_repository.install_hook_scripts(
        "resolve-personal-notes-config.sh", "check-setup.sh"
    )
    scratch_repository.install_hook_modules(missing_requirements)

    scratch_repository.write_setup_prerequisites()
    scratch_repository.write("CLAUDE.local.md", "notes\n")

    scratch_repository.commit_everything("initial commit")
    scratch_repository.publish_notes_branch(
        {
            NOTES_PATH: "my notes\n",
            PERSONAL_GIT_IDENTITY_PATH: SCRATCH_IDENTITY.as_git_config_file(),
        }
    )
    scratch_repository.resolve_notes_remote_to()
    return scratch_repository


def run_check_setup(
    repository: ScratchRepository, **environment_overrides: str
) -> SetupReport:
    """
    Run the scratch layout's check-setup.sh and parse its report.

    :param repository: A fixture-built scratch repository.
    :param environment_overrides: Environment variables to set for this run, for the
        tests that exercise resolution from the environment.
    :return: The parsed report.
    """
    return SetupReport.from_completed_process(
        repository.run_hook_script("check-setup.sh", **environment_overrides)
    )


# %% the already-set-up fast path


def test_reports_no_work_needed_when_everything_is_in_place(
    check_setup_repository: ScratchRepository,
):
    report = run_check_setup(check_setup_repository)
    assert report.exit_code == 0
    needing_setup = [
        check
        for check, result in report.results.items()
        if result.status == CheckStatus.NEEDS_SETUP
    ]
    assert needing_setup == []


def test_reports_every_check_it_documents(check_setup_repository: ScratchRepository):
    report = run_check_setup(check_setup_repository)
    assert set(report.results) == set(SetupCheck)


# %% the personal-notes branch


def test_reports_a_missing_notes_branch_and_the_remotes_it_tried(
    check_setup_repository: ScratchRepository, tmp_path: Path
):
    empty_remote = initialize_bare_repository(tmp_path / "empty-remote.git")
    check_setup_repository.resolve_notes_remote_to(empty_remote)

    report = run_check_setup(check_setup_repository)
    assert report.exit_code == 1
    assert report.results[SetupCheck.NOTES_BRANCH].status == CheckStatus.NEEDS_SETUP
    assert str(empty_remote) in report.results[SetupCheck.NOTES_BRANCH].detail


def test_does_not_check_for_the_notes_file_when_its_branch_is_missing(
    check_setup_repository: ScratchRepository, tmp_path: Path
):
    check_setup_repository.resolve_notes_remote_to(
        initialize_bare_repository(tmp_path / "empty-remote.git")
    )

    report = run_check_setup(check_setup_repository)
    assert report.results[SetupCheck.NOTES_FILE].status == CheckStatus.NEEDS_SETUP
    assert report.results[SetupCheck.NOTES_FILE].detail == (
        "not checked - the branch that would hold it doesn't exist yet"
    )


def test_reports_a_notes_branch_that_exists_but_holds_no_notes_file(
    check_setup_repository: ScratchRepository,
):
    check_setup_repository.run_git(
        "config", "claude.personalNotesPath", ".claude/personal/some-other-notes.md"
    )

    report = run_check_setup(check_setup_repository)
    assert report.exit_code == 1
    assert report.results[SetupCheck.NOTES_BRANCH].status == CheckStatus.OK
    assert report.results[SetupCheck.NOTES_FILE].status == CheckStatus.NEEDS_SETUP
    assert (
        ".claude/personal/some-other-notes.md"
        in report.results[SetupCheck.NOTES_FILE].detail
    )


# %% who commits here would be authored as


def test_reports_a_recorded_identity_that_matches_this_clone(
    check_setup_repository: ScratchRepository,
):
    report = run_check_setup(check_setup_repository)
    assert report.results[SetupCheck.GIT_IDENTITY].status == CheckStatus.OK
    assert (
        f"{SCRATCH_IDENTITY.name} <{SCRATCH_IDENTITY.email}>"
        in report.results[SetupCheck.GIT_IDENTITY].detail
    )


def test_reports_a_notes_branch_that_records_no_identity(
    check_setup_repository: ScratchRepository,
):
    check_setup_repository.remove_from_notes_branch(PERSONAL_GIT_IDENTITY_PATH)

    report = run_check_setup(check_setup_repository)
    assert report.exit_code == 1
    assert report.results[SetupCheck.GIT_IDENTITY].status == CheckStatus.NEEDS_SETUP
    assert (
        f"{SCRATCH_IDENTITY.name} <{SCRATCH_IDENTITY.email}>"
        in report.results[SetupCheck.GIT_IDENTITY].detail
    )


def test_reports_a_recorded_identity_this_clone_does_not_commit_as(
    check_setup_repository: ScratchRepository,
):
    check_setup_repository.run_git("config", "user.name", "Somebody Else")

    report = run_check_setup(check_setup_repository)
    assert report.exit_code == 1
    assert report.results[SetupCheck.GIT_IDENTITY].status == CheckStatus.NEEDS_SETUP
    detail = report.results[SetupCheck.GIT_IDENTITY].detail
    assert f"{SCRATCH_IDENTITY.name} <{SCRATCH_IDENTITY.email}>" in detail
    assert f"Somebody Else <{SCRATCH_IDENTITY.email}>" in detail


def test_reads_the_identity_the_environment_overrides_config_with(
    check_setup_repository: ScratchRepository,
):
    report = run_check_setup(
        check_setup_repository,
        GIT_AUTHOR_NAME="Environment Author",
        GIT_AUTHOR_EMAIL="environment@example.com",
    )
    assert report.exit_code == 1
    assert report.results[SetupCheck.GIT_IDENTITY].status == CheckStatus.NEEDS_SETUP
    assert (
        "Environment Author <environment@example.com>"
        in report.results[SetupCheck.GIT_IDENTITY].detail
    )


def test_does_not_check_the_identity_when_the_notes_branch_is_missing(
    check_setup_repository: ScratchRepository, tmp_path: Path
):
    check_setup_repository.resolve_notes_remote_to(
        initialize_bare_repository(tmp_path / "empty-remote.git")
    )

    report = run_check_setup(check_setup_repository)
    assert report.results[SetupCheck.GIT_IDENTITY].status == CheckStatus.NEEDS_SETUP
    assert report.results[SetupCheck.GIT_IDENTITY].detail == (
        "not checked - the branch that would record it doesn't exist yet"
    )


# %% how each setting was resolved


def test_reports_which_source_each_resolved_setting_came_from(
    check_setup_repository: ScratchRepository,
):
    report = run_check_setup(check_setup_repository)
    assert (
        "from git config claude.personalNotesRemote"
        in report.results[SetupCheck.NOTES_REMOTE].detail
    )
    assert report.results[SetupCheck.NOTES_BRANCH_NAME].detail == (
        f"{NOTES_BRANCH} (from built-in default)"
    )
    assert report.results[SetupCheck.NOTES_PATH].detail == (
        f"{NOTES_PATH} (from built-in default)"
    )


def test_reports_a_setting_resolved_from_the_environment(
    check_setup_repository: ScratchRepository,
):
    report = run_check_setup(
        check_setup_repository,
        CLAUDE_PERSONAL_NOTES_PATH=".claude/personal/from-the-environment.md",
    )
    assert report.results[SetupCheck.NOTES_PATH].detail == (
        ".claude/personal/from-the-environment.md"
        " (from environment variable CLAUDE_PERSONAL_NOTES_PATH)"
    )


# %% the tooling this checkout is expected to carry


def test_reports_which_tooling_files_this_checkout_is_missing(
    check_setup_repository: ScratchRepository,
):
    (check_setup_repository.project_root / SetupPrerequisiteFile.PLAN_SCHEMA).unlink()

    report = run_check_setup(check_setup_repository)
    assert report.exit_code == 1
    assert report.results[SetupCheck.TOOLING_FILES].status == CheckStatus.NEEDS_SETUP
    assert (
        SetupPrerequisiteFile.PLAN_SCHEMA
        in report.results[SetupCheck.TOOLING_FILES].detail
    )
    assert (
        SetupPrerequisiteFile.BUILD_DASHBOARD
        not in report.results[SetupCheck.TOOLING_FILES].detail
    )


def test_reports_a_session_start_hook_that_is_not_registered(
    check_setup_repository: ScratchRepository,
):
    check_setup_repository.write(".claude/settings.json", "{}\n")

    report = run_check_setup(check_setup_repository)
    assert report.exit_code == 1
    assert (
        report.results[SetupCheck.SESSION_START_HOOK].status == CheckStatus.NEEDS_SETUP
    )


def test_reports_a_claude_local_md_that_is_not_gitignored(
    check_setup_repository: ScratchRepository,
):
    check_setup_repository.write(".gitignore", "something-else\n")

    report = run_check_setup(check_setup_repository)
    assert report.exit_code == 1
    assert (
        report.results[SetupCheck.CLAUDE_LOCAL_MD_IGNORED].status
        == CheckStatus.NEEDS_SETUP
    )


# %% plan-dashboard dependencies


def test_reports_dashboard_requirements_that_are_not_installed(
    check_setup_repository: ScratchRepository,
):
    check_setup_repository.write(
        SetupPrerequisiteFile.DASHBOARD_REQUIREMENTS,
        "pytest>=1\nno-such-distribution-exists>=2  # a comment\n",
    )

    report = run_check_setup(check_setup_repository)
    assert report.exit_code == 1
    assert (
        report.results[SetupCheck.DASHBOARD_DEPENDENCIES].status
        == CheckStatus.NEEDS_SETUP
    )
    assert (
        "no-such-distribution-exists"
        in report.results[SetupCheck.DASHBOARD_DEPENDENCIES].detail
    )
    assert "pytest" not in report.results[SetupCheck.DASHBOARD_DEPENDENCIES].detail


# %% the outcome of it all working


def test_reports_a_claude_local_md_that_was_never_written(
    check_setup_repository: ScratchRepository,
):
    (check_setup_repository.project_root / "CLAUDE.local.md").unlink()

    report = run_check_setup(check_setup_repository)
    assert report.exit_code == 1
    assert report.results[SetupCheck.CLAUDE_LOCAL_MD].status == CheckStatus.NEEDS_SETUP


# %% the branch this work would be based on

CONFIGURED_BASE_BRANCH = "main"
"""
The branch the scratch repository's committed stack configuration names as its base.
"""

STAGING_DEFAULT_BRANCH = "integration"
"""
A default branch that is not the configured base - deliberately, since it is what puts
reviewed-but-unlanded work into every fresh checkout. It carries commits the base does
not, which is exactly why nothing may be based on it.
"""


def configure_a_staged_repository(
    repository: ScratchRepository, base: str = CONFIGURED_BASE_BRANCH
) -> str:
    """
    Set up the arrangement this check exists for: a configured base, and a different
    default branch carrying commits of its own.

    :param repository: The scratch repository to configure.
    :param base: The branch the stack configuration names as the base.
    :return: The commit the configured base points at.
    """
    repository.write(StackConfigurationPath.COMMITTED, stack_configuration(base))
    repository.commit_everything("declare the configured base")
    repository.add_work_remote()
    base_commit = repository.run_git("rev-parse", "HEAD").stdout.strip()
    repository.track_remote_branch(base, base_commit)
    staged = repository.publish_staging_branch(STAGING_DEFAULT_BRANCH)
    repository.declare_default_branch(STAGING_DEFAULT_BRANCH, staged)
    return base_commit


def test_refuses_a_branch_cut_from_the_staging_default_branch(
    check_setup_repository: ScratchRepository,
):
    configure_a_staged_repository(check_setup_repository)
    check_setup_repository.start_branch_from(
        "work", f"refs/remotes/origin/{STAGING_DEFAULT_BRANCH}"
    )

    report = run_check_setup(check_setup_repository)
    assert report.exit_code == 1
    assert report.results[SetupCheck.BRANCH_BASE].status == CheckStatus.NEEDS_SETUP
    detail = report.results[SetupCheck.BRANCH_BASE].detail
    assert STAGING_DEFAULT_BRANCH in detail
    assert CONFIGURED_BASE_BRANCH in detail


def test_accepts_a_branch_cut_from_the_configured_base(
    check_setup_repository: ScratchRepository,
):
    base_commit = configure_a_staged_repository(check_setup_repository)
    check_setup_repository.start_branch_from("work", base_commit)

    report = run_check_setup(check_setup_repository)
    assert report.exit_code == 0
    assert report.results[SetupCheck.BRANCH_BASE].status == CheckStatus.OK


def test_accepts_a_branch_stacked_on_another_branch(
    check_setup_repository: ScratchRepository,
):
    """
    Stacking on a parent pull request is this workflow's normal shape, so a rule that
    flagged it would fire on most of the fork.
    """
    base_commit = configure_a_staged_repository(check_setup_repository)
    check_setup_repository.start_branch_from("parent", base_commit)
    check_setup_repository.write("parent-work.txt", "what the parent adds\n")
    check_setup_repository.commit_everything("the parent's own work")
    check_setup_repository.start_branch_from("child", "parent")

    report = run_check_setup(check_setup_repository)
    assert report.exit_code == 0
    assert report.results[SetupCheck.BRANCH_BASE].status == CheckStatus.OK


def test_accepts_a_branch_whose_configured_base_has_moved_on_without_it(
    check_setup_repository: ScratchRepository,
):
    """
    The base advances constantly, so a branch cut from it is neither its ancestor nor
    its descendant within a day.

    Testing descent from the staging branch instead is what keeps that ordinary state
    from reading as a defect.
    """
    base_commit = configure_a_staged_repository(check_setup_repository)
    check_setup_repository.start_branch_from("work", base_commit)
    check_setup_repository.publish_staging_branch(CONFIGURED_BASE_BRANCH)

    report = run_check_setup(check_setup_repository)
    assert report.exit_code == 0
    assert report.results[SetupCheck.BRANCH_BASE].status == CheckStatus.OK


def test_accepts_a_repository_whose_default_branch_is_its_configured_base(
    check_setup_repository: ScratchRepository,
):
    check_setup_repository.write(
        StackConfigurationPath.COMMITTED, stack_configuration(CONFIGURED_BASE_BRANCH)
    )
    check_setup_repository.commit_everything("declare the configured base")
    check_setup_repository.add_work_remote()
    check_setup_repository.declare_default_branch(CONFIGURED_BASE_BRANCH)

    report = run_check_setup(check_setup_repository)
    assert report.exit_code == 0
    assert report.results[SetupCheck.BRANCH_BASE].status == CheckStatus.OK
    assert CONFIGURED_BASE_BRANCH in report.results[SetupCheck.BRANCH_BASE].detail


def test_reads_the_remotes_own_head_when_the_clone_records_no_default_branch(
    check_setup_repository: ScratchRepository,
):
    configure_a_staged_repository(check_setup_repository)
    check_setup_repository.start_branch_from(
        "work", f"refs/remotes/origin/{STAGING_DEFAULT_BRANCH}"
    )
    check_setup_repository.forget_declared_default_branch()
    check_setup_repository.declare_default_branch_on_work_remote(STAGING_DEFAULT_BRANCH)

    report = run_check_setup(check_setup_repository)
    assert report.exit_code == 1
    assert report.results[SetupCheck.BRANCH_BASE].status == CheckStatus.NEEDS_SETUP
    assert STAGING_DEFAULT_BRANCH in report.results[SetupCheck.BRANCH_BASE].detail


def test_prefers_the_personal_base_override_over_the_committed_one(
    check_setup_repository: ScratchRepository,
):
    overridden_base = "trunk"
    check_setup_repository.write(
        StackConfigurationPath.COMMITTED, stack_configuration(CONFIGURED_BASE_BRANCH)
    )
    check_setup_repository.commit_everything("declare the configured base")
    check_setup_repository.update_notes_branch_file(
        StackConfigurationPath.PERSONAL, stack_configuration(overridden_base)
    )
    check_setup_repository.add_work_remote()
    check_setup_repository.declare_default_branch(overridden_base)

    report = run_check_setup(check_setup_repository)
    assert report.exit_code == 0
    assert report.results[SetupCheck.BRANCH_BASE].status == CheckStatus.OK
    assert overridden_base in report.results[SetupCheck.BRANCH_BASE].detail


def test_reports_no_verdict_when_nothing_configures_a_base_branch(
    check_setup_repository: ScratchRepository,
):
    check_setup_repository.add_work_remote()
    check_setup_repository.declare_default_branch(STAGING_DEFAULT_BRANCH)

    report = run_check_setup(check_setup_repository)
    assert report.exit_code == 0
    assert report.results[SetupCheck.BRANCH_BASE].status == CheckStatus.INFORMATIONAL

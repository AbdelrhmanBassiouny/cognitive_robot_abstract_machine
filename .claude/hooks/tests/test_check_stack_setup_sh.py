"""
Integration tests for check-stack-setup.sh's per-check reporting and exit code.

Runs against a scratch project root whose fork, upstream and notes remotes are all local
bare repositories - so a full check completes with no network access, which is what lets
these run in CI.
"""

from __future__ import annotations

import os
import subprocess
from enum import StrEnum
from pathlib import Path

import pytest

from scratch_repository import ScratchRepository, initialize_bare_repository
from setup_report import CheckStatus, ExitCode, SetupReport

# The files check-stack-setup.sh's `stack_tooling_files` check requires, relative to the
# project root. Literals rather than values read from resolve-personal-notes-config.sh,
# for the reason test_check_setup_sh.py gives for the same list: a rename that breaks the
# check should have to be made deliberately here too.
STACK_TOOLING_FILES = (
    ".claude/stack/stack.py",
    ".claude/stack/stack.toml",
    ".claude/stack/README.md",
    ".claude/skills/stacked-pr-maintenance/SKILL.md",
    ".claude/skills/stacked-pr-maintenance/routine-prompt.md",
)

BOARD_PATH = ".claude/stack/board.json"

PERSONAL_STACK_CONFIG_PATH = ".claude/personal/stack.toml"

UPSTREAM_BASE = "main"

FORK_REPOSITORY = "a-fork-owner/a-project"
"""
The fork the scratch checkout is configured to hold its stack in.

Remotes are matched by the repository their URL names, so the bare repositories standing
in for them are created at paths ending in ``<owner>/<name>.git`` and addressed as
``file://`` URLs - which names a repository the same way an HTTPS URL does, while still
being a git remote these tests can actually push to without a network.
"""

UPSTREAM_REPOSITORY = "an-upstream-owner/a-project"
"""
The upstream the scratch checkout is reviewed in, overriding the committed default so
these tests name no real repository.
"""


class StackSetupCheck(StrEnum):
    """
    The checks check-stack-setup.sh reports on, in the order it prints them.
    """

    STACK_TOOLING_FILES = "stack_tooling_files"
    PYTHON_TOML_SUPPORT = "python_toml_support"
    STACK_CONFIGURATION = "stack_configuration"
    FORK_REMOTE = "fork_remote"
    FORK_REMOTE_URL = "fork_remote_url"
    UPSTREAM_REMOTE = "upstream_remote"
    UPSTREAM_REMOTE_URL = "upstream_remote_url"
    UPSTREAM_BASE = "upstream_base"
    PERSONAL_STACK_CONFIG = "personal_stack_config"
    BOARD_IGNORED = "board_ignored"
    BOARD_SNAPSHOT = "board_snapshot"


# %% the scratch layout


def repository_url(root: Path, repository: str) -> tuple[Path, str]:
    """
    Create a bare repository whose path names *repository*, and the URL addressing it.

    :param root: The directory to create it under.
    :param repository: The ``owner/name`` the remote should be seen as pointing at.
    :return: The bare repository's path, and the ``file://`` URL naming it.
    """
    path = initialize_bare_repository(root / f"{repository}.git")
    return path, f"file://{path}"


@pytest.fixture
def upstream_remote(tmp_path: Path, scratch_repository: ScratchRepository) -> Path:
    """
    A bare repository standing in for the upstream review remote, carrying the base
    branch every stack ultimately targets.

    :param tmp_path: pytest's per-test temporary directory.
    :param scratch_repository: The repository whose first commit seeds the base branch.
    :return: The bare repository's path.
    """
    return repository_url(tmp_path, UPSTREAM_REPOSITORY)[0]


@pytest.fixture
def stack_repository(
    scratch_repository: ScratchRepository, upstream_remote: Path, tmp_path: Path
) -> ScratchRepository:
    """
    A scratch repository set up so every check-stack-setup.sh check passes: the real
    scripts, the stack tooling files, a gitignored board, and fork/upstream remotes that
    both resolve.

    Individual tests break exactly one of those conditions to assert the matching check
    reports it.

    :param scratch_repository: The initialized scratch repository and notes remote.
    :param upstream_remote: The bare repository standing in for the upstream.
    :param tmp_path: pytest's per-test temporary directory.
    :return: The same repository, fully set up.
    """
    scratch_repository.install_hook_scripts(
        "resolve-personal-notes-config.sh", "check-stack-setup.sh"
    )
    install_stack_tooling(scratch_repository)

    scratch_repository.write(".gitignore", f"CLAUDE.local.md\n{BOARD_PATH}\n")
    scratch_repository.commit_everything("initial commit")

    _, fork_url = repository_url(tmp_path, FORK_REPOSITORY)
    scratch_repository.run_git("remote", "add", "origin", fork_url)
    scratch_repository.run_git("remote", "add", "cram2", f"file://{upstream_remote}")
    scratch_repository.run_git("push", "--quiet", "cram2", f"HEAD:{UPSTREAM_BASE}")
    scratch_repository.resolve_notes_remote_to()
    return scratch_repository


def install_stack_tooling(repository: ScratchRepository) -> None:
    """
    Copy the real ``.claude/stack/`` files into the scratch layout.

    The real stack.py is installed rather than a placeholder because the checker asks it
    for the resolved configuration - a stub would make the layering checks vacuous. Its
    stack.toml is rewritten to name this scratch layout's repositories, since the
    committed one deliberately names no fork at all.

    :param repository: The scratch repository to install into.
    """
    project_root = Path(__file__).parent.parent.parent.parent
    for tooling_file in STACK_TOOLING_FILES:
        (repository.project_root / tooling_file).parent.mkdir(
            parents=True, exist_ok=True
        )
        (repository.project_root / tooling_file).write_text(
            (project_root / tooling_file).read_text()
        )
    configuration = repository.project_root / ".claude" / "stack" / "stack.toml"
    kept = [
        line
        for line in configuration.read_text().splitlines()
        if not line.startswith("upstream_repository")
    ]
    configuration.write_text(
        "\n".join(
            [
                *kept,
                f'fork_repository = "{FORK_REPOSITORY}"',
                f'upstream_repository = "{UPSTREAM_REPOSITORY}"',
                "",
            ]
        )
    )


def run_check_stack_setup(repository: ScratchRepository) -> SetupReport:
    """
    Run the scratch layout's check-stack-setup.sh and parse its report.

    Every ``CLAUDE_PERSONAL_NOTES_*`` variable is stripped from the inherited
    environment first, so a value set in whoever's shell is running the tests can never
    change what they assert.

    :param repository: A fixture-built scratch repository.
    :return: The parsed report.
    """
    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith("CLAUDE_PERSONAL_NOTES_")
    }
    return SetupReport.from_completed_process(
        subprocess.run(
            [
                "bash",
                str(
                    repository.project_root
                    / ".claude"
                    / "hooks"
                    / "check-stack-setup.sh"
                ),
            ],
            cwd=repository.project_root,
            capture_output=True,
            text=True,
            env=environment,
        ),
        StackSetupCheck,
    )


# %% the fully set-up clone


def test_reports_no_work_needed_when_everything_is_in_place(
    stack_repository: ScratchRepository,
):
    report = run_check_stack_setup(stack_repository)

    assert report.exit_code == ExitCode.SET_UP
    assert [
        check
        for check, result in report.results.items()
        if result.status == CheckStatus.NEEDS_SETUP
    ] == []


def test_reports_every_check_it_documents(stack_repository: ScratchRepository):
    report = run_check_stack_setup(stack_repository)

    assert set(report.results) == set(StackSetupCheck)


# %% the tooling itself


def test_reports_which_stack_tooling_files_are_missing(
    stack_repository: ScratchRepository,
):
    (stack_repository.project_root / ".claude" / "stack" / "stack.toml").unlink()

    report = run_check_stack_setup(stack_repository)

    result = report.results[StackSetupCheck.STACK_TOOLING_FILES]
    assert result.status == CheckStatus.NEEDS_SETUP
    assert ".claude/stack/stack.toml" in result.detail
    assert report.exit_code == ExitCode.NEEDS_SETUP


def test_requires_the_maintenance_instructions_rather_than_the_retired_routine_document(
    stack_repository: ScratchRepository,
):
    """
    The instructions moved out of ``.claude/stack/`` and into the maintenance skill, so a
    checkout carrying the real layout must read as set up - and one missing the skill must
    not. Checking the retired paths reported ``needs-setup`` on a correct installation.
    """
    skill_document = (
        stack_repository.project_root
        / ".claude"
        / "skills"
        / "stacked-pr-maintenance"
        / "SKILL.md"
    )

    assert (
        run_check_stack_setup(stack_repository)
        .results[StackSetupCheck.STACK_TOOLING_FILES]
        .status
        == CheckStatus.OK
    )

    skill_document.unlink()
    result = run_check_stack_setup(stack_repository).results[
        StackSetupCheck.STACK_TOOLING_FILES
    ]

    assert result.status == CheckStatus.NEEDS_SETUP
    assert ".claude/skills/stacked-pr-maintenance/SKILL.md" in result.detail


def test_does_not_check_the_remotes_when_the_configuration_cannot_be_resolved(
    stack_repository: ScratchRepository,
):
    (stack_repository.project_root / ".claude" / "stack" / "stack.py").unlink()

    report = run_check_stack_setup(stack_repository)

    assert (
        report.results[StackSetupCheck.STACK_CONFIGURATION].status
        == CheckStatus.NEEDS_SETUP
    )
    assert report.results[StackSetupCheck.FORK_REMOTE].status == CheckStatus.NEEDS_SETUP
    assert "not checked" in report.results[StackSetupCheck.FORK_REMOTE].detail


# %% the remotes the configuration names


def test_reports_a_fork_remote_that_is_not_in_the_clone(
    stack_repository: ScratchRepository,
):
    stack_repository.run_git("remote", "remove", "origin")

    report = run_check_stack_setup(stack_repository)

    result = report.results[StackSetupCheck.FORK_REMOTE]
    assert result.status == CheckStatus.NEEDS_SETUP
    assert "origin" in result.detail


def test_checks_the_remote_the_personal_override_names_rather_than_the_committed_default(
    stack_repository: ScratchRepository,
):
    """
    ``fork_remote`` is the name to give the fork remote when the clone has none, so the
    override is what a contributor with no ``origin`` is told to add.
    """
    stack_repository.run_git("remote", "remove", "origin")
    stack_repository.publish_notes_branch(
        {PERSONAL_STACK_CONFIG_PATH: 'fork_remote = "my-own-fork"\n'}
    )
    stack_repository.resolve_notes_remote_to()

    report = run_check_stack_setup(stack_repository)

    result = report.results[StackSetupCheck.FORK_REMOTE]
    assert result.status == CheckStatus.NEEDS_SETUP
    assert "my-own-fork" in result.detail


def test_reports_the_remote_urls_as_context_rather_than_a_verdict(
    stack_repository: ScratchRepository,
):
    report = run_check_stack_setup(stack_repository)

    for check in (StackSetupCheck.FORK_REMOTE_URL, StackSetupCheck.UPSTREAM_REMOTE_URL):
        assert report.results[check].status == CheckStatus.INFORMATIONAL
    assert (
        f"{FORK_REPOSITORY}.git"
        in report.results[StackSetupCheck.FORK_REMOTE_URL].detail
    )


def test_reports_an_upstream_base_that_is_not_on_the_upstream_remote(
    stack_repository: ScratchRepository, upstream_remote: Path
):
    subprocess.run(
        ["git", "branch", "-D", UPSTREAM_BASE],
        cwd=upstream_remote,
        capture_output=True,
        check=True,
    )

    report = run_check_stack_setup(stack_repository)

    result = report.results[StackSetupCheck.UPSTREAM_BASE]
    assert result.status == CheckStatus.NEEDS_SETUP
    assert UPSTREAM_BASE in result.detail


# %% the personal override and the board


def test_reports_a_personal_stack_config_that_has_not_been_written(
    stack_repository: ScratchRepository,
):
    report = run_check_stack_setup(stack_repository)

    result = report.results[StackSetupCheck.PERSONAL_STACK_CONFIG]
    assert result.status == CheckStatus.INFORMATIONAL
    assert "no" in result.detail.lower()


def test_reports_a_personal_stack_config_that_exists(
    stack_repository: ScratchRepository,
):
    stack_repository.publish_notes_branch(
        {PERSONAL_STACK_CONFIG_PATH: 'upstream_base = "main"\n'}
    )
    stack_repository.resolve_notes_remote_to()

    report = run_check_stack_setup(stack_repository)

    result = report.results[StackSetupCheck.PERSONAL_STACK_CONFIG]
    assert result.status == CheckStatus.INFORMATIONAL
    assert PERSONAL_STACK_CONFIG_PATH in result.detail


def test_reports_a_board_snapshot_that_has_never_been_written(
    stack_repository: ScratchRepository,
):
    result = run_check_stack_setup(stack_repository).results[
        StackSetupCheck.BOARD_SNAPSHOT
    ]

    assert result.status == CheckStatus.INFORMATIONAL


def test_reports_a_board_that_is_not_gitignored(stack_repository: ScratchRepository):
    stack_repository.write(".gitignore", "CLAUDE.local.md\n")
    stack_repository.commit_everything("stop ignoring the board")

    report = run_check_stack_setup(stack_repository)

    result = report.results[StackSetupCheck.BOARD_IGNORED]
    assert result.status == CheckStatus.NEEDS_SETUP
    assert BOARD_PATH in result.detail
    assert report.exit_code == ExitCode.NEEDS_SETUP

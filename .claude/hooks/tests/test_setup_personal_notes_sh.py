"""
Integration tests for setup-personal-notes.sh: its argument contract, the full non-
interactive setup it performs, and its safety behaviour around a remote someone else
owns and labels it hasn't been asked to create.

Runs against a scratch project root whose notes remote is a local bare repository, with
``gh``, ``curl`` and ``pip`` stubbed on ``PATH`` - so a full setup completes with no
network access and no credentials, which is what lets these run in CI.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from github_api import GitHubRemoteUrl, PullRequestLabel
from scratch_repository import (
    FIXTURE_DIRECTORY,
    NOTES_PATH,
    SCRATCH_IDENTITY,
    GitIdentity,
    ScratchRepository,
)
from setup_report import CheckStatus, SetupCheck, SetupReport
from stub_executables import StubbedExecutable, StubExecutableDirectory
from tooling_files import HookScript, ProjectFile, SetupPrerequisiteFile

SCRIPTS_UNDER_TEST = (
    HookScript.CHECK_SETUP,
    HookScript.CREATE_NOTES_BRANCH,
    HookScript.WRITE_NOTES_FILE,
    HookScript.SESSION_START,
    HookScript.SAVE_GIT_IDENTITY,
    HookScript.GITHUB_API,
    HookScript.SETUP,
)
"""
The hook scripts a full setup run touches.

What each of them sources is installed with it, so nothing here restates another
script's own dependencies.
"""

STARTER_NOTES_FIXTURE = FIXTURE_DIRECTORY / "starter-notes.md"
"""
The template ``--starter-notes`` seeds the notes file from.
"""

STUB_LOGIN = "stub-user"
"""
The login the stubbed GitHub reports.
"""

ORIGIN_REPOSITORY = f"{STUB_LOGIN}/octo-repo"
"""
An origin owned by that login, so the ownership check has something real to agree with.
"""

SOMEONE_ELSE_REPOSITORY = "someone-else/their-repo"
"""
An origin owned by anybody else, which the ownership check must refuse.
"""

CREATE_LABEL_METHOD = "POST"
"""
The HTTP method a label creation is recognised by in the stub's call log.
"""


def identity_arguments(identity: GitIdentity) -> tuple[str, ...]:
    """
    The setup script's arguments recording *identity*.

    :param identity: The identity to record.
    :return: The ``--name``/``--email`` pair.
    """
    return ("--name", identity.name, "--email", identity.email)


# %% the scratch layout


@pytest.fixture
def setup_repository(scratch_repository: ScratchRepository) -> ScratchRepository:
    """
    A scratch repository that is deliberately not set up yet.

    The hook scripts and the tooling files are in place, but there is no notes branch, no
    notes file and no ``CLAUDE.local.md`` - setup-personal-notes.sh creates all three.

    :param scratch_repository: The initialized scratch repository and notes remote.
    :return: The same repository, ready for a setup run.
    """
    scratch_repository.install_hook_scripts(*SCRIPTS_UNDER_TEST)
    scratch_repository.write_setup_prerequisites()
    scratch_repository.write(
        ProjectFile.STARTER_NOTES, STARTER_NOTES_FIXTURE.read_text()
    )
    # The repository pull requests are opened against, which is where the labels are
    # checked - distinct from the notes remote, which is a local bare repository here.
    scratch_repository.run_git(
        "remote",
        "add",
        "origin",
        GitHubRemoteUrl.HTTPS_WITH_SUFFIX.for_repository(ORIGIN_REPOSITORY),
    )
    scratch_repository.commit_everything("initial commit")
    return scratch_repository


def run_setup(
    repository: ScratchRepository,
    stub_executables: StubExecutableDirectory,
    *arguments: str,
    identity: GitIdentity | None = SCRATCH_IDENTITY,
    hidden_executables: tuple[StubbedExecutable, ...] = (StubbedExecutable.GH,),
    **environment_overrides: str,
) -> subprocess.CompletedProcess[str]:
    """
    Run the scratch layout's setup-personal-notes.sh.

    :param repository: A fixture-built scratch repository.
    :param stub_executables: The stub directory the run resolves ``gh``/``curl``/``pip``
        from.
    :param arguments: Arguments to pass to the script.
    :param identity: The identity to record, appended as ``--name``/``--email``. The
        scratch repository's own by default, which is what a contributor recording the
        identity they already commit as looks like; ``None`` to record none.
    :param hidden_executables: Executables to make unfindable, defaulting to hiding a
        real ``gh`` so a test only sees the stubs it installed itself.
    :param environment_overrides: Variables to set, chiefly the stubs' ``STUB_*``
        controls.
    :return: The finished subprocess.
    """
    return subprocess.run(
        [
            "bash",
            str(repository.hook_script_path(HookScript.SETUP)),
            *arguments,
            *(identity_arguments(identity) if identity else ()),
        ],
        cwd=repository.project_root,
        capture_output=True,
        text=True,
        env=stub_executables.subprocess_environment(
            hidden_executables=hidden_executables, **environment_overrides
        ),
    )


def run_check_setup(
    repository: ScratchRepository, stub_executables: StubExecutableDirectory
) -> subprocess.CompletedProcess[str]:
    """
    Run check-setup.sh against the same scratch layout, to confirm a setup run left it
    in the state the script claims.

    :param repository: A fixture-built scratch repository.
    :param stub_executables: The stub directory, reused so the environment matches.
    :return: The finished subprocess.
    """
    return subprocess.run(
        ["bash", str(repository.hook_script_path(HookScript.CHECK_SETUP))],
        cwd=repository.project_root,
        capture_output=True,
        text=True,
        env=stub_executables.subprocess_environment(
            hidden_executables=(StubbedExecutable.GH,)
        ),
    )


# %% the argument contract


def test_requires_a_remote(
    setup_repository: ScratchRepository, stub_executables: StubExecutableDirectory
):
    result = run_setup(setup_repository, stub_executables)

    assert result.returncode != 0
    assert "--remote" in result.stderr
    assert setup_repository.notes_branch_commit() is None


def test_rejects_an_unknown_flag(
    setup_repository: ScratchRepository, stub_executables: StubExecutableDirectory
):
    result = run_setup(
        setup_repository,
        stub_executables,
        "--remote",
        str(setup_repository.notes_remote_path),
        "--not-a-flag",
    )

    assert result.returncode != 0
    assert "--not-a-flag" in result.stderr
    assert setup_repository.notes_branch_commit() is None


# %% the git identity every clone authors as


def test_records_the_git_identity_it_is_given(
    setup_repository: ScratchRepository,
    stub_executables: StubExecutableDirectory,
    tmp_path: Path,
):
    result = run_setup(
        setup_repository,
        stub_executables,
        "--remote",
        str(setup_repository.notes_remote_path),
    )

    assert result.returncode == 0, result.stderr
    checkout = setup_repository.clone_notes_branch(tmp_path / "notes-checkout")
    recorded = GitIdentity.from_git_config_file(
        checkout / ProjectFile.PERSONAL_GIT_IDENTITY
    )
    assert recorded == SCRATCH_IDENTITY
    report = SetupReport.from_completed_process(result)
    assert report.results[SetupCheck.GIT_IDENTITY].status is CheckStatus.OK


def test_refuses_a_name_without_an_email(
    setup_repository: ScratchRepository, stub_executables: StubExecutableDirectory
):
    # Half an identity cannot author a commit, and the refusal comes before anything is
    # written, so a run that got it wrong leaves the clone exactly as it found it.
    result = run_setup(
        setup_repository,
        stub_executables,
        "--remote",
        str(setup_repository.notes_remote_path),
        "--name",
        SCRATCH_IDENTITY.name,
        identity=None,
    )

    assert result.returncode != 0
    assert "--name" in result.stderr
    assert "--email" in result.stderr
    assert setup_repository.notes_branch_commit() is None


def test_finishes_the_rest_of_the_setup_when_given_no_identity(
    setup_repository: ScratchRepository,
    stub_executables: StubExecutableDirectory,
    tmp_path: Path,
):
    # Recording one is not this script's to guess at - what a contributor's commits
    # should say is theirs - so a run without it finishes everything else and leaves the
    # one check it cannot satisfy to the report, rather than aborting or inventing an
    # answer. What that report says is check-setup.sh's own, and is asserted there.
    result = run_setup(
        setup_repository,
        stub_executables,
        "--remote",
        str(setup_repository.notes_remote_path),
        identity=None,
    )

    assert setup_repository.notes_branch_commit() is not None
    checkout = setup_repository.clone_notes_branch(tmp_path / "notes-checkout")
    assert not (checkout / ProjectFile.PERSONAL_GIT_IDENTITY).exists()
    report = SetupReport.from_completed_process(result)
    assert report.results[SetupCheck.GIT_IDENTITY].status is CheckStatus.NEEDS_SETUP
    assert report.results[SetupCheck.NOTES_FILE].status is CheckStatus.OK


# %% a full, non-interactive setup


def test_completes_a_full_setup(
    setup_repository: ScratchRepository, stub_executables: StubExecutableDirectory
):
    result = run_setup(
        setup_repository,
        stub_executables,
        "--remote",
        str(setup_repository.notes_remote_path),
    )

    assert result.returncode == 0, result.stderr
    assert run_check_setup(setup_repository, stub_executables).returncode == 0


def test_points_the_configured_remote_at_the_one_it_was_given(
    setup_repository: ScratchRepository, stub_executables: StubExecutableDirectory
):
    run_setup(
        setup_repository,
        stub_executables,
        "--remote",
        str(setup_repository.notes_remote_path),
    )

    configured_remote = setup_repository.run_git(
        "config", "--get", "claude.personalNotesRemote"
    )
    assert configured_remote.stdout.strip() == str(setup_repository.notes_remote_path)


def test_leaves_the_notes_file_empty_without_starter_notes(
    setup_repository: ScratchRepository,
    stub_executables: StubExecutableDirectory,
    tmp_path: Path,
):
    run_setup(
        setup_repository,
        stub_executables,
        "--remote",
        str(setup_repository.notes_remote_path),
    )

    checkout = setup_repository.clone_notes_branch(tmp_path / "notes-checkout")
    assert (checkout / NOTES_PATH).read_text() == ""


def test_seeds_the_notes_file_from_the_starter_notes_when_asked(
    setup_repository: ScratchRepository,
    stub_executables: StubExecutableDirectory,
    tmp_path: Path,
):
    run_setup(
        setup_repository,
        stub_executables,
        "--remote",
        str(setup_repository.notes_remote_path),
        "--starter-notes",
    )

    checkout = setup_repository.clone_notes_branch(tmp_path / "notes-checkout")
    expected = STARTER_NOTES_FIXTURE.read_text()
    assert (checkout / NOTES_PATH).read_text() == expected


def test_prints_the_final_report(
    setup_repository: ScratchRepository, stub_executables: StubExecutableDirectory
):
    result = run_setup(
        setup_repository,
        stub_executables,
        "--remote",
        str(setup_repository.notes_remote_path),
    )

    report = SetupReport.from_completed_process(result)
    assert {
        SetupCheck.NOTES_BRANCH,
        SetupCheck.NOTES_FILE,
        SetupCheck.CLAUDE_LOCAL_MD,
    } <= report.results.keys()


# %% re-running


def test_a_second_run_changes_nothing(
    setup_repository: ScratchRepository, stub_executables: StubExecutableDirectory
):
    first = run_setup(
        setup_repository,
        stub_executables,
        "--remote",
        str(setup_repository.notes_remote_path),
        "--starter-notes",
    )
    assert first.returncode == 0, first.stderr
    commit_after_first_run = setup_repository.notes_branch_commit()

    second = run_setup(
        setup_repository,
        stub_executables,
        "--remote",
        str(setup_repository.notes_remote_path),
        "--starter-notes",
    )

    assert second.returncode == 0, second.stderr
    assert setup_repository.notes_branch_commit() == commit_after_first_run


# %% the remote's owner


def test_aborts_before_creating_anything_when_the_remote_belongs_to_someone_else(
    setup_repository: ScratchRepository, stub_executables: StubExecutableDirectory
):
    stub_executables.install(StubbedExecutable.GH)

    result = run_setup(
        setup_repository,
        stub_executables,
        "--remote",
        GitHubRemoteUrl.HTTPS_WITH_SUFFIX.for_repository(SOMEONE_ELSE_REPOSITORY),
        hidden_executables=(),
        STUB_GH_LOGIN=STUB_LOGIN,
    )

    assert result.returncode != 0
    assert SOMEONE_ELSE_REPOSITORY in result.stderr
    assert STUB_LOGIN in result.stderr
    # Nothing may have been pushed anywhere observable before the refusal.
    assert setup_repository.notes_branch_commit() is None


def test_completes_without_credentials_but_says_it_could_not_verify_the_owner(
    setup_repository: ScratchRepository, stub_executables: StubExecutableDirectory
):
    result = run_setup(
        setup_repository,
        stub_executables,
        "--remote",
        str(setup_repository.notes_remote_path),
    )

    assert result.returncode == 0, result.stderr
    assert setup_repository.notes_branch_commit() is not None
    assert "could not" in (result.stdout + result.stderr).lower()


# %% pull request labels


def test_reports_missing_labels_without_creating_them(
    setup_repository: ScratchRepository,
    stub_executables: StubExecutableDirectory,
    tmp_path: Path,
):
    stub_executables.install(StubbedExecutable.GH)
    call_log = tmp_path / "gh-calls.txt"

    result = run_setup(
        setup_repository,
        stub_executables,
        "--remote",
        str(setup_repository.notes_remote_path),
        hidden_executables=(),
        STUB_GH_LOGIN=STUB_LOGIN,
        STUB_GH_MISSING_LABELS=PullRequestLabel.IN_REVIEW,
        STUB_GH_CALL_LOG=str(call_log),
    )

    assert result.returncode == 0, result.stderr
    assert PullRequestLabel.IN_REVIEW in result.stdout
    assert CREATE_LABEL_METHOD not in call_log.read_text()


def test_creates_only_the_missing_labels_when_asked(
    setup_repository: ScratchRepository,
    stub_executables: StubExecutableDirectory,
    tmp_path: Path,
):
    stub_executables.install(StubbedExecutable.GH)
    call_log = tmp_path / "gh-calls.txt"

    result = run_setup(
        setup_repository,
        stub_executables,
        "--remote",
        str(setup_repository.notes_remote_path),
        "--create-labels",
        hidden_executables=(),
        STUB_GH_LOGIN=STUB_LOGIN,
        STUB_GH_MISSING_LABELS=PullRequestLabel.IN_REVIEW,
        STUB_GH_CALL_LOG=str(call_log),
    )

    assert result.returncode == 0, result.stderr
    creation_calls = [
        line
        for line in call_log.read_text().splitlines()
        if CREATE_LABEL_METHOD in line
    ]
    assert len(creation_calls) == 1
    assert f"name={PullRequestLabel.IN_REVIEW}" in creation_calls[0]
    assert f"repos/{ORIGIN_REPOSITORY}/labels" in creation_calls[0]


# %% the plan-dashboard dependencies


def test_reports_a_failed_dependency_install_and_carries_on(
    setup_repository: ScratchRepository, stub_executables: StubExecutableDirectory
):
    stub_executables.install(StubbedExecutable.PIP)
    setup_repository.write(
        SetupPrerequisiteFile.DASHBOARD_REQUIREMENTS,
        "a-distribution-that-is-not-installed\n",
    )

    result = run_setup(
        setup_repository,
        stub_executables,
        "--remote",
        str(setup_repository.notes_remote_path),
    )

    # The steps after the failed install still ran: session-start.sh wrote the file.
    assert (setup_repository.project_root / ProjectFile.CLAUDE_LOCAL_MD).is_file()
    assert setup_repository.notes_branch_commit() is not None
    assert StubbedExecutable.PIP in result.stdout + result.stderr

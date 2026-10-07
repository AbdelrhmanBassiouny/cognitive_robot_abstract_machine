"""
The one-time personal-notes setup: its argument contract, the full non-interactive setup
it performs, and its safety around a remote someone else owns and labels it hasn't been
asked to create.

The setup runs in-process against a scratch project root whose notes remote is a local bare
repository, with GitHub answered by an in-process stand-in - so a full setup completes with
no network and no credentials. The hook scripts it drives run for real.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from basstler.locations import HookScript, PackageLocation, ProjectLocation
from basstler.maintenance_github import AUTHENTICATED_USER_PATH, GitHubConnection
from basstler.repository import Repository
from basstler.repository_label import RepositoryLabel
from basstler.setup_personal_notes import (
    ExitCode,
    ForeignNotesRemoteError,
    PersonalNotesSetup,
    SetupRequest,
)
from basstler.setup_report import CheckStatus, SetupCheck, SetupReport
from basstler.setup_steps import PersonalNotesSetting

from .constants import PersonalNotesPath, ProjectFile
from .executable_stubs import (
    ExecutableStubDirectory,
    StubbedExecutable,
    path_hiding_executable,
)
from .github_api_replay import REPLAYED_REPOSITORY, HttpMethod, ReplayingGitHubApi
from .scratch_repository import (
    SCRATCH_IDENTITY,
    GitIdentity,
    ScratchRepository,
    SetupPrerequisiteFile,
    initialize_bare_repository,
)

SCRIPTS_UNDER_TEST = (
    HookScript.SETUP,
    HookScript.CHECK_SETUP,
    HookScript.CREATE_NOTES_BRANCH,
    HookScript.WRITE_NOTES_FILE,
    HookScript.SESSION_START,
    HookScript.SAVE_GIT_IDENTITY,
)
"""
The hook scripts a full setup run touches; what each sources is installed with it.
"""

SOMEONE_ELSE = Repository("someone-else", "their-repo")
"""
A repository owned by anybody but the credential's owner, which must be refused.
"""

UNINSTALLABLE_REQUIREMENT = "basstler-no-such-distribution>=1"
"""
A distribution nothing can have installed, so the run has something to install.
"""

A_TOKEN = "a-token"
"""
The credential the stand-in accepts; its value is never inspected.
"""


def github_url(repository: Repository) -> str:
    """
    :param repository: The repository to address.
    :return: Its HTTPS remote URL.
    """
    return f"https://github.com/{repository}.git"


def identity_arguments(identity: GitIdentity) -> list[str]:
    """
    :param identity: The identity to record.
    :return: The ``--name``/``--email`` pair recording it.
    """
    return ["--name", identity.name, "--email", identity.email]


# %% the scratch layout


@pytest.fixture
def setup_repository(scratch_repository: ScratchRepository) -> ScratchRepository:
    """
    A scratch repository that is deliberately not set up yet: the hook scripts, the
    package and the tooling files are in place, but there is no notes branch, no notes
    file and no ``CLAUDE.local.md``.

    :param scratch_repository: The initialized scratch repository and notes remote.
    :return: The same repository, ready for a setup run.
    """
    scratch_repository.install_hook_scripts(*SCRIPTS_UNDER_TEST)
    scratch_repository.install_package()
    scratch_repository.write_setup_prerequisites()
    scratch_repository.write(
        ProjectLocation.STARTER_NOTES,
        (PackageLocation.REPOSITORY_ROOT / ProjectLocation.STARTER_NOTES).read_text(),
    )
    # The repository pull requests are opened against, which is where the labels are
    # checked - distinct from the notes remote, a local bare repository here.
    scratch_repository.run_git(
        "remote", "add", "origin", github_url(REPLAYED_REPOSITORY)
    )
    scratch_repository.commit_everything("initial commit")
    return scratch_repository


def run_setup(
    repository: ScratchRepository,
    stub_bin: ExecutableStubDirectory,
    *arguments: str,
    connection: GitHubConnection | None = None,
    identity: GitIdentity | None = SCRATCH_IDENTITY,
    **environment_overrides: str,
) -> ExitCode:
    """
    Run the setup against the scratch layout.

    :param repository: A fixture-built scratch repository.
    :param stub_bin: The stub directory the hook scripts resolve ``pip`` from.
    :param arguments: Command-line arguments besides the identity.
    :param connection: GitHub access, ``None`` for a run with no credential.
    :param identity: The identity to record, the scratch repository's own by default;
        ``None`` records none.
    :param environment_overrides: Variables to set, chiefly the stubs' ``STUB_*``
        controls.
    :return: The run's exit code.
    """
    request = SetupRequest.from_arguments(
        [*arguments, *(identity_arguments(identity) if identity else [])]
    )
    environment = stub_bin.subprocess_environment(
        hidden_executables=(StubbedExecutable.GH,), **environment_overrides
    )
    return PersonalNotesSetup(
        repository.project_root, environment, request, connection
    ).run()


def setup_report(repository: ScratchRepository) -> SetupReport:
    """
    :param repository: The scratch repository a setup ran in.
    :return: What check-setup.sh reports there now.
    """
    return SetupReport.from_completed_process(
        repository.run_hook_script(HookScript.CHECK_SETUP)
    )


# %% the argument contract


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["--remote", "origin", "--not-a-flag"],
        ["--remote", "origin", "--name", SCRATCH_IDENTITY.name],
    ],
    ids=["no remote", "unknown flag", "name without email"],
)
def test_refuses_an_incomplete_or_unknown_command_line(arguments: list[str]):
    with pytest.raises(SystemExit):
        SetupRequest.from_arguments(arguments)


def test_the_shim_refuses_before_writing_anything(setup_repository: ScratchRepository):
    result = setup_repository.run_hook_script(HookScript.SETUP)

    assert result.returncode != 0
    assert setup_repository.notes_branch_commit() is None


def test_the_shim_runs_a_full_setup_with_no_credentials(
    setup_repository: ScratchRepository, tmp_path: Path
):
    result = setup_repository.run_hook_script(
        HookScript.SETUP,
        "--remote",
        str(setup_repository.notes_remote_path),
        *identity_arguments(SCRATCH_IDENTITY),
        PATH=path_hiding_executable(StubbedExecutable.GH, tmp_path),
    )

    assert result.returncode == ExitCode.SET_UP, result.stderr


# %% a full, non-interactive setup


def test_completes_a_full_setup(
    setup_repository: ScratchRepository, stub_bin: ExecutableStubDirectory
):
    exit_code = run_setup(
        setup_repository, stub_bin, "--remote", str(setup_repository.notes_remote_path)
    )

    assert exit_code is ExitCode.SET_UP
    assert setup_report(setup_repository).exit_code == ExitCode.SET_UP


def test_points_the_configured_remote_at_the_one_it_was_given(
    setup_repository: ScratchRepository, stub_bin: ExecutableStubDirectory
):
    run_setup(
        setup_repository, stub_bin, "--remote", str(setup_repository.notes_remote_path)
    )

    configured = setup_repository.run_git(
        "config", "--get", PersonalNotesSetting.REMOTE.git_config_key
    )
    assert configured.stdout.strip() == str(setup_repository.notes_remote_path)


def test_leaves_the_notes_file_empty_without_starter_notes(
    setup_repository: ScratchRepository,
    stub_bin: ExecutableStubDirectory,
    tmp_path: Path,
):
    run_setup(
        setup_repository, stub_bin, "--remote", str(setup_repository.notes_remote_path)
    )

    checkout = setup_repository.clone_notes_branch(tmp_path / "notes-checkout")
    assert (checkout / ProjectLocation.PERSONAL_NOTES_DOCUMENT).read_text() == ""


def test_seeds_the_notes_file_from_the_starter_notes_when_asked(
    setup_repository: ScratchRepository,
    stub_bin: ExecutableStubDirectory,
    tmp_path: Path,
):
    run_setup(
        setup_repository,
        stub_bin,
        "--remote",
        str(setup_repository.notes_remote_path),
        "--starter-notes",
    )

    checkout = setup_repository.clone_notes_branch(tmp_path / "notes-checkout")
    assert (checkout / ProjectLocation.PERSONAL_NOTES_DOCUMENT).read_text() == (
        setup_repository.project_root / ProjectLocation.STARTER_NOTES
    ).read_text()


def test_a_second_run_changes_nothing(
    setup_repository: ScratchRepository, stub_bin: ExecutableStubDirectory
):
    arguments = ("--remote", str(setup_repository.notes_remote_path), "--starter-notes")
    assert run_setup(setup_repository, stub_bin, *arguments) is ExitCode.SET_UP
    commit_after_first_run = setup_repository.notes_branch_commit()

    assert run_setup(setup_repository, stub_bin, *arguments) is ExitCode.SET_UP
    assert setup_repository.notes_branch_commit() == commit_after_first_run


# %% the git identity every clone authors as


def test_records_the_git_identity_it_is_given(
    setup_repository: ScratchRepository,
    stub_bin: ExecutableStubDirectory,
    tmp_path: Path,
):
    run_setup(
        setup_repository, stub_bin, "--remote", str(setup_repository.notes_remote_path)
    )

    checkout = setup_repository.clone_notes_branch(tmp_path / "notes-checkout")
    recorded = GitIdentity.from_git_config_file(
        checkout / PersonalNotesPath.GIT_IDENTITY
    )
    assert recorded == SCRATCH_IDENTITY


def test_finishes_the_rest_of_the_setup_when_given_no_identity(
    setup_repository: ScratchRepository,
    stub_bin: ExecutableStubDirectory,
    tmp_path: Path,
):
    # What a contributor's commits should say is theirs to give, so a run without it
    # finishes everything else and leaves that one check to the report.
    exit_code = run_setup(
        setup_repository,
        stub_bin,
        "--remote",
        str(setup_repository.notes_remote_path),
        identity=None,
    )

    assert exit_code is ExitCode.SETUP_INCOMPLETE
    checkout = setup_repository.clone_notes_branch(tmp_path / "notes-checkout")
    assert not (checkout / PersonalNotesPath.GIT_IDENTITY).exists()
    report = setup_report(setup_repository)
    assert report.results[SetupCheck.GIT_IDENTITY].status is CheckStatus.NEEDS_SETUP
    assert report.results[SetupCheck.NOTES_FILE].status is CheckStatus.OK


# %% the remote's owner


def test_refuses_a_remote_someone_else_owns_before_writing_anything(
    setup_repository: ScratchRepository,
    stub_bin: ExecutableStubDirectory,
    github_api: ReplayingGitHubApi,
):
    with pytest.raises(ForeignNotesRemoteError) as refusal:
        run_setup(
            setup_repository,
            stub_bin,
            "--remote",
            github_url(SOMEONE_ELSE),
            connection=GitHubConnection(A_TOKEN),
        )

    assert refusal.value.repository == SOMEONE_ELSE
    assert refusal.value.login == github_api.login
    assert (
        setup_repository.run_git_allowing_failure(
            "config", "--get", PersonalNotesSetting.REMOTE.git_config_key
        ).returncode
        != 0
    )
    assert setup_repository.notes_branch_commit() is None


def test_accepts_a_remote_the_credential_owner_owns(
    setup_repository: ScratchRepository,
    stub_bin: ExecutableStubDirectory,
    github_api: ReplayingGitHubApi,
    tmp_path: Path,
):
    # Addressed as a URL whose last two segments name an owner and a repository, the way
    # every GitHub remote does, while still being a remote git can push to locally.
    owned_remote = initialize_bare_repository(
        tmp_path / github_api.login / "personal-notes.git"
    )
    github_api.labels = set(RepositoryLabel)

    exit_code = run_setup(
        setup_repository,
        stub_bin,
        "--remote",
        owned_remote.as_uri(),
        connection=GitHubConnection(A_TOKEN),
    )

    assert exit_code is ExitCode.SET_UP
    assert (HttpMethod.GET, AUTHENTICATED_USER_PATH) in [
        (request.method, request.path) for request in github_api.requests
    ]


# %% pull request labels


def test_reports_missing_labels_without_creating_them(
    setup_repository: ScratchRepository,
    stub_bin: ExecutableStubDirectory,
    github_api: ReplayingGitHubApi,
):
    github_api.labels = set(RepositoryLabel) - {RepositoryLabel.IN_REVIEW}

    exit_code = run_setup(
        setup_repository,
        stub_bin,
        "--remote",
        str(setup_repository.notes_remote_path),
        connection=GitHubConnection(A_TOKEN),
    )

    assert exit_code is ExitCode.SET_UP
    assert github_api.created_labels() == []


def test_creates_only_the_missing_labels_when_asked(
    setup_repository: ScratchRepository,
    stub_bin: ExecutableStubDirectory,
    github_api: ReplayingGitHubApi,
):
    github_api.labels = set(RepositoryLabel) - {RepositoryLabel.IN_REVIEW}

    run_setup(
        setup_repository,
        stub_bin,
        "--remote",
        str(setup_repository.notes_remote_path),
        "--create-labels",
        connection=GitHubConnection(A_TOKEN),
    )

    assert github_api.created_labels() == [
        {
            "name": RepositoryLabel.IN_REVIEW.value,
            "description": RepositoryLabel.IN_REVIEW.purpose,
        }
    ]


def test_creates_every_label_a_fresh_repository_lacks(
    setup_repository: ScratchRepository,
    stub_bin: ExecutableStubDirectory,
    github_api: ReplayingGitHubApi,
):
    run_setup(
        setup_repository,
        stub_bin,
        "--remote",
        str(setup_repository.notes_remote_path),
        "--create-labels",
        connection=GitHubConnection(A_TOKEN),
    )

    assert github_api.labels == set(RepositoryLabel)


# %% the package's own dependencies


def test_a_failed_dependency_install_neither_stops_the_run_nor_reads_as_success(
    setup_repository: ScratchRepository, stub_bin: ExecutableStubDirectory
):
    # The install happens inside session-start.sh, which the setup runs.
    stub_bin.install(StubbedExecutable.PIP)
    setup_repository.write(
        SetupPrerequisiteFile.PACKAGE_METADATA,
        f'[project]\ndependencies = ["{UNINSTALLABLE_REQUIREMENT}"]\n',
    )
    setup_repository.commit_everything("declare something that is not installed")

    exit_code = run_setup(
        setup_repository,
        stub_bin,
        "--remote",
        str(setup_repository.notes_remote_path),
        STUB_PIP_STATUS="1",
    )

    assert exit_code is ExitCode.SETUP_INCOMPLETE
    assert (setup_repository.project_root / ProjectFile.CLAUDE_LOCAL_MD).is_file()
    report = setup_report(setup_repository)
    assert (
        report.results[SetupCheck.DASHBOARD_DEPENDENCIES].status
        is CheckStatus.NEEDS_SETUP
    )

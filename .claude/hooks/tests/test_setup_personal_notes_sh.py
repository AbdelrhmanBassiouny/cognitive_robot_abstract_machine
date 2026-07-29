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

from scratch_repository import ScratchRepository
from stub_executables import StubExecutableDirectory

# The hook scripts a full setup run touches, all installed into the scratch layout.
SCRIPTS_UNDER_TEST = (
    "resolve-personal-notes-config.sh",
    "check-setup.sh",
    "create-personal-notes-branch.sh",
    "write-personal-notes-file.sh",
    "session-start.sh",
    "github-api.sh",
    "setup-personal-notes.sh",
)

# The files check-setup.sh's `tooling_files` check requires. Literals rather than values
# read from resolve-personal-notes-config.sh, for the reason test_check_setup_sh.py gives
# for the same list: a rename that breaks the check should have to be made deliberately
# here too, instead of the test silently following along.
TOOLING_FILES = (
    ".claude/skills/plan-dashboard/build_dashboard.py",
    ".claude/skills/plan-dashboard/refresh_dashboard.sh",
    ".claude/skills/plan-dashboard/requirements.txt",
    ".claude/skills/plan-dashboard/plan-schema.md",
)

REQUIREMENTS_FILE = ".claude/skills/plan-dashboard/requirements.txt"

STARTER_NOTES_FILE = ".claude/skills/setup-personal-notes/starter-notes.md"

NOTES_PATH = ".claude/personal/cram-notes.md"

STARTER_NOTES_CONTENT = "# Personal notes\n\n- Always open pull requests as drafts.\n"

# The login the stubbed GitHub reports, and an origin owned by it - so the ownership
# check has something real to agree with.
STUB_LOGIN = "stub-user"
ORIGIN_REPOSITORY = f"{STUB_LOGIN}/octo-repo"


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

    for tooling_file in TOOLING_FILES:
        scratch_repository.write(tooling_file, "placeholder\n")
    # A requirement that is certainly installed, so the dependency step is a no-op and
    # the stub pip is never reached unless a test asks for it.
    scratch_repository.write(REQUIREMENTS_FILE, "pytest>=1\n")
    scratch_repository.write(STARTER_NOTES_FILE, STARTER_NOTES_CONTENT)

    scratch_repository.write(
        ".claude/settings.json",
        '{"hooks": {"SessionStart": [{"hooks": [{"type": "command",'
        ' "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/session-start.sh"}]}]}}\n',
    )
    scratch_repository.write(".gitignore", "CLAUDE.local.md\n")
    # The repository pull requests are opened against, which is where the labels are
    # checked - distinct from the notes remote, which is a local bare repository here.
    scratch_repository.run_git(
        "remote", "add", "origin", f"https://github.com/{ORIGIN_REPOSITORY}.git"
    )
    scratch_repository.commit_everything("initial commit")
    return scratch_repository


def run_setup(
    repository: ScratchRepository,
    stub_executables: StubExecutableDirectory,
    *arguments: str,
    hidden_executables: tuple[str, ...] = ("gh",),
    **environment_overrides: str,
) -> subprocess.CompletedProcess[str]:
    """
    Run the scratch layout's setup-personal-notes.sh.

    :param repository: A fixture-built scratch repository.
    :param stub_executables: The stub directory the run resolves ``gh``/``curl``/``pip``
        from.
    :param arguments: Arguments to pass to the script.
    :param hidden_executables: Executables to make unfindable, defaulting to hiding a
        real ``gh`` so a test only sees the stubs it installed itself.
    :param environment_overrides: Variables to set, chiefly the stubs' ``STUB_*``
        controls.
    :return: The finished subprocess.
    """
    return subprocess.run(
        [
            "bash",
            str(
                repository.project_root
                / ".claude"
                / "hooks"
                / "setup-personal-notes.sh"
            ),
            *arguments,
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
        ["bash", str(repository.project_root / ".claude" / "hooks" / "check-setup.sh")],
        cwd=repository.project_root,
        capture_output=True,
        text=True,
        env=stub_executables.subprocess_environment(hidden_executables=("gh",)),
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
    expected = (setup_repository.project_root / STARTER_NOTES_FILE).read_text()
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

    reported_checks = {
        line.split("\t")[0] for line in result.stdout.splitlines() if "\t" in line
    }
    assert {"notes_branch", "notes_file", "claude_local_md"} <= reported_checks


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
    stub_executables.install("gh")

    result = run_setup(
        setup_repository,
        stub_executables,
        "--remote",
        "https://github.com/someone-else/their-repo.git",
        hidden_executables=(),
        STUB_GH_LOGIN=STUB_LOGIN,
    )

    assert result.returncode != 0
    assert "someone-else" in result.stderr
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
    stub_executables.install("gh")
    call_log = tmp_path / "gh-calls.txt"

    result = run_setup(
        setup_repository,
        stub_executables,
        "--remote",
        str(setup_repository.notes_remote_path),
        hidden_executables=(),
        STUB_GH_LOGIN=STUB_LOGIN,
        STUB_GH_MISSING_LABELS="in-review",
        STUB_GH_CALL_LOG=str(call_log),
    )

    assert result.returncode == 0, result.stderr
    assert "in-review" in result.stdout
    assert "POST" not in call_log.read_text()


def test_creates_only_the_missing_labels_when_asked(
    setup_repository: ScratchRepository,
    stub_executables: StubExecutableDirectory,
    tmp_path: Path,
):
    stub_executables.install("gh")
    call_log = tmp_path / "gh-calls.txt"

    result = run_setup(
        setup_repository,
        stub_executables,
        "--remote",
        str(setup_repository.notes_remote_path),
        "--create-labels",
        hidden_executables=(),
        STUB_GH_LOGIN=STUB_LOGIN,
        STUB_GH_MISSING_LABELS="in-review",
        STUB_GH_CALL_LOG=str(call_log),
    )

    assert result.returncode == 0, result.stderr
    creation_calls = [
        line for line in call_log.read_text().splitlines() if "POST" in line
    ]
    assert len(creation_calls) == 1
    assert "name=in-review" in creation_calls[0]
    assert f"repos/{ORIGIN_REPOSITORY}/labels" in creation_calls[0]


# %% the plan-dashboard dependencies


def test_reports_a_failed_dependency_install_and_carries_on(
    setup_repository: ScratchRepository, stub_executables: StubExecutableDirectory
):
    stub_executables.install("pip")
    setup_repository.write(REQUIREMENTS_FILE, "a-distribution-that-is-not-installed\n")

    result = run_setup(
        setup_repository,
        stub_executables,
        "--remote",
        str(setup_repository.notes_remote_path),
    )

    # The steps after the failed install still ran: session-start.sh wrote the file.
    assert (setup_repository.project_root / "CLAUDE.local.md").is_file()
    assert setup_repository.notes_branch_commit() is not None
    assert "pip" in result.stdout + result.stderr

"""
Integration tests for write-branch-files.sh: the argument contract, the files it lands
on a branch, and its safety guarantees around destinations and the caller's own tree.

Runs against scratch repositories with local bare repositories standing in for remotes,
so nothing here needs network access.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scratch_repository import ScratchRepository, initialize_bare_repository

TOOLING_BRANCH = "claude/stack-tooling"
"""
The branch the tests write to, standing in for any non-notes branch a caller targets.
"""

# %% the scratch layout


@pytest.fixture
def writer_repository(scratch_repository: ScratchRepository) -> ScratchRepository:
    """
    A scratch repository with the script under test installed and one commit made, so
    ``git worktree add`` has a repository with history to work from.

    :param scratch_repository: The initialized scratch repository and notes remote.
    :return: The same repository, ready for a write.
    """
    scratch_repository.install_hook_scripts(
        "resolve-personal-notes-config.sh", "write-branch-files.sh"
    )
    scratch_repository.write("README.md", "scratch\n")
    scratch_repository.commit_everything("initial commit")
    return scratch_repository


@pytest.fixture
def tooling_remote(tmp_path: Path) -> Path:
    """
    A bare repository standing in for the remote a tooling branch is pushed to.

    Separate from the notes remote so a test can tell the two apart.

    :param tmp_path: pytest's per-test temporary directory.
    :return: The bare repository's path.
    """
    return initialize_bare_repository(tmp_path / "tooling.git")


def run_write_branch_files(
    repository: ScratchRepository, *arguments: str
) -> subprocess.CompletedProcess[str]:
    """
    Run the scratch layout's write-branch-files.sh.

    :param repository: A fixture-built scratch repository.
    :param arguments: The arguments to pass to the script.
    :return: The finished subprocess, for asserting on its status and output.
    """
    return subprocess.run(
        [
            "bash",
            str(
                repository.project_root / ".claude" / "hooks" / "write-branch-files.sh"
            ),
            *arguments,
        ],
        cwd=repository.project_root,
        capture_output=True,
        text=True,
    )


def write_source_files(
    repository: ScratchRepository, contents: dict[str, str]
) -> list[str]:
    """
    Write local source files and return them as ``--file`` arguments.

    :param repository: The repository to write them into.
    :param contents: File contents, keyed by the destination path on the branch.
    :return: One ``<source>:<destination>`` argument per file, each preceded by
        ``--file``.
    """
    arguments = []
    for destination, content in contents.items():
        source = repository.write(f"sources/{Path(destination).name}", content)
        arguments += ["--file", f"{source}:{destination}"]
    return arguments


# %% creating the branch


def test_creates_the_branch_when_asked_to_and_it_is_absent(
    writer_repository: ScratchRepository, tooling_remote: Path, tmp_path: Path
):
    result = run_write_branch_files(
        writer_repository,
        "--remote",
        str(tooling_remote),
        "--branch",
        TOOLING_BRANCH,
        "--message",
        "Install the stack tooling",
        "--create-branch-if-absent",
        *write_source_files(
            writer_repository,
            {".claude/stack/stack.py": "stack\n", ".claude/stack/stack.toml": "toml\n"},
        ),
    )

    assert result.returncode == 0, result.stderr
    checkout = writer_repository.clone_branch(
        tooling_remote, TOOLING_BRANCH, tmp_path / "checkout"
    )
    assert (checkout / ".claude" / "stack" / "stack.py").read_text() == "stack\n"
    assert (checkout / ".claude" / "stack" / "stack.toml").read_text() == "toml\n"


def test_refuses_a_missing_branch_when_not_asked_to_create_it(
    writer_repository: ScratchRepository, tooling_remote: Path
):
    result = run_write_branch_files(
        writer_repository,
        "--remote",
        str(tooling_remote),
        "--branch",
        TOOLING_BRANCH,
        "--message",
        "Install the stack tooling",
        *write_source_files(writer_repository, {"a.txt": "a\n"}),
    )

    assert result.returncode != 0
    assert TOOLING_BRANCH in result.stderr
    assert (
        writer_repository.remote_branch_commit(tooling_remote, TOOLING_BRANCH) is None
    )


def test_lands_every_file_in_a_single_commit(
    writer_repository: ScratchRepository, tooling_remote: Path, tmp_path: Path
):
    run_write_branch_files(
        writer_repository,
        "--remote",
        str(tooling_remote),
        "--branch",
        TOOLING_BRANCH,
        "--message",
        "Install the stack tooling",
        "--create-branch-if-absent",
        *write_source_files(
            writer_repository, {"one.txt": "one\n", "two.txt": "two\n"}
        ),
    )

    checkout = writer_repository.clone_branch(
        tooling_remote, TOOLING_BRANCH, tmp_path / "checkout"
    )
    commit_count = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=checkout,
        capture_output=True,
        text=True,
        check=True,
    )
    assert commit_count.stdout.strip() == "1"


# %% updating an existing branch


def test_updates_a_file_without_disturbing_the_rest_of_the_branch(
    writer_repository: ScratchRepository, tooling_remote: Path, tmp_path: Path
):
    common_arguments = (
        "--remote",
        str(tooling_remote),
        "--branch",
        TOOLING_BRANCH,
        "--message",
        "Install the stack tooling",
        "--create-branch-if-absent",
    )
    run_write_branch_files(
        writer_repository,
        *common_arguments,
        *write_source_files(
            writer_repository, {"kept.txt": "kept\n", "changed.txt": "before\n"}
        ),
    )

    result = run_write_branch_files(
        writer_repository,
        *common_arguments,
        *write_source_files(writer_repository, {"changed.txt": "after\n"}),
    )

    assert result.returncode == 0, result.stderr
    checkout = writer_repository.clone_branch(
        tooling_remote, TOOLING_BRANCH, tmp_path / "checkout"
    )
    assert (checkout / "changed.txt").read_text() == "after\n"
    assert (checkout / "kept.txt").read_text() == "kept\n"


def test_pushes_nothing_when_every_file_already_matches(
    writer_repository: ScratchRepository, tooling_remote: Path
):
    arguments = (
        "--remote",
        str(tooling_remote),
        "--branch",
        TOOLING_BRANCH,
        "--message",
        "Install the stack tooling",
        "--create-branch-if-absent",
        *write_source_files(writer_repository, {"same.txt": "unchanged\n"}),
    )
    run_write_branch_files(writer_repository, *arguments)
    commit_after_first_run = writer_repository.remote_branch_commit(
        tooling_remote, TOOLING_BRANCH
    )

    result = run_write_branch_files(writer_repository, *arguments)

    assert result.returncode == 0, result.stderr
    assert (
        writer_repository.remote_branch_commit(tooling_remote, TOOLING_BRANCH)
        == commit_after_first_run
    )


# %% safety


@pytest.mark.parametrize(
    "destination", ["/etc/passwd", "../escape.txt", "nested/../../escape.txt", ".."]
)
def test_rejects_a_destination_outside_the_branch(
    writer_repository: ScratchRepository, tooling_remote: Path, destination: str
):
    source = writer_repository.write("sources/payload.txt", "payload\n")

    result = run_write_branch_files(
        writer_repository,
        "--remote",
        str(tooling_remote),
        "--branch",
        TOOLING_BRANCH,
        "--message",
        "Install the stack tooling",
        "--create-branch-if-absent",
        "--file",
        f"{source}:{destination}",
    )

    assert result.returncode != 0
    assert destination in result.stderr


def test_leaves_the_callers_branch_and_working_tree_untouched(
    writer_repository: ScratchRepository, tooling_remote: Path
):
    writer_repository.write("uncommitted.txt", "work in progress\n")
    branch_before = writer_repository.run_git("branch", "--show-current").stdout
    commit_before = writer_repository.run_git("rev-parse", "HEAD").stdout

    run_write_branch_files(
        writer_repository,
        "--remote",
        str(tooling_remote),
        "--branch",
        TOOLING_BRANCH,
        "--message",
        "Install the stack tooling",
        "--create-branch-if-absent",
        *write_source_files(writer_repository, {"landed.txt": "landed\n"}),
    )

    assert writer_repository.run_git("branch", "--show-current").stdout == branch_before
    assert writer_repository.run_git("rev-parse", "HEAD").stdout == commit_before
    assert (
        writer_repository.project_root / "uncommitted.txt"
    ).read_text() == "work in progress\n"


# %% the argument contract


@pytest.mark.parametrize(
    "omitted_argument", ["--remote", "--branch", "--message", "--file"]
)
def test_requires_every_argument(
    writer_repository: ScratchRepository, tooling_remote: Path, omitted_argument: str
):
    source = writer_repository.write("sources/a.txt", "a\n")
    complete_arguments = {
        "--remote": str(tooling_remote),
        "--branch": TOOLING_BRANCH,
        "--message": "Install the stack tooling",
        "--file": f"{source}:a.txt",
    }
    arguments = [
        argument
        for name, value in complete_arguments.items()
        if name != omitted_argument
        for argument in (name, value)
    ]

    result = run_write_branch_files(writer_repository, *arguments)

    assert result.returncode != 0
    assert omitted_argument in result.stderr


def test_rejects_an_unrecognized_argument(
    writer_repository: ScratchRepository, tooling_remote: Path
):
    result = run_write_branch_files(writer_repository, "--nonsense")

    assert result.returncode != 0
    assert "--nonsense" in result.stderr


def test_rejects_a_file_argument_without_a_destination(
    writer_repository: ScratchRepository, tooling_remote: Path
):
    source = writer_repository.write("sources/a.txt", "a\n")

    result = run_write_branch_files(
        writer_repository,
        "--remote",
        str(tooling_remote),
        "--branch",
        TOOLING_BRANCH,
        "--message",
        "Install the stack tooling",
        "--file",
        str(source),
    )

    assert result.returncode != 0
    assert "<source>:<destination>" in result.stderr


def test_reports_a_source_file_that_does_not_exist(
    writer_repository: ScratchRepository, tooling_remote: Path
):
    missing_source = writer_repository.project_root / "sources" / "absent.txt"

    result = run_write_branch_files(
        writer_repository,
        "--remote",
        str(tooling_remote),
        "--branch",
        TOOLING_BRANCH,
        "--message",
        "Install the stack tooling",
        "--file",
        f"{missing_source}:absent.txt",
    )

    assert result.returncode != 0
    assert str(missing_source) in result.stderr

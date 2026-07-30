"""
Tests for :mod:`development_tooling.personal_notes`: the remote/branch resolution
precedence (git config, then environment variable, then default - the same order as
``resolve-personal-notes-config.sh``), fetching the notes branch, and reading plan
data off the fetched reference. Run against scratch git repositories - no network.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from development_tooling.personal_notes import (
    DEFAULT_PERSONAL_NOTES_BRANCH,
    DEFAULT_PERSONAL_NOTES_REMOTE,
    fetch_personal_notes_reference,
    plan_identifiers_at_reference,
    read_file_at_reference,
    resolve_personal_notes_branch,
    resolve_personal_notes_remote,
)

GIT_IDENTITY_ENVIRONMENT = {
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
    "PATH": "/usr/bin:/bin",
}


def run_git(repository_root: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", *arguments],
        cwd=repository_root,
        check=True,
        capture_output=True,
        env=GIT_IDENTITY_ENVIRONMENT,
    )


@pytest.fixture(autouse=True)
def clean_personal_notes_environment(monkeypatch):
    """
    Strip the caller's own personal-notes settings, so a session's real remote can never
    leak into a test's resolution (and from there onto the network).
    """
    monkeypatch.delenv("CLAUDE_PERSONAL_NOTES_REMOTE", raising=False)
    monkeypatch.delenv("CLAUDE_PERSONAL_NOTES_BRANCH", raising=False)


@pytest.fixture
def project_with_notes_remote(tmp_path: Path) -> Path:
    """
    A scratch project clone whose ``origin`` bare remote carries a personal-notes branch
    holding two plans.
    """
    remote = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--quiet", "--bare", str(remote)],
        check=True,
        capture_output=True,
    )

    seed = tmp_path / "seed"
    seed.mkdir()
    run_git(seed, "init", "--quiet", "--initial-branch", DEFAULT_PERSONAL_NOTES_BRANCH)
    for plan_identifier in ("plan-one", "plan-two"):
        plan_directory = seed / ".claude" / "personal" / "plans" / plan_identifier
        plan_directory.mkdir(parents=True)
        (plan_directory / "plan.yaml").write_text(f"id: {plan_identifier}\n")
        (plan_directory / "roadmap.md").write_text(f"# {plan_identifier}\n")
    run_git(seed, "add", ".")
    run_git(seed, "commit", "--quiet", "--message", "seed notes")
    run_git(seed, "push", "--quiet", str(remote), DEFAULT_PERSONAL_NOTES_BRANCH)

    project = tmp_path / "project"
    project.mkdir()
    run_git(project, "init", "--quiet")
    run_git(project, "remote", "add", "origin", str(remote))
    return project


# %% resolution precedence


def test_resolution_defaults_without_config_or_environment(tmp_path, monkeypatch):
    project = tmp_path / "bare-project"
    project.mkdir()
    run_git(project, "init", "--quiet")
    monkeypatch.delenv("CLAUDE_PERSONAL_NOTES_REMOTE", raising=False)
    monkeypatch.delenv("CLAUDE_PERSONAL_NOTES_BRANCH", raising=False)
    assert (
        resolve_personal_notes_remote(repository_root=project)
        == DEFAULT_PERSONAL_NOTES_REMOTE
    )
    assert (
        resolve_personal_notes_branch(repository_root=project)
        == DEFAULT_PERSONAL_NOTES_BRANCH
    )


def test_environment_variable_wins_over_the_default(tmp_path, monkeypatch):
    project = tmp_path / "bare-project"
    project.mkdir()
    run_git(project, "init", "--quiet")
    monkeypatch.setenv("CLAUDE_PERSONAL_NOTES_REMOTE", "environment-remote")
    monkeypatch.setenv("CLAUDE_PERSONAL_NOTES_BRANCH", "environment-branch")
    assert (
        resolve_personal_notes_remote(repository_root=project) == "environment-remote"
    )
    assert (
        resolve_personal_notes_branch(repository_root=project) == "environment-branch"
    )


def test_git_config_wins_over_the_environment_variable(tmp_path, monkeypatch):
    project = tmp_path / "bare-project"
    project.mkdir()
    run_git(project, "init", "--quiet")
    run_git(project, "config", "claude.personalNotesRemote", "configured-remote")
    run_git(project, "config", "claude.personalNotesBranch", "configured-branch")
    monkeypatch.setenv("CLAUDE_PERSONAL_NOTES_REMOTE", "environment-remote")
    monkeypatch.setenv("CLAUDE_PERSONAL_NOTES_BRANCH", "environment-branch")
    assert resolve_personal_notes_remote(repository_root=project) == "configured-remote"
    assert resolve_personal_notes_branch(repository_root=project) == "configured-branch"


# %% fetching and reading


def test_fetch_resolves_to_a_readable_reference(project_with_notes_remote):
    reference = fetch_personal_notes_reference(
        repository_root=project_with_notes_remote
    )
    assert reference == "FETCH_HEAD"


def test_fetch_of_a_missing_branch_resolves_to_none(project_with_notes_remote):
    assert (
        fetch_personal_notes_reference(
            repository_root=project_with_notes_remote, branch="no-such-branch"
        )
        is None
    )


def test_read_file_at_reference_returns_the_content(project_with_notes_remote):
    reference = fetch_personal_notes_reference(
        repository_root=project_with_notes_remote
    )
    content = read_file_at_reference(
        reference,
        ".claude/personal/plans/plan-one/plan.yaml",
        repository_root=project_with_notes_remote,
    )
    assert content == "id: plan-one\n"


def test_read_of_a_missing_file_returns_none(project_with_notes_remote):
    reference = fetch_personal_notes_reference(
        repository_root=project_with_notes_remote
    )
    assert (
        read_file_at_reference(
            reference, "no/such/file.yaml", repository_root=project_with_notes_remote
        )
        is None
    )


def test_plan_identifiers_lists_every_plan_with_a_manifest(project_with_notes_remote):
    reference = fetch_personal_notes_reference(
        repository_root=project_with_notes_remote
    )
    assert plan_identifiers_at_reference(
        reference, repository_root=project_with_notes_remote
    ) == ["plan-one", "plan-two"]

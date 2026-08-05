"""
Tests for :mod:`development_tooling.pr_state`'s local-git probes: lines changed.

between two references, and the non-mutating merge-conflict probe. Run against a
throwaway git repository built per test - no network, no real remotes.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from development_tooling.pr_state import (
    lines_changed_between,
    merge_conflicts_between,
)


def run_git(repository_root: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", *arguments],
        cwd=repository_root,
        check=True,
        capture_output=True,
        env={
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
            "PATH": "/usr/bin:/bin",
        },
    )


BASE_LINES = ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
"""The tracked file's content at the branch point - long enough that edits near its
top and bottom never fall into the same diff hunk."""


@pytest.fixture
def repository_with_branches(tmp_path: Path) -> Path:
    """
    A repository whose ``main`` diverged by rewriting the file's second line, with a
    ``clean-change`` branch editing only far away from that line (one deletion, two
    additions), and a ``conflicting-change`` branch rewriting the same second line
    differently.
    """
    root = tmp_path / "repository"
    root.mkdir()
    run_git(root, "init", "--quiet", "--initial-branch", "main")
    tracked_file = root / "tracked.txt"

    def commit_lines(lines: list[str], message: str) -> None:
        tracked_file.write_text("\n".join(lines) + "\n")
        run_git(root, "add", "tracked.txt")
        run_git(root, "commit", "--quiet", "--message", message)

    commit_lines(BASE_LINES, "base")

    run_git(root, "checkout", "--quiet", "-b", "clean-change")
    clean_lines = [line for line in BASE_LINES if line != "eight"] + ["ten", "eleven"]
    commit_lines(clean_lines, "clean change far from main's edit")

    run_git(root, "checkout", "--quiet", "main")
    run_git(root, "checkout", "--quiet", "-b", "conflicting-change")
    conflicting_lines = ["one", "two CONFLICT A", *BASE_LINES[2:]]
    commit_lines(conflicting_lines, "conflicting change")

    run_git(root, "checkout", "--quiet", "main")
    diverged_lines = ["one", "two CONFLICT B", *BASE_LINES[2:]]
    commit_lines(diverged_lines, "diverging base change")
    return root


# %% lines changed


def test_lines_changed_counts_additions_plus_deletions(repository_with_branches):
    assert (
        lines_changed_between(
            "main~1", "clean-change", repository_root=repository_with_branches
        )
        == 3
    )


def test_identical_references_change_zero_lines(repository_with_branches):
    assert (
        lines_changed_between("main", "main", repository_root=repository_with_branches)
        == 0
    )


def test_lines_changed_is_unknown_for_a_missing_reference(repository_with_branches):
    assert (
        lines_changed_between(
            "no-such-branch", "main", repository_root=repository_with_branches
        )
        is None
    )


# %% merge-conflict probe


def test_clean_branch_reports_no_conflict(repository_with_branches):
    assert (
        merge_conflicts_between(
            "main", "clean-change", repository_root=repository_with_branches
        )
        is False
    )


def test_conflicting_branch_reports_a_conflict(repository_with_branches):
    assert (
        merge_conflicts_between(
            "main", "conflicting-change", repository_root=repository_with_branches
        )
        is True
    )


def test_conflict_probe_is_unknown_for_a_missing_reference(repository_with_branches):
    assert (
        merge_conflicts_between(
            "main", "no-such-branch", repository_root=repository_with_branches
        )
        is None
    )

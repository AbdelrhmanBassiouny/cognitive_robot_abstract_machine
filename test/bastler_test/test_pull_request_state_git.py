"""
Tests for :mod:`bastler.pull_request_state`'s local-git probes.

The lines changed between two references, and the non-mutating merge-conflict probe. Run
against a scratch repository built per test - no network, no real remotes.
"""

from __future__ import annotations

from enum import StrEnum

import pytest

from bastler.pull_request_state import LocalGitProbe

from .scratch_repository import ScratchRepository

TRACKED_FILE = "tracked.txt"
"""
The one file every branch edits.
"""

BASE_LINES = ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
"""
The tracked file's content at the branch point - long enough that edits near its top
and bottom never fall into the same diff hunk.
"""


class Branch(StrEnum):
    """
    The branches the scratch repository carries.
    """

    MAIN = "main"
    """
    The base, which diverges by rewriting the file's second line.
    """

    CLEAN_CHANGE = "clean-change"
    """
    Edits only far from the base's rewrite: one deletion, two additions.
    """

    CONFLICTING_CHANGE = "conflicting-change"
    """
    Rewrites the same second line differently.
    """

    MISSING = "no-such-branch"
    """
    A branch that does not exist.
    """


@pytest.fixture
def probe(scratch_repository: ScratchRepository) -> LocalGitProbe:
    """
    A probe over a repository carrying every :class:`Branch` but :attr:`Branch.MISSING`.
    """

    def commit_lines(lines: list[str], message: str) -> None:
        scratch_repository.write(TRACKED_FILE, "\n".join(lines) + "\n")
        scratch_repository.commit_everything(message)

    scratch_repository.run_git("checkout", "--quiet", "-b", Branch.MAIN)
    commit_lines(BASE_LINES, "base")

    scratch_repository.run_git("checkout", "--quiet", "-b", Branch.CLEAN_CHANGE)
    clean_lines = [line for line in BASE_LINES if line != "eight"] + ["ten", "eleven"]
    commit_lines(clean_lines, "clean change far from the base's edit")

    scratch_repository.run_git("checkout", "--quiet", Branch.MAIN)
    scratch_repository.run_git("checkout", "--quiet", "-b", Branch.CONFLICTING_CHANGE)
    commit_lines(["one", "two CONFLICT A", *BASE_LINES[2:]], "conflicting change")

    scratch_repository.run_git("checkout", "--quiet", Branch.MAIN)
    commit_lines(["one", "two CONFLICT B", *BASE_LINES[2:]], "diverging base change")
    return LocalGitProbe(scratch_repository.project_root)


# %% lines changed


def test_lines_changed_counts_additions_plus_deletions(probe):
    assert probe.lines_changed_between(f"{Branch.MAIN}~1", Branch.CLEAN_CHANGE) == 3


def test_identical_references_change_zero_lines(probe):
    assert probe.lines_changed_between(Branch.MAIN, Branch.MAIN) == 0


def test_lines_changed_is_unknown_for_a_missing_reference(probe):
    assert probe.lines_changed_between(Branch.MISSING, Branch.MAIN) is None


# %% merge-conflict probe


def test_a_clean_branch_reports_no_conflict(probe):
    assert probe.merge_conflicts_between(Branch.MAIN, Branch.CLEAN_CHANGE) is False


def test_a_conflicting_branch_reports_a_conflict(probe):
    assert probe.merge_conflicts_between(Branch.MAIN, Branch.CONFLICTING_CHANGE) is True


def test_the_conflict_probe_is_unknown_for_a_missing_reference(probe):
    assert probe.merge_conflicts_between(Branch.MAIN, Branch.MISSING) is None

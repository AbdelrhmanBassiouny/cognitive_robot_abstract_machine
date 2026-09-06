"""
Tests for :mod:`bastler.git_commands`, the two contracts a git command can be run under.
"""

from __future__ import annotations

import pytest

from bastler.exceptions import GitCommandFailed
from bastler.git_commands import GitCommandRunner

from .scratch_repository import ScratchRepository


def test_a_command_that_succeeds_answers_with_its_output(
    scratch_repository: ScratchRepository,
):
    """
    ``run`` is for a command whose result the caller depends on, so it answers with
    git's own stdout rather than with a result to unpack.
    """
    runner = GitCommandRunner(working_directory=scratch_repository.project_root)

    assert runner.run("rev-parse", "--is-inside-work-tree") == "true"


def test_a_command_the_caller_depends_on_raises_rather_than_answering_nothing(
    scratch_repository: ScratchRepository,
):
    """
    The failure a push must never be able to hide: ``run`` raises, so a command that did
    nothing cannot be mistaken for one that worked.
    """
    runner = GitCommandRunner(working_directory=scratch_repository.project_root)

    with pytest.raises(GitCommandFailed) as failure:
        runner.run("rev-parse", "--verify", "no-such-reference")

    assert failure.value.status != 0
    assert failure.value.call == "git rev-parse --verify no-such-reference"


def test_a_command_whose_failure_is_expected_reports_instead_of_raising(
    scratch_repository: ScratchRepository,
):
    """
    The opposite contract, which derivation needs: a reference that does not resolve
    means there is no answer, not that the tool should stop.
    """
    runner = GitCommandRunner(working_directory=scratch_repository.project_root)

    result = runner.attempt("rev-parse", "--verify", "no-such-reference")

    assert result.succeeded is False
    assert result.output == ""

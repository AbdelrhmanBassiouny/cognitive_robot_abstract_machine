"""
Tests for the modules under ``.claude/shared`` that more than one tool imports.

They live in this suite rather than beside the code because CI already runs this
directory, and because the scratch repository these tests build is defined here.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import pytest
from command_line import Command, commands_of
from exceptions import ExternalCallFailed, GitCommandFailed
from git_commands import GitCommandRunner
from plan_model import ItemStatus
from scratch_repository import ScratchRepository

SHARED_DIRECTORY = Path(__file__).parent.parent.parent / "shared"
"""
The directory whose modules are under test.
"""


# %% the two contracts a git command can be run under


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


def test_a_failure_names_the_call_its_status_and_what_was_said():
    """
    Every external failure reports the same three things, so a caller never has to know
    which dependency refused in order to say what happened.
    """
    failure = GitCommandFailed(status=128, detail="bad revision", arguments=("log",))

    assert isinstance(failure, ExternalCallFailed)
    assert str(failure) == "git log failed with 128: bad revision"


def test_a_failure_with_no_suggestion_renders_only_its_error_message():
    """
    ``suggest_correction`` defaults to empty, so a failure with no advice to give does
    not grow a trailing suggestion line nobody wrote.
    """
    failure = GitCommandFailed(status=1, detail="not a git repository", arguments=())

    assert failure.error_message() == "git  failed with 1: not a git repository"
    assert failure.suggest_correction() == ""
    assert str(failure) == failure.error_message()


def test_a_failure_with_a_suggestion_appends_it_on_its_own_line():
    """
    Mirrors ``krrood``'s ``DataclassException``: a non-empty ``suggest_correction`` is
    composed onto ``error_message`` as a trailing ``"Suggestion: ..."`` line, so a
    subclass only has to say what to try rather than reformat the whole message.
    """

    class FailureWithASuggestion(ExternalCallFailed):
        """A failure whose subclass has advice to give."""

        @property
        def call(self) -> str:
            """:return: A fixed call name, since this test's failure is synthetic."""
            return "do-the-thing"

        def suggest_correction(self) -> str:
            """:return: The advice this test asserts gets appended."""
            return "try again with --force"

    failure = FailureWithASuggestion(status=1, detail="refused")

    assert str(failure) == (
        "do-the-thing failed with 1: refused\nSuggestion: try again with --force"
    )


# %% commands as classes


def test_every_subclass_is_reachable_in_the_order_it_was_defined():
    """
    The registry is what the parser is built from, so a command that exists but is
    unreachable should not be expressible - and the order is the order a reader sees in
    ``--help``.

    Asked of a tool's own base rather than of :class:`Command`, whose direct subclasses
    are the tool bases themselves.
    """

    class ExampleTool(Command):
        """The base one tool's commands are defined under."""

    class SecondCommand(ExampleTool):
        """Defined first, so it is expected first."""

        @property
        def invoked_as(self) -> str:
            """:return: The word selecting it."""
            return "second"

        @property
        def description(self) -> str:
            """:return: What it does."""
            return "defined first"

    class FirstCommand(ExampleTool):
        """Defined second, to prove the order is definition order rather than sorted."""

        @property
        def invoked_as(self) -> str:
            """:return: The word selecting it."""
            return "first"

        @property
        def description(self) -> str:
            """:return: What it does."""
            return "defined second"

    assert [command.invoked_as for command in commands_of(ExampleTool)] == [
        "second",
        "first",
    ]


def test_a_command_that_says_neither_what_it_is_called_nor_what_it_does_is_refused():
    """
    Both are abstract, and the registry builds every subclass - so the refusal lands as
    the caller's module is imported rather than when someone invokes the command.
    """

    class CommandWithoutAName(Command):
        """A command that never says what it is called."""

    with pytest.raises(TypeError, match="invoked_as"):
        CommandWithoutAName()


def test_a_command_declares_no_flags_unless_it_has_some():
    """
    Concrete rather than abstract: most commands take none, and requiring an empty
    override of every one of them would say nothing.
    """

    class CommandWithoutFlags(Command):
        """A command taking no flags of its own."""

        @property
        def invoked_as(self) -> str:
            """:return: The word selecting it."""
            return "flagless"

        @property
        def description(self) -> str:
            """:return: What it does."""
            return "takes nothing"

    parser = argparse.ArgumentParser()
    CommandWithoutFlags().declare_arguments(parser)

    assert parser.parse_args([]) == argparse.Namespace()


# %% the statuses both the hooks and the dashboard read


def test_the_statuses_are_the_words_the_manifest_carries():
    """
    The manifest is plain YAML that a person also edits, so these values are a written
    contract with every plan file rather than an internal vocabulary.
    """
    assert [status.value for status in ItemStatus] == [
        "not_started",
        "in_progress",
        "blocked",
        "deferred",
        "done",
    ]


# %% the tier these modules belong to


def test_every_shared_module_imports_with_nothing_installed():
    """
    A hook reads these on the SessionStart path, where only the standard library can be
    assumed - so importing one must not reach for yaml, jinja2, markdown or nh3.
    """
    blocked = "yaml", "jinja2", "markdown", "nh3"
    modules = sorted(path.stem for path in SHARED_DIRECTORY.glob("*.py"))

    for module in modules:
        program = (
            "import sys;"
            f"[sys.modules.__setitem__(name, None) for name in {blocked!r}];"
            f"import {module}"
        )
        result = subprocess.run(
            [sys.executable, "-c", program],
            cwd=SHARED_DIRECTORY,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"{module}: {result.stderr}"

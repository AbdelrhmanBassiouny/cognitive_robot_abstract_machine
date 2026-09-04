"""
Tests for running git on behalf of these scripts.

Everything runs against a scratch repository, so no network access is involved. What is
under test is the distinction the runner exists to draw: a command whose failure is an
error against one whose failure is an ordinary answer.
"""

from pathlib import Path

import pytest

from git_commands import GitCommandFailed, GitCommandRunner

UNRESOLVABLE_REFERENCE = "no-such-reference"
UNSET_CONFIG_KEY = "claude.nothingConfiguresThis"
CONFIGURED_KEY = "claude.somethingConfiguresThis"
CONFIGURED_VALUE = "a value"
FILE_WITH_TRAILING_BLANK_LINE = "trailing.txt"


@pytest.fixture
def repository(tmp_path: Path, scratch_git) -> GitCommandRunner:
    """
    A scratch repository with one commit, and a runner pointed at it.

    :param tmp_path: pytest's per-test temporary directory.
    :param scratch_git: The scratch git runner factory.
    :return: The runner.
    """
    git = scratch_git(tmp_path)
    git.run("init", "--quiet")
    (tmp_path / FILE_WITH_TRAILING_BLANK_LINE).write_text("content\n\n")
    git.run("add", ".")
    git.run("commit", "--quiet", "--message", "the only commit")
    return git


def test_a_command_that_succeeds_reports_its_output(repository: GitCommandRunner):
    """
    The common case: a command this tooling depends on the result of hands that result
    back, stripped.
    """
    assert repository.run("rev-parse", "--is-inside-work-tree") == "true"


def test_a_depended_on_command_that_fails_raises(repository: GitCommandRunner):
    """
    A failure git reports must not be swallowed - a push that silently did nothing
    would otherwise be indistinguishable from one that worked.
    """
    with pytest.raises(GitCommandFailed) as raised:
        repository.run("rev-parse", UNRESOLVABLE_REFERENCE)

    assert raised.value.arguments == ("rev-parse", UNRESOLVABLE_REFERENCE)
    assert raised.value.exit_status != 0
    assert str(raised.value).startswith("git rev-parse")


def test_a_command_whose_failure_is_an_answer_reports_nothing(
    repository: GitCommandRunner,
):
    """
    An unset config key is not an error - it is the answer "nothing is configured".
    """
    assert repository.output_or_none("config", "--get", UNSET_CONFIG_KEY) is None


def test_a_command_whose_failure_is_an_answer_still_reports_output(
    repository: GitCommandRunner,
):
    """
    Succeeding through the same method reports what git said, so a caller need not
    choose a second method once the value is present.
    """
    repository.run("config", CONFIGURED_KEY, CONFIGURED_VALUE)

    assert (
        repository.output_or_none("config", "--get", CONFIGURED_KEY) == CONFIGURED_VALUE
    )


def test_unstripped_output_keeps_a_file_s_own_trailing_whitespace(
    repository: GitCommandRunner,
):
    """
    File content must come back byte for byte: stripping it would make an empty file
    indistinguishable from a missing one, which is how a read reports absence.
    """
    unstripped = repository.output_or_none(
        "show", f"HEAD:{FILE_WITH_TRAILING_BLANK_LINE}", strip=False
    )

    assert unstripped == "content\n\n"


def test_an_attempted_command_reports_its_failure_rather_than_raising(
    repository: GitCommandRunner,
):
    """
    A caller that wants to branch on the outcome gets the finished command instead of an
    exception.
    """
    result = repository.attempt("rev-parse", UNRESOLVABLE_REFERENCE)

    assert result.succeeded is False
    assert result.error_output != ""


def test_pointing_the_runner_elsewhere_keeps_its_environment(
    repository: GitCommandRunner, tmp_path: Path
):
    """
    A worktree is run in with the same fixed identity the checkout was, so a commit made
    there does not depend on the running user's git configuration.
    """
    elsewhere = tmp_path / "elsewhere"

    moved = repository.in_directory(elsewhere)

    assert moved.working_directory == elsewhere
    assert moved.environment == repository.environment

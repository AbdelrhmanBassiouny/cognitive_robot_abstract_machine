"""
Tests for :mod:`bastler.dataclass_exception` and :mod:`bastler.exceptions`, the shared
composition every external-call failure in :mod:`bastler` is built on.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from bastler.dataclass_exception import DataclassException
from bastler.exceptions import ExternalCallFailed, GitCommandFailed, GitHubRequestFailed


def test_a_failure_names_the_call_its_status_and_what_was_said():
    """
    Every external failure reports the same three things, so a caller never has to know
    which dependency refused in order to say what happened.
    """
    failure = GitCommandFailed(status=128, detail="bad revision", arguments=("log",))

    assert isinstance(failure, ExternalCallFailed)
    assert str(failure) == "git log failed with 128: bad revision"


def test_a_github_failure_names_the_request_its_status_and_what_was_said():
    """
    :class:`GitHubRequestFailed` composes the same way as its git counterpart, naming
    the request line rather than a git command line.
    """
    failure = GitHubRequestFailed(
        status=422,
        detail="validation failed",
        method="PATCH",
        path="/repos/x/y/pulls/1",
    )

    assert str(failure) == "PATCH /repos/x/y/pulls/1 failed with 422: validation failed"


def test_a_failure_with_no_suggestion_renders_only_its_error_message():
    """
    ``GitCommandFailed`` answers ``suggest_correction`` with an empty string, so a
    failure with no advice to give does not grow a trailing suggestion line nobody wrote.
    """
    failure = GitCommandFailed(status=1, detail="not a git repository", arguments=())

    assert failure.error_message() == "git  failed with 1: not a git repository"
    assert failure.suggest_correction() == ""
    assert str(failure) == failure.error_message()


def test_a_failure_with_a_suggestion_appends_it_on_its_own_line():
    """
    A non-empty ``suggest_correction`` is composed onto ``error_message`` as a trailing
    ``"Suggestion: ..."`` line, so a subclass only has to say what to try rather than
    reformat the whole message.
    """

    class FailureWithASuggestion(ExternalCallFailed):
        """A failure whose subclass has advice to give."""

        @property
        def call(self) -> str:
            """:return: A fixed call name, since this test's failure is synthetic."""
            return "do-the-thing"

        def error_message(self) -> str:
            """:return: The same call/status/detail formula every failure composes."""
            return f"{self.call} failed with {self.status}: {self.detail}"

        def suggest_correction(self) -> str:
            """:return: The advice this test asserts gets appended."""
            return "try again with --force"

    failure = FailureWithASuggestion(status=1, detail="refused")

    assert str(failure) == (
        "do-the-thing failed with 1: refused\nSuggestion: try again with --force"
    )


def test_a_subclass_missing_an_abstract_method_is_refused_at_construction():
    """
    ``call``, ``error_message`` and ``suggest_correction`` are abstract, so a subclass
    that forgets one must fail loudly rather than build a failure that raises
    ``NotImplementedError`` the first time something reads it.

    ``BaseException.__new__`` bypasses ``ABCMeta``'s usual instantiation check, so this
    exercises :meth:`DataclassException.__post_init__`'s own enforcement, inherited by
    :class:`ExternalCallFailed`, rather than assuming Python's.
    """

    class MissingErrorMessage(ExternalCallFailed):
        """A subclass that never says what went wrong."""

        @property
        def call(self) -> str:
            """:return: A fixed call name, since this test's failure is synthetic."""
            return "do-the-thing"

        def suggest_correction(self) -> str:
            """:return: No advice, since this test is about the missing method."""
            return ""

    with pytest.raises(TypeError, match="error_message"):
        MissingErrorMessage(status=1, detail="refused")


def test_a_dataclass_exception_composes_its_message_and_suggestion():
    """
    ``DataclassException`` carries no fields of its own - :class:`ExternalCallFailed`
    adds ``status``/``detail``/``call``, but the composition in ``__str__`` works for any
    subclass that only supplies ``error_message``/``suggest_correction``.
    """

    @dataclass
    class OutOfDisk(DataclassException):
        """A dataclass exception unrelated to any external call, to prove reuse."""

        bytes_needed: int

        def error_message(self) -> str:
            """:return: What went wrong, independent of any call/status/detail."""
            return f"needed {self.bytes_needed} more bytes"

        def suggest_correction(self) -> str:
            """:return: The advice this test asserts gets appended."""
            return "free up disk space"

    assert str(OutOfDisk(bytes_needed=1024)) == (
        "needed 1024 more bytes\nSuggestion: free up disk space"
    )


def test_dataclass_exception_itself_cannot_be_instantiated():
    """
    ``DataclassException`` states the contract but answers neither ``error_message`` nor
    ``suggest_correction`` itself, so it must refuse construction the same way an
    incomplete subclass does.
    """

    @dataclass
    class BareDataclassException(DataclassException):
        """A subclass adding no fields, to isolate the base's own abstractness."""

    with pytest.raises(TypeError, match="error_message"):
        BareDataclassException()

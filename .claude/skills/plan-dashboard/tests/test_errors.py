"""
Tests for the base every error this tooling raises is built on.

What is under test is the two things the base does for its subclasses: composing the
message from their own fields, and refusing to construct one that never says what went
wrong.
"""

from dataclasses import dataclass

import pytest

from errors import PlanDashboardError

FAILED_STEP = "the step that failed"


@dataclass
class ExampleFailure(PlanDashboardError):
    """
    A failure carrying one field, standing in for the real ones.
    """

    step: str
    """
    What was being done.
    """

    def error_message(self) -> str:
        """:return: What went wrong, from this error's own field."""
        return f"{self.step} did not work"


def test_an_error_reads_as_the_message_its_fields_compose():
    """
    A caller logging the exception sees the composed sentence, not the raw fields.
    """
    assert str(ExampleFailure(step=FAILED_STEP)) == f"{FAILED_STEP} did not work"


def test_an_error_keeps_its_fields_readable():
    """
    The context stays typed rather than only appearing inside a formatted string, so a
    caller can branch on it without parsing.
    """
    assert ExampleFailure(step=FAILED_STEP).step == FAILED_STEP


def test_the_message_is_what_raising_reports():
    """
    Raising and logging read alike: the composed message survives being raised.
    """
    with pytest.raises(ExampleFailure) as raised:
        raise ExampleFailure(step=FAILED_STEP)

    assert str(raised.value) == f"{FAILED_STEP} did not work"


def test_an_error_that_says_nothing_cannot_be_constructed():
    """
    ``BaseException.__new__`` bypasses the usual abstract-class check, so a subclass
    that never composes a message would otherwise construct silently.
    """
    with pytest.raises(TypeError) as raised:
        PlanDashboardError()

    assert "error_message" in str(raised.value)

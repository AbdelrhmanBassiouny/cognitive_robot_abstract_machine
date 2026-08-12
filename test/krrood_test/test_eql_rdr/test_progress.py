"""
Tests for the fitting-progress vocabulary and the no-op reporter
(:mod:`krrood.entity_query_language.rdr.progress`).
"""

from krrood.entity_query_language.rdr.progress import (
    NullProgressReporter,
    ProgressDescription,
    ProgressReporter,
)

# %% ProgressDescription


def test_fitting_description_is_the_label_shown_beside_the_bar():
    assert ProgressDescription.FITTING == "Fitting RDR"


def test_description_is_usable_directly_as_the_start_label():
    reporter = _RecordingReporter()

    reporter.start(3, ProgressDescription.FITTING)

    assert reporter.calls == [("start", 3, "Fitting RDR")]


# %% NullProgressReporter


def test_null_reporter_accepts_the_whole_lifecycle_without_effect():
    reporter = NullProgressReporter()

    assert reporter.start(10, ProgressDescription.FITTING) is None
    assert reporter.update() is None
    assert reporter.update(5) is None
    assert reporter.reset(20) is None
    assert reporter.finish() is None


class _RecordingReporter(ProgressReporter):
    """
    Captures the arguments a caller passes, to assert on them by value.
    """

    def __init__(self):
        self.calls = []

    def start(self, total: int, description: str = "") -> None:
        self.calls.append(("start", total, description))

    def update(self, n: int = 1) -> None:
        self.calls.append(("update", n))

    def reset(self, total: int) -> None:
        self.calls.append(("reset", total))

    def finish(self) -> None:
        self.calls.append(("finish",))

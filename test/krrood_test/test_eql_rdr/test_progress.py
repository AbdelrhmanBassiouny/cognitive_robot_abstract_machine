"""
Tests for the fitting-progress vocabulary and the no-op reporter
(:mod:`krrood.entity_query_language.rdr.progress`).
"""

from krrood.entity_query_language.rdr.progress import (
    NullProgressReporter,
    ProgressDescription,
)

# %% ProgressDescription


def test_fitting_description_is_the_label_shown_beside_the_bar():
    assert ProgressDescription.FITTING == "Fitting RDR"


# %% NullProgressReporter


def test_null_reporter_accepts_the_whole_lifecycle_without_effect():
    reporter = NullProgressReporter()

    assert reporter.start(10, ProgressDescription.FITTING) is None
    assert reporter.update() is None
    assert reporter.update(5) is None
    assert reporter.reset(20) is None
    assert reporter.finish() is None

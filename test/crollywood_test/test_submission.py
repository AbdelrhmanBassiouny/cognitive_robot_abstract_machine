"""
Tests for :mod:`crollywood.submission`: what a venue accepts a video as.
"""

from __future__ import annotations

from datetime import timedelta

from crollywood.submission import SubmissionLimits
from krrood.units import DataSize

LARGEST = DataSize.of_bytes(1_000_000)


def test_the_size_budget_is_the_largest_file_in_proportion_to_the_length() -> None:
    venue = SubmissionLimits(
        longest=timedelta(seconds=100),
        largest=LARGEST,
        lowest=480,
        slowest=20,
    )
    assert venue.size_budget_for(venue.longest / 4) == venue.largest.scaled(1 / 4)
    assert venue.size_budget_for(2 * venue.longest) == venue.largest

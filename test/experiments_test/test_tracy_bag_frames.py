"""
Where in a recorded run the figure's frames are taken from: the moment the fingers let
go of the piece they carried, read off the knuckle joint's own positions.
"""

from __future__ import annotations

import pytest

from experiments.tracy_experiments.bag_frames import (
    HOLDING_KNUCKLE_POSITION,
    KnuckleReading,
    NoReleaseRecordedError,
    last_release,
)
from experiments.tracy_experiments.montessori.gripper_feedback import (
    FULLY_CLOSED_KNUCKLE_POSITION,
    OPEN_KNUCKLE_POSITION,
)

HOLDING = (HOLDING_KNUCKLE_POSITION + FULLY_CLOSED_KNUCKLE_POSITION) / 2
"""
A knuckle position the fingers stand at while they hold a piece.
"""


def readings(*positions: float) -> list[KnuckleReading]:
    """
    :param positions: Knuckle positions, one per nanosecond stamp from zero.
    :return: The readings, stamped in order.
    """
    return [
        KnuckleReading(stamp=stamp, position=position)
        for stamp, position in enumerate(positions)
    ]


def test_the_release_is_the_first_moment_the_fingers_stand_open_again() -> None:
    recorded = readings(OPEN_KNUCKLE_POSITION, HOLDING, HOLDING, OPEN_KNUCKLE_POSITION)

    assert last_release(recorded) == recorded[3].stamp


def test_of_two_releases_the_last_is_taken() -> None:
    """
    A run that lets go of something before the piece it sorts -- a grasp retried, say --
    is filmed letting go of the piece, which is the last thing it lets go of.
    """
    recorded = readings(
        HOLDING,
        OPEN_KNUCKLE_POSITION,
        HOLDING,
        HOLDING,
        OPEN_KNUCKLE_POSITION,
        OPEN_KNUCKLE_POSITION,
    )

    assert last_release(recorded) == recorded[4].stamp


def test_fingers_that_never_closed_let_nothing_go() -> None:
    with pytest.raises(NoReleaseRecordedError):
        last_release(readings(OPEN_KNUCKLE_POSITION, OPEN_KNUCKLE_POSITION))


def test_fingers_still_closed_when_the_recording_ends_let_nothing_go() -> None:
    with pytest.raises(NoReleaseRecordedError):
        last_release(readings(OPEN_KNUCKLE_POSITION, HOLDING, HOLDING))

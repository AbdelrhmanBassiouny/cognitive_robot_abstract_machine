"""
Where in a recorded run the figure's frames are taken from: the moment the fingers let
go of the piece they carried, read off the knuckle joint's own positions; and the
pictures of the look the run's plan was answered from, put where the figure reads them.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from experiments.episodes.artifacts import TrialArtifact
from experiments.montessori.perception.captures import SceneCapture
from experiments.montessori.perception.recordings import (
    REFERENCE_FRAME,
    RecordedCamera,
)
from experiments.montessori.perception.step_by_step import NarrowingPictures
from experiments.tracy_experiments.bag_frames import (
    FigureFramesFromBag,
    HOLDING_KNUCKLE_POSITION,
    FigureNarrowing,
    KnuckleReading,
    NoReleaseRecordedError,
    last_release,
)
from experiments.tracy_experiments.montessori.gripper_feedback import (
    FULLY_CLOSED_KNUCKLE_POSITION,
    OPEN_KNUCKLE_POSITION,
)

from .dataset.montessori_capture_truths import CAPTURE_TRUTHS

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


# %% reading the bag's own camera


def test_the_camera_is_read_in_the_frame_recordings_use() -> None:
    bag = Path("some_recording")

    assert FigureFramesFromBag(bag=bag).camera == RecordedCamera(
        bag=bag, reference_frame=REFERENCE_FRAME
    )


# %% the narrowing a frame before the robot acts shows


CUBE_ON_THE_LID_CAPTURE = "washed_out_lid"
"""
The shipped capture off the robot's camera with the smaller set on the table and the
cube resting on the lid, as a recording of the framework demo starts.
"""


@pytest.fixture(scope="module")
def narrowed_before_it_acts() -> NarrowingPictures:
    """
    The figure's look, read over a frame of the robot's table before the robot moves.
    """
    return FigureFramesFromBag.narrowing_over(
        SceneCapture.load(CUBE_ON_THE_LID_CAPTURE).to_frame()
    )


def test_a_frame_before_the_robot_acts_is_narrowed_down_to_the_cube_on_the_lid(
    narrowed_before_it_acts: NarrowingPictures,
) -> None:
    """
    The figure's look is the plan's own statement about the piece it sorts, so each of
    its conditions leaves less to read, down to the piece on the lid.
    """
    steps = narrowed_before_it_acts.steps

    assert [piece.category for piece in steps[-1].found] == list(
        CAPTURE_TRUTHS[CUBE_ON_THE_LID_CAPTURE].pieces_on_lid
    )
    assert steps[-1].searched_area < steps[0].searched_area


def test_a_frame_before_the_robot_acts_is_read_for_the_pieces_on_its_table(
    narrowed_before_it_acts: NarrowingPictures,
) -> None:
    assert (
        narrowed_before_it_acts.narrowing.pipeline.pieces
        == CAPTURE_TRUTHS[CUBE_ON_THE_LID_CAPTURE].piece_set
    )


# %% the narrowing a trial kept


def test_the_narrowing_a_trial_kept_is_put_where_the_figure_reads_it(
    tmp_path: Path,
) -> None:
    kept = tmp_path / TrialArtifact.NARROWING
    kept.mkdir()
    picture = kept / "picture.png"
    picture.write_bytes(bytes(range(8)))
    figure = tmp_path / "figure"

    written = FigureNarrowing(kept=kept).write(figure)

    assert written == [figure / TrialArtifact.NARROWING / picture.name]
    assert written[0].read_bytes() == picture.read_bytes()

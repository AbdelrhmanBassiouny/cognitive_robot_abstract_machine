"""
Tests for :mod:`experiments.tracy_experiments.rosbag_recording`: which messages of a
stream are kept when it is thinned, which topics thinning applies to, and where bags are
written.

No bag is recorded and no ROS graph is involved; these cover the decisions the recorder
makes, not the subscribing and writing it does once they are made.
"""

from __future__ import annotations

import os

import pytest

from experiments.tracy_experiments.rosbag_recording import (
    CAMERA_TOPICS,
    DECIMATED_TOPICS,
    DEFAULT_BAG_DIRECTORY,
    DEFAULT_TOPICS,
    JOINT_STATE_TOPICS,
    TRANSFORM_TOPICS,
    FrameCounter,
    RosbagRecorder,
    RosbagRecordingFailed,
)

# %% topic selection


def test_the_default_topics_cover_camera_depth_joint_states_and_transforms():
    """
    The bag has to be replayable on its own, so it carries the colour and depth streams,
    every joint state, and the transforms relating them.
    """
    assert "/camera/color/image_raw/compressed" in CAMERA_TOPICS
    assert "/camera/depth/image_raw" in CAMERA_TOPICS
    assert "/left_gripper/joint_states" in JOINT_STATE_TOPICS
    assert "/tf" in TRANSFORM_TOPICS
    assert DEFAULT_TOPICS == CAMERA_TOPICS + JOINT_STATE_TOPICS + TRANSFORM_TOPICS


def test_only_camera_streams_are_thinned():
    """
    Joint states and transforms are together a fraction of a percent of a bag, so
    thinning them would cost motion fidelity and replayability to save nothing.
    """
    for topic in JOINT_STATE_TOPICS + TRANSFORM_TOPICS:
        assert topic not in DECIMATED_TOPICS
    assert set(DECIMATED_TOPICS) <= set(CAMERA_TOPICS)


def test_camera_infos_are_not_thinned():
    """
    A consumer that cannot find a camera info alongside a thinned image stream cannot
    use the images at all, and they cost almost nothing to keep.
    """
    for topic in CAMERA_TOPICS:
        if topic.endswith("camera_info"):
            assert topic not in DECIMATED_TOPICS


# %% which messages are kept


def test_every_message_is_kept_when_not_thinning():
    counter = FrameCounter(keep_every_nth=1)

    assert [counter.wants() for _ in range(5)] == [True] * 5


def test_one_message_in_every_n_is_kept():
    counter = FrameCounter(keep_every_nth=3)

    kept = [counter.wants() for _ in range(9)]

    assert kept == [True, False, False, True, False, False, True, False, False]


def test_the_first_message_is_always_kept():
    """
    A thinned stream has to start at the beginning of the recording, not
    ``keep_every_nth`` frames into it.
    """
    counter = FrameCounter(keep_every_nth=10)

    assert counter.wants()


def test_the_counter_reports_what_it_kept():
    counter = FrameCounter(keep_every_nth=10)

    for _ in range(25):
        counter.wants()

    assert counter.seen == 25
    assert counter.kept == 3


# %% applying the thinning factor


def test_camera_streams_are_thinned_by_the_given_factor():
    recorder = RosbagRecorder(output_directory="bag", keep_every_nth_frame=10)

    for topic in DECIMATED_TOPICS:
        assert recorder.keep_every_nth_frame_of(topic) == 10


def test_joint_states_and_transforms_are_recorded_whole_however_much_is_thinned():
    recorder = RosbagRecorder(output_directory="bag", keep_every_nth_frame=10)

    for topic in JOINT_STATE_TOPICS + TRANSFORM_TOPICS:
        assert recorder.keep_every_nth_frame_of(topic) == 1


def test_nothing_is_thinned_by_default():
    recorder = RosbagRecorder(output_directory="bag")

    for topic in DEFAULT_TOPICS:
        assert recorder.keep_every_nth_frame_of(topic) == 1


def test_a_thinning_factor_below_one_is_refused():
    """
    ``0`` would divide by zero in the counter and a negative factor is meaningless, so
    both are refused where the caller can still see why.
    """
    with pytest.raises(RosbagRecordingFailed):
        with RosbagRecorder(output_directory="bag", keep_every_nth_frame=0):
            pytest.fail("recording must not start with an impossible thinning factor")


# %% where bags are written


def test_timestamped_bags_keep_the_prefix_and_do_not_collide(tmp_path):
    parent = str(tmp_path / "bags")
    first = RosbagRecorder.timestamped("tracy_pickup_demo", parent)
    second = RosbagRecorder.timestamped("tracy_pickup_demo", parent, topics=["/tf"])

    assert os.path.dirname(first.output_directory) == parent
    assert os.path.basename(first.output_directory).startswith("tracy_pickup_demo_")
    assert first.topics == DEFAULT_TOPICS
    assert second.topics == ["/tf"]


def test_timestamped_bags_are_written_outside_any_source_tree(monkeypatch):
    """
    A run produces tens of gigabytes; defaulting to the working directory once put a
    35 GB bag inside the package the demo was launched from.
    """
    monkeypatch.setattr(
        "experiments.tracy_experiments.rosbag_recording.os.makedirs",
        lambda path, exist_ok=False: None,
    )

    recorder = RosbagRecorder.timestamped("tracy_pickup_demo")

    assert os.path.isabs(recorder.output_directory)
    assert os.path.dirname(recorder.output_directory) == os.path.expanduser(
        DEFAULT_BAG_DIRECTORY
    )


def test_the_parent_directory_is_created_if_missing(tmp_path):
    parent = str(tmp_path / "not" / "there" / "yet")

    RosbagRecorder.timestamped("tracy_pickup_demo", parent)

    assert os.path.isdir(parent)


def test_the_thinning_factor_survives_into_the_timestamped_recorder(tmp_path):
    recorder = RosbagRecorder.timestamped(
        "tracy_pickup_demo", str(tmp_path), keep_every_nth_frame=10
    )

    assert recorder.keep_every_nth_frame == 10

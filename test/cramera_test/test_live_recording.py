"""
Tests for the rolling recording a live demo keeps of itself.
"""

from __future__ import annotations

from cramera.live.bridge import WorldStateSnapshot
from cramera.live.recording import DemoRecording, RecordedFrame


def snapshot_numbered(number: int) -> WorldStateSnapshot:
    """
    A world snapshot distinguishable from its siblings by its sequence number.

    :param number: The sequence number to stamp the snapshot with.
    """
    return WorldStateSnapshot(sequence_number=number)


def kept_numbers(recording: DemoRecording, start: float, end: float) -> list:
    """
    The sequence numbers of the frames a clip of ``recording`` returns.

    :param recording: The recording to clip.
    :param start: When the clip begins, in seconds since the epoch.
    :param end: When the clip ends, in seconds since the epoch.
    """
    return [frame.state.sequence_number for frame in recording.clip(start, end)]


# %% keeping frames
class TestKeepingFrames:
    def test_a_kept_frame_is_returned_within_its_window(self):
        recording = DemoRecording()
        recording.record(100.0, snapshot_numbered(1))

        assert kept_numbers(recording, 99.0, 101.0) == [1]

    def test_frames_outside_the_window_are_left_out(self):
        recording = DemoRecording()
        recording.record(100.0, snapshot_numbered(1))
        recording.record(101.0, snapshot_numbered(2))
        recording.record(102.0, snapshot_numbered(3))

        assert kept_numbers(recording, 100.5, 101.5) == [2]

    def test_the_window_bounds_are_part_of_the_clip(self):
        recording = DemoRecording()
        recording.record(100.0, snapshot_numbered(1))
        recording.record(101.0, snapshot_numbered(2))

        assert kept_numbers(recording, 100.0, 101.0) == [1, 2]

    def test_a_frame_too_close_to_the_kept_one_is_not_kept(self):
        recording = DemoRecording(min_interval_seconds=0.05)
        recording.record(100.0, snapshot_numbered(1))
        recording.record(100.01, snapshot_numbered(2))
        recording.record(100.06, snapshot_numbered(3))

        assert kept_numbers(recording, 99.0, 101.0) == [1, 3]

    def test_frames_older_than_the_kept_duration_are_dropped(self):
        recording = DemoRecording(max_duration_seconds=10.0)
        recording.record(100.0, snapshot_numbered(1))
        recording.record(105.0, snapshot_numbered(2))
        recording.record(111.0, snapshot_numbered(3))

        assert kept_numbers(recording, 0.0, 1000.0) == [2, 3]

    def test_clearing_forgets_every_kept_frame(self):
        recording = DemoRecording()
        recording.record(100.0, snapshot_numbered(1))
        recording.clear()

        assert kept_numbers(recording, 0.0, 1000.0) == []


# %% what a frame serves
class TestFramePayload:
    def test_a_frame_serves_its_time_and_the_snapshot_parts_the_viewer_steps(self):
        state = WorldStateSnapshot(
            sequence_number=7,
            frames={"world/torso_lift_joint": 0.2},
            base=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            objects={"milk.stl": [1.0, 2.0, 3.0, 0.0, 0.0, 0.0, 1.0]},
        )

        assert RecordedFrame(at=100.0, state=state).to_payload() == {
            "at": 100.0,
            "frames": {"world/torso_lift_joint": 0.2},
            "base": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            "objects": {"milk.stl": [1.0, 2.0, 3.0, 0.0, 0.0, 0.0, 1.0]},
        }

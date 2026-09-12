"""
What a run keeps of its world as it goes: where every joint stood, and what a camera
saw, sampled along the seconds of a trial, and put back afterwards.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from semantic_digital_twin.testing import two_arm_robot_world
from semantic_digital_twin.world import World

from experiments.episodes.artifacts import (
    ArtifactDirectory,
    TrialArtifact,
    TrialArtifactNotKept,
)
from experiments.episodes.trace import (
    JointPositions,
    JointTrace,
    JointTraceRecorder,
    TimedFrames,
    TimedFramesFile,
    TraceIsEmptyError,
)

from coraplex.datastructures.enums import ExecutionType

from experiments.episodes.episode import Episode

# %% the run the samples are taken in

FRAME_SIDE = 16
"""
Pixel width and height of the frames kept here, small because what is asserted is which
frame comes back rather than what it shows.
"""


def coloured_frames(count: int) -> list:
    """
    A run of frames that differ from one another.

    :param count: How many frames to make.
    """
    return [
        np.full((FRAME_SIDE, FRAME_SIDE, 3), index * 10, dtype=np.uint8)
        for index in range(count)
    ]


def sorting_episode() -> Episode:
    """
    An episode of one simulated sorting run.
    """
    return Episode(
        scenario_name="montessori_sorting", execution_type=ExecutionType.SIMULATED
    )


ENCODING_TOLERANCE = 3
"""
How far, per channel, a frame read back out of a video may differ from the one written
into it, since the video is encoded lossily.
"""

# %% the moments the samples are taken at

EARLIER = 1.0
"""
Seconds into the trial the first sample is taken at.
"""

LATER = 2.0
"""
Seconds into the trial the second sample is taken at.
"""

MOVED_TO = 0.4
"""
Where a joint of the robot stands at the second sample, in its own units.
"""


def a_joint_of(world: World):
    """
    One joint of the robot that can be moved, which is what a trace is checked on.

    :param world: The world holding the robot.
    """
    return world.degrees_of_freedom[0]


def traced_twice(world: World) -> JointTrace:
    """
    A trace of the given world sampled where it stands and again after one joint moved.

    :param world: The world to trace.
    """
    trace = JointTrace()
    trace.sample(world, EARLIER)
    world.state[a_joint_of(world).id].position = MOVED_TO
    world.notify_state_change()
    trace.sample(world, LATER)
    return trace


# %% where every joint stood


def test_a_sample_holds_every_joint_of_the_world(two_arm_robot_world: World) -> None:
    trace = JointTrace()
    trace.sample(two_arm_robot_world, EARLIER)

    assert set(trace.names) == {
        str(degree_of_freedom.name)
        for degree_of_freedom in two_arm_robot_world.degrees_of_freedom
    }


def test_the_sample_nearest_a_moment_is_the_one_handed_back(
    two_arm_robot_world: World,
) -> None:
    trace = traced_twice(two_arm_robot_world)

    nearer_the_later = trace.at((EARLIER + LATER) / 2 + 0.1)

    assert nearer_the_later.moment == LATER
    assert nearer_the_later.positions[str(a_joint_of(two_arm_robot_world).name)] == (
        MOVED_TO
    )


def test_a_moment_past_the_last_sample_is_read_as_the_last(
    two_arm_robot_world: World,
) -> None:
    assert traced_twice(two_arm_robot_world).at(LATER + 10.0).moment == LATER


def test_an_empty_trace_has_no_sample_to_hand_back() -> None:
    with pytest.raises(TraceIsEmptyError):
        JointTrace().at(EARLIER)


def test_a_sample_puts_the_world_back_where_it_stood(
    two_arm_robot_world: World,
) -> None:
    """
    The point of a trace is putting a moment of the trial back in front of a reader, so
    the world is stood as the sample says rather than as the run left it.
    """
    joint = a_joint_of(two_arm_robot_world)
    trace = traced_twice(two_arm_robot_world)

    trace.at(EARLIER).restore_into(two_arm_robot_world)

    assert two_arm_robot_world.state[joint.id].position == 0.0


def test_a_joint_the_sample_does_not_hold_is_left_where_it_is(
    two_arm_robot_world: World,
) -> None:
    """
    A run may add a body to the world after a sample was taken; the sample still puts
    back what it holds and leaves the rest alone.
    """
    joint = a_joint_of(two_arm_robot_world)
    two_arm_robot_world.state[joint.id].position = MOVED_TO

    JointPositions(moment=EARLIER, positions={}).restore_into(two_arm_robot_world)

    assert two_arm_robot_world.state[joint.id].position == MOVED_TO


def test_a_trace_written_out_is_read_back_the_same(
    two_arm_robot_world: World, tmp_path: Path
) -> None:
    trace = traced_twice(two_arm_robot_world)

    read_back = JointTrace.read(trace.write(tmp_path / "joints.npz"))

    assert read_back.names == trace.names
    assert read_back.moments == trace.moments
    assert all(
        np.array_equal(theirs, ours)
        for theirs, ours in zip(read_back.positions, trace.positions)
    )


# %% what a camera saw


def test_the_frame_nearest_a_moment_is_the_one_handed_back() -> None:
    earlier, later = coloured_frames(2)
    frames = TimedFrames()
    frames.keep(earlier, EARLIER)
    frames.keep(later, LATER)

    assert np.array_equal(frames.at(LATER - 0.1), later)


def test_the_frames_either_side_of_a_moment_are_the_last_before_and_first_after() -> (
    None
):
    """
    What the camera saw just before and just after something happened, each with the
    moment it was actually taken at.
    """
    earlier, later = coloured_frames(2)
    frames = TimedFrames()
    frames.keep(earlier, EARLIER)
    frames.keep(later, LATER)
    between = (EARLIER + LATER) / 2

    before, after = frames.last_at_or_before(between), frames.first_at_or_after(between)

    assert (before.moment, after.moment) == (EARLIER, LATER)
    assert np.array_equal(before.image, earlier)
    assert np.array_equal(after.image, later)


def test_a_moment_outside_the_film_is_shown_from_its_nearest_end() -> None:
    earlier, later = coloured_frames(2)
    frames = TimedFrames()
    frames.keep(earlier, EARLIER)
    frames.keep(later, LATER)

    assert frames.last_at_or_before(EARLIER - 1.0).moment == EARLIER
    assert frames.first_at_or_after(LATER + 1.0).moment == LATER


def test_no_frame_is_handed_back_before_one_was_kept() -> None:
    with pytest.raises(TraceIsEmptyError):
        TimedFrames().at(EARLIER)
    with pytest.raises(TraceIsEmptyError):
        TimedFrames().last_at_or_before(EARLIER)
    with pytest.raises(TraceIsEmptyError):
        TimedFrames().first_at_or_after(EARLIER)


def test_frames_written_out_are_read_back_with_their_moments(tmp_path: Path) -> None:
    """
    A video times its frames by their place in it; what puts a frame back at the second
    of the trial it shows is the moments kept beside it, so they come back with it.
    """
    frames = TimedFrames(frames_per_second=15)
    for moment, frame in zip((EARLIER, LATER), coloured_frames(2)):
        frames.keep(frame, moment)

    read_back = TimedFrames.read(frames.write(tmp_path / "camera.mp4"))

    assert read_back.moments == [EARLIER, LATER]
    assert len(read_back.frames) == 2
    assert read_back.frames_per_second == 15


def test_one_frame_of_a_written_film_is_read_without_the_rest(tmp_path: Path) -> None:
    """
    A card wants the frame nearest one moment of a film thousands of frames long, and
    the film on disk hands that one back without the whole film being decoded into
    memory.
    """
    frames = TimedFrames(frames_per_second=15)
    earlier, later = coloured_frames(2)
    frames.keep(earlier, EARLIER)
    frames.keep(later, LATER)
    film = TimedFramesFile(frames.write(tmp_path / "camera.mp4"))

    assert film.moments == [EARLIER, LATER]
    assert (
        np.abs(film.at(LATER).astype(int) - later.astype(int)).max()
        <= ENCODING_TOLERANCE
    )
    assert (
        np.abs(film.at(EARLIER).astype(int) - earlier.astype(int)).max()
        <= ENCODING_TOLERANCE
    )


def test_a_film_with_no_frame_hands_none_back(tmp_path: Path) -> None:
    film = TimedFramesFile(tmp_path / "camera.mp4")
    np.save(film.moments_path, np.array([], dtype=float))

    with pytest.raises(TraceIsEmptyError):
        film.at(EARLIER)


# %% kept with the trial


def test_a_trial_keeps_its_trace_and_its_camera_under_its_own_number(
    two_arm_robot_world: World, tmp_path: Path
) -> None:
    artifacts = ArtifactDirectory(path=tmp_path).open_for(sorting_episode())
    frames = TimedFrames()
    frames.keep(coloured_frames(1)[0], EARLIER)

    trial = artifacts.trial(2)
    trial.keep_joint_trace(traced_twice(two_arm_robot_world))
    trial.keep_camera(frames)

    assert trial.directory == artifacts.directory / "trials" / "2"
    assert trial.kept_a_joint_trace and trial.kept_a_camera
    assert trial.joint_trace.moments == [EARLIER, LATER]
    assert trial.camera.moments == [EARLIER]


def test_a_trial_that_kept_no_trace_says_which_one_is_missing_it(
    tmp_path: Path,
) -> None:
    trial = ArtifactDirectory(path=tmp_path).open_for(sorting_episode()).trial(1)

    assert not trial.kept_a_joint_trace
    with pytest.raises(TrialArtifactNotKept) as raised:
        trial.joint_trace
    assert raised.value.artifact is TrialArtifact.JOINT_TRACE
    assert raised.value.number == 1


# %% tracing as the world is driven


class Ticking:
    """
    A clock the test advances by hand.
    """

    def __init__(self) -> None:
        self.now = 0.0

    def read(self) -> float:
        return self.now


def test_a_recorder_samples_the_world_whenever_it_changes(
    two_arm_robot_world: World,
) -> None:
    clock = Ticking()
    recorder = JointTraceRecorder(_world=two_arm_robot_world, clock=clock.read)

    for moment in (EARLIER, LATER):
        clock.now = moment
        two_arm_robot_world.state[a_joint_of(two_arm_robot_world).id].position = moment
        two_arm_robot_world.notify_state_change()
    recorder.stop()

    assert recorder.trace.moments == [EARLIER, LATER]


def test_a_recorder_thins_changes_that_come_faster_than_its_period(
    two_arm_robot_world: World,
) -> None:
    """
    A world driven by a motion changes state far more often than a picture of a moment
    needs, so two changes within one period are kept as one sample.
    """
    clock = Ticking()
    recorder = JointTraceRecorder(
        _world=two_arm_robot_world, clock=clock.read, period=1.0
    )

    for moment in (EARLIER, EARLIER + 0.5, LATER):
        clock.now = moment
        two_arm_robot_world.state[a_joint_of(two_arm_robot_world).id].position = moment
        two_arm_robot_world.notify_state_change()
    recorder.stop()

    assert recorder.trace.moments == [EARLIER, LATER]


def test_a_stopped_recorder_samples_nothing_more(two_arm_robot_world: World) -> None:
    clock = Ticking()
    recorder = JointTraceRecorder(_world=two_arm_robot_world, clock=clock.read)
    recorder.stop()

    clock.now = LATER
    two_arm_robot_world.state[a_joint_of(two_arm_robot_world).id].position = MOVED_TO
    two_arm_robot_world.notify_state_change()

    assert recorder.trace.is_empty

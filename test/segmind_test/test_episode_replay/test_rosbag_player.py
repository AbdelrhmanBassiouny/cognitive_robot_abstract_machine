"""
Replaying a recorded rosbag into a world.
"""

from __future__ import annotations

import time
from copy import deepcopy
from datetime import timedelta
from pathlib import Path

import numpy as np
import pytest
from giskardpy.motion_statechart.context import MotionStatechartContext
from segmind.datastructures.enums import PlayerStatus
from segmind.datastructures.events import LossOfSupportEvent, SupportEvent
from segmind.detectors.base import SegmindContext
from segmind.detectors.spatial_relation_detector_nodes import (
    LossOfSupportDetector,
    SupportDetector,
)
from segmind.episode_segmenter import EpisodeSegmenterExecutor
from segmind.exceptions import (
    RecordingHoldsNothingToReplay,
    ReferenceFrameNotRecorded,
)
from segmind.players.rosbag_player import (
    MESSAGE_DEFINITIONS,
    RecordedMessage,
    RecordedState,
    RosbagMessageType,
    RosbagPlayer,
    RosbagTopic,
)
from segmind.statecharts.segmind_statechart import SegmindStatechart
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types import (
    HomogeneousTransformationMatrix,
    Vector3,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import (
    Connection6DoF,
    FixedConnection,
    RevoluteConnection,
)
from semantic_digital_twin.world_description.geometry import Box, Scale
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body

from ..dataset.recorded_episode import (
    JointPositionsAt,
    RecordedEpisode,
    RecordedTransform,
    TransformsAt,
)

# %% the recording and the world it was taken in

REFERENCE_FRAME = "map"
BOARD_FRAME = "board"
CUBE_FRAME = "cube"
LINK_FRAME = "link"
GHOST_FRAME = "ghost"
JOINT = "elbow_joint"
BOARD_IN_MAP = (1.0, 0.0, 0.0)
SAMPLE_TIMES = [1.0, 2.0, 3.0]
CUBE_HEIGHT_AT = {1.0: 0.1, 2.0: 0.2, 3.0: 0.3}
JOINT_POSITION_AT = {1.0: 0.0, 2.0: 0.5, 3.0: 1.0}


@pytest.fixture
def recording(tmp_path: Path) -> Path:
    """
    A board fixed in the map, a cube rising above the board, a robot link frame the
    joint states also describe, a frame no body answers to, and one joint moving.
    """
    episode = RecordedEpisode(
        static_transforms=[
            RecordedTransform(REFERENCE_FRAME, BOARD_FRAME, BOARD_IN_MAP)
        ],
        transforms=[
            TransformsAt(
                sample_time,
                [
                    RecordedTransform(
                        BOARD_FRAME, CUBE_FRAME, (0.0, 0.0, CUBE_HEIGHT_AT[sample_time])
                    ),
                    RecordedTransform(REFERENCE_FRAME, LINK_FRAME, (0.5, 0.0, 0.0)),
                    RecordedTransform(REFERENCE_FRAME, GHOST_FRAME, (0.0, 2.0, 0.0)),
                ],
            )
            for sample_time in SAMPLE_TIMES
        ],
        joint_positions=[
            JointPositionsAt(sample_time, {JOINT: JOINT_POSITION_AT[sample_time]})
            for sample_time in SAMPLE_TIMES
        ],
    )
    return episode.write(tmp_path / "recording")


@pytest.fixture
def world() -> World:
    """
    The world the recording was taken in: the board fixed where the recording says, the
    cube free to move, and the link on a revolute joint.
    """
    world = World()
    root = Body(name=PrefixedName(REFERENCE_FRAME))
    board = Body(name=PrefixedName(BOARD_FRAME))
    cube = Body(
        name=PrefixedName(CUBE_FRAME),
        collision=ShapeCollection([Box(scale=Scale(0.05, 0.05, 0.05))]),
    )
    link = Body(name=PrefixedName(LINK_FRAME))
    with world.modify_world():
        for body in (root, board, cube, link):
            world.add_kinematic_structure_entity(body)
        world.add_connection(
            FixedConnection(
                parent=root,
                child=board,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    *BOARD_IN_MAP, reference_frame=root
                ),
            )
        )
        world.add_connection(
            Connection6DoF.create_with_dofs(world=world, parent=root, child=cube)
        )
        world.add_connection(
            RevoluteConnection.create_with_dofs(
                world=world,
                parent=root,
                child=link,
                name=PrefixedName(JOINT),
                axis=Vector3.Z(reference_frame=root),
            )
        )
    return world


@pytest.fixture
def player(recording: Path, world: World) -> RosbagPlayer:
    """
    A player over the recording and the world it was taken in, sampling once a second so
    that a frame stands at each of the recording's own message times.
    """
    player = RosbagPlayer(
        file_path=str(recording),
        world=world,
        reference_frame=REFERENCE_FRAME,
        sampling_period=timedelta(seconds=1),
        time_between_frames=timedelta(milliseconds=1),
    )
    yield player
    RosbagPlayer.clear_instance()


def cube_position_at(sample_time: float) -> np.ndarray:
    """
    Where the recording puts the cube in the reference frame at a sample time, which is
    the board's own place raised by the height the cube stands at.

    :param sample_time: The time in seconds.
    """
    return np.array(BOARD_IN_MAP) + np.array([0.0, 0.0, CUBE_HEIGHT_AT[sample_time]])


def transforms_message_at(sample_time: float) -> RecordedMessage:
    """
    A message publishing the cube's own transform at a sample time.

    :param sample_time: The time in seconds.
    """
    published = TransformsAt(
        sample_time,
        [
            RecordedTransform(
                BOARD_FRAME, CUBE_FRAME, (0.0, 0.0, CUBE_HEIGHT_AT[sample_time])
            )
        ],
    )
    return RecordedMessage(
        topic=RosbagTopic.TRANSFORMS,
        content=published.to_message(),
        time=sample_time,
    )


def joint_positions_message_at(sample_time: float) -> RecordedMessage:
    """
    A message publishing the joint's own position at a sample time.

    :param sample_time: The time in seconds.
    """
    published = JointPositionsAt(sample_time, {JOINT: JOINT_POSITION_AT[sample_time]})
    return RecordedMessage(
        topic=RosbagTopic.JOINT_STATES,
        content=published.to_message(),
        time=sample_time,
    )


# %% what a recording states


def test_only_a_topic_published_over_time_advances_the_recordings_clock():
    """
    A static transform holds for the whole recording, so the frames are taken along the
    times the other two topics state and never along its own.
    """
    assert not RosbagTopic.STATIC_TRANSFORMS.advances_the_clock
    assert RosbagTopic.TRANSFORMS.advances_the_clock
    assert RosbagTopic.JOINT_STATES.advances_the_clock


def test_each_topic_names_the_type_of_message_it_carries():
    """
    Both transform topics carry the same message; only the joint states differ.
    """
    assert RosbagTopic.STATIC_TRANSFORMS.message_type is RosbagMessageType.TRANSFORMS
    assert RosbagTopic.TRANSFORMS.message_type is RosbagMessageType.TRANSFORMS
    assert RosbagTopic.JOINT_STATES.message_type is RosbagMessageType.JOINT_STATES


def test_every_message_type_named_is_one_the_recordings_definitions_hold():
    """
    The names are what a recording is read and written through, so one that the
    definitions do not hold is a name nothing can build or deserialize.
    """
    assert {message_type for message_type in RosbagMessageType} <= set(
        MESSAGE_DEFINITIONS.types
    )


# %% the state a recording has stated so far


def test_the_recorded_state_keeps_the_latest_of_what_each_message_says():
    """
    Every message is the newest word on the frames and the joints it names, so a later
    one replaces an earlier one rather than adding to it.
    """
    state = RecordedState()
    state.record(transforms_message_at(1.0))
    state.record(joint_positions_message_at(1.0))
    state.record(transforms_message_at(2.0))
    state.record(joint_positions_message_at(2.0))
    np.testing.assert_allclose(
        state.transform_tree.transform_to[CUBE_FRAME][:3, 3],
        [0.0, 0.0, CUBE_HEIGHT_AT[2.0]],
    )
    assert state.joint_positions == {JOINT: JOINT_POSITION_AT[2.0]}


def test_a_frame_of_the_state_holds_against_the_messages_that_follow_it():
    """
    A frame is the state as it stood when it was taken, so recording more afterwards
    leaves it as it was rather than aging it forward.
    """
    state = RecordedState()
    state.record(transforms_message_at(1.0))
    state.record(joint_positions_message_at(1.0))
    frame = state.frame_at(1.0, 0, BOARD_FRAME)
    state.record(transforms_message_at(2.0))
    state.record(joint_positions_message_at(2.0))
    np.testing.assert_allclose(
        frame.objects_data[CUBE_FRAME][:3, 3], [0.0, 0.0, CUBE_HEIGHT_AT[1.0]]
    )
    assert frame.joint_positions == {JOINT: JOINT_POSITION_AT[1.0]}
    assert frame.time == 1.0
    assert frame.frame_idx == 0


# %% sampling the recording into frames


def test_frames_are_sampled_at_the_period_along_the_recordings_clock(player):
    """
    The recording states its transforms once a second and the player samples once a
    second, so a frame stands at each of those times and nowhere else.
    """
    frames = list(player.frame_data_generator)
    assert [frame.time for frame in frames] == SAMPLE_TIMES
    assert [frame.frame_idx for frame in frames] == list(range(len(SAMPLE_TIMES)))


def test_a_shorter_period_holds_the_latest_state_between_messages(recording, world):
    """
    Sampling twice as often as the recording states anything doubles the frames, and
    every second one repeats the state of the message before it.
    """
    player = RosbagPlayer(
        file_path=str(recording),
        world=world,
        reference_frame=REFERENCE_FRAME,
        sampling_period=timedelta(milliseconds=500),
    )
    frames = list(player.frame_data_generator)
    RosbagPlayer.clear_instance()
    assert [frame.time for frame in frames] == [1.0, 1.5, 2.0, 2.5, 3.0]
    held = frames[1]
    np.testing.assert_allclose(
        held.objects_data[CUBE_FRAME][:3, 3], cube_position_at(1.0)
    )
    assert held.joint_positions == {JOINT: JOINT_POSITION_AT[1.0]}


def test_a_frame_holds_every_pose_in_the_reference_frame_and_every_joint(player):
    """
    The cube hangs off the board and the board off the reference frame, so a frame
    reports the cube at the composed chain rather than in its own parent.
    """
    frame = list(player.frame_data_generator)[1]
    np.testing.assert_allclose(
        frame.objects_data[CUBE_FRAME][:3, 3], cube_position_at(2.0)
    )
    np.testing.assert_allclose(frame.objects_data[BOARD_FRAME][:3, 3], BOARD_IN_MAP)
    assert frame.joint_positions == {JOINT: JOINT_POSITION_AT[2.0]}


# %% what a frame means in the world


def test_only_a_free_body_the_recording_names_is_posed(player, world):
    """
    The board stands on a fixed connection, the link on a revolute one and the ghost
    frame names no body at all, so the cube is the only pose a frame yields.
    """
    frame = list(player.frame_data_generator)[2]
    poses = player.get_objects_poses(frame)
    cube = world.get_body_by_name(CUBE_FRAME)
    assert list(poses) == [cube]
    assert poses[cube].reference_frame == world.root
    np.testing.assert_allclose(
        poses[cube].to_position().to_np()[:3].reshape(-1), cube_position_at(3.0)
    )


def test_a_joint_the_recording_names_is_positioned(player, world):
    """
    A robot link is moved by its joint rather than by its frame's own transform.
    """
    frame = list(player.frame_data_generator)[2]
    joint = world.get_connection_by_name(JOINT)
    assert player.get_joint_positions(frame) == {joint: JOINT_POSITION_AT[3.0]}


def test_replaying_moves_the_world_to_the_recordings_end(player, world):
    """
    Playing the recording out leaves the world standing at its last frame.
    """
    player.start()
    player.join(timeout=30)
    assert not player.is_alive()
    assert player.status == PlayerStatus.STOPPED
    cube = world.get_body_by_name(CUBE_FRAME)
    np.testing.assert_allclose(
        cube.global_pose.to_position().to_np()[:3].reshape(-1),
        cube_position_at(SAMPLE_TIMES[-1]),
        atol=1e-9,
    )
    assert world.get_connection_by_name(JOINT).position == pytest.approx(
        JOINT_POSITION_AT[SAMPLE_TIMES[-1]]
    )


# %% recordings that cannot be replayed


def test_a_recording_without_transforms_or_joint_states_is_refused(tmp_path, world):
    """
    A recording carrying none of the replayed topics is refused when the player is
    built, rather than yielding an episode with nothing in it.
    """
    bag = RecordedEpisode().write(tmp_path / "empty")
    with pytest.raises(RecordingHoldsNothingToReplay):
        RosbagPlayer(file_path=str(bag), world=world)
    RosbagPlayer.clear_instance()


def test_a_reference_frame_the_recording_never_publishes_is_refused(tmp_path, world):
    """
    A reference frame the transform tree never reaches is refused on the first frame,
    before anything in the world has moved.
    """
    episode = RecordedEpisode(
        transforms=[
            TransformsAt(1.0, [RecordedTransform("odom", CUBE_FRAME, (0.0, 0.0, 0.0))])
        ]
    )
    bag = episode.write(tmp_path / "elsewhere")
    player = RosbagPlayer(
        file_path=str(bag), world=world, reference_frame=REFERENCE_FRAME
    )
    with pytest.raises(ReferenceFrameNotRecorded):
        next(player.frame_data_generator)
    RosbagPlayer.clear_instance()


# %% the events an unchanged executor produces over a replay

MILK = "milk.stl"
MILK_ON_ITS_BOX = (-1.7, 0.0, 0.93)
MILK_LIFTED = (-1.7, 0.0, 1.5)


def test_a_replayed_recording_yields_support_events_from_the_unchanged_executor(
    _simple_apartment_setup, tmp_path
):
    """
    A recording that lifts the milk off its box and sets it back down is enough for the
    executor to say what happened, with no change to the executor itself.
    """
    world = deepcopy(_simple_apartment_setup)
    root_frame = world.root.name.name
    episode = RecordedEpisode(
        transforms=[
            TransformsAt(1.0, [RecordedTransform(root_frame, MILK, MILK_ON_ITS_BOX)]),
            TransformsAt(2.0, [RecordedTransform(root_frame, MILK, MILK_LIFTED)]),
            TransformsAt(3.0, [RecordedTransform(root_frame, MILK, MILK_ON_ITS_BOX)]),
        ]
    )
    bag = episode.write(tmp_path / "milk")
    player = RosbagPlayer(
        file_path=str(bag),
        world=world,
        reference_frame=root_frame,
        sampling_period=timedelta(seconds=1),
        time_between_frames=timedelta(milliseconds=300),
    )
    executor = EpisodeSegmenterExecutor(
        context=MotionStatechartContext(world=world), player=player
    )
    segmind_context = executor.context.require_extension(SegmindContext)
    statechart = SegmindStatechart().build_statechart(
        [SupportDetector(), LossOfSupportDetector()]
    )
    executor.compile(statechart)
    while player.is_alive():
        executor.tick()
        time.sleep(0.05)
    executor.tick()
    RosbagPlayer.clear_instance()
    events = segmind_context.logger.get_events()
    assert (
        len([event for event in events if isinstance(event, LossOfSupportEvent)]) == 1
    )
    assert len([event for event in events if isinstance(event, SupportEvent)]) == 2

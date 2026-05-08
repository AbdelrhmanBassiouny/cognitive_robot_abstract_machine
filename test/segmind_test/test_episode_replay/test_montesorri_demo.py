import datetime
import time
from os.path import dirname
from pathlib import Path
from unittest import TestCase

import pytest
try:
    import rclpy
except ImportError:
    rclpy = None

import segmind
from giskardpy.motion_statechart.context import MotionStatechartContext
from segmind.detectors.base import DetectorStateChart, SegmindContext
from segmind.episode_segmenter import EpisodeSegmenterExecutor
from segmind.event_logger import EventLogger
from segmind.players.csv_player import CSVEpisodePlayer
from semantic_digital_twin.adapters.package_resolver import FileUriResolver
try:
    from semantic_digital_twin.adapters.ros.visualization.viz_marker import VizMarkerPublisher
except ImportError:
    VizMarkerPublisher = None
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types import Vector3
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body
from segmind.statecharts.segmind_statechart import SegmindStatechart


@pytest.fixture(scope="function")
def test_csv_player_context():
    world = World()
    root = Body(name=PrefixedName(name="root", prefix="world"))
    with world.modify_world():
        world.add_kinematic_structure_entity(root)

    multiverse_episodes_dir = (
        f"{Path(segmind.__file__).parent.parent.parent}/resources/multiverse_episodes"
    )

    file_player = CSVEpisodePlayer(
        file_path=f"{multiverse_episodes_dir}/icub_montessori_no_hands/data.csv",
        world=world,
        time_between_frames=datetime.timedelta(milliseconds=0.01),
        position_shift=Vector3(0, 0, 0),
    )
    context = MotionStatechartContext(world=world)
    episode_executor = EpisodeSegmenterExecutor(
        context=context,
        player=file_player,
        ignored_objects=["iCub"],
        fixed_objects=["scene"],
    )
    episode_executor.spawn_scene(
        models_dir=f"{multiverse_episodes_dir}/icub_montessori_no_hands/models/",
        file_resolver=FileUriResolver(),
    )
    return {
        "world": world,
        "context": context,
        "file_player": file_player,
        "episode_executor": episode_executor,
    }

# @pytest.mark.skip(reason="This test takes too long to run.")
def test_replay_episode(test_csv_player_context):
    world = test_csv_player_context["world"]
    episode_executor = test_csv_player_context["episode_executor"]

    if rclpy is not None and VizMarkerPublisher is not None:
        rclpy.init()
        node = rclpy.create_node("test_csv_player")
        viz_marker_publisher = VizMarkerPublisher(_world=world, node=node)
        viz_marker_publisher.with_tf_publisher()

    statechart = SegmindStatechart().build_statechart()
    segmind_context = episode_executor.context.require_extension(SegmindContext)
    episode_executor.compile(statechart)


    try:
        while episode_executor.player.is_alive():
            episode_executor.tick()
    finally:
        print(segmind_context.logger.get_events())

    events = segmind_context.logger.get_events()





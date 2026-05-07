import datetime
import os
from pathlib import Path

import pytest
import rclpy

import segmind
from giskardpy.motion_statechart.context import MotionStatechartContext
from segmind.episode_segmenter import EpisodeSegmenterExecutor
from segmind.players.csv_player import CSVEpisodePlayer
from semantic_digital_twin.adapters.mjcf import MJCFParser
from semantic_digital_twin.adapters.package_resolver import FileUriResolver
from semantic_digital_twin.adapters.ros.visualization.viz_marker import VizMarkerPublisher
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types import Vector3
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body


@pytest.fixture(scope="function")
def test_csv_player_context():
    scene_path = "/home/sorin/dev/cognitive_robot_abstract_machine/segmind/resources/tiago_episodes/models/assets/mjcf/iai_tiago_velocity_in_apartment_with_multiverse.xml"
    world = MJCFParser(scene_path).parse()

    # root = Body(name=PrefixedName(name="root", prefix="world"))
    # with world.modify_world():
    #     world.add_kinematic_structure_entity(root)

    #multiverse_episodes_dir = (
    #    f"{Path(segmind.__file__).parent.parent.parent}/resources/multiverse_episodes"
    #)
    #
    # file_player = CSVEpisodePlayer(
    #     file_path=f"{multiverse_episodes_dir}/icub_montessori_no_hands/data.csv",
    #     world=world,
    #     time_between_frames=datetime.timedelta(milliseconds=0.01),
    #     position_shift=Vector3(0, 0, 0),
    # )
    # context = MotionStatechartContext(world=world)
    # episode_executor = EpisodeSegmenterExecutor(
    #     context=context,
    #     player=file_player,
    #     ignored_objects=["iCub"],
    #     fixed_objects=["scene"],
    # )
    # episode_executor.spawn_scene(
    #     models_dir=f"{multiverse_episodes_dir}/icub_montessori_no_hands/models/",
    #     file_resolver=FileUriResolver(),
    # )
    return {
        "world": world,
    #    "context": context,
    #    "file_player": file_player,
    #    "episode_executor": episode_executor,
    }

def test_segmind_demo(test_csv_player_context):
    world = test_csv_player_context["world"]
    rclpy.init()
    node = rclpy.create_node("test_csv_player")
    viz_marker_publisher = VizMarkerPublisher(_world=world, node=node)
    viz_marker_publisher.with_tf_publisher()

"""
Unit tests for bundling a live world's *current* state into a throwaway scene.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path

from typing_extensions import List

from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body

from cramera import paths
from cramera.live.bridge import Bridge
from cramera.onboard.bundle_urdf import BundleReport
from cramera.live.live_bundle import build_live_scene

from .test_robot_parts import ArmPart, NamedBody

ONE_LINK_URDF_TEXT = '<robot name="demo">\n  <link name="base_link"/>\n</robot>\n'

APARTMENT_URDF_TEXT = (
    '<robot name="apartment">\n  <link name="apartment_root"/>\n</robot>\n'
)


@dataclass
class RobotWithBase:
    """
    A robot mimic exposing only what :func:`build_live_scene` reads off it: a root body
    (for the base link name) and one arm (for :meth:`RobotPartAnnotation.of_robot`).
    """

    root: NamedBody
    arm: ArmPart

    def get_arms(self):
        return [self.arm]

    def get_left_arm_if_specified(self):
        return None

    def get_right_arm_if_specified(self):
        return None


def world_with_prefixed_body(prefix: str, name: str) -> World:
    """
    A real world with a single, prefixed body — enough for
    :func:`~cramera.robot_parts.model_identity` to find a model's prefix.

    :param prefix: The body's namespace prefix.
    :param name: The body's local name.
    """
    world = World()
    with world.modify_world():
        world.add_body(Body(name=PrefixedName(name=name, prefix=prefix)))
    return world


def use_scratch_scenes_directory(monkeypatch, tmp_path) -> Path:
    """
    Point :func:`cramera.paths.scenes_directory` at a throwaway directory.

    :param monkeypatch: The active monkeypatch fixture.
    :param tmp_path: The test's own scratch directory.
    """
    scenes = tmp_path / "scenes"
    monkeypatch.setenv("CRAMERA_SCENES", str(scenes))
    return scenes


class TestNothingTrackedYet:
    def test_a_fresh_bridge_bundles_nothing(self, monkeypatch, tmp_path):
        use_scratch_scenes_directory(monkeypatch, tmp_path)

        assert build_live_scene(Bridge()) is None


class TestBuildLiveScene:
    def test_a_tracked_source_is_bundled_under_the_reserved_name(
        self, monkeypatch, tmp_path
    ):
        scenes = use_scratch_scenes_directory(monkeypatch, tmp_path)
        urdf = tmp_path / "pr2.urdf"
        urdf.write_text(ONE_LINK_URDF_TEXT)
        bridge = Bridge()
        bridge.remember_model_source(str(urdf), BundleReport.of_source)
        bridge.world = world_with_prefixed_body("pr2_1", "base_link")
        bridge.robot = RobotWithBase(
            root=NamedBody("pr2_1/base_link"),
            arm=ArmPart(bodies=[NamedBody("pr2_1/l_upper_arm_link")]),
        )

        scene_name = build_live_scene(bridge)

        assert scene_name == paths.LIVE_SCENE_NAME
        scene = json.loads((scenes / scene_name / "scene.json").read_text())
        assert scene["models"] == [
            {
                "name": "pr2",
                "urdf": "pr2.urdf",
                "prefix": "pr2_1",
                "robot": True,
                "links": 1,
                "movableJoints": [],
            }
        ]
        assert scene["robot"]["name"] == "robotwithbase"
        assert scene["robot"]["prefix"] == "pr2_1"
        assert scene["robot"]["baseBody"] == "base_link"
        assert scene["robot"]["parts"] == {"ArmPart": ["l_upper_arm_link"]}
        assert scene["objects"] == []
        assert scene["segments"] == []
        assert "trajectory" not in scene

    def test_the_scene_records_whether_the_world_was_attached_at_build_time(
        self, monkeypatch, tmp_path
    ):
        """
        A bundle built before the demo's world attached cannot identify the models'
        prefixes or the robot; the flag lets the viewer rebuild it once the world is
        there.
        """
        scenes = use_scratch_scenes_directory(monkeypatch, tmp_path)
        urdf = tmp_path / "pr2.urdf"
        urdf.write_text(ONE_LINK_URDF_TEXT)
        bridge = Bridge()
        bridge.remember_model_source(str(urdf), BundleReport.of_source)

        early_name = build_live_scene(bridge)
        early = json.loads((scenes / early_name / "scene.json").read_text())
        assert early["worldBound"] is False

        bridge.world = world_with_prefixed_body("pr2_1", "base_link")
        bound_name = build_live_scene(bridge)
        bound = json.loads((scenes / bound_name / "scene.json").read_text())
        assert bound["worldBound"] is True

    def test_an_attached_world_without_tracked_sources_still_builds_a_scene(
        self, monkeypatch, tmp_path
    ):
        """
        A fully procedural world (no URDF/Gazebo/MJCF source ever parsed) must still get
        the viewer onto the live scene — the overlay renders its bodies from there.
        """
        scenes = use_scratch_scenes_directory(monkeypatch, tmp_path)
        bridge = Bridge()
        bridge.world = world_with_prefixed_body("montessori", "board")

        scene_name = build_live_scene(bridge)

        assert scene_name == paths.LIVE_SCENE_NAME
        scene = json.loads((scenes / scene_name / "scene.json").read_text())
        assert scene["models"] == []
        assert scene["robot"] is None

    def test_no_bound_robot_still_bundles_the_environment(self, monkeypatch, tmp_path):
        scenes = use_scratch_scenes_directory(monkeypatch, tmp_path)
        urdf = tmp_path / "kitchen.urdf"
        urdf.write_text(ONE_LINK_URDF_TEXT)
        bridge = Bridge()
        bridge.remember_model_source(str(urdf), BundleReport.of_source)

        scene_name = build_live_scene(bridge)

        scene = json.loads((scenes / scene_name / "scene.json").read_text())
        assert scene["models"][0]["robot"] is False
        assert scene["robot"] is None

    def test_a_model_absent_from_the_current_world_is_not_bundled(
        self, monkeypatch, tmp_path
    ):
        """
        A long-running process may parse one world after another; the live scene must
        show only the models the currently executing world contains, not everything the
        process ever loaded.
        """
        scenes = use_scratch_scenes_directory(monkeypatch, tmp_path)
        pr2 = tmp_path / "pr2.urdf"
        pr2.write_text(ONE_LINK_URDF_TEXT)
        apartment = tmp_path / "apartment.urdf"
        apartment.write_text(APARTMENT_URDF_TEXT)
        bridge = Bridge()
        bridge.remember_model_source(str(pr2), BundleReport.of_source)
        bridge.remember_model_source(str(apartment), BundleReport.of_source)
        bridge.world = world_with_prefixed_body("pr2_1", "base_link")

        scene_name = build_live_scene(bridge)

        scene = json.loads((scenes / scene_name / "scene.json").read_text())
        assert [model["name"] for model in scene["models"]] == ["pr2"]

    def test_every_model_is_bundled_before_the_world_attaches(
        self, monkeypatch, tmp_path
    ):
        """
        Without a world there is nothing to check presence against; the early bundle
        keeps every tracked model and the viewer rebuilds it once the world is there.
        """
        scenes = use_scratch_scenes_directory(monkeypatch, tmp_path)
        pr2 = tmp_path / "pr2.urdf"
        pr2.write_text(ONE_LINK_URDF_TEXT)
        apartment = tmp_path / "apartment.urdf"
        apartment.write_text(APARTMENT_URDF_TEXT)
        bridge = Bridge()
        bridge.remember_model_source(str(pr2), BundleReport.of_source)
        bridge.remember_model_source(str(apartment), BundleReport.of_source)

        scene_name = build_live_scene(bridge)

        scene = json.loads((scenes / scene_name / "scene.json").read_text())
        assert [model["name"] for model in scene["models"]] == ["pr2", "apartment"]

    def test_an_unchanged_world_does_not_rebuild_the_bundle(
        self, monkeypatch, tmp_path
    ):
        """
        The viewer calls ``/live_scene`` on every attach, and a page reloaded mid-run is
        still downloading the previous build's meshes at that moment — a rebuild would
        delete them mid-flight.

        While nothing the bundle is built from changed, the existing bundle must be left
        untouched.
        """
        scenes = use_scratch_scenes_directory(monkeypatch, tmp_path)
        urdf = tmp_path / "pr2.urdf"
        urdf.write_text(ONE_LINK_URDF_TEXT)
        bridge = Bridge()
        bridge.remember_model_source(str(urdf), BundleReport.of_source)
        bridge.world = world_with_prefixed_body("pr2_1", "base_link")
        build_live_scene(bridge)
        sentinel = scenes / paths.LIVE_SCENE_NAME / "in_flight_download.stl"
        sentinel.write_text("still being served")

        name = build_live_scene(bridge)

        assert name == paths.LIVE_SCENE_NAME
        assert sentinel.exists()

    def test_a_world_attach_after_an_early_build_rebuilds_the_bundle(
        self, monkeypatch, tmp_path
    ):
        """
        The early bundle (built before the demo's world attached) cannot identify
        prefixes or the robot; the attach changes what the bundle would be built from,
        so the next ``/live_scene`` must rebuild it.
        """
        scenes = use_scratch_scenes_directory(monkeypatch, tmp_path)
        urdf = tmp_path / "pr2.urdf"
        urdf.write_text(ONE_LINK_URDF_TEXT)
        bridge = Bridge()
        bridge.remember_model_source(str(urdf), BundleReport.of_source)
        build_live_scene(bridge)
        sentinel = scenes / paths.LIVE_SCENE_NAME / "stale_marker"
        sentinel.write_text("from the early build")

        bridge.world = world_with_prefixed_body("pr2_1", "base_link")
        build_live_scene(bridge)

        assert not sentinel.exists()
        scene = json.loads((scenes / paths.LIVE_SCENE_NAME / "scene.json").read_text())
        assert scene["worldBound"] is True

    def test_the_output_directory_is_cleared_between_builds(
        self, monkeypatch, tmp_path
    ):
        scenes = use_scratch_scenes_directory(monkeypatch, tmp_path)
        first_urdf = tmp_path / "kitchen.urdf"
        first_urdf.write_text(ONE_LINK_URDF_TEXT)
        bridge = Bridge()
        bridge.remember_model_source(str(first_urdf), BundleReport.of_source)
        build_live_scene(bridge)

        second_bridge = Bridge()
        second_urdf = tmp_path / "apartment.urdf"
        second_urdf.write_text(ONE_LINK_URDF_TEXT)
        second_bridge.remember_model_source(str(second_urdf), BundleReport.of_source)
        build_live_scene(second_bridge)

        bundle_directory = scenes / paths.LIVE_SCENE_NAME
        assert not (bundle_directory / "kitchen.urdf").exists()
        assert (bundle_directory / "apartment.urdf").exists()


class TestConcurrentBuilds:
    """
    The bridge serves on a threading HTTP server, and the viewer keeps polling
    ``/live_scene`` while the demo has not parsed its world yet, so two builds of the
    same throwaway scene overlap routinely.

    Each one clears the output directory before writing
    it -- the directory the other one is deleting and writing at the same time.
    """

    VIEWERS_ASKING_AT_ONCE = 8
    """
    How many builds are started together.

    More than two, so the window between one build's delete and its write is actually
    hit rather than only theoretically open.
    """

    def test_overlapping_builds_all_produce_a_complete_bundle(
        self, monkeypatch, tmp_path
    ):
        scenes = use_scratch_scenes_directory(monkeypatch, tmp_path)
        urdf = tmp_path / "kitchen.urdf"
        urdf.write_text(ONE_LINK_URDF_TEXT)
        bridge = Bridge()
        bridge.remember_model_source(str(urdf), BundleReport.of_source)

        names: List[str] = []
        failures: List[BaseException] = []
        start = threading.Barrier(self.VIEWERS_ASKING_AT_ONCE)

        def build() -> None:
            start.wait()
            try:
                names.append(build_live_scene(bridge))
            except BaseException as failure:
                failures.append(failure)

        builders = [
            threading.Thread(target=build, name="viewer-%d" % index)
            for index in range(self.VIEWERS_ASKING_AT_ONCE)
        ]
        for builder in builders:
            builder.start()
        for builder in builders:
            builder.join(timeout=60)

        assert [type(failure).__name__ for failure in failures] == []
        assert names == [paths.LIVE_SCENE_NAME] * self.VIEWERS_ASKING_AT_ONCE
        scene = json.loads((scenes / paths.LIVE_SCENE_NAME / "scene.json").read_text())
        assert [model["name"] for model in scene["models"]] == ["kitchen"]
        assert (scenes / paths.LIVE_SCENE_NAME / "kitchen.urdf").exists()

"""
Tests for :mod:`experiments.tracy_experiments.camera_replay`: only camera topics are
replayed, the topics come from the bag's own metadata, and the colour republisher is
subscribed before playback starts.

No bag is played; :class:`LaunchReplayProcess` stands in for the child processes and
:class:`BagMetadata` for what ``rosbag2_py`` reads.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field

import pytest
from typing_extensions import List, Optional

from experiments.tracy_experiments.camera_replay import (
    COMPRESSED_COLOUR_TOPIC,
    RAW_COLOUR_TOPIC,
    CameraReplay,
    CameraReplayFailed,
    camera_topics_in,
)
from experiments.tracy_experiments.rosbag_recording import (
    CAMERA_TOPICS,
    JOINT_STATE_TOPICS,
    TRANSFORM_TOPICS,
)

# %% test doubles


@dataclass
class TopicMetadata:
    """
    One topic entry of a bag's metadata, shaped the way ``rosbag2_py`` returns it.
    """

    name: str
    """
    The recorded topic's name.
    """

    @property
    def topic_metadata(self) -> "TopicMetadata":
        return self


@dataclass
class BagMetadata:
    """
    Stands in for the metadata ``rosbag2_py.Info.read_metadata`` returns.
    """

    topics_with_message_count: List[TopicMetadata]
    """
    Every topic the bag holds.
    """


@dataclass
class ReplayProcess:
    """
    Stands in for a replay child process that exits immediately.
    """

    pid: int = 555
    """
    Any value; only passed to the patched process-group calls.
    """

    returncode: Optional[int] = 0
    """
    Already exited, so the replay never signals it.
    """

    def poll(self) -> Optional[int]:
        return self.returncode

    def wait(self, timeout: Optional[float] = None) -> int:
        return self.returncode


@dataclass
class LaunchReplayProcess:
    """
    Replaces ``subprocess.Popen``, capturing every command the replay launched.
    """

    commands: List[List[str]] = field(default_factory=list)
    """
    Argument vectors of the launches, in order.
    """

    def __call__(self, command: List[str], **kwargs) -> ReplayProcess:
        self.commands.append(command)
        return ReplayProcess()

    @property
    def player_command(self) -> List[str]:
        """
        :return: The ``ros2 bag play`` command, whichever order things were started in.
        """
        return next(command for command in self.commands if "play" in command)

    @property
    def republisher_commands(self) -> List[List[str]]:
        """
        :return: Every ``image_transport republish`` command launched.
        """
        return [command for command in self.commands if "republish" in command]


@pytest.fixture
def replay_launch(monkeypatch):
    """
    Patch out process launching, the sleep that waits for the republisher, and the bag
    metadata read, so a replay runs without ROS or a bag.

    :return: The :class:`LaunchReplayProcess` standing in for ``subprocess.Popen``.
    """
    module = "experiments.tracy_experiments.camera_replay"
    launch = LaunchReplayProcess()
    monkeypatch.setattr(f"{module}.subprocess.Popen", launch)
    monkeypatch.setattr(f"{module}.shutil.which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(f"{module}.time.sleep", lambda seconds: None)
    monkeypatch.setattr(f"{module}.os.getpgid", lambda pid: pid)
    monkeypatch.setattr(f"{module}.os.killpg", lambda pid, number: None)
    monkeypatch.setattr(
        f"{module}.camera_topics_in", lambda directory: list(CAMERA_TOPICS)
    )
    return launch


@pytest.fixture
def bag_holding(monkeypatch, tmp_path):
    """
    :return: A factory making a readable bag directory whose metadata lists the given
        topics.
    """

    def make(topics: List[str]) -> str:
        directory = tmp_path / "bag"
        directory.mkdir(exist_ok=True)

        @dataclass
        class Info:
            def read_metadata(self, uri: str, storage: str) -> BagMetadata:
                return BagMetadata([TopicMetadata(name) for name in topics])

        monkeypatch.setattr(
            "experiments.tracy_experiments.camera_replay.rosbag2_py.Info", Info
        )
        return str(directory)

    return make


# %% reading the bag


def test_only_the_camera_topics_a_bag_actually_holds_are_returned(bag_holding):
    """
    A bag recorded with a trimmed topic list must replay the streams it has, rather than
    asking the player for topics that are not there.
    """
    directory = bag_holding(
        [COMPRESSED_COLOUR_TOPIC, "/camera/depth/image_raw", "/tf", "/joint_states"]
    )

    assert camera_topics_in(directory) == [
        COMPRESSED_COLOUR_TOPIC,
        "/camera/depth/image_raw",
    ]


def test_a_bag_without_camera_topics_raises(bag_holding):
    directory = bag_holding(JOINT_STATE_TOPICS + TRANSFORM_TOPICS)

    with pytest.raises(CameraReplayFailed):
        camera_topics_in(directory)


def test_a_missing_bag_raises():
    with pytest.raises(CameraReplayFailed):
        camera_topics_in("/nonexistent")


# %% what gets replayed


def test_joint_states_and_transforms_are_never_replayed(replay_launch):
    """
    Republishing the recorded transforms or joint states onto a live system would fight
    the real robot's own publishers and corrupt the TF tree every other node reads.
    """
    CameraReplay(bag_directory="bag").play()

    played = replay_launch.player_command
    for topic in JOINT_STATE_TOPICS + TRANSFORM_TOPICS:
        assert topic not in played


def test_the_camera_topics_are_replayed(replay_launch):
    CameraReplay(bag_directory="bag").play()

    played = replay_launch.player_command
    for topic in CAMERA_TOPICS:
        assert topic in played


# %% colour decompression


def test_colour_is_decompressed_onto_the_raw_topic(replay_launch):
    CameraReplay(bag_directory="bag").play()

    [republisher] = replay_launch.republisher_commands
    assert f"in/compressed:={COMPRESSED_COLOUR_TOPIC}" in republisher
    assert f"out:={RAW_COLOUR_TOPIC}" in republisher


def test_the_transports_are_passed_as_parameters(replay_launch):
    """
    ``in_transport``/``out_transport`` must be parameters. Passed positionally the node
    silently keeps its ``raw`` default and republishes nothing useful.
    """
    CameraReplay(bag_directory="bag").play()

    [republisher] = replay_launch.republisher_commands
    assert "in_transport:=compressed" in republisher
    assert "out_transport:=raw" in republisher


def test_the_republisher_starts_before_playback(replay_launch):
    """
    A republisher that subscribes after playback has begun misses the opening frames.
    """
    CameraReplay(bag_directory="bag").play()

    assert "republish" in replay_launch.commands[0]
    assert "play" in replay_launch.commands[1]


def test_decompression_can_be_turned_off(replay_launch):
    CameraReplay(bag_directory="bag", decompress_colour=False).play()

    assert replay_launch.republisher_commands == []


def test_nothing_is_decompressed_when_the_bag_has_no_compressed_colour(
    replay_launch, monkeypatch
):
    monkeypatch.setattr(
        "experiments.tracy_experiments.camera_replay.camera_topics_in",
        lambda directory: ["/camera/depth/image_raw"],
    )

    CameraReplay(bag_directory="bag").play()

    assert replay_launch.republisher_commands == []


# %% playback options


def test_the_rate_is_passed_to_the_player(replay_launch):
    CameraReplay(bag_directory="bag", rate=4.0).play()

    played = replay_launch.player_command
    assert played[played.index("--rate") + 1] == "4.0"


def test_looping_is_off_unless_asked_for(replay_launch):
    CameraReplay(bag_directory="bag").play()

    assert "--loop" not in replay_launch.player_command


def test_looping_is_passed_to_the_player(replay_launch):
    CameraReplay(bag_directory="bag", loop=True).play()

    assert "--loop" in replay_launch.player_command


def test_a_start_offset_is_passed_to_the_player(replay_launch):
    CameraReplay(bag_directory="bag", start_offset=12.5).play()

    played = replay_launch.player_command
    assert played[played.index("--start-offset") + 1] == "12.5"


def test_no_start_offset_is_passed_when_playing_from_the_beginning(replay_launch):
    CameraReplay(bag_directory="bag").play()

    assert "--start-offset" not in replay_launch.player_command


# %% failures


def test_replaying_without_ros2_on_the_path_raises(replay_launch, monkeypatch):
    monkeypatch.setattr(
        "experiments.tracy_experiments.camera_replay.shutil.which", lambda name: None
    )

    with pytest.raises(CameraReplayFailed):
        CameraReplay(bag_directory="bag").play()

    assert replay_launch.commands == []

from __future__ import annotations

import logging
from datetime import timedelta
import os

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing_extensions import Any, Callable, Optional, Dict, Generator, List

from segmind.datastructures.enums import PlayerStatus
from segmind.episode_player import EpisodePlayer
from semantic_digital_twin.spatial_types import Vector3
from semantic_digital_twin.spatial_types.spatial_types import (
    Pose,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import ActiveConnection1DOF
from semantic_digital_twin.world_description.world_entity import Body

logger = logging.getLogger(__name__)


@dataclass
class FrameData:
    """
    One frame of an episode: where things are and how the joints stand at one time.
    """

    time: float
    """
    The time of the frame.
    """
    objects_data: Dict[str, Any]
    """
    The objects data which contains the poses of the objects, in the form the player's
    source states them.
    """
    frame_idx: int
    """
    The frame index.
    """
    joint_positions: Dict[str, float] = field(default_factory=dict)
    """
    The position of each joint the source states, by the joint's name.
    """


FrameDataGenerator = Generator[FrameData, None, None]


@dataclass(eq=False)
class DataPlayer(EpisodePlayer, ABC):
    """
    Abstract class for players that play the episode from a data source.
    """

    frame_callbacks: List[Callable[[float], None]] = field(
        default_factory=list, hash=False, compare=False
    )
    """
    Callbacks that will be called every time a new frame is processed.
    """

    sync_robot_only: bool = False
    """
    If True, only the robot will be synchronized.
    """

    frame_data_generator: FrameDataGenerator = field(init=False)
    """
    The generator that yields frame data for playback.
    """

    def __post_init__(self):
        super().__post_init__()
        self.frame_data_generator = self.get_frame_data_generator()

    def reset(self):
        """
        Reset the player to its initial state.
        """
        logger.debug("Resetting DataPlayer !!!!!!!!!!!!!!!!")
        self.ready = False
        self.frame_callbacks = []
        self.frame_data_generator = self.get_frame_data_generator()

    @abstractmethod
    def get_frame_data_generator(self) -> FrameDataGenerator:
        """
        :return: the frame data generator.
        """

    def _run(self):
        """
        Starts the episode player and processes the frames, while also setting the time between frames.
        """

        is_first_frame = True
        start_time: float = 0.0
        for frame_data in self.frame_data_generator:

            if self.kill_event.is_set():
                break

            self._wait_if_paused()

            last_processing_time = time.time()

            time.sleep(self.time_between_frames.total_seconds())

            current_time = frame_data.time
            if is_first_frame:
                start_time = current_time
            dt = current_time - start_time
            self.apply_frame(frame_data)

            self.ready = True

            if self._status == PlayerStatus.STOPPED:
                break

            if self.use_realtime:
                wait_time = timedelta(seconds=dt)
                self._wait_to_maintain_frame_rate(last_processing_time, wait_time)

            is_first_frame = False
        self._status = PlayerStatus.STOPPED

    def apply_frame(self, frame_data: FrameData):
        """
        Move the world to one frame: pose its objects and position its joints, notifying
        the world once for the whole frame.

        :param frame_data: The frame data.
        """
        with self.world.batch_state_changes():
            self.process_objects_data(frame_data)
            self.process_joint_positions(frame_data)

    def process_objects_data(self, frame_data: FrameData):
        """
        Process the objects data, by extracting and setting the poses of objects.

        :param frame_data: The frame data.
        """
        objects_poses = self.get_objects_poses(frame_data)
        if not objects_poses:
            return
        for obj in self.world.bodies_with_collision:
            if obj in objects_poses:
                obj.parent_connection.origin = objects_poses[
                    obj
                ].to_homogeneous_matrix()

    def process_joint_positions(self, frame_data: FrameData):
        """
        Position the joints the frame states.

        :param frame_data: The frame data.
        """
        for connection, position in self.get_joint_positions(frame_data).items():
            connection.position = position

    @abstractmethod
    def get_objects_poses(self, frame_data: FrameData) -> Dict[Body, Pose]:
        """
        Get the poses of the objects.

        :param frame_data: The frame data.
        :return: The poses of the objects.
        """
        pass

    def get_joint_positions(
        self, frame_data: FrameData
    ) -> Dict[ActiveConnection1DOF, float]:
        """
        Get the joint positions the frame states, for the connections of the world that
        the source names. A source that records no joints states none.

        :param frame_data: The frame data.
        :return: The position of each named connection.
        """
        return {}


@dataclass(eq=False)
class FilePlayer(DataPlayer, ABC):
    """
    Plays the episode from a file.
    """

    file_path: str = ""
    """
    The path to the file.
    """

    models_dir: Optional[str] = None
    """
    The directory containing the models.
    """

    position_shift: Optional[Vector3] = None
    """
    Position shift that needs to be applied to the objects.
    """

    def __post_init__(self):
        super().__post_init__()
        if self.models_dir is None:
            self.models_dir = os.path.join(os.path.dirname(self.file_path), "models")

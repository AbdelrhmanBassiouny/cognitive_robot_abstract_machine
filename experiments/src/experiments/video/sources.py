"""
What the video is cut from: one run the robot recorded, read back from the results
database and the artifacts kept beside it.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

import numpy as np
import yaml
from typing_extensions import List, Optional

from experiments.episodes.artifacts import ArtifactDirectory, EpisodeArtifacts
from experiments.episodes.episode import RecordedTrial
from experiments.episodes.long_term_memory import LongTermMemory
from experiments.montessori.perception.camera import RgbdFrame
from experiments.montessori.perception.recordings import (
    REFERENCE_FRAME,
    RecordedCamera,
    TransformTopic,
)
from experiments.montessori.results_database import ResultsDatabase
from coraplex.datastructures.grasp import GraspDescription
from coraplex.plans.plan_node import DesignatorNode
from coraplex.robot_plans.actions.core.pick_up import ReachAction
from segmind.datastructures.events import TranslationEvent
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body

FRAMEWORK_DEMO_EPISODE = "3bfe66c1afe644379180e9950081dbc5"
"""
The run of the framework figure's plan on the robot that the video shows.
"""


@dataclass
class RecordedRun:
    """
    One episode the robot recorded: its trial as the database kept it, and the camera
    recording kept beside it.
    """

    episode_identifier: str
    """
    Which episode.
    """

    database: ResultsDatabase = field(default_factory=ResultsDatabase)
    """
    Where its trial was recorded.
    """

    artifacts: ArtifactDirectory = field(default_factory=ArtifactDirectory)
    """
    Where its files were kept.
    """

    camera_pose_from: Optional[Path] = None
    """
    A recording to read the camera's pose from where this episode's own recording
    carries no transforms, or None to insist on this episode's.
    """

    @cached_property
    def trials(self) -> List[RecordedTrial]:
        """
        The episode's trials, read back whole.
        """
        return LongTermMemory(self.database).recall_trials(self.episode_identifier)

    @property
    def trial(self) -> RecordedTrial:
        """
        The episode's first trial.
        """
        return self.trials[0]

    @property
    def world(self) -> World:
        """
        The world the episode kept.
        """
        return self.trial.episode.world

    def body(self, name: str) -> Body:
        """
        :param name: A body's name, as its prefixed name reads.
        :return: That body of the episode's world.
        """
        return next(body for body in self.world.bodies if str(body.name) == name)

    def pose_before_it_moved(self, body: Body) -> np.ndarray:
        """
        Where a body stood when the look found it: where its first recorded translation
        set out from, or where the world keeps it if the run never moved it.

        :param body: The body.
        :return: Its pose in the world root frame, as a four by four matrix.
        """
        for tick in self.trial.ticks:
            for event in tick.events:
                if isinstance(event, TranslationEvent) and event.tracked_object is body:
                    return event.start_pose.to_np()
        return self.world.compute_forward_kinematics_np(self.world.root, body)

    def recorded_grasp(self) -> GraspDescription:
        """
        The grasp the run's pick-up was carried out with, as the first action that
        states one recorded it.

        :raises StopIteration: If no recorded action states a grasp.
        """
        return next(
            node.designator.grasp_description
            for performed in self.trial.plans
            for node in performed.plan.nodes
            if isinstance(node, DesignatorNode)
            and isinstance(node.designator, ReachAction)
        )

    @cached_property
    def kept(self) -> EpisodeArtifacts:
        """
        The episode's files.
        """
        return self.artifacts.open_for(self.trial.episode)

    @property
    def bag(self) -> Path:
        """
        The directory of the camera recording.
        """
        return self.kept.camera_recording

    @cached_property
    def metadata(self) -> dict:
        """
        What the recording says of itself.
        """
        return yaml.safe_load((self.bag / "metadata.yaml").read_text())[
            "rosbag2_bagfile_information"
        ]

    @property
    def recording_began(self) -> datetime.datetime:
        """
        When the recording began, on the machine's own clock.
        """
        nanoseconds = self.metadata["starting_time"]["nanoseconds_since_epoch"]
        return datetime.datetime.fromtimestamp(nanoseconds / 1e9)

    def recording_second_of(self, trial: RecordedTrial, moment: float) -> float:
        """
        A moment of a trial as seconds into the recording.

        :param trial: The trial, whose start the moment is counted from.
        :param moment: Seconds into the trial.
        """
        return (trial.began_at - self.recording_began).total_seconds() + moment

    @property
    def carries_camera_pose(self) -> bool:
        """
        Whether the recording holds the static transforms the camera's pose is read
        from.
        """
        return any(
            topic["topic_metadata"]["name"] == str(TransformTopic.STATIC)
            and topic["message_count"] > 0
            for topic in self.metadata["topics_with_message_count"]
        )

    @cached_property
    def camera(self) -> RecordedCamera:
        """
        The robot's camera, as the recording holds it, its pose borrowed from another
        recording where this one kept none.
        """
        return RecordedCamera(
            bag=self.bag,
            reference_frame=REFERENCE_FRAME,
            camera_bag=None if self.carries_camera_pose else self.camera_pose_from,
        )

    def frame(self, index: int) -> RgbdFrame:
        """
        One frame of the recording, with the depth, calibration and pose the look reads
        it with.

        :param index: Which colour image of the recording.
        """
        camera = self.camera
        return camera.image_at_index(index).to_frame(
            camera.intrinsics, camera.reference_frame_T_camera
        )

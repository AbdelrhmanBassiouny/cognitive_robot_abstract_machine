"""
Where a look at the Montessori scene comes from.

A source is handed what the look was asked for and answers with what it found. Acting on
the request is a source's own affair: one that takes a fresh look narrows it, while one
serving a look already taken answers with everything it has and leaves the narrowing to
whoever asked.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from experiments.montessori.perception.camera import RgbdFrame
from experiments.montessori.perception.detections import MontessoriScene
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.perception.scene_request import SceneRequest
from semantic_digital_twin.world_description.world_entity import (
    KinematicStructureEntity,
)
from typing_extensions import Optional

# %% where a scene comes from


class MontessoriSceneSource(ABC):
    """
    Something that can say what the Montessori scene currently looks like.
    """

    @property
    @abstractmethod
    def reference_frame(self) -> Optional[KinematicStructureEntity]:
        """
        The frame this source reports its detections in, or None where it reports them
        in none.

        A region a statement names is a world entity, so what it reaches in metres can
        only be read against the frame the things it is stated about are placed in.
        """

    @abstractmethod
    def scene(self, request: SceneRequest = SceneRequest()) -> MontessoriScene:
        """
        Look at the scene.

        :param request: What the look is asked for. A source that cannot narrow its look
            may answer with more than this asks for.
        :return: What was found.
        """


@dataclass
class FixedScene(MontessoriSceneSource):
    """
    A scene that was already looked at, for querying one captured moment repeatedly.
    """

    captured: MontessoriScene
    """
    The scene to answer every query from.
    """

    reported_in: Optional[KinematicStructureEntity] = None
    """
    The frame the captured scene's detections were placed in, where it is known.
    """

    @property
    def reference_frame(self) -> Optional[KinematicStructureEntity]:
        return self.reported_in

    def scene(self, request: SceneRequest = SceneRequest()) -> MontessoriScene:
        """
        :param request: Ignored: this look was taken before the request existed.
        :return: The captured scene, whole.
        """
        return self.captured


@dataclass
class RecordedFrame(MontessoriSceneSource):
    """
    One frame of camera data, looked at afresh for every request.

    The counterpart of :class:`FixedScene` for a recording: the look has not been taken
    yet, so what a request narrows is what is actually searched rather than what is
    filtered afterwards.
    """

    pipeline: MontessoriPerceptionPipeline
    """
    What takes the look.
    """

    frame: RgbdFrame
    """
    The camera data to look at.
    """

    @property
    def reference_frame(self) -> Optional[KinematicStructureEntity]:
        return self.pipeline.reference_frame

    def scene(self, request: SceneRequest = SceneRequest()) -> MontessoriScene:
        """
        :param request: What the look is asked for, which this one acts on.
        :return: What was found.
        """
        return self.pipeline.detect(self.frame, request)

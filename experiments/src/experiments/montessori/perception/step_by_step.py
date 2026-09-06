"""
Watch a look narrow itself, one stated condition at a time.

The backend takes a statement one stated condition at a time, and after each one the
picture that is left to search is drawn together with what a look answering that much of
it reports. Two pictures per step: the camera's own image cut to what is left, and the
rectified plane the detectors read, turned the way the camera sees it and with
everything but a stated colour blacked out. Neither carries a mark, since a step is
where there is still to look; a run ends by putting the whole image back on screen with
a box around what the statement found. Each window is named by how the statement reads
so far, so what is on screen and what was asked for are the same sentence.

Everything but the drawing is :class:`SearchNarrowing`, so a run with no window at all
takes the same steps and can be checked without a screen.
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path

import cv2
import numpy as np
from typing_extensions import Callable, List, Optional, Self, Tuple

from experiments.montessori.perception.backend import MontessoriPerceptionBackend
from experiments.montessori.perception.camera import RgbdFrame
from experiments.montessori.perception.captures import CAPTURE_DIRECTORY, SceneCapture
from experiments.montessori.perception.detections import (
    MontessoriBoardDetection,
    MontessoriScene,
    DetectedMontessoriShape,
)
from experiments.montessori.perception.orthophoto import WorkspaceRegion
from experiments.montessori.perception.overlay import (
    CameraView,
    DetectionOverlay,
    DetectionView,
    RectifiedView,
    ViewFromAbove,
)
from experiments.montessori.perception.pipeline import (
    MontessoriPerceptionPipeline,
    SurfaceColors,
)
from experiments.montessori.perception.recorded_setup import (
    camera_in,
    perception_pipeline,
    recorded_world,
)
from experiments.montessori.perception.scene_request import SceneRequest
from experiments.montessori.pieces import KNOWN_PIECES
from experiments.montessori.perception.scene_source import RecordedFrame
from experiments.montessori.perception.viewer import (
    ImageDisplay,
    OpenCvDisplay,
    QuitKey,
    scale_to_fit,
)
from krrood.entity_query_language.query.match import Match
from krrood.entity_query_language.verbalization.pipeline import (
    verbalize_expression,
    VerbalizationPipeline,
)
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
)
from semantic_digital_twin.world import World

logger = logging.getLogger(__name__)

DEMONSTRATION_CAPTURE = "tracy_pickup_demo"
"""
The shipped capture a run watches where none was named: the one holding pieces on the
table and on the board's lid, which is what a narrowing has something to leave out of.
"""

# %% which capture is watched, and how


@dataclass(frozen=True)
class WatchedCapture:
    """
    Which of the shipped captures a run is watched on, and whether it draws anything.
    """

    name: str = DEMONSTRATION_CAPTURE
    """
    What the capture is called.
    """

    directory: Path = CAPTURE_DIRECTORY
    """
    Where the captures lie.
    """

    draws_windows: bool = True
    """
    Whether each step is put on screen, or only taken -- which is what a run with no
    screen needs.
    """

    @classmethod
    def from_command_line(cls, arguments: Optional[List[str]] = None) -> Self:
        """
        Read off the command line which capture to watch and whether to draw it.

        :param arguments: The command line to read, or None for this process's own.
        :return: What it asked for, with this class's own defaults for what it left
            unsaid.
        """
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument(
            "capture",
            nargs="?",
            default=cls.name,
            help="name of the capture to watch the narrowing on",
        )
        parser.add_argument(
            "--directory",
            type=Path,
            default=cls.directory,
            help="where the captures lie",
        )
        parser.add_argument(
            "--without-windows",
            action="store_true",
            help="take the steps without drawing anything, for a run with no screen",
        )
        read = parser.parse_args(arguments)
        return cls(
            name=read.capture,
            directory=read.directory,
            draws_windows=not read.without_windows,
        )


# %% one look at the setup the recordings were made on


@dataclass
class RecordedLook:
    """
    One look at the recorded setup: the world it is described in, the pictures it was
    taken from, and the board they show.

    A statement is written over the things a world holds rather than over a capture
    name, so what a demonstration states is written over this.
    """

    world: World
    """
    The world the surfaces this look was taken over are described in.
    """

    pipeline: MontessoriPerceptionPipeline
    """
    What answers a look at those surfaces.
    """

    frame: RgbdFrame
    """
    The camera data the look was taken from.
    """

    board: Optional[MontessoriBoardDetection]
    """
    The board as this look found it, which is what says how far its lid reaches and
    where each of its holes lies, or None if it was not in view.
    """

    seen_from: HomogeneousTransformationMatrix
    """
    Where the camera stood, in the convention a pose is stated in, which is what a
    stated direction is read from.
    """

    @classmethod
    def taken_from(cls, capture: WatchedCapture) -> Self:
        """
        Take one look at a shipped capture.

        :param capture: Which capture to read.
        :return: That look, with the board it found and the spot it was taken from.
        """
        world = recorded_world()
        pipeline = perception_pipeline(world)
        frame = SceneCapture.load(capture.name, capture.directory).to_frame()
        return cls(
            world=world,
            pipeline=pipeline,
            frame=frame,
            board=pipeline.board_in(frame),
            seen_from=frame.point_of_view(world.root, camera_in(world, frame)),
        )

    @property
    def backend(self) -> MontessoriPerceptionBackend:
        """
        What answers a statement about this look, by looking at its own pictures.
        """
        return MontessoriPerceptionBackend(
            source=RecordedFrame(pipeline=self.pipeline, frame=self.frame)
        )


# %% what a step is shown as


class NarrowingView(StrEnum):
    """
    The pictures a narrowing is drawn as: two per step, and the one it ends in.
    """

    CAMERA = "camera"
    RECTIFIED = "rectified"
    ANSWER = "answer"


@dataclass(frozen=True)
class NarrowingStep:
    """
    One statement, and the stretch of the scene a look answering it still has to read.
    """

    label: str
    """
    How the statement reads, which is what the pictures of this step are named by.
    """

    request: SceneRequest
    """
    What the statement compiles to, which is what a look acts on.
    """

    region: Optional[WorkspaceRegion]
    """
    The patch of plane the look still rectifies, or None where the statement narrowed it
    away from every surface of the scene.
    """

    plane_height: float
    """
    Height of the plane that patch lies in, above the world frame's origin, in metres.
    """

    found: Tuple[DetectedMontessoriShape, ...]
    """
    What a look answering the statement so far reports.
    """

    @property
    def searched_area(self) -> float:
        """
        How much table, in square metres, the look still reads.
        """
        if self.region is None:
            return 0.0
        return (self.region.maximum_x - self.region.minimum_x) * (
            self.region.maximum_y - self.region.minimum_y
        )


# %% narrowing a look one condition at a time


@dataclass
class SearchNarrowing:
    """
    Adds one stated condition after another to a look, and says what each one leaves.

    Reading the conditions and working out what is left is the whole of it; drawing them
    is optional, so the same steps can be checked with no screen.
    """

    pipeline: MontessoriPerceptionPipeline
    """
    The pipeline whose surfaces the conditions narrow.
    """

    display: Optional[ImageDisplay] = None
    """
    Where the pictures are put on screen, or None to take the steps without drawing.
    """

    maximum_width: int = 720
    """
    Widest a picture is drawn, in pixels.
    """

    maximum_height: int = 540
    """
    Tallest a picture is drawn, in pixels.
    """

    def steps(
        self,
        frame: RgbdFrame,
        statement: Match[DetectedMontessoriShape],
        board: Optional[MontessoriBoardDetection] = None,
    ) -> List[NarrowingStep]:
        """
        Read one statement as it grows, from saying nothing about the piece it is
        looking for to saying everything it says.

        The statement is written whole and interpreted here rather than assembled a
        condition at a time, so what is watched is one query being read by the backend
        that answers it.

        :param frame: The camera data the look is taken from, which is what says where
            the board stands and so how far its lid reaches.
        :param statement: What the look is being asked for.
        :param board: The board as this frame shows it, where it has already been found
            -- which it has whenever the statement names one of its holes -- or None to
            find it here.
        :return: One step per condition the statement states about the piece, plus the
            bare statement they grow from.
        """
        board = self.pipeline.board_in(frame) if board is None else board
        backend = MontessoriPerceptionBackend(
            source=RecordedFrame(pipeline=self.pipeline, frame=frame)
        )
        return [
            self._step(said, board, backend, frame)
            for said in statement.one_condition_at_a_time()
        ]

    def _step(
        self,
        statement: Match[DetectedMontessoriShape],
        board: Optional[MontessoriBoardDetection],
        backend: MontessoriPerceptionBackend,
        frame: RgbdFrame,
    ) -> NarrowingStep:
        """
        What one statement leaves a look to read, and what answering it reports.

        :param statement: The statement so far.
        :param board: The board as this frame showed it, which is what says how far its
            lid reaches.
        :param backend: What answers the statement by looking.
        :param frame: The camera data the look is taken from.
        """
        request = backend.scene_request(backend.read_request(statement))
        searches = self.pipeline.scene_to_search(frame, request).searched_surfaces(
            board
        )
        return NarrowingStep(
            label=verbalize_expression(statement, backend=backend),
            request=request,
            region=searches[0].region if searches else None,
            plane_height=(
                searches[0].surface.height if searches else self.pipeline.table.height
            ),
            found=tuple(statement.evaluate(backend=backend)),
        )

    def watch(
        self,
        frame: RgbdFrame,
        statement: Match[DetectedMontessoriShape],
        board: Optional[MontessoriBoardDetection] = None,
    ) -> List[NarrowingStep]:
        """
        Take the steps, drawing each one and holding it until a key is pressed.

        :param frame: The camera data the look is taken from.
        :param statement: What the look is being asked for.
        :param board: The board as this frame shows it, where it has already been found.
        :return: The steps taken, however many of them were drawn.
        """
        taken = self.steps(frame, statement, board)
        for step in taken:
            logger.info(
                "%s -- %.3f m2 left to read, and %s in it",
                step.label,
                step.searched_area,
                ", ".join(piece.label for piece in step.found) or "nothing",
            )
            if self.display is None:
                continue
            self.draw(step, frame)
            pressed = self.display.wait(0)
            if pressed is not None and pressed in QuitKey:
                return taken
        if self.display is None:
            return taken
        self.draw_answer(taken[-1], frame)
        self.display.wait(0)
        return taken

    def draw(self, step: NarrowingStep, frame: RgbdFrame) -> None:
        """
        Put one step's two pictures on screen, each in a window named by the statement.

        A step says where there is still to look, so nothing is drawn over either
        picture: what the statement ends up finding is marked once, in
        :meth:`draw_answer`.

        A step that narrowed the look away from every surface has nothing to draw, and
        says so by drawing nothing.

        :param step: The step to draw.
        :param frame: The camera data the look is taken from.
        """
        if self.display is None or step.region is None:
            return
        camera = self.pipeline.workspace_over(step.region).clip(frame.color, frame)
        rectified = self.rectified_view(step, frame).to_image()
        for view, picture in (
            (NarrowingView.CAMERA, camera),
            (NarrowingView.RECTIFIED, rectified),
        ):
            self.display.draw(self.window_name(view, step), self._fitted(picture))

    def draw_answer(self, step: NarrowingStep, frame: RgbdFrame) -> None:
        """
        Put the camera's whole image on screen with a box around every piece the
        statement found, which is what all the narrowing was for.

        :param step: The step whose statement was read whole.
        :param frame: The camera data the look is taken from.
        """
        if self.display is None:
            return
        self.display.draw(
            self.window_name(NarrowingView.ANSWER, step),
            self._fitted(
                DetectionOverlay().draw(
                    CameraView(frame=frame),
                    MontessoriScene(shapes=list(step.found)),
                )
            ),
        )

    def rectified_view(self, step: NarrowingStep, frame: RgbdFrame) -> DetectionView:
        """
        The plane a step still searches, as the detectors read it and the way round the
        camera sees it.

        A rectified image is indexed the way its patch is measured, which is a quarter
        turn from the camera's own view of the same table, so it is turned back before
        it is shown: a direction stated from where the camera stands is meant to read on
        screen the way it was said.

        A colour is a narrowing like the others, so a step stating one has everything
        else blacked out: what is left is what a look asked for that colour marks.

        :param step: The step to draw.
        :param frame: The camera data the look is taken from.
        """
        rectified = self.pipeline.rectify(frame, step.plane_height, step.region)
        if step.request.color is not None:
            rectified = replace(
                rectified,
                image=cv2.bitwise_and(
                    rectified.image,
                    rectified.image,
                    mask=self._piece_colors().color_mask(
                        rectified, step.request.color
                    ),
                ),
            )
        return ViewFromAbove(view=RectifiedView(frame=frame, orthophoto=rectified))

    def _piece_colors(self) -> SurfaceColors:
        """
        How a piece separates from a surface by colour, as the detector that would read
        the table states it.

        The drawing blacks out everything but the colour a step asked for, so it marks
        the picture the way the look marking it does rather than by a second set of
        thresholds.
        """
        [(detector, _)] = (
            self.pipeline.look_rules.find_the_pieces.detector_rules.detectors_for(
                self.pipeline.table, KNOWN_PIECES
            )
        )
        return detector.colors

    @staticmethod
    def window_name(view: NarrowingView, step: NarrowingStep) -> str:
        """
        What one picture of one step is called on screen.

        :param view: Which of the step's pictures it is.
        :param step: The step being drawn.
        """
        return f"{view.value}: {step.label}"

    def _fitted(self, picture: np.ndarray) -> np.ndarray:
        """
        Shrink a picture to the size this narrowing draws at.

        :param picture: The picture to fit.
        """
        return scale_to_fit(picture, self.maximum_width, self.maximum_height)


# %% watching one statement being read


def show_step_by_step(
    statement_about: Callable[[RecordedLook], Match[DetectedMontessoriShape]],
    capture: WatchedCapture = WatchedCapture(),
) -> List[NarrowingStep]:
    """
    Watch one statement being read, one stated condition at a time.

    The look is taken here, so a caller supplies the statement and nothing else: which
    capture it is watched on, the world it is described in, the pipeline that answers it
    and the display it is drawn on all belong to the watching rather than to the
    statement. A statement is written over the things a world holds, so what is supplied
    is how to state it about a look rather than a statement already stated.

    :param statement_about: What to ask of the look, written over the look it asks it
        of.
    :param capture: Which shipped capture to watch it on, and whether to draw anything.
    :return: One step per condition the statement states, plus the bare statement.
    """
    look = RecordedLook.taken_from(capture)
    statement = statement_about(look)
    display = OpenCvDisplay() if capture.draws_windows else None
    print(
        VerbalizationPipeline.ansi(hierarchical=True).verbalize(
            statement, backend=look.backend
        )
    )
    try:
        return SearchNarrowing(pipeline=look.pipeline, display=display).watch(
            look.frame, statement, look.board
        )
    finally:
        if display is not None:
            display.close()

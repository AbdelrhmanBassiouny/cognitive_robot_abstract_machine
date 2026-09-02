"""
Watch a look narrow itself, one stated condition at a time.

Run it as::

    python -m experiments.montessori.perception.watch_narrowing

One statement says the whole of it -- what the piece rests on, which way it lies from
one of the board's own holes, what colour it is, and what those things it is related to
are -- and it is the reading of that statement that is watched: the backend takes it one
stated condition at a time, and after each one the picture that is left to search is
drawn, together with what a look answering that much of it reports. Two pictures per
step: the camera's own image cut to what is left, and the rectified plane the detectors
read, turned the way the camera sees it and with everything but a stated colour blacked
out. Neither carries a mark, since a step is where there is still to look; the run ends
by putting the whole image back on screen with a box around what the statement found.
Each window is named by how the statement reads so far, so what is on screen and what
was asked for are the same sentence. Press any key for the next condition; press ``q``
or escape to stop.

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
from typing_extensions import List, Optional, Tuple

from experiments.montessori.hole_geometry import HOLE_NAME_BY_CATEGORY
from experiments.montessori.perception.backend import MontessoriPerceptionBackend
from experiments.montessori.perception.camera import RgbdFrame
from experiments.montessori.perception.captures import CAPTURE_DIRECTORY, SceneCapture
from experiments.montessori.perception.detections import (
    MontessoriBoardDetection,
    MontessoriScene,
    MontessoriShapeDetection,
)
from experiments.montessori.perception.orthophoto import WorkspaceRegion
from experiments.montessori.perception.overlay import (
    CameraView,
    DetectionOverlay,
    DetectionView,
    RectifiedView,
    ViewFromAbove,
)
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.perception.recorded_setup import (
    board_holes_in,
    camera_in,
    lid_surface,
    recorded_world,
    perception_pipeline,
)
from experiments.montessori.perception.scene_request import SceneRequest
from experiments.montessori.perception.scene_source import RecordedFrame
from experiments.montessori.perception.viewer import (
    ImageDisplay,
    OpenCvDisplay,
    QuitKey,
    scale_to_fit,
)
from experiments.montessori.pieces import KNOWN_PIECE_BY_CATEGORY
from experiments.montessori.semantics import MontessoriShapeCategory
from krrood.entity_query_language.factories import a, variable
from krrood.entity_query_language.query.match import Match
from krrood.entity_query_language.verbalization.pipeline import (
    verbalize_expression,
    VerbalizationPipeline,
)
from semantic_digital_twin.reasoning.predicates import (
    Above,
    Colored,
    SupportedBy,
    LeftOf,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body

logger = logging.getLogger(__name__)


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

    found: Tuple[MontessoriShapeDetection, ...]
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

    def board_in(self, frame: RgbdFrame) -> Optional[MontessoriBoardDetection]:
        """
        The board as one frame shows it, which is what says how far its lid reaches and
        where each of its holes lies.

        :param frame: The camera data the look is taken from.
        :return: The board, or None if it was not in view.
        """
        return self.pipeline.board_detector.detect(
            self.pipeline.rectify(frame, self.pipeline.lid.height),
            self.pipeline.reference_frame,
        )

    def steps(
        self,
        frame: RgbdFrame,
        statement: Match[MontessoriShapeDetection],
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
        board = self.board_in(frame) if board is None else board
        backend = MontessoriPerceptionBackend(
            source=RecordedFrame(pipeline=self.pipeline, frame=frame)
        )
        return [
            self._step(said, board, backend)
            for said in statement.one_condition_at_a_time()
        ]

    def _step(
        self,
        statement: Match[MontessoriShapeDetection],
        board: Optional[MontessoriBoardDetection],
        backend: MontessoriPerceptionBackend,
    ) -> NarrowingStep:
        """
        What one statement leaves a look to read, and what answering it reports.

        :param statement: The statement so far.
        :param board: The board as this frame showed it, which is what says how far its
            lid reaches.
        :param backend: What answers the statement by looking.
        """
        request = backend.scene_request(backend.read_request(statement))
        searches = self.pipeline.searched_surfaces(board, request)
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
        statement: Match[MontessoriShapeDetection],
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
                    mask=self.pipeline.piece_detector.colors.color_mask(
                        rectified, step.request.color
                    ),
                ),
            )
        return ViewFromAbove(view=RectifiedView(frame=frame, orthophoto=rectified))

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


# %% the statement this demonstration narrows


def look_for_the_cube_on_the_lid(
    world: World, frame: RgbdFrame, board: MontessoriBoardDetection
) -> Match[MontessoriShapeDetection]:
    """
    The statement the demonstration watches, written whole: the piece it is looking for,
    the things it says that piece stands in relation to, and every one of those
    relations.

    Nothing is fetched out of the world beforehand. The lid and the two holes are
    described in the statement itself, by what the world calls them -- the lid beside
    the relation naming it, each hole as a statement of its own handed to the relation
    in its place -- and answering those descriptions is the backend's own first move,
    which is what lets the relations that mention them narrow the look at all.

    Support first, because it is the narrowing the request language already had and the
    one the digital twin answers by itself: naming the surface names a stretch of a
    plane the world describes. Directions from two of the board's own holes second,
    because they are the world's own vocabulary saying where on that surface to look.
    The colour last, because it narrows what is worth fitting rather than where to fit
    it, and so is the one narrowing a picture of the region cannot show on its own.

    A direction is read from where the camera stands, so left, right and above mean what
    they mean on screen. Which of them tells the two pieces on the lid apart is measured
    rather than assumed: on ``tracy_pickup_demo`` the cube stands left of the square
    hole in the picture and above the triangle hole, and the cylinder stands right of
    the one and below the other.

    :param world: The world holding the surfaces the statement describes.
    :param frame: The camera data the look is taken from, which is what says where the
        directions are read from.
    :param board: The board as this look found it, which is what says where its holes
        lie; they are put in the world here so the statement can describe two of them.
    :return: The whole statement.
    """
    board_holes_in(world, board)
    seen_from = frame.point_of_view(world.root, camera_in(world, frame))
    lid = variable(Body, world.bodies)
    cube = KNOWN_PIECE_BY_CATEGORY[MontessoriShapeCategory.CUBE]
    triangle = KNOWN_PIECE_BY_CATEGORY[MontessoriShapeCategory.TRIANGULAR_PRISM]
    square_hole = a(Body)().from_(world.bodies)
    square_hole.where(
        square_hole.variable.name.name == HOLE_NAME_BY_CATEGORY[cube.category]
    )
    triangle_hole = a(Body)().from_(world.bodies)
    triangle_hole.where(
        triangle_hole.variable.name.name == HOLE_NAME_BY_CATEGORY[triangle.category]
    )
    sought = a(MontessoriShapeDetection)()
    return sought.where(
        lid.name == lid_surface().name,
        SupportedBy(sought.variable, lid),
        LeftOf(sought.variable, square_hole.expression, seen_from),
        Above(sought.variable, triangle_hole.expression, seen_from),
        Colored(sought.variable, cube.color),
    )


def main() -> None:
    """
    Watch the narrowing on one of the captures shipped with this package.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "capture",
        nargs="?",
        default="tracy_pickup_demo",
        help="name of the capture to watch the narrowing on",
    )
    parser.add_argument(
        "--directory",
        type=Path,
        default=CAPTURE_DIRECTORY,
        help="where the captures lie",
    )
    parser.add_argument(
        "--without-windows",
        action="store_true",
        help="take the steps without drawing anything, for a run with no screen",
    )
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    world = recorded_world()
    pipeline = perception_pipeline(world)
    narrowing = SearchNarrowing(
        pipeline,
        display=None if arguments.without_windows else OpenCvDisplay(),
    )
    frame = SceneCapture.load(arguments.capture, arguments.directory).to_frame()
    board = narrowing.board_in(frame)
    statement = look_for_the_cube_on_the_lid(world, frame, board)
    backend = MontessoriPerceptionBackend(
        source=RecordedFrame(pipeline=pipeline, frame=frame)
    )
    verbalization = VerbalizationPipeline.ansi(hierarchical=True).verbalize(
        statement, backend=backend
    )
    print("=====================================================")
    print(verbalization)
    print("=====================================================")
    try:
        narrowing.watch(frame, statement, board)
    finally:
        if narrowing.display is not None:
            narrowing.display.close()


if __name__ == "__main__":
    main()

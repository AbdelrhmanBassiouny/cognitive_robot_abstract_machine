"""
Watch a look narrow itself, one stated condition at a time.

Run it as::

    python -m experiments.montessori.perception.watch_narrowing

A statement is built up condition by condition -- what the piece rests on, which way it
lies from one of the board's own holes, what colour it is -- and after each one the
picture that is left to search is drawn: the camera's own image cut to it, and the
rectified plane the detectors would actually read, with everything but a stated colour
blacked out. Each window is named by how the statement reads so far, so what is on
screen and what was asked for are the same sentence, and each step also reports what a
look answering it finds. Press any key to add the next condition; press ``q`` or escape
to stop.

Everything but the drawing is :class:`SearchNarrowing`, so a run with no window at all
takes the same steps and can be checked without a screen.
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import cv2
import numpy as np
from typing_extensions import Any, Callable, List, Optional, Sequence, Tuple

from experiments.montessori.perception.backend import MontessoriPerceptionBackend
from experiments.montessori.perception.camera import RgbdFrame
from experiments.montessori.perception.captures import CAPTURE_DIRECTORY, SceneCapture
from experiments.montessori.perception.orthophoto import WorkspaceRegion
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.hole_geometry import HOLE_NAME_BY_CATEGORY
from experiments.montessori.perception.recorded_setup import (
    board_holes_in,
    lid_surface,
    recorded_world,
    perception_pipeline,
)
from experiments.montessori.pieces import KNOWN_PIECE_BY_CATEGORY
from experiments.montessori.semantics import MontessoriShapeCategory
from experiments.montessori.perception.scene_request import SceneRequest
from experiments.montessori.perception.scene_source import RecordedFrame
from experiments.montessori.perception.viewer import (
    ImageDisplay,
    OpenCvDisplay,
    QuitKey,
    scale_to_fit,
)
from krrood.entity_query_language.factories import an
from krrood.entity_query_language.verbalization.pipeline import verbalize_expression
from experiments.montessori.perception.detections import (
    MontessoriBoardDetection,
    MontessoriShapeDetection,
)
from semantic_digital_twin.reasoning.predicates import (
    Colored,
    InFrontOf,
    SupportedBy,
)
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body

logger = logging.getLogger(__name__)

# %% what a step is shown as


class NarrowingView(StrEnum):
    """
    The two pictures one step of a narrowing is drawn as.
    """

    CAMERA = "camera"
    RECTIFIED = "rectified"


StatedCondition = Callable[[Any], Any]
"""
Something a statement can say about the thing it is looking for.

Written as a call taking that thing, since a condition is stated about the statement's
own variable and the variable does not exist until the statement does.
"""


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
        conditions: Sequence[StatedCondition],
        board: Optional[MontessoriBoardDetection] = None,
    ) -> List[NarrowingStep]:
        """
        Take the statement from saying nothing to saying every condition in turn.

        :param frame: The camera data the look is taken from, which is what says where
            the board stands and so how far its lid reaches.
        :param conditions: The conditions to add, in the order they are stated.
        :param board: The board as this frame shows it, where it has already been found
            -- which it has whenever a condition names one of its holes -- or None to
            find it here.
        :return: One step for the bare statement and one for each condition added.
        """
        board = self.board_in(frame) if board is None else board
        backend = MontessoriPerceptionBackend(
            source=RecordedFrame(pipeline=self.pipeline, frame=frame)
        )
        statement = an(MontessoriShapeDetection)()
        taken = [self._step(statement, board, backend)]
        for condition in conditions:
            statement = statement.where(condition(statement.variable))
            taken.append(self._step(statement, board, backend))
        return taken

    def _step(
        self,
        statement: Any,
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
        conditions: Sequence[StatedCondition],
        board: Optional[MontessoriBoardDetection] = None,
    ) -> List[NarrowingStep]:
        """
        Take the steps, drawing each one and holding it until a key is pressed.

        :param frame: The camera data the look is taken from.
        :param conditions: The conditions to add, in the order they are stated.
        :param board: The board as this frame shows it, where it has already been found.
        :return: The steps taken, however many of them were drawn.
        """
        taken = self.steps(frame, conditions, board)
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
                break
        return taken

    def draw(self, step: NarrowingStep, frame: RgbdFrame) -> None:
        """
        Put one step's two pictures on screen, each in a window named by the statement.

        A step that narrowed the look away from every surface has nothing to draw, and
        says so by drawing nothing.

        :param step: The step to draw.
        :param frame: The camera data the look is taken from.
        """
        if self.display is None or step.region is None:
            return
        for view, picture in (
            (
                NarrowingView.CAMERA,
                self.pipeline.workspace_over(step.region).clip(frame.color, frame),
            ),
            (NarrowingView.RECTIFIED, self._rectified(step, frame)),
        ):
            self.display.draw(self.window_name(view, step), self._fitted(picture))

    def _rectified(self, step: NarrowingStep, frame: RgbdFrame) -> np.ndarray:
        """
        The plane a step still searches, as the detectors would read it.

        A colour is a narrowing like the others, so a step stating one has everything
        else blacked out: what is left is what a look asked for that colour marks.

        :param step: The step to draw.
        :param frame: The camera data the look is taken from.
        """
        rectified = self.pipeline.rectify(frame, step.plane_height, step.region)
        if step.request.color is None:
            return rectified.image
        return cv2.bitwise_and(
            rectified.image,
            rectified.image,
            mask=self.pipeline.piece_detector.colors.color_mask(
                rectified, step.request.color
            ),
        )

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


# %% the conditions this demonstration states


def conditions_over(
    world: World, board: Optional[MontessoriBoardDetection]
) -> Tuple[StatedCondition, ...]:
    """
    The conditions the demonstration adds, each narrowing what is left of the one
    before.

    Support first, because it is the narrowing the request language already had and the
    one the digital twin answers by itself: naming the surface names a stretch of a
    plane the world describes. A direction from one of the board's own holes second,
    because it is the world's own vocabulary saying where on that surface to look. The
    colour last, because it narrows what is worth fitting rather than where to fit it,
    and so is the one narrowing a picture of the region cannot show on its own.

    *In front of* rather than *right of*, measured: on ``tracy_pickup_demo`` the cube
    stands 25 mm in front of the square hole and the cylinder 40 mm behind it, while
    both stand to the same side of it along the robot's own left-right axis. Which
    direction is stated is one word, and the two pieces are told apart by this one.

    :param world: The world holding the surfaces and holes the conditions name.
    :param board: The board as this look found it, which is what says where its holes
        are, or None where it was not in view.
    :return: One condition per step.
    """
    lid = Body(name=lid_surface().name)
    conditions = [lambda sought: SupportedBy(sought, lid)]
    if board is not None:
        square_hole = board_holes_in(world, board)[
            HOLE_NAME_BY_CATEGORY[MontessoriShapeCategory.CUBE]
        ]
        conditions.append(
            lambda sought: InFrontOf(
                sought,
                square_hole,
                HomogeneousTransformationMatrix.from_xyz_rpy(
                    reference_frame=world.root
                ),
            )
        )
    conditions.append(
        lambda sought: Colored(
            sought, KNOWN_PIECE_BY_CATEGORY[MontessoriShapeCategory.CUBE].color
        )
    )
    return tuple(conditions)


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
    narrowing = SearchNarrowing(
        pipeline=perception_pipeline(world),
        display=None if arguments.without_windows else OpenCvDisplay(),
    )
    frame = SceneCapture.load(arguments.capture, arguments.directory).to_frame()
    board = narrowing.board_in(frame)
    try:
        narrowing.watch(frame, conditions_over(world, board), board)
    finally:
        if narrowing.display is not None:
            narrowing.display.close()


if __name__ == "__main__":
    main()

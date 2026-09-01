"""
Watch a look narrow itself, one stated condition at a time.

Run it as::

    python -m experiments.montessori.perception.watch_narrowing

A statement is built up condition by condition, and after each one the picture that is
left to search is drawn: the camera's own image cut to it, and the rectified plane the
detectors would actually read. Each window is named by how the statement reads so far,
so what is on screen and what was asked for are the same sentence. Press any key to add
the next condition; press ``q`` or escape to stop.

Everything but the drawing is :class:`SearchNarrowing`, so a run with no window at all
takes the same steps and can be checked without a screen.
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

import numpy as np
from typing_extensions import Any, Callable, List, Optional, Sequence, Tuple

from experiments.montessori.perception.backend import MontessoriPerceptionBackend
from experiments.montessori.perception.camera import RgbdFrame
from experiments.montessori.perception.captures import CAPTURE_DIRECTORY, SceneCapture
from experiments.montessori.perception.orthophoto import WorkspaceRegion
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.perception.recorded_setup import (
    lid_surface,
    recorded_world,
    region_over,
    searched_workspace,
    perception_pipeline,
)
from experiments.montessori.perception.scene_request import SceneRequest
from experiments.montessori.perception.scene_source import FixedScene
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
    MontessoriScene,
    MontessoriShapeDetection,
)
from semantic_digital_twin.reasoning.predicates import InsideRegion, SupportedBy
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

    _backend: MontessoriPerceptionBackend = field(init=False)
    """
    Reads a statement, and gives the verbalization its *"Look for ..."* verb.
    """

    def __post_init__(self) -> None:
        self._backend = MontessoriPerceptionBackend(
            source=FixedScene(
                captured=MontessoriScene(shapes=[], board=None),
                reported_in=self.pipeline.reference_frame,
            )
        )

    def steps(
        self, frame: RgbdFrame, conditions: Sequence[StatedCondition]
    ) -> List[NarrowingStep]:
        """
        Take the statement from saying nothing to saying every condition in turn.

        :param frame: The camera data the look is taken from, which is what says where
            the board stands and so how far its lid reaches.
        :param conditions: The conditions to add, in the order they are stated.
        :return: One step for the bare statement and one for each condition added.
        """
        board = self.pipeline.board_detector.detect(
            self.pipeline.rectify(frame, self.pipeline.lid.height),
            self.pipeline.reference_frame,
        )
        statement = an(MontessoriShapeDetection)()
        taken = [self._step(statement, board)]
        for condition in conditions:
            statement = statement.where(condition(statement.variable))
            taken.append(self._step(statement, board))
        return taken

    def _step(
        self, statement: Any, board: Optional[MontessoriBoardDetection]
    ) -> NarrowingStep:
        """
        What one statement leaves a look to read.

        :param statement: The statement so far.
        :param board: The board as this frame showed it, which is what says how far its
            lid reaches.
        """
        request = self._backend.scene_request(self._backend.read_request(statement))
        searches = self.pipeline.searched_surfaces(board, request)
        return NarrowingStep(
            label=verbalize_expression(statement, backend=self._backend),
            request=request,
            region=searches[0].region if searches else None,
            plane_height=(
                searches[0].surface.height if searches else self.pipeline.table.height
            ),
        )

    def watch(
        self, frame: RgbdFrame, conditions: Sequence[StatedCondition]
    ) -> List[NarrowingStep]:
        """
        Take the steps, drawing each one and holding it until a key is pressed.

        :param frame: The camera data the look is taken from.
        :param conditions: The conditions to add, in the order they are stated.
        :return: The steps taken, however many of them were drawn.
        """
        taken = self.steps(frame, conditions)
        for step in taken:
            logger.info("%s -- %.3f m2 left to read", step.label, step.searched_area)
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
            (
                NarrowingView.RECTIFIED,
                self.pipeline.rectify(frame, step.plane_height, step.region).image,
            ),
        ):
            self.display.draw(self.window_name(view, step), self._fitted(picture))

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


def conditions_over(world: World) -> Tuple[StatedCondition, ...]:
    """
    The conditions the demonstration adds, each narrowing what is left of the one
    before.

    Support first, because it is the narrowing the request language already had and the
    one the digital twin answers by itself: naming the surface names a stretch of a
    plane the world describes. Containment second, because it is extents said outright,
    and it cuts down what support left.

    :param world: The world holding the surfaces and regions the conditions name.
    :return: One condition per step.
    """
    lid = Body(name=lid_surface().name)
    near_the_board = region_over(
        world, _half_the_table_nearest_the_robot(), "near_half"
    )
    return (
        lambda sought: SupportedBy(sought, lid),
        lambda sought: InsideRegion(sought, near_the_board),
    )


def _half_the_table_nearest_the_robot() -> WorkspaceRegion:
    """
    The half of the searched table closest to the world frame's origin along y.

    Nothing measures this: it is a stretch chosen so a second condition visibly cuts
    into what the first one left.
    """
    searched = searched_workspace()
    return WorkspaceRegion(
        minimum_x=searched.minimum_x,
        maximum_x=searched.maximum_x,
        minimum_y=searched.minimum_y,
        maximum_y=(searched.minimum_y + searched.maximum_y) / 2,
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
    narrowing = SearchNarrowing(
        pipeline=perception_pipeline(world),
        display=None if arguments.without_windows else OpenCvDisplay(),
    )
    capture = SceneCapture.load(arguments.capture, arguments.directory)
    try:
        narrowing.watch(capture.to_frame(), conditions_over(world))
    finally:
        if narrowing.display is not None:
            narrowing.display.close()


if __name__ == "__main__":
    main()

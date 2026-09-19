"""
The probabilistic backend answering the open approach direction, watched sampling.

The plan states the grasp comes from above and leaves open which side of the cube the
hand faces. The backend asks its model registry for a model over what is left open,
draws samples from it, sorts them by likelihood and hands the plan the first. The scene
shows what the model says of each option, the samples arriving, and which option the
run went with, drawn on the robot's own picture of the cube.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property

import cv2
import numpy as np
from typing_extensions import Dict, List, Optional, Tuple

from coraplex.datastructures.enums import ApproachDirection
from coraplex.datastructures.grasp import GraspDescription
from experiments.montessori.perception.overlay import project_to_pixels
from experiments.open_slots.plan import FROM_ABOVE
from experiments.paper.lettering import Face
from experiments.video.canvas import (
    Anchor,
    Area,
    Ink,
    Typesetting,
    filled,
    fitted,
)
from experiments.video.sources import RecordedRun
from experiments.video.timeline import Frame, Resolution, Scene, eased
from krrood.entity_query_language.backends import ProbabilisticBackend
from krrood.entity_query_language.factories import a
from krrood.parametrization.parameterizer import UnderspecifiedParameters

CLOSE_UP = Resolution(width=1600, height=900)
"""
The size the scene draws itself at.
"""

STATEMENT = (
    "a(GraspDescription)(approach_direction=..., vertical_alignment=TOP, end_effector=LEFT_HAND)"
)
"""
The open slot, as the plan writes it.
"""

# %% what the backend does


@dataclass
class GraspSampling:
    """
    The backend's answer to the open approach direction, taken the way the backend
    takes it, with the model's own probabilities kept beside the samples.
    """

    answered: ApproachDirection
    """
    The direction the run actually went with, as the recorded pick-up states it.
    """

    backend: ProbabilisticBackend = field(default_factory=ProbabilisticBackend)
    """
    The backend, with the registry the run used.
    """

    @cached_property
    def statement(self):
        """
        The grasp with its approach direction left open, as the plan states it.
        """
        return a(GraspDescription)(
            approach_direction=..., vertical_alignment=FROM_ABOVE, end_effector=None
        )

    @cached_property
    def probabilities(self) -> Dict[ApproachDirection, float]:
        """
        What the model gives each direction, read off the model itself.
        """
        parameters = UnderspecifiedParameters(self.statement)
        model = parameters.resolve_conditioned_and_truncated_model(
            self.backend.model_registry.get_model(parameters)
        )
        # a sample carries each symbolic value as its index among the enumeration's members
        [approach, alignment] = model.variables
        directions = list(approach.domain.simple_set_example.all_elements)
        alignments = list(alignment.domain.simple_set_example.all_elements)
        rows = np.array(
            [
                [directions.index(direction), alignments.index(FROM_ABOVE)]
                for direction in directions
            ],
            dtype=float,
        )
        likelihoods = np.exp(model.log_likelihood(rows))
        return {
            direction: float(likelihood)
            for direction, likelihood in zip(directions, likelihoods)
        }

    @cached_property
    def samples(self) -> List[ApproachDirection]:
        """
        One draw of the backend's samples, in the order it hands them on.
        """
        return [
            grasp.approach_direction for grasp in self.statement.evaluate(backend=self.backend)
        ]

    def tally(self, count: int) -> Dict[ApproachDirection, int]:
        """
        How many of the first samples fell on each direction.

        :param count: How many samples have arrived.
        """
        counted = {direction: 0 for direction in self.probabilities}
        for direction in self.samples[:count]:
            counted[direction] += 1
        return counted


# %% the grasp options on the robot's picture


@dataclass
class GraspOptionsOnThePicture:
    """
    The four approach directions drawn as arrows onto the robot's own picture of the
    cube, each arrow pointing the way the hand would move.
    """

    run: RecordedRun
    """
    The run, whose first camera frame is drawn on.
    """

    cube_at: np.ndarray
    """
    Where the cube stands in the world root frame, at its top.
    """

    reach: float = 0.075
    """
    How far from the cube's centre each arrow starts, in metres.
    """

    @cached_property
    def frame(self):
        return self.run.frame(0)

    def arrow(self, direction: ApproachDirection) -> Tuple[np.ndarray, np.ndarray]:
        """
        Where an arrow for a direction starts and ends, in the picture's pixels.
        """
        axis = np.array(direction.axis.value, dtype=float)
        motion = axis * direction.value[1]
        tail = self.cube_at[:2] - motion[:2] * self.reach
        head = self.cube_at[:2] - motion[:2] * self.reach * 0.35
        pixels = project_to_pixels(
            self.frame, np.array([tail, head]), float(self.cube_at[2])
        )
        return pixels[0], pixels[1]

    def crop(self) -> Area:
        """
        The stretch of the picture around the cube and its arrows.
        """
        [centre] = project_to_pixels(
            self.frame, self.cube_at[:2].reshape(1, 2), float(self.cube_at[2])
        )
        ends = np.array([end for direction in ApproachDirection for end in self.arrow(direction)])
        radius = float(np.abs(ends - centre).max()) * 1.9
        return Area(centre[0] - radius, centre[1] - radius, 2 * radius, 2 * radius)

    def drawn(self, highlighted: Optional[ApproachDirection], weight: float) -> Frame:
        """
        The picture with the arrows on it, cropped around the cube.

        :param highlighted: The direction drawn strong, or None for all alike.
        :param weight: How strongly the highlight shows, from zero to one.
        """
        picture = cv2.cvtColor(self.frame.color, cv2.COLOR_BGR2RGB).copy()
        for direction in ApproachDirection:
            tail, head = self.arrow(direction)
            strong = direction is highlighted
            color = Ink.PROBABILISTIC.rgb if strong or highlighted is None else Ink.MUTED.rgb
            cv2.arrowedLine(
                picture,
                tuple(tail.round().astype(int)),
                tuple(head.round().astype(int)),
                color,
                4 if strong else 2,
                cv2.LINE_AA,
                tipLength=0.35,
            )
            # the name sits just beyond the arrow's tail, clear of the arrow itself
            beyond = tail + (tail - head) * 0.5
            (text_width, text_height), _ = cv2.getTextSize(direction.name, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
            cv2.putText(
                picture,
                direction.name,
                (int(beyond[0] - text_width / 2), int(beyond[1] + text_height / 2)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                color,
                2,
                cv2.LINE_AA,
            )
        left, top, width, height = self.crop().rounded()
        left, top = max(left, 0), max(top, 0)
        return picture[top : top + height, left : left + width]


# %% the scene


@dataclass
class GraspDistribution(Scene):
    """
    The bars of the model's distribution over the four directions, samples arriving
    into a tally under them, and the direction the run took, pointed out on the cube.
    """

    sampling: GraspSampling
    """
    What the backend did.
    """

    options: GraspOptionsOnThePicture
    """
    The four directions on the robot's picture.
    """

    statement_for: float = 2.0
    """
    Seconds the statement alone is shown before sampling starts.
    """

    sampling_for: float = 7.0
    """
    Seconds the samples take to arrive.
    """

    answer_for: float = 5.0
    """
    Seconds the run's answer is pointed out at the end.
    """

    resolution: Resolution = CLOSE_UP
    """
    The size the scene draws itself at.
    """

    @property
    def duration(self) -> float:
        return self.statement_for + self.sampling_for + self.answer_for

    def arrived_at(self, seconds: float) -> int:
        """
        How many samples have arrived by a moment.
        """
        progress = (seconds - self.statement_for) / self.sampling_for
        return int(round(min(max(progress, 0.0), 1.0) * len(self.sampling.samples)))

    def picture_at(self, seconds: float) -> Frame:
        frame = self.resolution.blank(255)
        frame = Typesetting(size=26, face=Face.BOLD, color=Ink.PROBABILISTIC.rgb).written(
            frame, STATEMENT, (40, 40), Anchor.LEFT_MIDDLE
        )
        arrived = self.arrived_at(seconds)
        answering = seconds >= self.statement_for + self.sampling_for
        frame = self._chart(frame, arrived, answering)
        highlighted = self.sampling.answered if answering else None
        weight = eased((seconds - self.statement_for - self.sampling_for) / 0.8) if answering else 0.0
        picture = self.options.drawn(highlighted, weight)
        frame = fitted(frame, picture, Area(940, 90, 620, 620))
        frame = Typesetting(size=22, color=Ink.MUTED.rgb).written(
            frame, "the four options on the robot's own picture of the cube", (1250, 740), Anchor.CENTRE_MIDDLE
        )
        caption = "the model over what the plan left open, asked from the backend's registry"
        if arrived > 0:
            caption = f"{arrived} of {len(self.sampling.samples)} samples drawn, sorted by likelihood"
        if answering:
            caption = f"every option equally likely under this model; this run's draw: {self.sampling.answered.name}"
        return Typesetting(size=28, color=Ink.TEXT.rgb).written(
            frame, caption, (self.resolution.width / 2, self.resolution.height - 40), Anchor.CENTRE_MIDDLE
        )

    def _chart(self, frame: Frame, arrived: int, answering: bool) -> Frame:
        left, top, width, height = 80, 120, 780, 620
        base = top + height - 70
        probabilities = self.sampling.probabilities
        tally = self.sampling.tally(arrived)
        slot = width / len(probabilities)
        bar = slot * 0.5
        # a share of half the samples reaches the top; the first few samples' shares are wilder and are clipped
        top_scale = (base - top) / 0.5
        label = Typesetting(size=24, face=Face.BOLD, color=Ink.TEXT.rgb)
        small = Typesetting(size=22, color=Ink.MUTED.rgb)
        frame = filled(frame, Area(left, base, width, 2), Ink.HAIRLINE.rgb)
        for number, (direction, probability) in enumerate(probabilities.items()):
            x = left + number * slot + (slot - bar) / 2
            # the model's own probability, as a hollow bar
            model_height = probability * top_scale
            frame = filled(frame, Area(x, base - model_height, bar, model_height), Ink.PROBABILISTIC_FILL.rgb)
            # the tally of samples so far, filling it in
            share = tally[direction] / max(arrived, 1) if arrived else 0.0
            sample_height = min(share * top_scale, base - top)
            strong = answering and direction is self.sampling.answered
            frame = filled(frame, Area(x, base - sample_height, bar, sample_height), Ink.PROBABILISTIC.rgb if strong or not answering else Ink.MUTED.rgb)
            frame = label.written(frame, direction.name, (x + bar / 2, base + 24), Anchor.CENTRE_MIDDLE)
            frame = small.written(frame, f"P = {probability:.2f}", (x + bar / 2, base - model_height - 18), Anchor.CENTRE_MIDDLE)
            if arrived:
                frame = small.written(frame, f"{tally[direction]}", (x + bar / 2, base + 52), Anchor.CENTRE_MIDDLE)
        frame = small.written(frame, "bar: the model's probability   ·   filled: share of the samples so far", (left, top - 20), Anchor.LEFT_MIDDLE)
        return frame

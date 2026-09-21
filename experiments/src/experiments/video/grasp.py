"""
The probabilistic backend answering the open approach direction, watched sampling.

The plan states the grasp comes from above and leaves open which side of the cube the
hand faces. The backend asks its model registry for a model over what is left open,
draws samples from it, sorts them by likelihood and hands the plan the first. The scene
shows what the model says of each option, the samples arriving, and which option the
run went with.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property

import numpy as np
from typing_extensions import Dict, List

from coraplex.datastructures.enums import ApproachDirection
from coraplex.datastructures.grasp import GraspDescription
from experiments.montessori.perception.overlay import project_to_pixels
from experiments.open_slots.plan import FROM_ABOVE
from experiments.paper.lettering import Face
from experiments.video.canvas import (
    BODY_SIZE,
    LABEL_SIZE,
    Anchor,
    Area,
    Ink,
    Typesetting,
    filled,
)
from experiments.video.stages import PANEL_VISUAL
from experiments.video.timeline import Frame, Resolution, Scene
from krrood.entity_query_language.backends import ProbabilisticBackend
from krrood.entity_query_language.factories import a
from krrood.parametrization.model_registries import ModelRegistry
from krrood.parametrization.parameterizer import (
    ModelQueryParameters,
    UnderspecifiedParameters,
)
from probabilistic_model.probabilistic_circuit.rx.helper import fully_factorized
from probabilistic_model.probabilistic_circuit.rx.probabilistic_circuit import (
    ProbabilisticCircuit,
)
from probabilistic_model.utils import MissingDict

# %% the prior over the approach

APPROACH_ATTRIBUTE = "GraspDescription.approach_direction"
"""
How the parameterizer names the variable of the approach direction.
"""


@dataclass
class ApproachPrior(ModelRegistry):
    """
    A registry whose model favours some approach directions over others.

    The backend's default registry hands out a uniform model, under which every direction
    is as likely as the next and the first sample wins. This one keeps that model for
    everything but the approach direction, and gives the approach the distribution stated
    here, so the direction the robot goes with is the one the prior favours.
    """

    probabilities: Dict[ApproachDirection, float]
    """
    The probability given to each direction; they are normalised before use, and a
    direction left out gets nothing.
    """

    @classmethod
    def favouring(cls, direction: ApproachDirection, share: float = 0.55) -> ApproachPrior:
        """
        A prior that gives one direction a share of the probability and splits the rest
        evenly among the others.

        :param direction: The direction favoured.
        :param share: How much of the probability it gets.
        """
        others = [other for other in ApproachDirection if other is not direction]
        probabilities = {other: (1.0 - share) / len(others) for other in others}
        probabilities[direction] = share
        return cls(probabilities)

    @property
    def favoured(self) -> ApproachDirection:
        """
        The direction given the most probability.
        """
        return max(self.probabilities, key=self.probabilities.get)

    def get_model(self, parameters: ModelQueryParameters) -> ProbabilisticCircuit:
        circuit = fully_factorized(parameters.variables.values())
        for leaf in circuit.leaves:
            if leaf.variable.name == APPROACH_ATTRIBUTE:
                leaf.distribution.probabilities = self._probabilities_of(leaf.variable)
        return circuit

    def _probabilities_of(self, variable) -> MissingDict:
        """
        The stated distribution, keyed the way the leaf keys its own.

        :param variable: The approach variable, whose domain lists the directions in the
            same order as the members of the enumeration.
        """
        total = sum(self.probabilities.values())
        elements = variable.domain.simple_sets
        directions = variable.domain.simple_set_example.all_elements
        return MissingDict(
            float,
            {
                hash(element): self.probabilities.get(direction, 0.0) / total
                for element, direction in zip(elements, directions)
            },
        )


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
class GraspDistribution(Scene):
    """
    The bars of the model's distribution over the four directions, samples arriving
    into them, and the direction handed to the plan standing out at the end.
    """

    sampling: GraspSampling
    """
    What the backend did.
    """

    statement_for: float = 2.0
    """
    Seconds the model's bars alone are shown before sampling starts.
    """

    sampling_for: float = 7.0
    """
    Seconds the samples take to arrive.
    """

    answer_for: float = 5.0
    """
    Seconds the run's answer stands out at the end.
    """

    resolution: Resolution = PANEL_VISUAL
    """
    The size the scene draws itself at.
    """

    @property
    def duration(self) -> float:
        return self.statement_for + self.sampling_for + self.answer_for

    @property
    def answers_at(self) -> float:
        """
        Seconds into the scene the answer stands out.
        """
        return self.statement_for + self.sampling_for

    def arrived_at(self, seconds: float) -> int:
        """
        How many samples have arrived by a moment.
        """
        progress = (seconds - self.statement_for) / self.sampling_for
        return int(round(min(max(progress, 0.0), 1.0) * len(self.sampling.samples)))

    def picture_at(self, seconds: float) -> Frame:
        frame = self.resolution.blank(255)
        return self._chart(frame, self.arrived_at(seconds), seconds >= self.answers_at)

    def _chart(self, frame: Frame, arrived: int, answering: bool) -> Frame:
        """
        One bar per direction: the model's probability pale, the share of the samples
        so far filling it in, the direction named under it and its probability over it;
        once answered, the direction handed to the plan keeps its colour and the others
        go grey.
        """
        left, top, width, height = 40, 24, self.resolution.width - 80, self.resolution.height - 24
        base = top + height - 70
        probabilities = self.sampling.probabilities
        tally = self.sampling.tally(arrived)
        slot = width / len(probabilities)
        bar = slot * 0.5
        # the tallest model bar, or a share of half the samples, reaches the top; the
        # first few samples' shares are wilder and are clipped
        top_scale = (base - top - 30) / max(0.7, max(probabilities.values()) * 1.25)
        label = Typesetting(size=BODY_SIZE, face=Face.BOLD, color=Ink.TEXT.rgb)
        small = Typesetting(size=LABEL_SIZE, color=Ink.MUTED.rgb)
        frame = filled(frame, Area(left, base, width, 2), Ink.HAIRLINE.rgb)
        for number, (direction, probability) in enumerate(probabilities.items()):
            x = left + number * slot + (slot - bar) / 2
            model_height = probability * top_scale
            frame = filled(frame, Area(x, base - model_height, bar, model_height), Ink.PROBABILISTIC_FILL.rgb)
            share = tally[direction] / max(arrived, 1) if arrived else 0.0
            sample_height = min(share * top_scale, base - top)
            strong = answering and direction is self.sampling.answered
            frame = filled(frame, Area(x, base - sample_height, bar, sample_height), Ink.PROBABILISTIC.rgb if strong or not answering else Ink.HAIRLINE.rgb)
            named = Typesetting(size=BODY_SIZE, face=Face.BOLD, color=Ink.PROBABILISTIC.rgb if strong else Ink.TEXT.rgb)
            frame = named.written(frame, direction.name, (x + bar / 2, base + 22), Anchor.CENTRE_MIDDLE)
            frame = small.written(frame, f"{probability:.2f}", (x + bar / 2, base - max(model_height, sample_height) - 16), Anchor.CENTRE_MIDDLE)
            if arrived:
                frame = small.written(frame, f"{tally[direction]} of {arrived}", (x + bar / 2, base + 50), Anchor.CENTRE_MIDDLE)
        return frame

"""
Tests for the prior over the approach direction: the backend's model carries the stated
probabilities, its samples are handed on with the favoured direction first, and the
tally of the samples leans the prior's way.
"""

from __future__ import annotations

import pytest

from coraplex.datastructures.enums import ApproachDirection
from experiments.video.grasp import ApproachPrior, GraspSampling
from krrood.entity_query_language.backends import ProbabilisticBackend

FAVOURING_LEFT = {
    ApproachDirection.LEFT: 0.55,
    ApproachDirection.FRONT: 0.25,
    ApproachDirection.RIGHT: 0.12,
    ApproachDirection.BACK: 0.08,
}


@pytest.fixture
def sampling() -> GraspSampling:
    return GraspSampling(
        answered=ApproachDirection.LEFT,
        backend=ProbabilisticBackend(ApproachPrior(FAVOURING_LEFT)),
    )


def test_the_model_carries_the_stated_probabilities(sampling: GraspSampling) -> None:
    for direction, probability in FAVOURING_LEFT.items():
        assert sampling.probabilities[direction] == pytest.approx(probability)


def test_the_first_sample_handed_on_is_the_favoured_direction(sampling: GraspSampling) -> None:
    assert sampling.samples[0] is ApproachDirection.LEFT


def test_the_tally_leans_the_priors_way(sampling: GraspSampling) -> None:
    tally = sampling.tally(len(sampling.samples))
    assert sum(tally.values()) == len(sampling.samples)
    assert max(tally, key=tally.get) is ApproachDirection.LEFT


def test_probabilities_are_normalised() -> None:
    sampling = GraspSampling(
        answered=ApproachDirection.BACK,
        backend=ProbabilisticBackend(
            ApproachPrior({ApproachDirection.BACK: 3.0, ApproachDirection.FRONT: 1.0})
        ),
    )
    assert sampling.probabilities[ApproachDirection.BACK] == pytest.approx(0.75)
    assert sampling.probabilities[ApproachDirection.FRONT] == pytest.approx(0.25)
    assert sampling.probabilities[ApproachDirection.LEFT] == pytest.approx(0.0)

"""
Validation of causal-query grounding against the CTU Mutagenesis dataset
(https://relational.fel.cvut.cz/dataset/Mutagenesis), covering plan step 5:
registering chlorine count as a cause of mutagenicity and comparing naive
conditioning against backdoor adjustment.
"""

from __future__ import annotations

import pytest

from experiments.causal_reasoning.mutagenesis.causal_query import (
    ChlorineCountCausalQuery,
)
from experiments.causal_reasoning.mutagenesis.dataset import (
    fetch_mutagenesis_molecules,
    is_mutagenesis_dataset_reachable,
)

requires_mutagenesis_dataset = pytest.mark.skipif(
    not is_mutagenesis_dataset_reachable(),
    reason="CTU relational-dataset repository is not reachable from this environment",
)


@pytest.fixture(scope="module")
def causal_query_result():
    molecules = fetch_mutagenesis_molecules()
    return ChlorineCountCausalQuery().run(molecules, atom_count=2)


@requires_mutagenesis_dataset
def test_causal_circuit_is_support_deterministic(causal_query_result):
    assert causal_query_result.support_determinism_verified


@requires_mutagenesis_dataset
def test_every_distinct_chlorine_count_is_reported(causal_query_result):
    """
    ``mutagenesis_188`` has molecules with chlorine counts 0 through 5 (chlorine is
    rare: 177 of 188 molecules have none). All six must survive grounding and
    registration, not just the dominant one.
    """
    reported_counts = [effect.chlorine_count for effect in causal_query_result.effects]
    assert reported_counts == sorted(reported_counts)
    assert len(reported_counts) == len(set(reported_counts))
    assert reported_counts == [0, 1, 2, 3, 4, 5]


@requires_mutagenesis_dataset
def test_region_probabilities_sum_to_one(causal_query_result):
    total = sum(effect.region_probability for effect in causal_query_result.effects)
    assert total == pytest.approx(1.0, abs=0.01)


@requires_mutagenesis_dataset
def test_effect_probabilities_are_valid_probabilities(causal_query_result):
    for effect in causal_query_result.effects:
        assert 0.0 <= effect.naive_probability_mutagenic <= 1.0
        assert 0.0 <= effect.adjusted_probability_mutagenic <= 1.0

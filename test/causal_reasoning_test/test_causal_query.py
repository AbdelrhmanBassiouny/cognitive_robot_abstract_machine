"""
Validation of causal-query grounding against the CTU Mutagenesis dataset
(https://relational.fel.cvut.cz/dataset/Mutagenesis), covering plan step 5:
registering chlorine count as a cause of mutagenicity and comparing naive
conditioning against backdoor adjustment.
"""

from __future__ import annotations

import numpy as np
import pytest

from experiments.causal_reasoning.mutagenesis.causal_query import (
    run_chlorine_count_backdoor_adjustment,
)
from experiments.causal_reasoning.mutagenesis.dataset import (
    fetch_mutagenesis_molecules,
    is_mutagenesis_dataset_reachable,
    molecules_with_distinct_chlorine_counts,
)

requires_mutagenesis_dataset = pytest.mark.skipif(
    not is_mutagenesis_dataset_reachable(),
    reason="CTU relational-dataset repository is not reachable from this environment",
)


@pytest.fixture(scope="module")
def causal_query_result():
    molecules = fetch_mutagenesis_molecules()
    training_molecules = molecules_with_distinct_chlorine_counts(
        molecules, np.random.default_rng(0)
    )
    return run_chlorine_count_backdoor_adjustment(training_molecules, atom_count=2)


@requires_mutagenesis_dataset
def test_causal_circuit_is_support_deterministic(causal_query_result):
    assert causal_query_result.support_determinism_verified


@requires_mutagenesis_dataset
def test_every_selected_chlorine_count_is_reported(causal_query_result):
    reported_counts = [effect.chlorine_count for effect in causal_query_result.effects]
    assert reported_counts == sorted(reported_counts)
    assert len(reported_counts) == len(set(reported_counts))
    assert len(reported_counts) == causal_query_result.training_molecule_count


@requires_mutagenesis_dataset
def test_effect_probabilities_are_valid_probabilities(causal_query_result):
    for effect in causal_query_result.effects:
        assert 0.0 <= effect.naive_probability_mutagenic <= 1.0
        assert 0.0 <= effect.adjusted_probability_mutagenic <= 1.0

"""
Validation of causal-query grounding against the CTU Mutagenesis dataset
(https://relational.fel.cvut.cz/dataset/Mutagenesis), covering plan step 5:
registering branching-atom count as a cause of mutagenicity and comparing naive
conditioning against backdoor adjustment.
"""

from __future__ import annotations

import numpy as np
import pytest

from experiments.causal_reasoning.mutagenesis.causal_query import (
    BranchingAtomCountCausalQuery,
)
from experiments.causal_reasoning.mutagenesis.dataset import (
    fetch_mutagenesis_molecules,
    is_mutagenesis_dataset_reachable,
    synthetic_mutagenesis_molecules,
)
from experiments.causal_reasoning.mutagenesis.domain import (
    MutagenesisMoleculeAggregations,
)

requires_mutagenesis_dataset = pytest.mark.skipif(
    not is_mutagenesis_dataset_reachable(),
    reason="CTU relational-dataset repository is not reachable from this environment",
)


# %% synthetic-data pipeline (no network access, runs in CI)


def test_synthetic_causal_circuit_is_support_deterministic():
    """
    Regression test, paired with the live-dataset tests below: stratifying the class
    circuit by branching-atom count used to fail support-determinism verification once a
    partition was large and varied enough for JointProbabilityTree to split it further
    on other variables, because both grounding and verification computed marginals
    through a path that flattens nested SumUnits and erases which partition a further-
    split branch actually belongs to.
    """
    molecules = synthetic_mutagenesis_molecules(
        np.random.default_rng(0), molecule_count=60, atom_count=3, bond_count=4
    )
    result = BranchingAtomCountCausalQuery().run(molecules, atom_count=2, bond_count=1)
    assert result.support_determinism_verified


# %% live-dataset pipeline (real CTU Mutagenesis data, skipped without network access)


@pytest.fixture(scope="module")
def mutagenesis_molecules():
    return fetch_mutagenesis_molecules()


@pytest.fixture(scope="module")
def causal_query_result(mutagenesis_molecules):
    return BranchingAtomCountCausalQuery().run(mutagenesis_molecules, atom_count=2)


@requires_mutagenesis_dataset
def test_causal_circuit_is_support_deterministic(causal_query_result):
    assert causal_query_result.support_determinism_verified


@requires_mutagenesis_dataset
def test_every_distinct_branching_atom_count_is_reported(
    causal_query_result, mutagenesis_molecules
):
    """
    Every distinct branching-atom-count value present in the training population must
    survive grounding and registration, not just the dominant one.
    """
    expected_counts = sorted(
        {
            MutagenesisMoleculeAggregations(instance=molecule).branching_atom_count()
            for molecule in mutagenesis_molecules
        }
    )
    reported_counts = [
        effect.branching_atom_count for effect in causal_query_result.effects
    ]
    assert reported_counts == sorted(reported_counts)
    assert len(reported_counts) == len(set(reported_counts))
    assert reported_counts == expected_counts


@requires_mutagenesis_dataset
def test_region_probabilities_sum_to_one(causal_query_result):
    total = sum(effect.region_probability for effect in causal_query_result.effects)
    assert total == pytest.approx(1.0, abs=0.01)


@requires_mutagenesis_dataset
def test_effect_probabilities_are_valid_probabilities(causal_query_result):
    for effect in causal_query_result.effects:
        assert 0.0 <= effect.naive_probability_mutagenic <= 1.0
        assert 0.0 <= effect.adjusted_probability_mutagenic <= 1.0

"""
Registering the Mutagenesis dataset's chlorine count as a cause of mutagenicity and
running backdoor adjustment on the grounded circuit.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from krrood.entity_query_language.factories import a, variable
from krrood.ormatic.data_access_objects.helper import to_dao
from random_events.product_algebra import SimpleEvent
from typing_extensions import List

from experiments.causal_reasoning.mutagenesis.domain import (
    MutagenesisAtom,
    MutagenesisBond,
    MutagenesisMolecule,
    MutagenesisMoleculeAggregations,
)
from probabilistic_model.probabilistic_circuit.relational.causal import (
    RelationalCausalCircuit,
)
from probabilistic_model.probabilistic_circuit.relational.rspn import (
    RelationalProbabilisticCircuit,
)

CHLORINE_COUNT_VARIABLE = variable(MutagenesisMoleculeAggregations).chlorine_count()
"""
EQL attribute-access expression naming the chlorine-count cause variable.
"""

MUTAGENIC_VARIABLE = variable(MutagenesisMolecule).mutagenic
"""
EQL attribute-access expression naming the mutagenicity effect variable.
"""

INDICATOR_1_VARIABLE = variable(MutagenesisMolecule).indicator_1
"""
EQL attribute-access expression naming the ``ind1`` structural-indicator adjustment
variable.
"""


@dataclass(frozen=True)
class ChlorineCountCausalEffect:
    """
    The naive and backdoor-adjusted probability of mutagenicity at one chlorine-count
    value.
    """

    chlorine_count: int
    """
    The chlorine-count value this row reports on.
    """

    region_probability: float
    """
    ``P(chlorine_count)`` under the fitted circuit -- the share of the training
    population this value accounts for.
    """

    naive_probability_mutagenic: float
    """
    ``P(mutagenic = True | chlorine_count)``, read directly off the grounded circuit
    with no adjustment.
    """

    adjusted_probability_mutagenic: float
    """
    ``P(mutagenic = True | do(chlorine_count))``, backdoor-adjusted for
    :data:`INDICATOR_1_VARIABLE`.
    """


@dataclass
class MutagenesisCausalQueryResult:
    """
    Everything a run of :func:`run_chlorine_count_backdoor_adjustment` produced.
    """

    training_molecule_count: int
    """
    Number of molecules the circuit was fitted on.
    """

    atom_count: int
    """
    Number of atoms the grounding query specified.
    """

    bond_count: int
    """
    Number of bonds the grounding query specified.
    """

    support_determinism_verified: bool
    """
    Whether verify_support_determinism passed on the grounded circuit.
    """

    effects: List[ChlorineCountCausalEffect] = field(default_factory=list)
    """
    One row per chlorine-count value the grounded circuit's support covers.
    """


def _build_query(atom_count: int, bond_count: int):
    """
    Build a molecule query with a fixed atom and bond count, every atom's element and
    every bond's type left unspecified, so grounding must retain chlorine count as an
    undetermined latent.

    :param atom_count: Number of atoms the query specifies.
    :param bond_count: Number of bonds the query specifies.
    :return: The resolved query.
    """
    query = a(MutagenesisMolecule)(
        indicator_1=...,
        logp=...,
        lumo=...,
        mutagenic=...,
        atoms=[
            a(MutagenesisAtom)(element=..., atom_type=..., charge=...)
            for _ in range(atom_count)
        ],
        bonds=[a(MutagenesisBond)(bond_type=...) for _ in range(bond_count)],
    )
    query.resolve()
    return query


def run_chlorine_count_backdoor_adjustment(
    training_molecules: List[MutagenesisMolecule],
    atom_count: int = 2,
    bond_count: int = 1,
    random_seed: int = 0,
    monte_carlo_sample_count: int = 2000,
) -> MutagenesisCausalQueryResult:
    """
    Fit a relational circuit, register chlorine count as a cause of mutagenicity, and
    compare naive conditioning against backdoor adjustment for the structural indicator
    ``ind1``.

    Fits the class circuit stratified by chlorine count (``stratify_class_circuit_by``):
    a plain, unconstrained fit gives no guarantee that training rows sharing a chlorine-
    count value end up under one circuit branch, and
    `CausalCircuit.verify_support_determinism` rejects the registration when they do not
    (two branches would then each claim the same value). Stratifying partitions the
    training dataframe by that exact value before fitting, so every value's rows share
    one branch by construction, on the full dataset without subsampling it down to one
    row per value.

    :param training_molecules: Molecules to fit the circuit on.
    :param atom_count: Number of atoms the grounding query specifies; every atom's
        element is left unspecified, so chlorine count stays undetermined and is
        retained rather than integrated out.
    :param bond_count: Number of bonds the grounding query specifies; every bond's type
        is left unspecified.
    :param random_seed: Seed applied to the global NumPy random state before grounding,
        which draws the Monte-Carlo samples that retain chlorine count. Fixing it keeps
        the result reproducible across runs.
    :param monte_carlo_sample_count: Number of Monte-Carlo samples grounding draws when
        retaining chlorine count. Chlorine is rare in the Mutagenesis dataset (about one
        atom in ninety), so the default is set well above what a small sample count
        would reliably catch: at the default JPT sample count of 10, a value observed in
        only 1 of 188 training molecules has better than a 99% chance of never being
        drawn at all, whereas 2000 draws drops that miss chance under 1% for every
        observed value (see ``causal_query_results.md`` for the derivation).
    :return: The fitted result, including one causal-effect row per chlorine-count value
        the grounded circuit's support covers.
    """
    model = RelationalProbabilisticCircuit(MutagenesisMolecule)
    model.monte_carlo_sample_count = monte_carlo_sample_count
    model.fit(
        [to_dao(molecule) for molecule in training_molecules],
        stratify_class_circuit_by=CHLORINE_COUNT_VARIABLE,
    )

    query = _build_query(atom_count, bond_count)
    np.random.seed(random_seed)
    grounded_circuit = model.ground(query)

    relational_causal_circuit = RelationalCausalCircuit()
    causal_circuit = relational_causal_circuit.from_grounded_circuit(
        grounded_circuit,
        causal_variables=[CHLORINE_COUNT_VARIABLE],
        effect_variables=[MUTAGENIC_VARIABLE],
        adjustment_variables=[INDICATOR_1_VARIABLE],
        trim_to_registered_variables=True,
    )

    probabilistic_circuit = causal_circuit.probabilistic_circuit
    chlorine_count_variable = RelationalCausalCircuit.resolve_variable(
        probabilistic_circuit, CHLORINE_COUNT_VARIABLE
    )
    mutagenic_variable = RelationalCausalCircuit.resolve_variable(
        probabilistic_circuit, MUTAGENIC_VARIABLE
    )
    indicator_1_variable = RelationalCausalCircuit.resolve_variable(
        probabilistic_circuit, INDICATOR_1_VARIABLE
    )

    naive_circuit = causal_circuit.backdoor_adjustment(
        chlorine_count_variable, mutagenic_variable
    )
    adjusted_circuit = causal_circuit.backdoor_adjustment(
        chlorine_count_variable,
        mutagenic_variable,
        adjustment_variables=[indicator_1_variable],
    )

    chlorine_count_regions = causal_circuit._extract_disjoint_regions_for_variable(
        chlorine_count_variable
    )
    regions_by_value = {
        int(
            region.event.simple_sets[0][chlorine_count_variable].simple_sets[0].lower
        ): region
        for region in chlorine_count_regions
    }

    effects = [
        ChlorineCountCausalEffect(
            chlorine_count=value,
            region_probability=region.probability,
            naive_probability_mutagenic=_probability_mutagenic_at(
                naive_circuit, chlorine_count_variable, mutagenic_variable, value
            ),
            adjusted_probability_mutagenic=_probability_mutagenic_at(
                adjusted_circuit, chlorine_count_variable, mutagenic_variable, value
            ),
        )
        for value, region in sorted(regions_by_value.items())
    ]

    return MutagenesisCausalQueryResult(
        training_molecule_count=len(training_molecules),
        atom_count=atom_count,
        bond_count=bond_count,
        support_determinism_verified=True,
        effects=effects,
    )


def _probability_mutagenic_at(
    interventional_circuit,
    chlorine_count_variable,
    mutagenic_variable,
    chlorine_count_value: int,
) -> float:
    """
    Read ``P(mutagenic = True)`` off ``interventional_circuit`` at one chlorine-count
    value.

    :param interventional_circuit: A joint circuit over (chlorine count, mutagenic),
        as returned by :meth:`~probabilistic_model.probabilistic_circuit.causal.causal_circuit.CausalCircuit.backdoor_adjustment`.
    :param chlorine_count_variable: The chlorine-count Variable.
    :param mutagenic_variable: The mutagenicity Variable.
    :param chlorine_count_value: The chlorine-count value to truncate to.
    :return: The truncated circuit's probability that ``mutagenic`` is ``True``.
    """
    event = SimpleEvent.from_data(
        {chlorine_count_variable: float(chlorine_count_value)}
    ).as_composite_set()
    truncated_circuit, _ = interventional_circuit.truncated(
        event.fill_missing_variables_pure(interventional_circuit.variables)
    )
    true_event = (
        SimpleEvent.from_data({mutagenic_variable: True})
        .as_composite_set()
        .fill_missing_variables_pure(truncated_circuit.variables)
    )
    return float(truncated_circuit.probability(true_event))

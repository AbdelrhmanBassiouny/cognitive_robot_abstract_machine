"""
Registering the Mutagenesis dataset's chlorine count as a cause of mutagenicity and
running backdoor adjustment on the grounded circuit.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from krrood.entity_query_language.factories import a
from krrood.ormatic.data_access_objects.helper import to_dao
from random_events.product_algebra import SimpleEvent
from typing_extensions import List

from experiments.causal_reasoning.mutagenesis.domain import (
    MutagenesisAtom,
    MutagenesisMolecule,
)
from probabilistic_model.probabilistic_circuit.relational.causal import (
    RelationalCausalCircuit,
)
from probabilistic_model.probabilistic_circuit.relational.rspn import (
    RelationalProbabilisticCircuit,
)

CHLORINE_COUNT_PATH = "chlorine_count()"
"""
Dotted access-path suffix identifying the chlorine-count cause variable in a grounded
circuit.
"""

MUTAGENIC_PATH = "mutagenic"
"""
Dotted access-path suffix identifying the mutagenicity effect variable in a grounded
circuit.
"""

INDICATOR_1_PATH = "indicator_1"
"""
Dotted access-path suffix identifying the ``ind1`` structural-indicator adjustment
variable in a grounded circuit.
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

    naive_probability_mutagenic: float
    """
    ``P(mutagenic = True | chlorine_count)``, read directly off the grounded circuit
    with no adjustment.
    """

    adjusted_probability_mutagenic: float
    """
    ``P(mutagenic = True | do(chlorine_count))``, backdoor-adjusted for
    :data:`INDICATOR_1_PATH`.
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

    support_determinism_verified: bool
    """
    Whether :meth:`~probabilistic_model.probabilistic_circuit.causal.causal_circuit.CausalCircuit.verify_support_determinism`
    passed on the grounded circuit.
    """

    effects: List[ChlorineCountCausalEffect] = field(default_factory=list)
    """
    One row per chlorine-count value the grounded circuit's support covers.
    """


def _build_query(atom_count: int):
    """
    Build a molecule query with a fixed atom count and every atom's element left
    unspecified, so grounding must retain chlorine count as an undetermined latent.

    :param atom_count: Number of atoms the query specifies.
    :return: The resolved query.
    """
    query = a(MutagenesisMolecule)(
        indicator_1=...,
        logp=...,
        lumo=...,
        double_bond_count=...,
        aromatic_bond_count=...,
        mutagenic=...,
        atoms=[
            a(MutagenesisAtom)(element=..., atom_type=..., charge=...)
            for _ in range(atom_count)
        ],
    )
    query.resolve()
    return query


def run_chlorine_count_backdoor_adjustment(
    training_molecules: List[MutagenesisMolecule],
    atom_count: int = 2,
    random_seed: int = 0,
) -> MutagenesisCausalQueryResult:
    """
    Fit a relational circuit, register chlorine count as a cause of mutagenicity, and
    compare naive conditioning against backdoor adjustment for the structural
    indicator ``ind1``.

    :param training_molecules: Molecules to fit the circuit on.
    :param atom_count: Number of atoms the grounding query specifies; every atom's
        element is left unspecified, so chlorine count stays undetermined and is
        retained rather than integrated out.
    :param random_seed: Seed applied to the global NumPy random state before
        grounding, which draws the Monte-Carlo samples that retain chlorine count.
        Fixing it keeps the result reproducible across runs.
    :return: The fitted result, including one causal-effect row per chlorine-count
        value the grounded circuit's support covers.
    """
    model = RelationalProbabilisticCircuit(MutagenesisMolecule)
    model.fit([to_dao(molecule) for molecule in training_molecules])

    query = _build_query(atom_count)
    np.random.seed(random_seed)
    grounded_circuit = model.ground(query)

    relational_causal_circuit = RelationalCausalCircuit()
    causal_circuit = relational_causal_circuit.from_grounded_circuit(
        grounded_circuit,
        causal_variables=[CHLORINE_COUNT_PATH],
        effect_variables=[MUTAGENIC_PATH],
        adjustment_variables=[INDICATOR_1_PATH],
    )

    probabilistic_circuit = causal_circuit.probabilistic_circuit
    chlorine_count_variable = RelationalCausalCircuit.resolve_variable(
        probabilistic_circuit, CHLORINE_COUNT_PATH
    )
    mutagenic_variable = RelationalCausalCircuit.resolve_variable(
        probabilistic_circuit, MUTAGENIC_PATH
    )
    indicator_1_variable = RelationalCausalCircuit.resolve_variable(
        probabilistic_circuit, INDICATOR_1_PATH
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
    chlorine_count_values = sorted(
        int(region.event.simple_sets[0][chlorine_count_variable].simple_sets[0].lower)
        for region in chlorine_count_regions
    )

    effects = [
        ChlorineCountCausalEffect(
            chlorine_count=value,
            naive_probability_mutagenic=_probability_mutagenic_at(
                naive_circuit, chlorine_count_variable, mutagenic_variable, value
            ),
            adjusted_probability_mutagenic=_probability_mutagenic_at(
                adjusted_circuit, chlorine_count_variable, mutagenic_variable, value
            ),
        )
        for value in chlorine_count_values
    ]

    return MutagenesisCausalQueryResult(
        training_molecule_count=len(training_molecules),
        atom_count=atom_count,
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

"""
A relational, EQL-grounded template for hidden Markov models expressed as probabilistic
circuits.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from krrood.entity_query_language.query.match import AbstractMatchExpression
from probabilistic_model.exceptions import ShapeMismatchError
from probabilistic_model.probabilistic_circuit.relational.exceptions import (
    EmptyMarkovChainError,
    NotAProbabilityDistributionError,
)
from probabilistic_model.probabilistic_circuit.relational.helper import (
    rename_variables_with_part_prefix,
)
from probabilistic_model.probabilistic_circuit.relational.rspn import (
    RelationalProbabilisticCircuit,
)
from probabilistic_model.probabilistic_circuit.rx.probabilistic_circuit import (
    ProbabilisticCircuit,
    ProductUnit,
    SumUnit,
)


@dataclass
class MarkovChainDistributionTemplate:
    """
    A fitted distribution template for one sequential (Markov chain) relation.

    Grounds one ``RelationalProbabilisticCircuit`` per position in a sequence, the
    same way :class:`~probabilistic_model.probabilistic_circuit.relational.rspn.ExchangeableDistributionTemplate`
    grounds one per exchangeable child, and chains the grounded copies into a
    hidden Markov model instead of combining them under a product.

    Each grounded copy's root is a :class:`~probabilistic_model.probabilistic_circuit.rx.probabilistic_circuit.SumUnit`;
    its latent-variable interpretation (see the "Latent Variable Interpretation"
    theorem in ``doc/circuits.md``) is the chain's hidden state at that position:
    the root's children are the states, and ``root.subcircuits[s]`` is
    ``P(observation | state = s)``.
    """

    template_distribution: RelationalProbabilisticCircuit
    """
    One time step's fitted relational circuit.

    Its class-level circuit's root is a ``SumUnit``; that sum unit's latent-variable
    interpretation is the chain's hidden state, shared across every grounded part.
    """

    starting_distribution: npt.NDArray
    """
    1D array of length K (K = number of hidden states); the probability of each
    hidden state for the first grounded part.
    """

    transition_model: npt.NDArray
    """
    (K, K) row-stochastic array; ``transition_model[i, j]`` is the probability of
    transitioning to hidden state ``j`` given hidden state ``i``, applied between
    every consecutive pair of grounded parts.
    """

    def __post_init__(self):
        expected_transition_shape = (len(self.starting_distribution),) * 2
        if self.transition_model.shape != expected_transition_shape:
            raise ShapeMismatchError(
                self.transition_model.shape, expected_transition_shape
            )
        if np.any(self.starting_distribution < 0) or not np.isclose(
            self.starting_distribution.sum(), 1.0
        ):
            raise NotAProbabilityDistributionError(
                "starting_distribution", self.starting_distribution
            )
        if np.any(self.transition_model < 0) or not np.allclose(
            self.transition_model.sum(axis=1), 1.0
        ):
            raise NotAProbabilityDistributionError(
                "transition_model", self.transition_model
            )

    def ground(self, parts_to_ground: list) -> ProbabilisticCircuit:
        """
        Ground one copy of the template per part and chain them into a hidden Markov
        model.

        :param parts_to_ground: The query parts, one per position in the sequence, in
            sequence order.
        :return: A circuit over all variables implied by the query, with the per-
            position hidden states marginalized out.
        """
        if len(parts_to_ground) == 0:
            raise EmptyMarkovChainError()

        result = ProbabilisticCircuit()
        roots = [
            self._ground_and_mount_part(result, index, part)
            for index, part in enumerate(parts_to_ground)
        ]

        state_count = len(roots[0].subcircuits)
        expected_shape = (state_count,)
        if self.starting_distribution.shape != expected_shape:
            raise ShapeMismatchError(self.starting_distribution.shape, expected_shape)

        # Read every position's emission branches once, up front: these are plain
        # leaves/subtrees ("P(observation at t | state = s)"), never mutated below, so
        # reading them here fixes what "state s" means at each position once and for
        # all -- the chain built below only ever adds new nodes, it never re-derives a
        # position's state ordering from a circuit structure that could have changed.
        emission_given_state = [list(root.subcircuits) for root in roots]

        self._point_root_at_hidden_markov_chain(result, roots[0], emission_given_state)

        result.remove_unreachable_nodes(roots[0])
        result.simplify()
        return result

    def _ground_and_mount_part(self, result: ProbabilisticCircuit, index: int, part):
        """
        Ground one part of the sequence and mount it into ``result``.

        :param result: The circuit the grounded part is mounted into.
        :param index: Position of the part in the sequence; used as fallback prefix when
            ``part`` does not carry a symbolic variable.
        :param part: The query part (a ``Match`` or a concrete domain object).
        :return: The root of the mounted part, owned by ``result``.
        """
        part_circuit = self.template_distribution.ground(part)
        prefix = (
            str(part.variable)
            if isinstance(part, AbstractMatchExpression)
            else str(index)
        )
        rename_variables_with_part_prefix(part_circuit, prefix, [])
        part_root_index = part_circuit.root.index
        node_index_map = result.mount(part_circuit.root)
        return node_index_map[part_root_index]

    def _point_root_at_hidden_markov_chain(
        self,
        result: ProbabilisticCircuit,
        first_root: SumUnit,
        emission_given_state: list,
    ) -> None:
        """
        Rebuild ``first_root``'s edges so it becomes the root of the whole chain.

        Builds ``P(observation_t, ..., observation_{T-1} | state_t = s)`` from the
        last position back to the first: at each step it sums the next position's
        already-built continuations, weighted by :attr:`transition_model`, and pairs
        that sum with the current position's own emission. ``first_root``'s own
        children are then replaced by these length-``T`` continuations, weighted by
        :attr:`starting_distribution`.

        Working right to left means every node this method adds is only ever
        referenced once it is fully built, so nothing here depends on the order
        :meth:`~probabilistic_model.probabilistic_circuit.rx.probabilistic_circuit.InnerUnit.subcircuits`
        happens to report for a node whose edges were changed earlier in the method
        -- unlike ``SumUnit.mount_with_interaction_terms``, which is built for a
        single pairwise combination and does not preserve a node's own children
        order once it has been used as its first argument, this never re-reads the
        children of a node it has already rebuilt.

        :param result: The circuit every new node is added to.
        :param first_root: The mounted root of the first grounded part; ends up as
            the root of the whole chain.
        :param emission_given_state: ``emission_given_state[t][s]`` is
            ``P(observation_t | state_t = s)``, read once before any mutation.
        """
        state_count = len(self.starting_distribution)
        continuation_given_state = emission_given_state[-1]
        for position in reversed(range(len(emission_given_state) - 1)):
            next_continuation_given_state = continuation_given_state
            continuation_given_state = []
            for state in range(state_count):
                transition = SumUnit(probabilistic_circuit=result)
                for next_state in range(state_count):
                    transition.add_subcircuit(
                        next_continuation_given_state[next_state],
                        np.log(self.transition_model[state, next_state]),
                    )
                joint = ProductUnit(probabilistic_circuit=result)
                joint.add_subcircuit(emission_given_state[position][state])
                joint.add_subcircuit(transition)
                continuation_given_state.append(joint)

        for state, own_subcircuit in enumerate(emission_given_state[0]):
            result.remove_edge(first_root, own_subcircuit)
            first_root.add_subcircuit(
                continuation_given_state[state],
                np.log(self.starting_distribution[state]),
            )

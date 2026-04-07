from __future__ import annotations

import copy
import itertools
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from tabulate import tabulate

from anytree import NodeMixin, PreOrderIter, findall
from scipy.special import logsumexp

from krrood.utils import DataclassException
from random_events.interval import closed
from random_events.product_algebra import SimpleEvent
from random_events.variable import Variable

from probabilistic_model.probabilistic_circuit.rx.probabilistic_circuit import (
    ProbabilisticCircuit,
    ProductUnit,
    SumUnit,
    leaf,
)

from probabilistic_model.probabilistic_circuit.causal.utils import (
    attach_marginal_circuit,
    sum_unit_is_normalized,
)


@dataclass
class MarginalDeterminismTreeNode(NodeMixin):
    """
    One node of a Marginal Determinism Variable Tree.

    Each node carries the Variable objects in its subtree and a query_set
    specifying which Variables SumUnits at this level must be
    support-deterministic over. Support determinism enables polytime backdoor
    adjustment.

    Inherits from anytree.NodeMixin, which provides parent / children
    management, is_leaf and is_root properties, and PreOrderIter / findall
    traversal utilities.

    Build using MarginalDeterminismTreeNode.from_causal_graph() rather than
    constructing nodes manually.

    :param variables: All Variables in this node's subtree.
    :param query_set: Variables for which SumUnits at this level must be
        support-deterministic. Defaults to an empty set.
    :param parent_node: Parent node in the tree. None for the root.
    """

    variables: Set[Variable]
    """All Variables in this node's subtree."""

    query_set: Set[Variable] = field(default=None)
    """Variables for which SumUnits at this level must be support-deterministic.
    Defaults to an empty set."""

    parent_node: Optional[MarginalDeterminismTreeNode] = field(default=None)
    """Parent node supplied at construction. Consumed by __post_init__ to wire
    the tree. Named parent_node so it does not shadow NodeMixin's parent descriptor."""

    def __post_init__(self) -> None:
        NodeMixin.__init__(self)
        if self.query_set is None:
            self.query_set = set()
        self.parent = self.parent_node

    def find_node_for_variable(
        self, variable: Variable
    ) -> Optional[MarginalDeterminismTreeNode]:
        """
        Return the shallowest node whose query_set contains variable, or None.

        :param variable: The Variable to search for.
        :returns: The shallowest matching node, or None if not found.
        """
        results = findall(
            self,
            filter_=lambda node: variable in node.query_set,
            maxlevel=None,
        )
        return results[0] if results else None

    def all_query_sets(self) -> List[Set[Variable]]:
        """
        Return all non-empty query_sets in pre-order (depth-first) order.

        :returns: List of non-empty query_sets in pre-order traversal sequence.
        """
        return [
            node.query_set
            for node in PreOrderIter(self)
            if node.query_set
        ]

    @classmethod
    def from_causal_graph(
        cls,
        causal_variables: List[Variable],
        effect_variables: List[Variable],
        causal_priority_order: List[Variable] = None,
    ) -> MarginalDeterminismTreeNode:
        """
        Build a Marginal Determinism Variable Tree from a causal graph specification.

        :param causal_variables: All input Variables that causally affect the outcome.
        :param effect_variables: All outcome Variables.
        :param causal_priority_order: Ordering of cause Variables from most to least
            important. Defaults to causal_variables order if None.
        """
        ordered = (
            causal_priority_order
            if causal_priority_order is not None
            else causal_variables
        )
        return cls._build_subtree(ordered, parent=None)

    @classmethod
    def _build_subtree(
        cls,
        ordered: List[Variable],
        parent: Optional[MarginalDeterminismTreeNode],
    ) -> MarginalDeterminismTreeNode:
        """
        Recursively build a subtree from an ordered list of Variables. The first
        Variable becomes the query_set at this level; the remainder are split evenly
        between left and right children, with the primary Variable repeated in the left
        child to propagate its determinism constraint.

        :param ordered: Variables in priority order, highest priority first.
        :param parent: Parent node to attach this subtree to. None for the root.
        :returns: The root node of the constructed subtree.
        """
        if len(ordered) == 0:
            return cls(variables=set(), query_set=set(), parent_node=parent)
        if len(ordered) == 1:
            return cls(variables={ordered[0]}, query_set={ordered[0]}, parent_node=parent)

        primary = ordered[0]
        remaining = ordered[1:]
        split = len(remaining) // 2
        left_vars = [primary] + remaining[:split]
        right_vars = remaining[split:]

        node = cls(variables=set(ordered), query_set={primary}, parent_node=parent)
        cls._build_subtree(left_vars, parent=node)
        if right_vars:
            cls._build_subtree(right_vars, parent=node)

        return node


@dataclass
class SupportDeterminismViolation(DataclassException):
    """
    Base class for all violations produced by verify_support_determinism().

    Inherits from DataclassException so each violation is also a raiseable
    exception. Subclasses set self.message in __post_init__ before calling
    super().__post_init__().
    """


@dataclass
class MissingQueryVariableViolation(SupportDeterminismViolation):
    """
    Violation raised when a Variable declared in a query_set is absent from the circuit.

    Produced by Check 1 of verify_support_determinism().
    """

    missing_variables: List[Variable]
    """Variables present in the query_set but not in the circuit."""

    available_variables: List[Variable]
    """All Variables currently registered in the circuit."""

    def __post_init__(self) -> None:
        missing = [v.name for v in self.missing_variables]
        available = [v.name for v in self.available_variables]
        self.message = (
            f"Query-set Variables {missing} not found in circuit. "
            f"Available: {available}"
        )
        super().__post_init__()

    def __str__(self) -> str:
        return self.message


@dataclass
class UnnormalizedSumUnitViolation(SupportDeterminismViolation):
    """
    Violation raised when a SumUnit's log-weights do not sum to log(1).

    Produced by Check 2 of verify_support_determinism().
    Unnormalized SumUnits produce incorrect backdoor adjustment probabilities.
    """

    sum_unit_index: int
    """Graph index of the offending SumUnit."""

    actual_log_weight_sum: float
    """The actual sum of log-weights, which should be 0.0."""

    def __post_init__(self) -> None:
        self.message = (
            f"SumUnit (index={self.sum_unit_index}) log-weights sum to "
            f"{self.actual_log_weight_sum:.6f}, expected 0.0. "
            f"Unnormalized circuits produce incorrect backdoor probabilities."
        )
        super().__post_init__()

    def __str__(self) -> str:
        return self.message


@dataclass
class OverlappingChildSupportsViolation(SupportDeterminismViolation):
    """
    Violation raised when a SumUnit's children have overlapping marginal support
    on a declared query Variable.

    Produced by Check 3 of verify_support_determinism().
    Overlapping supports violate the support-determinism property required for
    tractable backdoor adjustment.
    """

    sum_unit_index: int
    """Graph index of the offending SumUnit."""

    query_variable: Variable
    """The declared query Variable on which the overlap was detected."""

    def __post_init__(self) -> None:
        self.message = (
            f"SumUnit (index={self.sum_unit_index}) has overlapping children supports "
            f"on declared query Variable '{self.query_variable.name}': children are not "
            f"support-deterministic for this Variable."
        )
        super().__post_init__()

    def __str__(self) -> str:
        return self.message


@dataclass
class SupportDeterminismVerificationResult(DataclassException):
    """
    Result of verifying support determinism of a circuit against its
    Marginal Determinism Variable Tree.

    Support determinism requires that for each declared cause Variable,
    SumUnit children have disjoint support regions — i.e. each child
    exclusively owns a non-overlapping partition of that Variable's domain.
    This structural property is required for tractable backdoor adjustment.

    Based on the Q-determinism condition from:
        Broadrick et al. (2023), Tractable Probabilistic Circuits
        https://arxiv.org/abs/2304.07438
    """

    passed: bool
    """True if all three checks passed with no violations."""

    violations: List[SupportDeterminismViolation]
    """Typed violations found, in check order. Empty when passed is True."""

    checked_query_sets: List[Set[Variable]]
    """All non-empty query_sets from the Marginal Determinism Variable Tree."""

    circuit_variables: List[Variable]
    """All Variables present in the circuit at verification time."""

    def __post_init__(self) -> None:
        self.message = str(self)
        super().__post_init__()

    def __str__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        checked_names = [{v.name for v in qs} for qs in self.checked_query_sets]
        circuit_names = [v.name for v in self.circuit_variables]
        lines = [
            f"Support determinism verification: {status}",
            f"  Checked query_sets: {checked_names}",
            f"  Circuit variables:  {circuit_names}",
        ]
        if self.violations:
            lines.append("  Violations:")
            for violation in self.violations:
                lines.append(f"    - {str(violation)}")
        return "\n".join(lines)


@dataclass
class FailureDiagnosisResult:
    """
    Result of identifying which cause Variable is most responsible for an
    observed outcome falling outside the training distribution.

    interventional_probability_at_failure is P(cause in training support
    at the observed value), evaluated in the joint (cause, effect)
    interventional circuit. Zero means the observed value lies entirely
    outside the training distribution — the most unambiguous signal that
    this Variable is the primary cause of the unexpected outcome.
    """

    primary_cause_variable: Variable
    """The cause Variable with the lowest interventional probability at its observed value."""

    actual_value: float
    """The observed value of the primary cause Variable."""

    interventional_probability_at_failure: float
    """P(cause in training support at observed value) from the interventional circuit.
    Zero indicates the observed value lies entirely outside the training distribution."""

    recommended_region: Any
    """The cause support region with the highest interventional probability,
    as a composite set event. None if no regions were found. The caller can
    derive a point recommendation from region.simple_sets[0][cause_variable]."""

    interventional_probability_at_recommendation: float
    """Interventional probability of the recommended region."""

    all_variable_results: Dict[Variable, Dict[str, Any]]
    """Per-variable diagnosis results keyed by Variable. Each entry contains
    actual_value, interventional_probability, and recommended_region."""

    def __str__(self) -> str:
        if self.recommended_region is not None:
            simple_set = self.recommended_region.simple_sets[0]
            interval_set = simple_set[self.primary_cause_variable]
            interval = (
                interval_set.simple_sets[0]
                if hasattr(interval_set, "simple_sets")
                else interval_set
            )
            region_str = f"[{interval.lower:.4f}, {interval.upper:.4f}]"
        else:
            region_str = "None"
        header = [
            ["Primary cause",    self.primary_cause_variable.name],
            ["Actual value",     f"{self.actual_value:.4f}"],
            ["P(outcome | do)",  f"{self.interventional_probability_at_failure:.4f}"],
            ["Recommended region", region_str],
            ["P(outcome | rec)", f"{self.interventional_probability_at_recommendation:.4f}"],
        ]

        rows = [
            [
                variable.name + (" <- PRIMARY" if variable == self.primary_cause_variable else ""),
                f"{result['actual_value']:.4f}",
                f"{result['interventional_probability']:.4f}",
            ]
            for variable, result in self.all_variable_results.items()
        ]

        return (
            "Failure Diagnosis\n"
            + tabulate(header, tablefmt="simple") + "\n\n"
            + "All variables:\n"
            + tabulate(rows, headers=["Variable", "Actual", "P(do)"], tablefmt="simple")
        )


@dataclass
class CausalCircuit:
    """
    A ProbabilisticCircuit extended with exact, tractable causal inference
    using the marginal determinism framework. The Marginal Determinism
    Variable Tree structure encodes the causal graph and enables polytime
    backdoor adjustment for any valid adjustment set Z.

    Wraps a fitted ProbabilisticCircuit and adds:
      - backdoor_adjustment()        — P(effect | do(cause)) as a new circuit
      - verify_support_determinism() — structural validity check against the tree
      - diagnose_failure()           — identify the most anomalous cause Variable

    Use empty adjustment sets for independent randomised training data.
    Supply confounder Variables for correlated deployment data.
    """

    probabilistic_circuit: ProbabilisticCircuit
    """The fitted circuit that encodes the joint distribution over all variables."""

    marginal_determinism_tree: MarginalDeterminismTreeNode
    """Tree encoding which Variables SumUnits must be support-deterministic over."""

    causal_variables: List[Variable]
    """Ordered list of cause Variables registered at construction time."""

    effect_variables: List[Variable]
    """Ordered list of effect Variables registered at construction time."""

    def __post_init__(self) -> None:
        self.causal_variables = list(self.causal_variables)
        self.effect_variables = list(self.effect_variables)

    @classmethod
    def from_probabilistic_circuit(
        cls,
        circuit: ProbabilisticCircuit,
        marginal_determinism_tree: MarginalDeterminismTreeNode,
        causal_variables: List[Variable],
        effect_variables: List[Variable],
    ) -> CausalCircuit:
        """
        Construct a CausalCircuit from an existing ProbabilisticCircuit without retraining.

        :param circuit: A fitted ProbabilisticCircuit over all causal and effect variables.
        :param marginal_determinism_tree: Tree encoding support-determinism constraints.
        :param causal_variables: Ordered list of cause Variables.
        :param effect_variables: Ordered list of effect Variables.
        :returns: A new CausalCircuit wrapping the provided circuit and tree.
        """
        return cls(circuit, marginal_determinism_tree, causal_variables, effect_variables)

    def _check_query_variables_exist(
        self, all_query_variables: Set[Variable]
    ) -> List[MissingQueryVariableViolation]:
        """
        Check that every Variable in every query_set exists in the circuit.

        :param all_query_variables: Union of all Variables across all query_sets.
        :returns: List of violations, empty if all Variables are present.
        """
        circuit_variables: Set[Variable] = set(self.probabilistic_circuit.variables)
        missing_variables = [v for v in all_query_variables if v not in circuit_variables]
        if not missing_variables:
            return []
        return [
            MissingQueryVariableViolation(
                missing_variables=missing_variables,
                available_variables=list(self.probabilistic_circuit.variables),
            )
        ]

    def _check_sum_units_normalized(self) -> List[UnnormalizedSumUnitViolation]:
        """
        Check that every SumUnit's log-weights sum to log(1).

        :returns: List of violations, empty if all SumUnits are normalised.
        """
        violations: List[UnnormalizedSumUnitViolation] = []
        for node in self.probabilistic_circuit.nodes():
            if isinstance(node, SumUnit) and not sum_unit_is_normalized(node):
                violations.append(
                    UnnormalizedSumUnitViolation(
                        sum_unit_index=node.index,
                        actual_log_weight_sum=float(logsumexp(node.log_weights)),
                    )
                )
        return violations

    @staticmethod
    def _child_marginals_split_on_variable(
        child_marginals: List[Any],
    ) -> bool:
        """
        Return True if at least one pair of child marginals is disjoint.

        A SumUnit is treated as a split node for a query Variable only when at
        least one pair of its children has disjoint support on that Variable.
        SumUnits whose children all share the same marginal (e.g. a sibling
        SumUnit in a ProductUnit that has no relationship to this variable) are
        not split nodes and must be skipped to avoid false positives.

        :param child_marginals: Marginal support events, one per SumUnit child.
        :returns: True if any pair of marginals is disjoint.
        """
        return any(
            child_marginals[i].intersection_with(child_marginals[j]).is_empty()
            for i, j in itertools.combinations(range(len(child_marginals)), 2)
        )

    @staticmethod
    def _overlapping_pair_exists(child_marginals: List[Any]) -> bool:
        """
        Return True if any pair of child marginals has non-empty intersection.

        :param child_marginals: Marginal support events, one per SumUnit child.
        :returns: True if any pair overlaps.
        """
        return any(
            not child_marginals[i].intersection_with(child_marginals[j]).is_empty()
            for i, j in itertools.combinations(range(len(child_marginals)), 2)
        )

    def _check_sum_unit_for_variable(
        self,
        node: SumUnit,
        child_support_events: List[Any],
        query_variable: Variable,
    ) -> Optional[OverlappingChildSupportsViolation]:
        """
        Check a single SumUnit against a single query Variable.

        Returns a violation if the SumUnit splits on the variable but has at
        least one overlapping child pair. Returns None if the SumUnit does not
        split on the variable, or if all splitting children are pairwise disjoint.

        :param node: The SumUnit to inspect.
        :param child_support_events: result_of_current_query from each child.
        :param query_variable: The query Variable to check marginal disjointness on.
        :returns: A violation if overlapping children are detected, else None.
        """

        if not all(query_variable in event.variables for event in child_support_events):
            return None
        child_marginals = [
            event.marginal([query_variable])
            for event in child_support_events
        ]
        if not self._child_marginals_split_on_variable(child_marginals):
            return None
        if self._overlapping_pair_exists(child_marginals):
            return OverlappingChildSupportsViolation(
                sum_unit_index=node.index,
                query_variable=query_variable,
            )
        return None

    def _check_support_disjointness(
            self, all_query_variables: Set[Variable]
    ) -> List[OverlappingChildSupportsViolation]:
        """
        Check that for each declared query Variable, no SumUnit that splits on
        that Variable has children with overlapping marginal support.

        Calls self.probabilistic_circuit.support exactly once to populate
        result_of_current_query on every node via a bottom-up traversal, then
        delegates per-node, per-variable inspection to _check_sum_unit_for_variable.

        :param all_query_variables: Union of all Variables across all query_sets.
        :returns: List of violations, empty if all split nodes are support-disjoint.
        """
        violations: List[OverlappingChildSupportsViolation] = []
        self.probabilistic_circuit.support

        for layer in self.probabilistic_circuit.layers:
            for node in layer:
                if not isinstance(node, SumUnit) or len(node.subcircuits) < 2 or len(node.variables) == 1:
                    continue

                child_support_events = [
                    child.result_of_current_query
                    for child in node.subcircuits
                ]
                if any(event is None for event in child_support_events):
                    continue

                for query_variable in all_query_variables:
                    violation = self._check_sum_unit_for_variable(
                        node, child_support_events, query_variable
                    )
                    if violation is not None:
                        violations.append(violation)

        return violations

    def verify_support_determinism(self) -> SupportDeterminismVerificationResult:
        """
        Verify support determinism of the circuit against the Marginal Determinism
        Variable Tree. Runs three checks in order — variable existence, SumUnit
        normalization, and pairwise support disjointness for all declared query
        Variables. Returns early after Check 1 if any Variables are missing, since
        Variable objects are required for marginalisation in Check 3.
        """
        checked_query_sets = self.marginal_determinism_tree.all_query_sets()
        all_query_variables: Set[Variable] = {v for qs in checked_query_sets for v in qs}

        violations: List[SupportDeterminismViolation] = self._check_query_variables_exist(all_query_variables)
        if violations:
            return SupportDeterminismVerificationResult(
                passed=False,
                violations=violations,
                checked_query_sets=checked_query_sets,
                circuit_variables=list(self.probabilistic_circuit.variables),
            )

        violations += self._check_sum_units_normalized()
        violations += self._check_support_disjointness(all_query_variables)

        return SupportDeterminismVerificationResult(
            passed=len(violations) == 0,
            violations=violations,
            checked_query_sets=checked_query_sets,
            circuit_variables=list(self.probabilistic_circuit.variables),
        )

    def backdoor_adjustment(
        self,
        cause_variable: Variable,
        effect_variable: Variable,
        adjustment_variables: List[Variable] = None,
        query_resolution: float = 0.005,
    ) -> ProbabilisticCircuit:
        """
        Compute P(effect | do(cause)) as a new ProbabilisticCircuit.

        With empty adjustment set:
            P(effect | do(cause=v)) = P(effect | cause=v)

        With non-empty adjustment set Z:
            P(effect | do(cause=v)) = sum_z P(effect | cause=v, Z=z) * P(Z=z)

        The output encodes the joint P(effect, cause) — probability(),
        marginal(), and sample() all work on the returned circuit.

        :param cause_variable: A registered cause Variable.
        :param effect_variable: A registered effect Variable.
        :param adjustment_variables: Variables to adjust for. Empty list performs
            no adjustment. Defaults to None, treated as empty.
        :param query_resolution: Half-width of the interval used when querying
            point probabilities. Defaults to 0.005.
        :returns: Joint interventional circuit over (cause, effect).
        """
        if cause_variable not in self.causal_variables:
            raise ValueError(
                f"'{cause_variable.name}' is not a registered cause Variable. "
                f"Registered: {[v.name for v in self.causal_variables]}."
            )
        if effect_variable not in self.effect_variables:
            raise ValueError(
                f"'{effect_variable.name}' is not a registered effect Variable. "
                f"Registered: {[v.name for v in self.effect_variables]}."
            )
        if adjustment_variables is None:
            adjustment_variables = []

        if not adjustment_variables:
            return self._compute_interventional_circuit_without_adjustment(
                cause_variable, effect_variable, query_resolution
            )
        return self._compute_interventional_circuit_with_adjustment(
            cause_variable, effect_variable, adjustment_variables, query_resolution,
        )

    def _build_product_unit_for_region(
        self,
        cause_event: Any,
        cause_weight: float,
        effect_variable: Variable,
        cause_marginal_circuit: ProbabilisticCircuit,
        conditioned_circuit: ProbabilisticCircuit,
        output_circuit: ProbabilisticCircuit,
        root_sum_unit: SumUnit,
    ) -> bool:
        """
        Build one ProductUnit for a single cause region and attach it to root_sum_unit.

        Truncates conditioned_circuit to the cause region, extracts the effect
        marginal, truncates cause_marginal_circuit to the cause region, then
        assembles a ProductUnit of (cause branch, effect branch) weighted by
        cause_weight.

        :param cause_event: Composite event defining the cause support region.
        :param cause_weight: Probability mass of this cause region.
        :param effect_variable: The effect Variable to marginalise onto.
        :param cause_marginal_circuit: Marginal circuit over the cause Variable.
        :param conditioned_circuit: Full circuit to truncate to the cause region.
        :param output_circuit: Circuit to attach the new ProductUnit to.
        :param root_sum_unit: SumUnit to attach the weighted ProductUnit to.
        :returns: True if the ProductUnit was successfully added, False if
            truncation produced an empty circuit.
        """
        truncated_circuit, _ = copy.deepcopy(conditioned_circuit).log_truncated_in_place(
            cause_event.fill_missing_variables_pure(conditioned_circuit.variables)
        )
        if truncated_circuit is None:
            return False

        effect_marginal_circuit = truncated_circuit.marginal([effect_variable])
        cause_region_circuit, _ = copy.deepcopy(
            cause_marginal_circuit
        ).log_truncated_in_place(
            cause_event.fill_missing_variables_pure(cause_marginal_circuit.variables)
        )
        if cause_region_circuit is None:
            return False

        product_unit = ProductUnit(probabilistic_circuit=output_circuit)
        attach_marginal_circuit(cause_region_circuit, product_unit, output_circuit)
        attach_marginal_circuit(effect_marginal_circuit, product_unit, output_circuit)
        root_sum_unit.add_subcircuit(product_unit, math.log(cause_weight))
        return True

    def _compute_interventional_circuit_without_adjustment(
            self,
            cause_variable: Variable,
            effect_variable: Variable,
            query_resolution: float,
    ) -> ProbabilisticCircuit:
        """
        Compute P(cause, effect | do(cause)) with an empty adjustment set.

        Returns a joint circuit over (cause, effect) as a SumUnit of
        ProductUnits, one per disjoint cause support region.

        Structure::

            SumUnit [weight = P(cause in region_i)]
                ProductUnit
                    cause branch  (UniformDistribution over region_i)
                    effect branch (P(effect | cause in region_i))

        :param cause_variable: The cause Variable to intervene on.
        :param effect_variable: The effect Variable to compute the distribution over.
        :param query_resolution: Half-width passed through to region extraction.
        :returns: Joint interventional circuit over (cause, effect).
        """
        cause_marginal_circuit = copy.deepcopy(self.probabilistic_circuit).marginal([cause_variable])
        output_circuit = ProbabilisticCircuit()
        root_sum_unit = SumUnit(probabilistic_circuit=output_circuit)
        regions_added = sum(
            self._build_product_unit_for_region(
                cause_event=region_event,
                cause_weight=region_weight,
                effect_variable=effect_variable,
                cause_marginal_circuit=cause_marginal_circuit,
                conditioned_circuit=copy.deepcopy(self.probabilistic_circuit),
                output_circuit=output_circuit,
                root_sum_unit=root_sum_unit,
            )
            for region_event, region_weight in self._extract_leaf_regions_for_variable(cause_variable)
            if region_weight > 0.0
        )

        if regions_added == 0:
            raise ValueError(
                f"Interventional circuit is empty for cause '{cause_variable.name}'. "
                f"Ensure the circuit was trained on data covering this Variable's domain."
            )
        return output_circuit

    def _add_regions_for_adjustment_stratum(
        self,
        adjustment_event: Any,
        adjustment_weight: float,
        cause_variable: Variable,
        effect_variable: Variable,
        cause_marginal_circuit: ProbabilisticCircuit,
        output_circuit: ProbabilisticCircuit,
        root_sum_unit: SumUnit,
    ) -> int:
        """
        Add ProductUnit components to root_sum_unit for one adjustment stratum.

        Truncates the circuit to the adjustment stratum, then for each cause
        region within that stratum builds a joint (cause, effect) ProductUnit
        weighted by P(adjustment) * P(cause | adjustment).

        :param adjustment_event: Composite event defining the adjustment stratum.
        :param adjustment_weight: Probability mass of this adjustment stratum.
        :param cause_variable: The cause Variable to intervene on.
        :param effect_variable: The effect Variable to marginalise onto.
        :param cause_marginal_circuit: Marginal circuit over the cause Variable.
        :param output_circuit: Circuit to attach new ProductUnits to.
        :param root_sum_unit: SumUnit to attach the weighted ProductUnits to.
        :returns: Number of ProductUnit components successfully added.
        """
        adjustment_conditioned_circuit, _ = copy.deepcopy(
            self.probabilistic_circuit
        ).log_truncated_in_place(
            adjustment_event.fill_missing_variables_pure(self.probabilistic_circuit.variables)
        )
        if adjustment_conditioned_circuit is None:
            return 0

        regions_added = 0
        for cause_event, cause_weight in self._extract_leaf_regions_for_variable(
            cause_variable, base_circuit=adjustment_conditioned_circuit
        ):
            if cause_weight <= 0.0:
                continue

            joint_event = adjustment_event.intersection_with(cause_event)
            joint_conditioned_circuit, _ = copy.deepcopy(
                self.probabilistic_circuit
            ).log_truncated_in_place(
                joint_event.fill_missing_variables_pure(self.probabilistic_circuit.variables)
            )
            if joint_conditioned_circuit is None:
                continue

            regions_added += self._build_product_unit_for_region(
                cause_event=cause_event,
                cause_weight=adjustment_weight * cause_weight,
                effect_variable=effect_variable,
                cause_marginal_circuit=cause_marginal_circuit,
                conditioned_circuit=joint_conditioned_circuit,
                output_circuit=output_circuit,
                root_sum_unit=root_sum_unit,
            )

        return regions_added

    def _compute_interventional_circuit_with_adjustment(
            self,
            cause_variable: Variable,
            effect_variable: Variable,
            adjustment_variables: List[Variable],
            query_resolution: float,
    ) -> ProbabilisticCircuit:
        """
        Compute P(cause, effect | do(cause)) with a non-empty adjustment set Z.

        Implements:
            P(effect | do(cause=v)) = sum_z P(effect | cause=v, Z=z) * P(Z=z)

        :param cause_variable: The cause Variable to intervene on.
        :param effect_variable: The effect Variable to compute the distribution over.
        :param adjustment_variables: Variables to condition on and marginalise over.
        :param query_resolution: Half-width passed through to region extraction.
        :returns: Joint interventional circuit over (cause, effect).
        """
        cause_marginal_circuit = copy.deepcopy(self.probabilistic_circuit).marginal([cause_variable])
        output_circuit = ProbabilisticCircuit()
        root_sum_unit = SumUnit(probabilistic_circuit=output_circuit)
        regions_added = sum(
            self._add_regions_for_adjustment_stratum(
                adjustment_event=adjustment_event,
                adjustment_weight=adjustment_weight,
                cause_variable=cause_variable,
                effect_variable=effect_variable,
                cause_marginal_circuit=cause_marginal_circuit,
                output_circuit=output_circuit,
                root_sum_unit=root_sum_unit,
            )
            for adjustment_event, adjustment_weight in self._extract_leaf_regions_for_variables(
                adjustment_variables
            )
            if adjustment_weight > 0.0
        )

        if regions_added == 0:
            raise ValueError(
                f"Interventional circuit with adjustment is empty. "
                f"cause='{cause_variable.name}', "
                f"adjustment={[v.name for v in adjustment_variables]}."
            )
        return output_circuit

    def _extract_leaf_regions_for_variable(
        self,
        variable: Variable,
        base_circuit: ProbabilisticCircuit = None,
    ) -> List[Tuple[Any, float]]:
        """
        Return (region_event, probability) pairs for each support region of variable.

        :param variable: The Variable whose support regions to extract.
        :param base_circuit: Circuit to query. Defaults to self.probabilistic_circuit.
        :returns: List of (composite_set_event, probability) pairs, one per region.
        """
        circuit = base_circuit if base_circuit is not None else self.probabilistic_circuit
        regions: List[Tuple[Any, float]] = []
        variable_support = circuit.support.marginal([variable])
        for simple_region in variable_support.simple_sets:
            region_event = SimpleEvent.from_data(
                {variable: simple_region[variable]}
            ).as_composite_set()
            probability = circuit.probability(
                region_event.fill_missing_variables_pure(circuit.variables)
            )
            if probability > 0.0:
                regions.append((region_event, float(probability)))
        return regions

    def _extract_leaf_regions_for_variables(
        self,
        variables: List[Variable],
    ) -> List[Tuple[Any, float]]:
        """
        Return (region_event, probability) pairs for the joint support of variables.

        :param variables: Variables whose joint support regions to extract.
        :returns: List of (composite_set_event, probability) pairs, one per joint region.
        """
        regions: List[Tuple[Any, float]] = []
        joint_support = self.probabilistic_circuit.support.marginal(variables)
        for simple_region in joint_support.simple_sets:
            region_event = SimpleEvent.from_data(
                {variable: simple_region[variable] for variable in variables}
            ).as_composite_set()
            probability = self.probabilistic_circuit.probability(
                region_event.fill_missing_variables_pure(self.probabilistic_circuit.variables)
            )
            if probability > 0.0:
                regions.append((region_event, float(probability)))
        return regions

    def _query_probability_at_value(
        self,
        interventional_circuit: ProbabilisticCircuit,
        cause_variable: Variable,
        value: float,
        query_resolution: float,
    ) -> float:
        """
        Query P(cause in [value - eps, value + eps]) on the interventional circuit.

        :param interventional_circuit: Joint circuit over (cause, effect).
        :param cause_variable: The Variable whose value to query.
        :param value: The point value to query around.
        :param query_resolution: Half-width of the query interval.
        :returns: Probability mass within the query interval.
        """
        event = SimpleEvent.from_data(
            {cause_variable: closed(value - query_resolution, value + query_resolution)}
        ).as_composite_set()
        return float(
            interventional_circuit.probability(
                event.fill_missing_variables_pure(interventional_circuit.variables)
            )
        )

    def _best_region(
        self,
        cause_variable: Variable,
        interventional_circuit: ProbabilisticCircuit,
    ) -> Optional[Any]:
        """
        Return the cause support region with the highest interventional probability,
        or None if no regions are found.

        The full composite set event is returned so callers retain the interval
        bounds rather than a lossy midpoint summary.

        :param cause_variable: The Variable whose support regions to search.
        :param interventional_circuit: Joint circuit used to score each region.
        :returns: Composite set event of the highest-probability region, or None.
        """
        best_probability = -1.0
        best_region: Optional[Any] = None
        for region_event, _ in self._extract_leaf_regions_for_variable(cause_variable):
            region_probability = float(
                interventional_circuit.probability(
                    region_event.fill_missing_variables_pure(interventional_circuit.variables)
                )
            )
            if region_probability > best_probability:
                best_probability = region_probability
                best_region = region_event
        return best_region

    def _diagnose_single_cause_variable(
        self,
        cause_variable: Variable,
        observed_value: float,
        effect_variable: Variable,
        adjustment_variables: List[Variable],
        query_resolution: float,
    ) -> Tuple[Dict[str, Any], ProbabilisticCircuit]:
        """
        Run diagnosis for a single cause Variable at its observed value.

        :param cause_variable: The cause Variable to diagnose.
        :param observed_value: The observed value of the cause Variable.
        :param effect_variable: The effect Variable.
        :param adjustment_variables: Variables to adjust for.
        :param query_resolution: Half-width of the query interval.
        :returns: Tuple of (result_dict, interventional_circuit).
        """
        interventional_circuit = self.backdoor_adjustment(
            cause_variable, effect_variable, adjustment_variables, query_resolution,
        )
        probability_at_observed = self._query_probability_at_value(
            interventional_circuit, cause_variable, observed_value, query_resolution,
        )
        recommended_region = self._best_region(cause_variable, interventional_circuit)
        result = {
            "actual_value": observed_value,
            "interventional_probability": round(probability_at_observed, 6),
            "recommended_region": recommended_region,
        }
        return result, interventional_circuit

    def diagnose_failure(
        self,
        observed_values: Dict[Variable, float],
        effect_variable: Variable,
        query_resolution: float = 0.005,
        adjustment_variables: List[Variable] = None,
    ) -> FailureDiagnosisResult:
        """
        Identify the primary cause Variable whose observed value is most
        anomalous under the interventional distribution.

        For each cause Variable, queries the interventional circuit at the
        observed value. The Variable with the lowest interventional probability
        at its observed value is identified as the primary cause. The
        recommendation is the cause region with the highest interventional
        probability, returned as a full composite set event.

        The interventional_probability recorded per Variable is
        P(cause in [observed-eps, observed+eps]) in the joint (cause, effect)
        interventional circuit. Zero means the value is outside training support.

        :param observed_values: Mapping from each cause Variable to its observed value.
        :param effect_variable: The effect Variable to evaluate the interventional
            distribution over.
        :param query_resolution: Half-width of the interval used when evaluating
            point probabilities. Defaults to 0.005.
        :param adjustment_variables: Variables to adjust for. Defaults to None,
            treated as empty.
        :returns: FailureDiagnosisResult identifying the primary cause and
            recommended corrective region.
        """
        if adjustment_variables is None:
            adjustment_variables = []

        all_variable_results: Dict[Variable, Dict[str, Any]] = {}
        interventional_circuits_by_cause: Dict[Variable, ProbabilisticCircuit] = {}

        for cause_variable in self.causal_variables:
            if cause_variable not in observed_values or not cause_variable.is_numeric:
                continue
            result, interventional_circuit = self._diagnose_single_cause_variable(
                cause_variable=cause_variable,
                observed_value=observed_values[cause_variable],
                effect_variable=effect_variable,
                adjustment_variables=adjustment_variables,
                query_resolution=query_resolution,
            )
            all_variable_results[cause_variable] = result
            interventional_circuits_by_cause[cause_variable] = interventional_circuit

        if not all_variable_results:
            raise ValueError(
                f"No cause Variables found in observed_values. "
                f"Expected at least one of: {[v.name for v in self.causal_variables]}"
            )

        primary_cause_variable = min(
            all_variable_results,
            key=lambda v: all_variable_results[v]["interventional_probability"],
        )
        primary_result = all_variable_results[primary_cause_variable]
        recommended_region = primary_result["recommended_region"]

        if recommended_region is not None:
            interval_set = recommended_region.simple_sets[0][primary_cause_variable]
            interval = (
                interval_set.simple_sets[0]
                if hasattr(interval_set, "simple_sets")
                else interval_set
            )
            region_midpoint = (float(interval.lower) + float(interval.upper)) / 2.0
            probability_at_recommendation = self._query_probability_at_value(
                interventional_circuits_by_cause[primary_cause_variable],
                primary_cause_variable,
                region_midpoint,
                query_resolution,
            )
        else:
            probability_at_recommendation = 0.0

        return FailureDiagnosisResult(
            primary_cause_variable=primary_cause_variable,
            actual_value=primary_result["actual_value"],
            interventional_probability_at_failure=primary_result["interventional_probability"],
            recommended_region=recommended_region,
            interventional_probability_at_recommendation=round(probability_at_recommendation, 6),
            all_variable_results=all_variable_results,
        )
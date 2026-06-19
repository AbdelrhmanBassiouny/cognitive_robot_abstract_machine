from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, TYPE_CHECKING

import krrood.symbolic_math.symbolic_math as sm
from giskardpy.qp.dof_limits import DofLimits
from giskardpy.qp.enforcement_strategy import (
    EnforcementStrategy,
    SystemDynamicsStrategy,
)
from giskardpy.qp.constraint_collection import ConstraintCollection
from krrood.symbolic_math.symbolic_math import Vector, Matrix
from semantic_digital_twin.world_description.degree_of_freedom import DegreeOfFreedom

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from giskardpy.qp.qp_controller_config import QPControllerConfig


@dataclass
class QPVariableAccumulator:
    """
    Collects the per-block cost weights, box bounds, and variable names of all decision and slack
    variables while the QP is assembled, so the assembly logic stays free of hidden side effects.
    """

    quadratic_weights: List[Vector] = field(default_factory=list)
    """
    The quadratic cost blocks, one per registered variable block.
    """
    linear_weights: List[Vector] = field(default_factory=list)
    """
    The linear cost blocks, one per registered variable block.
    """
    box_lower_constraints: List[Vector] = field(default_factory=list)
    """
    The lower box-bound blocks, one per registered variable block.
    """
    box_upper_constraints: List[Vector] = field(default_factory=list)
    """
    The upper box-bound blocks, one per registered variable block.
    """
    free_variable_names: List[str] = field(default_factory=list)
    """
    The names of all registered variables, in column order.
    """


@dataclass
class QPDataSymbolic:
    """
    Takes free variables and constraints and converts them to a QP problem in the following format, depending on the
    class attributes:
    min_x 0.5 x^T H x + g^T x
    s.t.  lb <= x <= ub     (box constraints)
          Edof x <= bE_dof          (equality constraints)
          Eslack x <= bE_slack        (equality constraints)
          lbA <= Adof x <= ubA_dof  (lower/upper inequality constraints)
          lbA <= Aslack x <= ubA_slack  (lower/upper inequality constraints)
    """

    degrees_of_freedom: List[DegreeOfFreedom]
    """
    The degrees of freedom whose decision variables make up the non-slack part of the QP.
    """
    constraint_collection: ConstraintCollection
    """
    The equality and inequality constraints to encode into the QP.
    """
    config: QPControllerConfig
    """
    Controller configuration, e.g. prediction horizon and time step.
    """

    quadratic_weights: Vector = field(init=False)
    """
    Diagonal of the QP cost matrix H, for all decision and slack variables.
    """
    linear_weights: Vector = field(init=False)
    """
    The linear cost vector g, for all decision and slack variables.
    """

    box_lower_constraints: Vector = field(init=False)
    """
    Lower box bounds lb for all decision and slack variables.
    """
    box_upper_constraints: Vector = field(init=False)
    """
    Upper box bounds ub for all decision and slack variables.
    """

    free_variable_names: list[str] = field(init=False)
    """
    Names of all decision and slack variables, in column order.
    """

    eq_matrix_dofs: Matrix = field(init=False)
    """
    Equality constraint matrix block acting on the degree-of-freedom variables.
    """
    eq_matrix_slack: Matrix = field(init=False)
    """
    Equality constraint matrix block acting on the equality slack variables.
    """
    eq_bounds: Vector = field(init=False)
    """
    Right-hand side bounds of the equality constraints.
    """
    eq_constraint_names: list[str] = field(init=False)
    """
    Names of the equality constraints, in row order.
    """

    neq_matrix_dofs: Matrix = field(init=False)
    """
    Inequality constraint matrix block acting on the degree-of-freedom variables.
    """
    neq_matrix_slack: Matrix = field(init=False)
    """
    Inequality constraint matrix block acting on the inequality slack variables.
    """
    neq_lower_bounds: Vector = field(init=False)
    """
    Lower bounds of the inequality constraints.
    """
    neq_upper_bounds: Vector = field(init=False)
    """
    Upper bounds of the inequality constraints.
    """
    neq_constraint_names: list[str] = field(init=False)
    """
    Names of the inequality constraints, in row order.
    """

    @staticmethod
    def _append_slack_block(
        strategy: EnforcementStrategy,
        constraint_names: List[str],
        accumulator: QPVariableAccumulator,
    ) -> tuple[Matrix, Matrix]:
        """
        Appends the strategy's slack weights, box bounds, and names to the accumulator and the given
        constraint-name list, and returns its constraint matrix and slack matrix.
        """
        slack_variables = strategy.create_slack_variables()
        accumulator.quadratic_weights.append(slack_variables.quadratic_weights)
        accumulator.linear_weights.append(slack_variables.linear_weights)
        accumulator.box_lower_constraints.append(slack_variables.lower_bounds)
        accumulator.box_upper_constraints.append(slack_variables.upper_bounds)
        constraint_names.extend(strategy.create_names())
        accumulator.free_variable_names.extend(slack_variables.names)
        return strategy.create_matrix(), strategy.create_slack_matrix()

    def __post_init__(self):
        direct_limits = DofLimits.create(self.degrees_of_freedom, self.config)
        accumulator = QPVariableAccumulator(
            quadratic_weights=[direct_limits.quadratic_weights],
            linear_weights=[direct_limits.linear_weights],
            box_lower_constraints=[direct_limits.lower_bounds],
            box_upper_constraints=[direct_limits.upper_bounds],
            free_variable_names=list(direct_limits.names),
        )

        ineq_matrix_dofs = []
        ineq_matrix_slack = []
        lower_bounds = []
        upper_bounds = []
        self.neq_constraint_names = []

        eq_matrix_dofs = []
        eq_matrix_slack = []
        eq_bounds = []
        self.eq_constraint_names = []

        system_dynamics_strategy = SystemDynamicsStrategy(
            degrees_of_freedom=self.degrees_of_freedom,
            config=self.config,
            constraints=[],
        )
        eq_matrix_dofs.append(system_dynamics_strategy.create_matrix())
        eq_matrix_slack.append(system_dynamics_strategy.create_slack_matrix())
        eq_bounds.append(system_dynamics_strategy.create_equality_bounds())
        self.eq_constraint_names.extend(system_dynamics_strategy.create_names())

        for (
            enforcement_strategy,
            constraints,
        ) in self.constraint_collection.get_equality_constraint_blocks().items():
            strategy = enforcement_strategy(
                degrees_of_freedom=self.degrees_of_freedom,
                config=self.config,
                constraints=constraints,
            )
            matrix, slack_matrix = self._append_slack_block(
                strategy, self.eq_constraint_names, accumulator
            )
            eq_matrix_dofs.append(matrix)
            eq_matrix_slack.append(slack_matrix)
            eq_bounds.append(strategy.create_equality_bounds())

        for (
            enforcement_strategy,
            constraints,
        ) in self.constraint_collection.get_inequality_constraint_blocks().items():
            strategy = enforcement_strategy(
                degrees_of_freedom=self.degrees_of_freedom,
                config=self.config,
                constraints=constraints,
            )
            matrix, slack_matrix = self._append_slack_block(
                strategy, self.neq_constraint_names, accumulator
            )
            ineq_matrix_dofs.append(matrix)
            ineq_matrix_slack.append(slack_matrix)
            lower_bounds.append(strategy.create_lower_bounds())
            upper_bounds.append(strategy.create_upper_bounds())

        self.free_variable_names = accumulator.free_variable_names
        self.quadratic_weights = sm.concatenate(*accumulator.quadratic_weights)
        self.linear_weights = sm.concatenate(*accumulator.linear_weights)
        self.box_lower_constraints = sm.concatenate(*accumulator.box_lower_constraints)
        self.box_upper_constraints = sm.concatenate(*accumulator.box_upper_constraints)
        self.eq_matrix_dofs = sm.vstack(eq_matrix_dofs)
        self.eq_matrix_slack = sm.diag_stack(eq_matrix_slack)
        self.eq_bounds = sm.concatenate(*eq_bounds)

        if ineq_matrix_dofs:
            self.neq_matrix_dofs = sm.vstack(ineq_matrix_dofs)
        else:
            self.neq_matrix_dofs = sm.Matrix()

        if ineq_matrix_slack:
            self.neq_matrix_slack = sm.diag_stack(ineq_matrix_slack)
        else:
            self.neq_matrix_slack = sm.Matrix()

        if lower_bounds:
            self.neq_lower_bounds = sm.concatenate(*lower_bounds)
        else:
            self.neq_lower_bounds = sm.Vector()

        if upper_bounds:
            self.neq_upper_bounds = sm.concatenate(*upper_bounds)
        else:
            self.neq_upper_bounds = sm.Vector()

    def __hash__(self):
        return hash(id(self))

    @property
    def num_free_variable_constraints(self) -> int:
        return len(self.degrees_of_freedom)

    @property
    def num_eq_slack_variables(self) -> int:
        return self.eq_matrix_slack.shape[1]

    @property
    def num_neq_slack_variables(self) -> int:
        return self.neq_matrix_slack.shape[1]

    @property
    def num_slack_variables(self) -> int:
        return self.num_eq_slack_variables + self.num_neq_slack_variables

    @property
    def num_non_slack_variables(self) -> int:
        return self.quadratic_weights.shape[0] - self.num_slack_variables

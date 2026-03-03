from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Union

import numpy as np
import scipy.sparse as sp
from scipy.sparse import issparse


@dataclass
class Conditioning:
    """
    Change the conditioning of a QP problem.
    Inherit from this to implement different strategies
    """

    C: np.ndarray | None = field(default=None)
    R_eq: np.ndarray | None = field(default=None)
    R_neq: np.ndarray | None = field(default=None)

    def apply(self, qp_data: QPData) -> QPData:
        """
        Apply the conditioning to the QP problem data.
        """
        new_qp_data = deepcopy(qp_data)
        if self.C is not None:
            new_qp_data.quadratic_weights = (
                self.C @ new_qp_data.quadratic_weights @ self.C
            )
            new_qp_data.linear_weights = self.C @ new_qp_data.linear_weights
            new_qp_data.box_lower_constraints = (
                self.C @ new_qp_data.box_lower_constraints
            )
            new_qp_data.box_upper_constraints = (
                self.C @ new_qp_data.box_upper_constraints
            )
            new_qp_data.eq_matrix = new_qp_data.eq_matrix @ self.C
            new_qp_data.neq_matrix = new_qp_data.neq_matrix @ self.C
        if self.R_eq is not None:
            new_qp_data.eq_matrix = self.R_eq @ new_qp_data.eq_matrix
            new_qp_data.eq_bounds = self.R_eq @ new_qp_data.eq_bounds
        if self.R_neq is not None:
            new_qp_data.neq_matrix = self.R_neq @ new_qp_data.neq_matrix
            new_qp_data.neq_lower_bounds = self.R_neq @ new_qp_data.neq_lower_bounds
            new_qp_data.neq_upper_bounds = self.R_neq @ new_qp_data.neq_upper_bounds
        return new_qp_data

    def unapply(self, xdot: np.ndarray) -> np.ndarray:
        """
        Retrieve the xdot of the original QP Problem
        """
        return np.linalg.inv(self.C) @ xdot


@dataclass
class MyConditioning:
    def __post_init__(self):
        C = np.ones(self.quadratic_weights.shape)
        C[-3:] = 1 / np.sqrt(self.quadratic_weights[-3:])
        C = np.diag(C)
        new_eq_matrix = self.eq_matrix @ C
        maxx = np.abs(new_eq_matrix[-3:, :]).max(axis=1)
        R_eq = np.ones(self.eq_matrix.shape[0])
        R_eq[-3:] = 1 / maxx
        R_eq = np.diag(R_eq)
        return QPData(
            quadratic_weights=C @ self.quadratic_weights @ C,
            linear_weights=self.linear_weights,
            box_lower_constraints=self.box_lower_constraints @ C,
            box_upper_constraints=self.box_upper_constraints @ C,
            eq_matrix=R_eq @ self.eq_matrix @ C,
            eq_bounds=R_eq @ self.eq_bounds,
            neq_matrix=self.neq_matrix,
            neq_lower_bounds=self.neq_lower_bounds,
            neq_upper_bounds=self.neq_upper_bounds,
            R_eq=R_eq,
            C=C,
        )


@dataclass
class Relaxo:
    def partially_relaxed(self, relaxed_solution: np.ndarray) -> QPData:
        relaxed_qp_data = QPData(
            quadratic_weights=self.filtered.quadratic_weights.copy(),
            linear_weights=self.filtered.linear_weights,
            box_lower_constraints=self.filtered.box_lower_constraints.copy(),
            box_upper_constraints=self.filtered.box_upper_constraints.copy(),
            eq_matrix=self.filtered.eq_matrix,
            eq_bounds=self.filtered.eq_bounds,
            neq_matrix=self.filtered.neq_matrix,
            neq_lower_bounds=self.filtered.neq_lower_bounds,
            neq_upper_bounds=self.filtered.neq_upper_bounds,
        )
        lower_box_filter = relaxed_solution < self.filtered.box_lower_constraints
        upper_box_filter = relaxed_solution > self.filtered.box_upper_constraints
        relaxed_qp_data.box_lower_constraints[lower_box_filter] -= 100
        relaxed_qp_data.box_upper_constraints[upper_box_filter] += 100
        relaxed_qp_data.quadratic_weights[lower_box_filter | upper_box_filter] *= 1000

        return relaxed_qp_data

    def relaxed(self) -> QPData:
        relaxed_qp_data = QPData(
            quadratic_weights=self.filtered.quadratic_weights,
            linear_weights=self.filtered.linear_weights,
            box_lower_constraints=self.filtered.box_lower_constraints.copy(),
            box_upper_constraints=self.filtered.box_upper_constraints.copy(),
            eq_matrix=self.filtered.eq_matrix,
            eq_bounds=self.filtered.eq_bounds,
            neq_matrix=self.filtered.neq_matrix,
            neq_lower_bounds=self.filtered.neq_lower_bounds,
            neq_upper_bounds=self.filtered.neq_upper_bounds,
        )

        relaxed_qp_data.box_lower_constraints[self.num_non_constraints :] -= 100
        relaxed_qp_data.box_upper_constraints[self.num_non_constraints :] += 100

        return relaxed_qp_data


@dataclass
class ZeroWeightQPDataFilter:

    def apply_filters(
        self,
        zero_quadratic_weight_filter: np.ndarray,
        bE_filter: np.ndarray,
        bA_filter: np.ndarray,
    ):
        self.zero_quadratic_weight_filter = zero_quadratic_weight_filter
        self.bE_filter = bE_filter
        self.bA_filter = bA_filter
        qp_data_filtered = QPData()
        qp_data_filtered.quadratic_weights = self.quadratic_weights[
            zero_quadratic_weight_filter
        ]
        qp_data_filtered.linear_weights = self.linear_weights[
            zero_quadratic_weight_filter
        ]
        qp_data_filtered.box_lower_constraints = self.box_lower_constraints[
            zero_quadratic_weight_filter
        ]
        qp_data_filtered.box_upper_constraints = self.box_upper_constraints[
            zero_quadratic_weight_filter
        ]
        if (
            len(self.eq_matrix.shape) > 1
            and self.eq_matrix.shape[0] * self.eq_matrix.shape[1] > 0
        ):
            qp_data_filtered.eq_matrix = self.eq_matrix[bE_filter, :][
                :, zero_quadratic_weight_filter
            ]
        else:
            qp_data_filtered.eq_matrix = self.eq_matrix
        # when no eq constraints were filtered, we can just cut off at the end, because that section is always all 0
        # qp_data_filtered.eq_matrix = self.eq_matrix_np_raw[:, :self.zero_quadratic_weight_filter.sum()]
        qp_data_filtered.eq_bounds = self.eq_bounds[bE_filter]
        if (
            len(self.neq_matrix.shape) > 1
            and self.neq_matrix.shape[0] * self.neq_matrix.shape[1] > 0
        ):
            qp_data_filtered.neq_matrix = self.neq_matrix[
                :, zero_quadratic_weight_filter
            ][bA_filter, :]
        else:
            qp_data_filtered.neq_matrix = self.neq_matrix
        qp_data_filtered.neq_lower_bounds = self.neq_lower_bounds[bA_filter]
        qp_data_filtered.neq_upper_bounds = self.neq_upper_bounds[bA_filter]
        self.filtered = qp_data_filtered


@dataclass
class QPData:
    """
    Container for a QP of the form:

    min_x 0.5 * x^T np.diag(quadratic_weights) x + linear_weights^T x
    s.t. box_lower_constraints <= x <= box_upper_constraints
         eq_matrix x = eq_bounds
         neq_lower_bounds <= neq_matrix x <= neq_upper_bounds

    .. note: matrices use sparse format
    """

    quadratic_weights: np.ndarray
    linear_weights: np.ndarray

    box_lower_constraints: np.ndarray
    box_upper_constraints: np.ndarray

    eq_matrix: sp.csc_matrix
    eq_bounds: np.ndarray

    neq_matrix: sp.csc_matrix
    neq_lower_bounds: np.ndarray
    neq_upper_bounds: np.ndarray

    @property
    def sparse_hessian(self) -> sp.csc_matrix:
        return sp.diags(self.quadratic_weights)

    @property
    def dense_hessian(self) -> np.ndarray:
        return np.diag(self.quadratic_weights)

    @property
    def dense_eq_matrix(self) -> np.ndarray:
        return self.eq_matrix.toarray()

    @property
    def dense_neq_matrix(self) -> np.ndarray:
        return self.neq_matrix.toarray()

    def to_print_testcase(self):
        testcase = (
            f"linear_weights = np.array({self.linear_weights.tolist()}, dtype=float)\n"
            f"quadratic_weights = np.array({self.quadratic_weights.tolist()}, dtype=float)\n"
            f"box_lower_constraints = np.array({self.box_lower_constraints.tolist()}, dtype=float)\n"
            f"box_upper_constraints = np.array({self.box_upper_constraints.tolist()}, dtype=float)\n"
            f"eq_bounds = np.array({self.eq_bounds.tolist()}, dtype=float)\n"
            f"neq_lower_bounds = np.array({self.neq_lower_bounds.tolist()}, dtype=float)\n"
            f"neq_upper_bounds = np.array({self.neq_upper_bounds.tolist()}, dtype=float)\n"
            f"eq_matrix_data = np.array({self.eq_matrix.data.tolist()}, dtype=float)\n"
            f"eq_matrix_indices = np.array({self.eq_matrix.indices.tolist()}, dtype=int)\n"
            f"eq_matrix_indptr = np.array({self.eq_matrix.indptr.tolist()}, dtype=int)\n"
            f"eq_matrix_shape = {self.eq_matrix.shape}\n"
            f"eq_matrix = csc_matrix((eq_matrix_data, eq_matrix_indices, eq_matrix_indptr), shape=eq_matrix_shape).toarray()\n"
            f"neq_matrix_data = np.array({self.neq_matrix.data.tolist()}, dtype=float)\n"
            f"neq_matrix_indices = np.array({self.neq_matrix.indices.tolist()}, dtype=int)\n"
            f"neq_matrix_indptr = np.array({self.neq_matrix.indptr.tolist()}, dtype=int)\n"
            f"neq_matrix_shape = {self.neq_matrix.shape}\n"
            f"neq_matrix = csc_matrix((neq_matrix_data, neq_matrix_indices, neq_matrix_indptr), shape=neq_matrix_shape).toarray()\n"
            "x = solve_and_verify_qp_solution(quadratic_weights, linear_weights, box_lower_constraints, box_upper_constraints, eq_matrix, eq_bounds, neq_matrix, neq_lower_bounds, neq_upper_bounds, benchmark=False)"
        )
        print(testcase)

    # @property
    # def num_non_constraints(self) -> int:
    #     return (
    #         len(self.quadratic_weights)
    #         - self.num_eq_constraints
    #         - self.num_neq_constraints
    #     )

    def pretty_print_problem(self):
        print("QP data")
        large = int(1e10)
        if self.quadratic_weights is not None:
            print(
                f"H (quadratic_weights): \n{np.array2string(self.quadratic_weights, max_line_width=large)}"
            )
        if self.linear_weights is not None:
            print(
                f"g (linear_weights): \n{np.array2string(self.linear_weights, max_line_width=large)})"
            )

        if self.box_lower_constraints is not None:
            print(
                f"lb (box_lower_constraints): \n{np.array2string(self.box_lower_constraints, max_line_width=large)}"
            )
        if self.box_upper_constraints is not None:
            print(
                f"ub (box_upper_constraints): \n{np.array2string(self.box_upper_constraints, max_line_width=large)}"
            )

        if self.eq_matrix is not None:
            try:
                print(
                    f"E (eq_matrix): \n{np.array2string(self.eq_matrix.toarray(), max_line_width=large)}"
                )
            except:
                print(
                    f"E (eq_matrix): \n{np.array2string(self.eq_matrix, max_line_width=large)}"
                )
        if self.eq_bounds is not None:
            print(
                f"bE (eq_bounds): \n{np.array2string(self.eq_bounds, max_line_width=large)}"
            )

        if self.neq_matrix is not None:
            try:
                print(
                    f"A (neq_matrix): \n{np.array2string(self.neq_matrix.toarray(), max_line_width=large)}"
                )
            except:
                print(
                    f"A (neq_matrix): \n{np.array2string(self.neq_matrix, max_line_width=large)}"
                )
        if self.neq_lower_bounds is not None:
            print(
                f"lbA (neq_lower_bounds): \n{np.array2string(self.neq_lower_bounds, max_line_width=large)}"
            )
        if self.neq_upper_bounds is not None:
            print(
                f"ubA (neq_upper_bounds): \n{np.array2string(self.neq_upper_bounds, max_line_width=large)}"
            )

    def analyze_well_posedness(self):
        """
        Analyzes the QP problem data for numerical issues and poor posing.
        Prints statistics and warnings for potentially ill-posed problems.
        """
        print("--- QP Well-Posedness Analysis ---")
        self._analyze_hessian()
        self._analyze_constraints()
        print("----------------------------------")

    def _analyze_hessian(self):
        """
        Checks the condition number of the Hessian.
        """
        if self.quadratic_weights is not None:
            max_weight = np.max(np.abs(self.quadratic_weights))
            min_weight = np.min(
                np.abs(self.quadratic_weights)[np.abs(self.quadratic_weights) > 0]
            )
            condition_number = max_weight / min_weight
            print(f"  Weight Matrix max singular value: {max_weight}")
            print(f"  Weight Matrix min singular value: {min_weight}")
            print(f"  Weight Matrix Condition Number: {condition_number}")
            if condition_number > 1_000:
                print("  Warning: Weight Matrix is poorly conditioned.")

    def _analyze_constraints(self):
        """
        Checks for scale imbalances and potential rank issues in constraints.
        """
        self._check_matrix_condition(self.eq_matrix, "Equality Constraint Matrix (E)")
        self._check_matrix_condition(
            self.neq_matrix, "Inequality Constraint Matrix (A)"
        )

        # Simple infeasibility check for box constraints
        if (
            self.box_lower_constraints is not None
            and self.box_upper_constraints is not None
        ):
            violations = self.box_lower_constraints > self.box_upper_constraints
            if np.any(violations):
                print(
                    f"  WARNING: Box constraints are infeasible for indices {np.where(violations)[0]}."
                )

    def _check_matrix_condition(
        self, matrix: Union[sp.csc_matrix, np.ndarray], name: str
    ):
        if issparse(matrix):
            matrix = matrix.toarray()
        if matrix.shape[0] * matrix.shape[1] == 0:
            print(f"  {name} is empty.")
            return
        singular_value_decomposition = np.linalg.svd(matrix, compute_uv=False)
        condition_number = (
            singular_value_decomposition[0] / singular_value_decomposition[-1]
        )
        print(f"  {name} max singular value: {singular_value_decomposition[0]}")
        print(f"  {name} min singular value: {singular_value_decomposition[-1]}")
        print(f"  {name} Condition Number: {condition_number}")
        if condition_number > 1_000:
            print(f"        WARNING: this is very large.")

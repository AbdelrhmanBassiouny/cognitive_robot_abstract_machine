from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from line_profiler.explicit_profiler import profile

from giskardpy.qp.qp_data import QPDataExplicit

if TYPE_CHECKING:
    pass
from enum import IntEnum

import numpy as np

from giskardpy.qp.solvers.qp_solver import QPSolver

import qpSWIFT_sparse_bindings as qpSWIFT


class QPSWIFTExitFlags(IntEnum):
    Optimal = 0  # Solution Found
    KKT_Failure = 1  # Failure in factorising KKT matrix
    MAX_ITER_REACHED = 2  # Maximum Number of Iterations Reached
    ERROR = 3  # Unknown Problem in Solver
    INFEASIBLE = 4  # Unknown Problem in Solver


@dataclass
class QPSolverQPSwift(QPSolver[QPDataExplicit]):
    """
    min_x 0.5 x^T P x + c^T x
    s.t.  Ax = b
          Gx <= h
    """

    ignore_fail: bool = False

    opts = {
        "OUTPUT": 1,  # 0 = sol; 1 = sol + basicInfo; 2 = sol + basicInfo + advInfo
        "MAXITER": 100,  # 0 < MAXITER < 200; default 100. maximum number of iterations needed
        # 'ABSTOL': 9e-4,  # 0 < ABSTOL < 1; default 1e-6. absolute tolerance
        "RELTOL": 3.5e-5,  # 0 < RELTOL < 1; default 1e-6. relative tolerance
        # 'SIGMA': 0.01,  # default 100. maximum centering allowed
        "VERBOSE": 0,  # 0 = no print; 1 = print
        "CheckInfeasibility": 1,
    }

    @profile
    def solver_call_explicit_interface(self, qp_data: QPDataExplicit) -> np.ndarray:
        result = qpSWIFT.solve_sparse_H_diag(
            H=qp_data.quadratic_weights,
            g=qp_data.linear_weights,
            lb=qp_data.box_lower_constraints,
            ub=qp_data.box_upper_constraints,
            E=qp_data.eq_matrix,
            b=qp_data.eq_bounds,
            A=qp_data.neq_matrix,
            lbA=qp_data.neq_lower_bounds,
            ubA=qp_data.neq_upper_bounds,
            options=self.opts,
        )
        exit_flag = result.exit_flag
        # print(result)
        # if not self.ignore_fail:
        #     if exit_flag == 4:
        #         # print(":((")
        #
        #         error_code = QPSWIFTExitFlags(exit_flag)
        #         if error_code == QPSWIFTExitFlags.INFEASIBLE:
        #             raise InfeasibleException(f"Failed to solve qp: {str(error_code)}")
        #         raise QPSolverException(f"Failed to solve qp: {str(error_code)}")
        return result.x

    solver_call = solver_call_explicit_interface

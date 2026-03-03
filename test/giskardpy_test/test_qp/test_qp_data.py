import numpy as np
import scipy.sparse as sp
from giskardpy.qp.qp_data import QPData, Conditioning
from giskardpy.qp.solvers.qp_solver_qpSWIFT import QPSolverQPSwift


def test_qp_data():
    """
    min_{x1, x2} x1^2 + x2^2
    s.t.
        -inf <= x1 <= inf
        -inf <= x2 <= inf
        -inf <= x1 + x2 <= -0.5
    """
    qp_data = QPData(
        quadratic_weights=np.array([1.0, 1.0]),
        linear_weights=np.array([0.0, 0.0]),
        box_lower_constraints=np.array([-np.inf, -np.inf]),
        box_upper_constraints=np.array([np.inf, np.inf]),
        eq_matrix=sp.csc_matrix(np.zeros((0, 2))),
        eq_bounds=np.array([]),
        neq_matrix=sp.csc_matrix(np.array([[1.0, 1.0]])),
        neq_lower_bounds=np.array([-np.inf]),
        neq_upper_bounds=np.array([-0.5]),
    )
    qp_solver = QPSolverQPSwift()
    result = qp_solver.solver_call(qp_data)
    expected = np.array([-0.25, -0.25])
    assert np.allclose(result, expected)

    conditioning = Conditioning(C=np.diag([69.0, 23.0]))
    conditioned_qp_data = conditioning.apply(qp_data)
    conditioned_result = qp_solver.solver_call(conditioned_qp_data)
    result = conditioning.unapply(conditioned_result)
    assert np.allclose(result, expected)

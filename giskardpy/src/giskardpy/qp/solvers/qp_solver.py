from __future__ import annotations

from dataclasses import dataclass
from typing import Type

import numpy as np
from typing_extensions import ClassVar, TypeVar, Generic, get_args

from giskardpy.qp.qp_data import QPDataExplicit, QPDataTwoSidedInequality
from giskardpy.qp.solvers.qp_solver_ids import SupportedQPSolver

T = TypeVar("T", QPDataExplicit, QPDataTwoSidedInequality)


@dataclass
class QPSolver(Generic[T]):
    solver_id: ClassVar[SupportedQPSolver]

    @classmethod
    @property
    def qp_data_type(cls) -> Type[T]:
        """
        The semDT type for which this converter handles conversion.
        """
        return get_args(cls.__orig_bases__[0])[0]

    def get_factory(self):
        return None

    def solver_call(self, qp_data: T) -> np.ndarray:
        raise NotImplementedError()

    def solver_call_explicit_interface(self, qp_data: QPDataExplicit) -> np.ndarray:
        """
        min_x 0.5 x^T H x + g^T x
        s.t.  lb <= x <= ub     (box constraints)
                   Ex <= bE     (equality constraints)
            lbA <= Ax <= ubA    (lower/upper inequality constraints)
        """
        raise NotImplementedError()

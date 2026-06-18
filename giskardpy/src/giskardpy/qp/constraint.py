"""
Decision-variable limits and constraint enforcement strategies for the QP controller.

Defines the box limits and weights of the QP decision variables (:class:`DirectLimits`,
:class:`DofLimits`, :class:`DofLimitProfiler`), the strategies that turn high level constraints
into QP matrix rows, slack columns, and bounds (:class:`EnforcementStrategy` and subclasses), and
the constraint description classes (:class:`GiskardConstraint` and subclasses).
"""

from __future__ import annotations

import logging
from abc import ABC
from abc import abstractmethod
from copy import copy
from dataclasses import dataclass, field
from itertools import product
from typing import List, TYPE_CHECKING, Type
from uuid import UUID

import giskardpy.utils.math as gm
import krrood.symbolic_math.symbolic_math as sm
import numpy as np
from giskardpy.motion_statechart.data_types import FloatEnum
from giskardpy.qp.exceptions import (
    InfeasibleException,
    MismatchedLimitLengthsError,
    VelocityLimitUnreachableException,
)
from giskardpy.qp.pos_in_vel_limits import (
    shifted_velocity_profile,
    compute_slowdown_asap_vel_profile,
)
from giskardpy.qp.solvers.qp_solver import QPSolver
from giskardpy.utils.math import mpc
from krrood.symbolic_math.symbolic_math import Vector, Matrix, Scalar, FloatVariable
from semantic_digital_twin.spatial_types.derivatives import Derivatives, DerivativeMap
from semantic_digital_twin.world_description.degree_of_freedom import DegreeOfFreedom
from semantic_digital_twin.world_description.degree_of_freedom import (
    DegreeOfFreedomLimits,
)
from typing_extensions import Callable

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from giskardpy.qp.qp_controller_config import QPControllerConfig


LargeNumber = 1e4


def normalize_slack_weight(
    weight: Scalar,
    normalization_factor: float,
    control_horizon: int = 1,
) -> Scalar:
    """
    Scales a slack weight so constraints with different units become comparable.
    The control horizon spreads the weight over the time steps a constraint is active.
    """
    return weight * (1 / (sm.Scalar(normalization_factor) ** 2 * control_horizon))


def max_velocity_from_horizon_and_jerk_qp(
    prediction_horizon: int,
    vel_limit: float,
    acc_limit: float,
    jerk_limit: float,
    dt: float,
    max_derivative: Derivatives,
    solver_class: Type[QPSolver],
):
    """
    Computes the highest velocity reachable within the prediction horizon under the given
    acceleration and jerk limits, by solving an MPC that maximizes velocity without a binding
    velocity limit.
    """
    upper_limits = (
        (vel_limit,) * prediction_horizon,
        (acc_limit,) * prediction_horizon,
        (jerk_limit,) * prediction_horizon,
    )
    lower_limits = (
        (-vel_limit,) * prediction_horizon,
        (-acc_limit,) * prediction_horizon,
        (-jerk_limit,) * prediction_horizon,
    )
    return mpc(
        upper_limits=upper_limits,
        lower_limits=lower_limits,
        current_values=(0, 0),
        dt=dt,
        ph=prediction_horizon,
        q_weight=(0, 0, 0),
        lin_weight=(-1, 0, 0),
        solver_class=solver_class,
        link_to_current_vel=False,
    )


@dataclass
class DirectLimits:
    """
    Represents weights and limits of decision variables in a QP.
    All fields must have the same length.
    """

    lower_bounds: sm.Vector
    """
    Lower box limit of each decision variable.
    """

    upper_bounds: sm.Vector
    """
    Upper box limit of each decision variable.
    """

    quadratic_weights: sm.Vector
    """
    Quadratic objective weight of each decision variable.
    """

    linear_weights: sm.Vector
    """
    Linear objective weight of each decision variable.
    """

    names: list[str]
    """
    Human readable name of each decision variable, used for debugging.
    """

    def __post_init__(self):
        """
        Ensures all bound, weight, and name fields describe the same number of decision variables.
        """
        lengths = {
            "lower_bounds": self.lower_bounds.shape[0],
            "upper_bounds": self.upper_bounds.shape[0],
            "quadratic_weights": self.quadratic_weights.shape[0],
            "linear_weights": self.linear_weights.shape[0],
            "names": len(self.names),
        }
        if len(set(lengths.values())) > 1:
            raise MismatchedLimitLengthsError(
                f"All DirectLimits fields must have the same length, got {lengths}."
            )

    @classmethod
    def empty(cls) -> DirectLimits:
        """
        Creates a DirectLimits without any decision variables.
        """
        return cls(
            lower_bounds=sm.Vector([]),
            upper_bounds=sm.Vector([]),
            quadratic_weights=sm.Vector([]),
            linear_weights=sm.Vector([]),
            names=[],
        )


@dataclass
class DofLimitProfiler:
    """
    Computes the per-degree-of-freedom velocity, acceleration, and jerk bounds across the
    prediction horizon, including the MPC-based position-aware slowdown profiles.
    """

    config: QPControllerConfig
    """
    Controller configuration providing horizon length, time step, and solver.
    """

    def _compute_position_constrained_velocity_bounds(
        self,
        dof_symbols: DerivativeMap[FloatVariable],
        lower_limits: DerivativeMap[float],
        upper_limits: DerivativeMap[float],
        solver_class: Type[QPSolver],
        time_step: float,
        prediction_horizon: int,
    ) -> tuple[sm.Vector, sm.Vector, sm.Vector, sm.Scalar]:
        """
        Computes per-step velocity bounds that keep the degree of freedom within its position
        limits, slowing it down early enough to stop before a limit is reached.
        Returns the lower and upper velocity bounds, a goal velocity profile, and a flag marking
        when the first step is already at rest against a limit.
        """
        velocity_limit = upper_limits.velocity
        if lower_limits.position is None:
            velocity_upper_bound = sm.Vector.ones(prediction_horizon) * velocity_limit
            velocity_lower_bound = -velocity_upper_bound
            goal_profile = sm.Vector.zeros(prediction_horizon)
            skip_first = sm.Scalar.const_false()
            return velocity_lower_bound, velocity_upper_bound, goal_profile, skip_first

        acceleration_limit = upper_limits.acceleration
        jerk_limit = upper_limits.jerk
        position_range = upper_limits.position - lower_limits.position
        velocity_limit = min(velocity_limit * time_step, position_range / 2) / time_step
        profile = gm.simple_mpc(
            vel_limit=velocity_limit,
            acc_limit=acceleration_limit,
            jerk_limit=jerk_limit,
            current_vel=velocity_limit,
            current_acc=0,
            dt=time_step,
            ph=prediction_horizon,
            q_weight=(0, 0, 0),
            lin_weight=(-1, 0, 0),
            solver_class=solver_class,
        )
        mpc_velocity_profile = profile[:prediction_horizon]
        mpc_acceleration_profile = profile[prediction_horizon : prediction_horizon * 2]
        position_error_lower_bound = lower_limits.position - dof_symbols.position
        position_error_upper_bound = upper_limits.position - dof_symbols.position
        velocity_lower_bound, _ = shifted_velocity_profile(
            vel_profile=mpc_velocity_profile,
            acc_profile=mpc_acceleration_profile,
            distance=-position_error_lower_bound,
            dt=time_step,
        )
        velocity_lower_bound *= -1
        velocity_upper_bound, _ = shifted_velocity_profile(
            vel_profile=mpc_velocity_profile,
            acc_profile=mpc_acceleration_profile,
            distance=position_error_upper_bound,
            dt=time_step,
        )
        one_step_change = jerk_limit * time_step**2
        one_step_change_lower_bound = sm.min(
            sm.max(Scalar(0), position_error_lower_bound / time_step),
            Scalar(one_step_change),
        )
        one_step_change_lower_bound = sm.limit(
            one_step_change_lower_bound, -velocity_limit, velocity_limit
        )
        one_step_change_upper_bound = sm.max(
            sm.min(Scalar(0), position_error_upper_bound / time_step),
            -Scalar(one_step_change),
        )
        one_step_change_upper_bound = sm.limit(
            one_step_change_upper_bound, -velocity_limit, velocity_limit
        )
        velocity_lower_bound[0] = sm.if_greater(
            position_error_lower_bound,
            0,
            one_step_change_lower_bound,
            copy(velocity_lower_bound[0]),
        )
        velocity_upper_bound[0] = sm.if_less(
            position_error_upper_bound,
            0,
            one_step_change_upper_bound,
            copy(velocity_upper_bound[0]),
        )
        goal_profile = sm.max(velocity_lower_bound, 0) + sm.min(velocity_upper_bound, 0)
        skip_first = sm.logic_or(
            velocity_lower_bound[0] >= 0, velocity_upper_bound[0] <= 0
        )
        return velocity_lower_bound, velocity_upper_bound, goal_profile, skip_first

    def compute_horizon_bounds(
        self,
        dof_symbols: DerivativeMap[FloatVariable],
        lower_limits: DerivativeMap[float],
        upper_limits: DerivativeMap[float],
        solver_class: Type[QPSolver],
        time_step: float,
        prediction_horizon: int,
        epsilon: float = 0.00001,
    ) -> DegreeOfFreedomLimits[sm.Vector]:
        """
        Computes the velocity, acceleration, and jerk bounds for one degree of freedom across the
        whole prediction horizon, relaxing the jerk limit on the first steps when the position
        goal would otherwise be unreachable.
        """
        jerk_limit = upper_limits.jerk
        acceleration_limit = upper_limits.acceleration

        velocity_lower_bound, velocity_upper_bound, goal_profile, skip_first = (
            self._compute_position_constrained_velocity_bounds(
                dof_symbols=dof_symbols,
                lower_limits=lower_limits,
                upper_limits=upper_limits,
                solver_class=solver_class,
                time_step=time_step,
                prediction_horizon=prediction_horizon,
            )
        )

        acceleration_profile = (
            sm.Vector.ones(velocity_upper_bound.shape[0]) * acceleration_limit
        )
        jerk_profile = sm.Vector.ones(velocity_upper_bound.shape[0]) * jerk_limit

        projected_velocity_profile, _, _ = compute_slowdown_asap_vel_profile(
            dof_symbols.velocity,
            dof_symbols.acceleration,
            goal_profile,
            Scalar(jerk_limit),
            Scalar(time_step),
            prediction_horizon,
            skip_first,
        )
        _, _, projected_jerk_profile_violated = compute_slowdown_asap_vel_profile(
            dof_symbols.velocity,
            dof_symbols.acceleration,
            goal_profile,
            Scalar(np.inf),
            Scalar(time_step),
            prediction_horizon,
            skip_first,
        )
        velocity_lower_bound_violated = sm.logic_or(
            sm.logic_any(projected_velocity_profile < velocity_lower_bound - epsilon),
            sm.abs(projected_velocity_profile[-1]) >= epsilon,
        )
        velocity_upper_bound_violated = sm.logic_or(
            sm.logic_any(projected_velocity_profile > velocity_upper_bound + epsilon),
            sm.abs(projected_velocity_profile[-1]) >= epsilon,
        )
        needs_relaxed_jerk_limits = sm.logic_or(
            velocity_lower_bound_violated, velocity_upper_bound_violated
        )
        jerk_profile[0] = sm.if_else(
            needs_relaxed_jerk_limits,
            sm.max(Scalar(jerk_limit), sm.abs(projected_jerk_profile_violated[0])),
            sm.Scalar(jerk_limit),
        )
        jerk_profile[1] = sm.if_else(
            needs_relaxed_jerk_limits,
            sm.max(Scalar(jerk_limit), sm.abs(projected_jerk_profile_violated[1])),
            sm.Scalar(jerk_limit),
        )
        jerk_profile[2] = sm.if_else(
            needs_relaxed_jerk_limits,
            sm.max(Scalar(jerk_limit), sm.abs(projected_jerk_profile_violated[2])),
            sm.Scalar(jerk_limit),
        )

        velocity_lower_bound = sm.min(velocity_lower_bound, velocity_upper_bound)
        velocity_upper_bound = sm.max(velocity_lower_bound, velocity_upper_bound)
        acceleration_lower_bounds = -acceleration_profile
        acceleration_upper_bounds = acceleration_profile
        jerk_lower_bounds = sm.min(jerk_profile, -jerk_profile) * time_step**2
        jerk_upper_bounds = sm.max(jerk_profile, jerk_profile) * time_step**2
        return DegreeOfFreedomLimits[sm.Vector](
            lower=DerivativeMap(
                velocity=velocity_lower_bound,
                acceleration=acceleration_lower_bounds,
                jerk=jerk_lower_bounds,
            ),
            upper=DerivativeMap(
                velocity=velocity_upper_bound,
                acceleration=acceleration_upper_bounds,
                jerk=jerk_upper_bounds,
            ),
        )

    def find_best_jerk_limit(
        self,
        prediction_horizon: int,
        time_step: float,
        target_velocity_limit: float,
        solver_class: Type[QPSolver],
        almost_equal_threshold: float = 0.0001,
    ) -> float:
        """
        Finds the jerk limit under which the controller just barely reaches the target velocity
        within the prediction horizon.
        :param target_velocity_limit: The velocity limit that should be reachable.
        :return: The jerk limit that achieves target_velocity_limit.
        """
        jerk_limit = (4 * target_velocity_limit) / time_step**2
        upper_bound = jerk_limit
        lower_bound = 0
        best_vel_limit = 0
        best_jerk_limit = 0
        i = -1
        for i in range(100):
            vel_limit = max_velocity_from_horizon_and_jerk_qp(
                prediction_horizon=prediction_horizon,
                vel_limit=1000,
                acc_limit=np.inf,
                jerk_limit=jerk_limit,
                dt=time_step,
                max_derivative=Derivatives.jerk,
                solver_class=solver_class,
            )[0]
            if abs(vel_limit - target_velocity_limit) < abs(
                best_vel_limit - target_velocity_limit
            ):
                best_vel_limit = vel_limit
                best_jerk_limit = jerk_limit
            if abs(vel_limit - target_velocity_limit) < almost_equal_threshold:
                break
            if vel_limit > target_velocity_limit:
                upper_bound = jerk_limit
                jerk_limit = round((jerk_limit + lower_bound) / 2, 4)
            else:
                lower_bound = jerk_limit
                jerk_limit = round((jerk_limit + upper_bound) / 2, 4)
        logger.debug(
            f"best velocity limit: {best_vel_limit} "
            f"(target = {target_velocity_limit}) with jerk limit: {best_jerk_limit} after {i + 1} iterations"
        )
        return best_jerk_limit

    def compute(
        self,
        degree_of_freedom: DegreeOfFreedom,
        max_derivative: Derivatives,
    ) -> DegreeOfFreedomLimits[sm.Vector]:
        """
        Computes the horizon bounds for a single degree of freedom, filling in missing
        acceleration and jerk limits and raising when its velocity limit is unreachable.
        """
        config = self.config
        lower_limits = DerivativeMap()
        upper_limits = DerivativeMap()

        # %% pos limits
        if not degree_of_freedom.has_position_limits():
            lower_limits.position = upper_limits.position = None
        else:
            lower_limits.position = degree_of_freedom.limits.lower.position
            upper_limits.position = degree_of_freedom.limits.upper.position

        # %% vel limits
        lower_limits.velocity = degree_of_freedom.limits.lower.velocity
        upper_limits.velocity = degree_of_freedom.limits.upper.velocity
        if config.prediction_horizon == 1:
            raise NotImplementedError("tell ichumuh you actually need this")

        # %% acc limits
        if degree_of_freedom.limits.lower.acceleration is None:
            lower_limits.acceleration = -np.inf
        else:
            lower_limits.acceleration = degree_of_freedom.limits.lower.acceleration
        if degree_of_freedom.limits.upper.acceleration is None:
            upper_limits.acceleration = np.inf
        else:
            upper_limits.acceleration = degree_of_freedom.limits.upper.acceleration

        # %% jerk limits
        if upper_limits.jerk is None:
            upper_limits.jerk = self.find_best_jerk_limit(
                config.prediction_horizon,
                config.mpc_dt,
                upper_limits.velocity,
                solver_class=config.qp_solver_class,
            )
            lower_limits.jerk = -upper_limits.jerk
        else:
            upper_limits.jerk = degree_of_freedom.limits.upper.jerk
            lower_limits.jerk = degree_of_freedom.limits.lower.jerk

        try:
            return self.compute_horizon_bounds(
                dof_symbols=degree_of_freedom.variables,
                lower_limits=lower_limits,
                upper_limits=upper_limits,
                solver_class=config.qp_solver_class,
                time_step=config.mpc_dt,
                prediction_horizon=config.prediction_horizon,
            )
        except InfeasibleException as e:
            max_reachable_vel = max_velocity_from_horizon_and_jerk_qp(
                prediction_horizon=config.prediction_horizon,
                vel_limit=100,
                acc_limit=upper_limits.acceleration,
                jerk_limit=upper_limits.jerk,
                dt=config.mpc_dt,
                max_derivative=max_derivative,
                solver_class=config.qp_solver_class,
            )[0]
            if max_reachable_vel < upper_limits.velocity:
                error_msg = (
                    f'Free variable "{degree_of_freedom.name}" can\'t reach velocity limit of "{upper_limits.velocity}". '
                    f'Maximum reachable with prediction horizon = "{config.prediction_horizon}", '
                    f'jerk limit = "{upper_limits.jerk}" and dt = "{config.mpc_dt}" is "{max_reachable_vel}".'
                )
                logger.error(error_msg)
                raise VelocityLimitUnreachableException(error_msg)
            else:
                raise


@dataclass
class DofLimits:
    """
    Builds a :class:`DirectLimits` holding the bounds and weights of the robot's free variables
    (velocity and jerk decision variables across the prediction horizon).
    """

    @classmethod
    def create(
        cls,
        degrees_of_freedom: List[DegreeOfFreedom],
        config: QPControllerConfig,
    ) -> DirectLimits:
        """
        Builds the :class:`DirectLimits` for the given degrees of freedom and configuration.
        """
        self = cls()
        lower_bounds, upper_bounds = self.free_variable_bounds(
            degrees_of_freedom, config
        )
        quadratic_weights, linear_weights = self.init_weights(
            degrees_of_freedom, config
        )
        return DirectLimits(
            lower_bounds=lower_bounds,
            upper_bounds=upper_bounds,
            quadratic_weights=quadratic_weights,
            linear_weights=linear_weights,
            names=self.make_names(degrees_of_freedom, config),
        )

    def active_slots(
        self,
        degrees_of_freedom: List[DegreeOfFreedom],
        config: QPControllerConfig,
    ):
        """
        Yields every active decision variable slot as a ``(derivative, time_step, dof)`` tuple.
        The order defines the layout shared by bounds, weights, and names so they stay aligned.
        """
        max_derivative = config.max_derivative
        for derivative, time_step in product(
            [Derivatives.velocity, Derivatives.jerk],
            range(config.prediction_horizon),
        ):
            if time_step >= config.prediction_horizon - (max_derivative - derivative):
                continue
            for degree_of_freedom in degrees_of_freedom:
                yield derivative, time_step, degree_of_freedom

    def make_names(
        self, degrees_of_freedom: List[DegreeOfFreedom], config: QPControllerConfig
    ) -> list[str]:
        """
        Creates a debug name for every free variable slot.
        """
        short_label = {Derivatives.velocity: "vel", Derivatives.jerk: "jerk"}
        return [
            f"{dof.name}_{short_label[derivative]}_k_{time_step}"
            for derivative, time_step, dof in self.active_slots(
                degrees_of_freedom, config
            )
        ]

    def free_variable_bounds(
        self,
        degrees_of_freedom: list[DegreeOfFreedom],
        config: QPControllerConfig,
    ) -> tuple[sm.Vector, sm.Vector]:
        """
        Computes the lower and upper box limits of every free variable slot.
        """
        max_derivative = config.max_derivative
        lower_bounds = []
        upper_bounds = []
        profiler = DofLimitProfiler(config)
        cache: dict[UUID, DegreeOfFreedomLimits[sm.Vector]] = {}
        for degree_of_freedom in degrees_of_freedom:
            cache[degree_of_freedom.id] = profiler.compute(
                degree_of_freedom=degree_of_freedom,
                max_derivative=max_derivative,
            )
        for derivative, t, degree_of_freedom in self.active_slots(
            degrees_of_freedom, config
        ):
            lower_bounds.append(cache[degree_of_freedom.id].lower[derivative][t])
            upper_bounds.append(cache[degree_of_freedom.id].upper[derivative][t])

        return sm.Vector(lower_bounds), sm.Vector(upper_bounds)

    def init_weights(
        self,
        degrees_of_freedom: list[DegreeOfFreedom],
        config: QPControllerConfig,
    ) -> tuple[sm.Vector, sm.Vector]:
        """
        Computes the quadratic and linear objective weights of every free variable slot.
        """
        quadratic_weights = []
        for derivative, t, degree_of_freedom in self.active_slots(
            degrees_of_freedom, config
        ):
            normalized_weight = self.normalize_dof_weight(
                limit=degree_of_freedom.limits.upper[derivative],
                base_weight=config.get_dof_weight(degree_of_freedom.name, derivative),
                t=t,
                horizon=config.prediction_horizon - 3,
                alpha=config.horizon_weight_gain_scalar,
            )
            quadratic_weights.append(normalized_weight)
        return sm.Vector(quadratic_weights), sm.Vector.zeros(len(quadratic_weights))

    def normalize_dof_weight(
        self,
        limit: float | None,
        base_weight: float,
        t: int,
        horizon: int,
        alpha: float,
    ) -> sm.Scalar:
        """
        Scales a free variable weight by its limit so derivatives become comparable, and ramps it
        over the horizon so later time steps are penalized more.
        """

        def linear(x_in: float, weight: float, h: int, alpha: float) -> float:
            start = weight * alpha
            a = (weight - start) / h
            return a * x_in + start

        if limit is None:
            return 0.0
        weight = linear(t, base_weight, horizon, alpha)

        return weight * (1 / limit) ** 2


@dataclass
class EnforcementStrategy(ABC):
    """
    Turns a block of constraints into the QP building blocks that enforce them: the constraint
    matrix over the free variables, the slack columns and their limits, the bounds, and the row
    names. Subclasses define how a constraint is mapped onto the prediction horizon.
    """

    degrees_of_freedom: list[DegreeOfFreedom]
    """
    Free variables of the robot the constraints act on.
    """

    constraints: list[GiskardConstraint]
    """
    Constraints enforced by this strategy.
    """

    config: QPControllerConfig
    """
    Controller configuration providing horizon length and time step.
    """

    @abstractmethod
    def create_matrix(self) -> Matrix:
        """
        Builds the constraint matrix mapping the free variables onto the constraint rows.
        """
        ...

    @abstractmethod
    def create_slack_matrix(self) -> Matrix:
        """
        Builds the matrix coupling the slack variables to the constraint rows.
        """
        ...

    @abstractmethod
    def create_names(self) -> list[str]:
        """
        Creates a debug name for every constraint row.
        """
        ...

    @abstractmethod
    def create_slack_variables(self) -> DirectLimits:
        """
        Creates the limits and weights of the slack variables introduced by this strategy.
        """
        ...

    @abstractmethod
    def create_bounds(
        self, bounds_getter: Callable[GiskardConstraint, Scalar]
    ) -> Vector:
        """
        Builds the constraint bounds, reading the relevant bound of each constraint via the getter.
        """
        ...

    def create_lower_bounds(self) -> Vector:
        """
        Builds the lower bounds of the inequality constraints.
        """
        for c in self.constraints:
            assert isinstance(c, GiskardInequalityConstraint)
        return self.create_bounds(lambda c: c.lower_bound)

    def create_upper_bounds(self) -> Vector:
        """
        Builds the upper bounds of the inequality constraints.
        """
        for c in self.constraints:
            assert isinstance(c, GiskardInequalityConstraint)
        return self.create_bounds(lambda c: c.upper_bound)

    def create_equality_bounds(self) -> Vector:
        """
        Builds the bounds of the equality constraints.
        """
        for c in self.constraints:
            assert isinstance(c, GiskardEqualityConstraint)
        return self.create_bounds(lambda c: c.bound)

    @property
    def number_of_free_variables(self) -> int:
        """
        Number of degrees of freedom controlled by this strategy.
        """
        return len(self.degrees_of_freedom)

    @property
    def number_of_velocity_columns(self) -> int:
        """
        Number of velocity decision variable columns across the horizon.
        """
        return self.number_of_free_variables * (self.config.prediction_horizon - 2)

    @property
    def number_of_jerk_columns(self) -> int:
        """
        Number of jerk decision variable columns across the horizon.
        """
        return self.number_of_free_variables * self.config.prediction_horizon

    @property
    def position_variables(self) -> Vector:
        """
        Symbolic position variables of the degrees of freedom.
        """
        return Vector([dof.variables.position for dof in self.degrees_of_freedom])

    @property
    def velocity_variables(self) -> Vector:
        """
        Symbolic velocity variables of the degrees of freedom.
        """
        return Vector([dof.variables.velocity for dof in self.degrees_of_freedom])

    @property
    def acceleration_variables(self) -> Vector:
        """
        Symbolic acceleration variables of the degrees of freedom.
        """
        return Vector([dof.variables.acceleration for dof in self.degrees_of_freedom])


@dataclass
class IntegralStrategy(EnforcementStrategy):
    """
    Enforces a constraint on the integral of an expression's derivative over the prediction
    horizon, so a single row covers the whole horizon.

    Equality constraints have the form:
    .. math::
        f(q) = b

    where

    .. math::

        target - f = \\Delta t \\  \\sum_{k=0}^{N-3} J_{f} + \\Delta t \\epsilon

    ::

        |   k1   |   k2   |   k1   |   k2   |   k1   |   k2   | prediction horizon
        |v1 v2 v3|v1 v2 v3|j1 j2 j3|j1 j2 j3|   eps  |   eps  | free variables / slack
        |--------+--------+--------+--------+--------+--------|
        |  J1*dt |  J1*dt |  J3*dt | J3*dt  |   dt   |   dt   |
        |-----------------------------------------------------|
    """

    def create_matrix(self) -> Matrix:
        """
        Builds the constraint matrix by repeating the expression jacobian across the velocity
        horizon and padding the jerk columns with zeros.
        """
        if len(self.constraints) == 0:
            return sm.Matrix()
        jacobian = (
            sm.Vector([c.expression for c in self.constraints]).jacobian(
                variables=self.position_variables
            )
            * self.config.mpc_dt
        )
        return sm.hstack(
            [jacobian for _ in range(self.config.control_horizon)]
            + [sm.Matrix.zeros(jacobian.shape[0], self.number_of_jerk_columns)]
        )

    def create_slack_matrix(self) -> Matrix:
        """
        Builds the diagonal slack matrix with one slack variable per constraint.
        """
        if len(self.constraints) == 0:
            return sm.Matrix()
        return sm.Matrix.diag([self.config.mpc_dt for _ in self.constraints])

    def create_slack_variables(self) -> DirectLimits:
        """
        Creates one slack variable per constraint with normalized weights.
        """
        number_of_slack_variables = len(self.constraints)
        return DirectLimits(
            lower_bounds=Vector([-LargeNumber] * number_of_slack_variables),
            upper_bounds=Vector([LargeNumber] * number_of_slack_variables),
            quadratic_weights=Vector(
                [
                    normalize_slack_weight(
                        c.quadratic_weight,
                        c.normalization_factor,
                        self.config.control_horizon,
                    )
                    for c in self.constraints
                ]
            ),
            linear_weights=Vector(
                [
                    normalize_slack_weight(
                        c.linear_weight,
                        c.normalization_factor,
                        self.config.control_horizon,
                    )
                    for c in self.constraints
                ]
            ),
            names=[c.name for c in self.constraints],
        )

    def _apply_cap(
        self,
        value: Scalar,
        dt: float,
        normalization_number: float,
        control_horizon: int,
    ) -> Scalar:
        """
        Clamps a bound to the largest change reachable within the control horizon.
        """
        # todo normalization with jacobian???
        return sm.limit(
            value,
            -normalization_number * dt * control_horizon,
            normalization_number * dt * control_horizon,
        )

    def capped_bound(
        self,
        equality_bound: Scalar,
        dt: float,
        normalization_number: float,
        control_horizon: int,
    ) -> Scalar:
        """
        Returns the bound capped to what is reachable within the control horizon.
        """
        return self._apply_cap(
            equality_bound, dt, normalization_number, control_horizon
        )

    def create_bounds(
        self, bounds_getter: Callable[GiskardConstraint, Scalar]
    ) -> Vector:
        """
        Builds the capped bounds, one per constraint.
        """
        return Vector(
            [
                self.capped_bound(
                    bounds_getter(c),
                    self.config.mpc_dt,
                    c.normalization_factor,
                    self.config.control_horizon,
                )
                for c in self.constraints
            ]
        )

    def create_names(self) -> list[str]:
        """
        Returns the constraint names, one row per constraint.
        """
        return [c.name for c in self.constraints]


@dataclass
class VelocityStrategy(EnforcementStrategy):
    """
    The constraint will be applied to the derivative of the expression.
    Position constraints are implemented by constraining the integral of the expressions' derivative over a prediction horizon.
    All other constraints are applied directly to that derivative of the expression.
    As a result, position constraints are cheaper, as they only require a single constraint.

    Equality constraints have the form:
    .. math::
        f(q) = b

    where

    .. math::

        target - f = \\Delta t \\ \\sum_{k=0}^{N-1} J_{f}

    ::

        |   t1   |   t2   |   t3   |   t1   |   t2   |   t3   |   t1   |   t2   |   t3   | prediction horizon
        |v1 v2 v3|v1 v2 v3|v1 v2 v3|a1 a2 a3|a1 a2 a3|a1 a2 a3|j1 j2 j3|j1 j2 j3|j1 j2 j3| free variables
        |--------------------------------------------------------------------------------|
        |  Jv*dt |        |        |  Ja*dt |        |        |  Jj*dt |        |        |
        |  Jv*dt |        |        |  Ja*dt |        |        |  Jj*dt |        |        |
        |--------------------------------------------------------------------------------|
        |        |  Jv*dt |        |        |  Ja*dt |        |        |  Jj*dt |        |
        |        |  Jv*dt |        |        |  Ja*dt |        |        |  Jj*dt |        |
        |--------------------------------------------------------------------------------|
    """

    def create_matrix(self) -> Matrix:
        """
        Builds the constraint matrix applying the expression jacobian at each velocity step of the
        horizon, padding the jerk columns with zeros.
        """
        number_of_vel_rows = len(self.constraints) * (
            self.config.prediction_horizon - 2
        )
        if number_of_vel_rows == 0:
            return sm.Matrix()
        jacobian = (
            sm.Vector([c.expression for c in self.constraints]).jacobian(
                variables=self.position_variables
            )
            * self.config.mpc_dt
        )
        missing_variables = self.config.max_derivative - 1
        eye = sm.Matrix.eye(self.config.prediction_horizon)[
            :-2, : self.config.prediction_horizon - missing_variables
        ]
        J_vel_limit_block = eye.kron(jacobian)

        return sm.hstack(
            [
                J_vel_limit_block,
                sm.Matrix.zeros(
                    J_vel_limit_block.shape[0], self.number_of_jerk_columns
                ),
            ]
        )

    def create_slack_matrix(self) -> Matrix:
        """
        Builds the diagonal slack matrix with one slack variable per constraint and velocity step.
        """
        if len(self.constraints) == 0:
            return sm.Matrix()
        num_slack_variables = sum(
            self.config.prediction_horizon - 2 for c in self.constraints
        )
        return sm.Matrix.eye(num_slack_variables) * self.config.mpc_dt

    def create_slack_variables(self) -> DirectLimits:
        """
        Creates one slack variable per constraint and velocity step with normalized weights.
        """
        lower_slack = []
        upper_slack = []
        quadratic_weights = []
        linear_weights = []
        names = []
        for t in range(self.config.prediction_horizon):
            for c in self.constraints:
                if t < self.config.prediction_horizon - 2:
                    lower_slack.append(c.lower_slack_limit)
                    upper_slack.append(c.upper_slack_limit)
                    quadratic_weights.append(
                        normalize_slack_weight(
                            c.quadratic_weight, c.normalization_factor
                        )
                    )
                    linear_weights.append(c.linear_weight)
                    names.append(f"t{t:03}/{c.name}")
        return DirectLimits(
            lower_bounds=sm.Vector(lower_slack),
            upper_bounds=sm.Vector(upper_slack),
            quadratic_weights=sm.Vector(quadratic_weights),
            linear_weights=sm.Vector(linear_weights),
            names=names,
        )

    def create_bounds(
        self, bounds_getter: Callable[GiskardConstraint, Scalar]
    ) -> Vector:
        """
        Builds the bounds, one per constraint and control step.
        """
        bounds2 = []
        for t in range(self.config.control_horizon):
            for c in self.constraints:
                bounds2.append(bounds_getter(c) * self.config.mpc_dt)
        return Vector(bounds2)

    def create_names(self) -> list[str]:
        """
        Creates a name per constraint and control step, prefixed with the time step.
        """
        names = []
        for t in range(self.config.control_horizon):
            for c in self.constraints:
                names.append(f"t{t:03}/{c.name}")
        return names


@dataclass
class SystemDynamicsStrategy(EnforcementStrategy):
    """
    The constraints produced by this class describe the discrete-time relationships between variables
    in the prediction horizon :math:`N` using a semi-implicit euler integration method:

    .. math::

        v_k = v_{k-1} + a_{k} \\, \\Delta t

        a_k = a_{k-1} + j_{k} \\, \\Delta t

    Where v, a and j are velocity, acceleration and jerk, respectively, and k is the time step.
    Acceleration variables are removed using substitution.
    The first two rows links the MPC to the current state:

    .. math::

        -v_{c} - a_{c} \\, \\Delta t = -v_0 + j_0 \\, \\Delta t^2

        v_{c} = - v_1 + 2 v_0 + j_1 \\, \\Delta t^2

    Rows from 2 until k-2 have this form:

    .. math::

        0 = - v_k + 2 v_{k-1} - v_{k-2} + j_k \\, \\Delta t^2

    The final two rows have this form:

    .. math::

        0 = 2 v_{k-1} - v_{k-2} + j_k \\, \\Delta t^2

        0 = - v_{k-2} + j_k \\, \\Delta t^2

    For a prediciton horizon of 5 with 1 degree of freedom, the matrix looks like this:

    ::

        |  equality_bounds |   |           equality constraint matrix          |   |    v_0    |
        |------------------|   |-----------------------------------------------|   |    v_1    |
        | - v_c - a_c * dt |   | -1  |     |     |  1  |     |     |     |     |   |    v_2    |
        |       v_c        |   |  2  | -1  |     |     |  1  |     |     |     |   | j_0*dt**2 |
        |        0         | = | -1  |  2  | -1  |     |     |  1  |     |     | @ | j_1*dt**2 |
        |        0         |   |     | -1  |  2  |     |     |     |  1  |     |   | j_2*dt**2 |
        |        0         |   |     |     | -1  |     |     |     |     |  1  |   | j_3*dt**2 |
        |------------------|   |-----------------------------------------------|   | j_4*dt**2 |

    This means that the QP does not optimize jerk, but jerk :math:`*\\Delta t^2`, this improves the conditioning of the
    constraint matrix, which helps some solvers.
    """

    def create_matrix(self) -> Matrix:
        """
        Builds the equality matrix encoding the velocity, acceleration, and jerk integration over
        the horizon.
        """
        matrix = np.zeros(
            (
                self.number_of_jerk_columns,
                self.number_of_velocity_columns + self.number_of_jerk_columns,
            )
        )
        for k in range(self.config.prediction_horizon):
            row_start = k * self.number_of_free_variables
            row_end = (k + 1) * self.number_of_free_variables

            # velocity at k
            if k < self.config.prediction_horizon - 2:
                col_start = k * self.number_of_free_variables
                col_end = (k + 1) * self.number_of_free_variables
                matrix[row_start:row_end, col_start:col_end] -= np.eye(
                    self.number_of_free_variables
                )

            # velocity at k-1
            if 0 < k < self.config.prediction_horizon - 1:
                col_start = (k - 1) * self.number_of_free_variables
                col_end = k * self.number_of_free_variables
                matrix[row_start:row_end, col_start:col_end] += 2 * np.eye(
                    self.number_of_free_variables
                )

            # velocity at k-2
            if k > 1:
                col_start = (k - 2) * self.number_of_free_variables
                col_end = (k - 1) * self.number_of_free_variables
                matrix[row_start:row_end, col_start:col_end] -= np.eye(
                    self.number_of_free_variables
                )

            # jerk at k
            col_start = self.number_of_velocity_columns + row_start
            col_end = self.number_of_velocity_columns + row_end
            matrix[row_start:row_end, col_start:col_end] += np.eye(
                self.number_of_free_variables
            )

        return sm.Matrix(matrix)

    def create_slack_matrix(self) -> Matrix:
        """
        Returns an empty slack matrix, as the system dynamics need no slack variables.
        """
        return sm.Matrix.zeros(self.number_of_jerk_columns, 0)

    def create_slack_variables(self) -> DirectLimits:
        """
        Returns empty limits, as the system dynamics introduce no slack variables.
        """
        return DirectLimits.empty()

    def create_names(self) -> list[str]:
        """
        Creates a name for every velocity/jerk integration row.
        """
        names = []
        for k in range(self.config.prediction_horizon):
            for dof in self.degrees_of_freedom:
                names.append(f"{dof.name} k_{k} vel/jerk link")
        return names

    def create_bounds(
        self, bounds_getter: Callable[GiskardConstraint, Scalar]
    ) -> Vector:
        """
        Unused; the system dynamics provide equality bounds via :meth:`create_equality_bounds`.
        """
        ...

    def create_equality_bounds(self) -> Vector:
        """
        Builds the equality bounds linking the first horizon steps to the current state.
        """
        res = sm.Vector.zeros(self.number_of_jerk_columns)
        res[: self.number_of_free_variables] = (
            -self.velocity_variables - self.acceleration_variables * self.config.mpc_dt
        )
        res[self.number_of_free_variables : self.number_of_free_variables * 2] = (
            self.velocity_variables
        )
        return res


@dataclass(kw_only=True)
class GiskardConstraint(ABC):
    """
    Defines a (slack-relaxed) constraint on expression for a quadratic program.
    """

    name: str
    """
    Human readable name of the constraint, used for debugging.
    """

    expression: Scalar
    """
    The expression that is being constrained.
    """

    quadratic_weight: sm.ScalarData
    """
    The quadratic weight of this constraint. Describes how expensive it is to violate.
    """

    linear_weight: sm.ScalarData = field(default=0)
    """
    The linear weight of this constraint. Its only hear for completeness sake, I haven't found a use case for it.
    """

    normalization_factor: float
    """
    This value is important to make constraints with different units comparable.
    The meaning depends on derivative.
    If the derivative is position, the normalization factor is rough velocity with which the expression can change.
    For example:
        - If you have a joint position constraint, the normalization factor should be the joint velocity limit.
        - If you have a cartesian position constraint, the normalization factor should be the cartesian velocity limit.
    In practice, use joint limits from the URDF for joint space constraints and define two values for cartesian constraints:
        - a m/s limit for translation
        - a rad/s value for rotation
    """

    enforcement_strategy: type[EnforcementStrategy]
    """
    The strategy used to enforce this constraint within the QP.
    """

    lower_slack_limit: sm.ScalarData = field(default=-LargeNumber)
    """
    How far the constraint may be violated below its bound.
    """

    upper_slack_limit: sm.ScalarData = field(default=LargeNumber)
    """
    How far the constraint may be violated above its bound.
    """


@dataclass
class GiskardEqualityConstraint(GiskardConstraint):
    """
    A constraint that drives the expression to a single target value.
    """

    bound: Scalar
    """
    The target value the expression should reach.
    """


@dataclass
class GiskardInequalityConstraint(GiskardConstraint):
    """
    A constraint that keeps the expression between a lower and upper bound.
    """

    lower_bound: Scalar
    """
    The lowest allowed value of the expression.
    """

    upper_bound: Scalar
    """
    The highest allowed value of the expression.
    """

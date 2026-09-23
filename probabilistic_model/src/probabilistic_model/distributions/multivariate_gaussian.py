from __future__ import annotations

import copy
import itertools
import math
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
from random_events.interval import SimpleInterval, singleton
from random_events.product_algebra import Event, SimpleEvent, VariableMap
from random_events.variable import Continuous, Variable
from scipy.optimize import lsq_linear
from scipy.stats import multivariate_normal, norm, truncnorm
from scipy.stats._multivariate import multivariate_normal_frozen
from typing_extensions import (
    Any,
    Dict,
    Iterable,
    Iterator,
    List,
    Optional,
    Self,
    Tuple,
)

from probabilistic_model.exceptions import (
    EventIsNotABoxError,
    ProbabilisticCircuitRequiredError,
    ShapeMismatchError,
    VariableNotInDistributionError,
)
from probabilistic_model.probabilistic_model import (
    CenterType,
    MomentType,
    OrderType,
    ProbabilisticModel,
)

# %% the covariance matrix


@dataclass
class Covariance:
    """
    The covariance matrix of a multivariate Gaussian.

    A covariance matrix is symmetric, so only the entries on and below its diagonal are
    stored. Every row and column is addressed by its index.
    """

    lower_triangle: npt.NDArray
    """
    The entries of the covariance matrix on and below its diagonal, row by row.
    """

    def __post_init__(self):
        self.lower_triangle = np.asarray(self.lower_triangle, dtype=float)
        self.validate()

    def validate(self):
        """
        :raises ShapeMismatchError: If the entries are not the lower triangle of a
            square matrix.
        """
        entries = self.dimension * (self.dimension + 1) // 2
        if self.lower_triangle.shape != (entries,):
            raise ShapeMismatchError(self.lower_triangle.shape, (entries,))

    @classmethod
    def from_matrix(cls, matrix: npt.ArrayLike) -> Self:
        """
        :param matrix: A covariance matrix, of which only the entries on and below the
            diagonal are read.
        :return: The covariance.
        :raises ShapeMismatchError: If the matrix is not square.
        """
        matrix = np.atleast_2d(np.asarray(matrix, dtype=float))
        dimension = len(matrix)
        if matrix.shape != (dimension, dimension):
            raise ShapeMismatchError(matrix.shape, (dimension, dimension))
        return cls(lower_triangle=matrix[np.tril_indices(dimension)])

    @property
    def dimension(self) -> int:
        """
        :return: How many rows, and columns, the matrix has.
        """
        return int((math.isqrt(8 * len(self.lower_triangle) + 1) - 1) // 2)

    @property
    def matrix(self) -> npt.NDArray:
        """
        :return: The full, symmetric matrix.
        """
        rows, columns = np.tril_indices(self.dimension)
        matrix = np.empty((self.dimension, self.dimension))
        matrix[rows, columns] = self.lower_triangle
        matrix[columns, rows] = self.lower_triangle
        return matrix

    @property
    def variances(self) -> npt.NDArray:
        """
        :return: The diagonal of the matrix.
        """
        indices = np.arange(self.dimension)
        return self.lower_triangle[indices * (indices + 1) // 2 + indices]

    @property
    def is_diagonal(self) -> bool:
        """
        :return: Whether every entry off the diagonal is zero.
        """
        rows, columns = np.tril_indices(self.dimension)
        return not np.any(self.lower_triangle[rows != columns])

    def between(self, first: int, second: int) -> float:
        """
        :param first: The index of a row.
        :param second: The index of a column.
        :return: The entry at that row and column.
        """
        row, column = max(first, second), min(first, second)
        return float(self.lower_triangle[row * (row + 1) // 2 + column])

    def marginal(self, indices: List[int]) -> Self:
        """
        :param indices: The rows and columns to keep, in the order to keep them in.
        :return: The covariance of only those.
        """
        return self.from_matrix(self.matrix[np.ix_(indices, indices)])

    def scaled(self, factors: npt.NDArray) -> Self:
        """
        :param factors: What to multiply each index by.
        :return: The covariance after every index is multiplied by its factor, which
            scales each entry once per index it relates.
        """
        rows, columns = np.tril_indices(self.dimension)
        return type(self)(
            lower_triangle=self.lower_triangle * factors[rows] * factors[columns]
        )


# %% a Gaussian over several variables at once


@dataclass
class MultivariateGaussianDistribution(ProbabilisticModel):
    """
    A multivariate Gaussian distribution over continuous random variables.

    Every tractable query is answered by :mod:`scipy.stats.multivariate_normal`, the
    same way :class:`~probabilistic_model.distributions.gaussian.GaussianDistribution`
    answers its own through :mod:`scipy.stats.norm`.
    """

    variables: Tuple[Continuous, ...]
    """
    The variables of the distribution.
    """

    mean: npt.NDArray
    """
    The mean.

    Its dimension corresponds to the variables in the same order.
    """

    covariance: Covariance
    """
    The covariance.

    Its rows and columns correspond to the variables in the same order.
    """

    def __post_init__(self):
        self.variables = tuple(self.variables)
        self.mean = np.asarray(self.mean, dtype=float)
        self.validate()

    def validate(self):
        """
        :raises ShapeMismatchError: If the mean or the covariance is not laid out by
            this distribution's variables.
        """
        amount = len(self.variables)
        if self.mean.shape != (amount,):
            raise ShapeMismatchError(self.mean.shape, (amount,))
        if self.covariance.dimension != amount:
            raise ShapeMismatchError(
                (self.covariance.dimension, self.covariance.dimension),
                (amount, amount),
            )

    @classmethod
    def from_mean_and_covariance(
        cls,
        variables: Iterable[Continuous],
        mean: npt.ArrayLike,
        covariance: npt.ArrayLike,
    ) -> Self:
        """
        Build the distribution from a full covariance matrix, of which only the entries
        on and below the diagonal are read.

        :param variables: The variables of the distribution.
        :param mean: The mean, laid out by the variables.
        :param covariance: The covariance matrix, both of whose dimensions are laid out
            by the variables.
        :return: The distribution.
        :raises ShapeMismatchError: If the mean or the covariance is not laid out by the
            variables.
        """
        return cls(
            variables=tuple(variables),
            mean=mean,
            covariance=Covariance.from_matrix(covariance),
        )

    @property
    def support(self) -> Event:
        return self.universal_simple_event().as_composite_set()

    @property
    def scipy_distribution(self) -> multivariate_normal_frozen:
        """
        :return: The scipy distribution every tractable query is answered by.
        """
        return multivariate_normal(mean=self.mean, cov=self.covariance.matrix)

    # %% reading it by variable

    def index_of(self, variable: Continuous) -> int:
        """
        :param variable: The variable to locate.
        :return: Its index in the mean and in the covariance.
        :raises VariableNotInDistributionError: If this distribution is not over it.
        """
        try:
            return self.variables.index(variable)
        except ValueError as error:
            raise VariableNotInDistributionError(
                variable=variable, variables=list(self.variables)
            ) from error

    def covariance_between(self, first: Continuous, second: Continuous) -> float:
        """
        The covariance of two variables is an integral over both of them, and this
        distribution is one of the few for which it is tractable in closed form.

        :param first: One of the variables.
        :param second: The other one.
        :return: Their covariance.
        :raises VariableNotInDistributionError: If this distribution is not over either
            of them.
        """
        return self.covariance.between(self.index_of(first), self.index_of(second))

    # %% density and probability

    def log_likelihood(self, events: npt.NDArray) -> npt.NDArray:
        return np.atleast_1d(self.scipy_distribution.logpdf(events))

    def cumulative_distribution_function(self, events: npt.NDArray) -> npt.NDArray:
        return np.atleast_1d(self.scipy_distribution.cdf(events))

    def probability_of_simple_event(self, event: SimpleEvent) -> float:
        """
        The probability of an axis-aligned box under a correlated Gaussian has no closed
        form, so it is integrated numerically. A variable confined to several intervals
        makes several boxes, and their probabilities add.

        :param event: The box, or boxes, to measure.
        :return: How probable it is.
        """
        return float(
            sum(
                max(float(self.scipy_distribution.cdf(upper, lower_limit=lower)), 0.0)
                for lower, upper in self._bounds_of_boxes(event)
            )
        )

    def _bounds_of_boxes(
        self, event: SimpleEvent
    ) -> Iterator[Tuple[npt.NDArray, npt.NDArray]]:
        """
        :param event: The event to split into boxes.
        :return: The lower and the upper bounds of each box the event makes, laid out
            by this distribution's variables.
        """
        intervals_per_variable = [
            tuple(event[variable].simple_sets) for variable in self.variables
        ]
        for box in itertools.product(*intervals_per_variable):
            yield (
                np.array([interval.lower for interval in box]),
                np.array([interval.upper for interval in box]),
            )

    def log_mode(self) -> Tuple[Event, float]:
        """
        A Gaussian is most dense exactly at its mean.

        :return: The mean, and the log-density there.
        """
        mode = SimpleEvent.from_data(
            {
                variable: singleton(float(value))
                for variable, value in zip(self.variables, self.mean)
            }
        ).as_composite_set()
        return mode, float(self.log_likelihood(self.mean.reshape(1, -1))[0])

    # %% reading fewer variables

    def marginal(self, variables: Iterable[Variable]) -> Optional[Self]:
        """
        :param variables: The variables to keep. They are kept in this distribution's
            own order, whatever order they are asked for in, and those it is not over
            are ignored.
        :return: The Gaussian over only those variables, or nothing if none of them is
            one of this distribution's.
        """
        kept = set(variables)
        indices = [
            index for index, variable in enumerate(self.variables) if variable in kept
        ]
        if not indices:
            return None
        return self._marginal_over_variable_indices(indices)

    def _marginal_over_variable_indices(self, indices: List[int]) -> Self:
        """
        :param indices: The indices of the variables to keep, in this distribution's own
            order.
        :return: The Gaussian over those variables.
        """
        return type(self)(
            variables=tuple(self.variables[index] for index in indices),
            mean=self.mean[indices],
            covariance=self.covariance.marginal(indices),
        )

    # %% fixing variables at a value

    def log_conditional(
        self, point: Dict[Variable, Any]
    ) -> Tuple[Optional[ProbabilisticModel], float]:
        """
        Fix some of the variables at the values given and answer with the distribution
        over the rest, which stays Gaussian.

        :param point: What each fixed variable is known to be.
        :return: The distribution over whatever is left, and the log-density of the
            values given.
        :raises VariableNotInDistributionError: If a fixed variable is not one of this
            distribution's.
        :raises ProbabilisticCircuitRequiredError: If every variable is fixed, which
            leaves a product of Dirac impulses rather than a Gaussian.
        """
        fixed_indices = [self.index_of(variable) for variable in point]
        free_indices = [
            index
            for index in range(len(self.variables))
            if index not in set(fixed_indices)
        ]
        if not free_indices:
            raise ProbabilisticCircuitRequiredError(model=self)

        fixed_at = np.array([float(point[variable]) for variable in point])
        log_density = float(
            self._marginal_over_variable_indices(fixed_indices).log_likelihood(
                fixed_at.reshape(1, -1)
            )[0]
        )

        return (
            self._conditional_over_variable_indices(
                free_indices, fixed_indices, fixed_at
            ),
            log_density,
        )

    def _conditional_over_variable_indices(
        self,
        free_indices: List[int],
        fixed_indices: List[int],
        fixed_at: npt.NDArray,
    ) -> Self:
        """
        :param free_indices: The indices of the variables the answer is over, in this
            distribution's order.
        :param fixed_indices: The indices of the variables held at a value, in the order
            ``fixed_at`` uses.
        :param fixed_at: What those variables are held at.
        :return: The Gaussian over the free variables, conditioned on the fixed ones.
        """
        free = self._marginal_over_variable_indices(free_indices)
        matrix = self.covariance.matrix
        cross = matrix[np.ix_(free_indices, fixed_indices)]
        explained = cross @ np.linalg.inv(matrix[np.ix_(fixed_indices, fixed_indices)])
        return self.from_mean_and_covariance(
            variables=free.variables,
            mean=free.mean + explained @ (fixed_at - self.mean[fixed_indices]),
            covariance=free.covariance.matrix - explained @ cross.T,
        )

    def product_with_gaussian_likelihood(
        self, other: MultivariateGaussianDistribution
    ) -> Self:
        """
        Multiply this density by the density of another Gaussian over some of the same
        variables, and normalize the product.

        The product of two Gaussian densities is again a Gaussian density, over the
        variables of this distribution.

        :param other: The Gaussian to multiply by. Its variables must all be this
            distribution's.
        :return: The normalized product.
        :raises VariableNotInDistributionError: If ``other`` is over a variable this
            distribution is not over.
        """
        indices = [self.index_of(variable) for variable in other.variables]
        matrix = self.covariance.matrix
        cross = matrix[:, indices]
        gain = cross @ np.linalg.inv(
            matrix[np.ix_(indices, indices)] + other.covariance.matrix
        )
        return self.from_mean_and_covariance(
            variables=self.variables,
            mean=self.mean + gain @ (other.mean - self.mean[indices]),
            covariance=matrix - gain @ cross.T,
        )

    # %% confining it to an event

    def log_truncated(
        self, event: Event, singleton_allowed: bool = False
    ) -> Tuple[Optional[ProbabilisticModel], float]:
        """
        Confine this Gaussian to a box.

        A Gaussian confined to anything other than the whole space is no longer a
        Gaussian, so this answers with a
        :class:`TruncatedMultivariateGaussianDistribution` rather than with one of its
        own kind.

        :param event: The box to confine it to.
        :param singleton_allowed: Ignored, since a Gaussian gives every single point
            probability zero.
        :return: The confined distribution and the log-probability of the box, or
            nothing at all if it cannot happen.
        :raises EventIsNotABoxError: If the event is not one simple interval per
            variable.
        """
        event.fill_missing_variables(set(self.variables))
        if not event.is_box():
            raise EventIsNotABoxError(model=self, event=event)
        [box] = event.simple_sets
        probability = self.probability_of_simple_event(box)
        if probability == 0.0:
            return None, -np.inf
        return (
            TruncatedMultivariateGaussianDistribution(untruncated=self, box=box),
            math.log(probability),
        )

    # %% moments

    def moment(self, order: OrderType, center: CenterType) -> MomentType:
        """
        Every moment asked for here is of one variable on its own, so each is answered
        by that variable's own marginal, through :mod:`scipy.stats.norm`.

        :param order: The order of the moment of each variable to answer for.
        :param center: What to take each of those moments about.
        :return: The moment of each variable asked for.
        """
        moments = VariableMap()
        for variable in order:
            index = self.index_of(variable)
            moments[variable] = float(
                norm(
                    loc=self.mean[index] - center[variable],
                    scale=math.sqrt(self.covariance.between(index, index)),
                ).moment(order[variable])
            )
        return moments

    # %% translation and scaling

    def apply_translation(self, translation: Dict[Variable, float]):
        """
        Move the mean, leaving the covariance as it is.

        :param translation: How far to move each variable; one left out does not move,
            and one this distribution is not over is ignored.
        """
        for index, variable in enumerate(self.variables):
            self.mean[index] += translation.get(variable, 0.0)

    def apply_scaling(self, scaling: Dict[Variable, float]):
        """
        Scale the variables, which scales the mean once and the covariance once per
        variable it relates.

        :param scaling: What to multiply each variable by; one left out keeps its size,
            and one this distribution is not over is ignored.
        """
        factors = np.array(
            [scaling.get(variable, 1.0) for variable in self.variables], dtype=float
        )
        self.mean = self.mean * factors
        self.covariance = self.covariance.scaled(factors)

    # %% sampling

    def sample(self, amount: int) -> npt.NDArray:
        return self.scipy_distribution.rvs(size=amount).reshape(
            amount, len(self.variables)
        )

    def __copy__(self) -> Self:
        return type(self)(
            variables=self.variables,
            mean=self.mean.copy(),
            covariance=Covariance(lower_triangle=self.covariance.lower_triangle.copy()),
        )

    def __deepcopy__(self, memo=None) -> Self:
        if memo is None:
            memo = {}
        id_self = id(self)
        if id_self in memo:
            return memo[id_self]
        result = type(self)(
            variables=tuple(
                variable.__class__(name=variable.name, domain=variable.domain)
                for variable in self.variables
            ),
            mean=self.mean.copy(),
            covariance=Covariance(lower_triangle=self.covariance.lower_triangle.copy()),
        )
        memo[id_self] = result
        return result


# %% a Gaussian that has been confined to a box


@dataclass
class TruncatedMultivariateGaussianDistribution(ProbabilisticModel):
    """
    A Gaussian confined to a box, which is what is left of one once part of the space is
    ruled out.

    It is not itself a Gaussian: cutting a correlated Gaussian along an axis leaves a
    shape no Gaussian has. What it keeps is the shape of the original inside the box,
    scaled up so that the box is certain.

    A box is one simple interval per variable, which is as far as one such shape
    reaches: ruling out a hole in the middle of the space leaves several of them, which
    is a circuit rather than a distribution.
    """

    untruncated: MultivariateGaussianDistribution
    """
    The Gaussian before anything was ruled out.
    """

    box: SimpleEvent
    """
    Everything still considered possible, one simple interval per variable.
    """

    @property
    def variables(self) -> Tuple[Variable, ...]:
        return self.untruncated.variables

    @property
    def support(self) -> Event:
        return self.box.as_composite_set()

    @property
    def normalizing_constant(self) -> float:
        """
        :return: How probable the box was before it was the only thing left, which is
            what every density here is scaled up by.
        """
        return self.untruncated.probability_of_simple_event(self.box)

    def interval_of(self, variable: Variable) -> SimpleInterval:
        """
        :param variable: The variable to read.
        :return: The one simple interval the box leaves it.
        """
        return self.box[variable].simple_sets[0]

    def log_likelihood(self, events: npt.NDArray) -> npt.NDArray:
        inside = np.array([self.support.contains(event) for event in events])
        return np.where(
            inside,
            np.atleast_1d(self.untruncated.scipy_distribution.logpdf(events))
            - math.log(self.normalizing_constant),
            -np.inf,
        )

    def probability_of_simple_event(self, event: SimpleEvent) -> float:
        surviving = event.intersection_with(self.box)
        if surviving.is_empty():
            return 0.0
        scipy_distribution = self.untruncated.scipy_distribution
        probability = sum(
            max(float(scipy_distribution.cdf(upper, lower_limit=lower)), 0.0)
            for lower, upper in self.untruncated._bounds_of_boxes(surviving)
        )
        return probability / self.normalizing_constant

    # %% the most likely point the box still allows

    def log_mode(self) -> Tuple[Event, float]:
        """
        The density falls away from the untruncated mean in every direction and the box
        is convex, so there is exactly one most likely point: the mean itself while the
        box still contains it, and otherwise the point of the box nearest to it in the
        distribution's own metric.

        :return: That point and its log-density.
        """
        most_likely = self._most_likely_point()
        mode = SimpleEvent.from_data(
            {
                variable: singleton(value)
                for variable, value in zip(self.variables, most_likely)
            }
        ).as_composite_set()
        return mode, float(self.log_likelihood(most_likely.reshape(1, -1))[0])

    def _most_likely_point(self) -> npt.NDArray:
        """
        The point of the box nearest to the mean in the distribution's own metric
        minimises :math:`\\lVert W (x - \\mu) \\rVert^2` over the box, where
        :math:`W^T W` is the inverse of the covariance. That is a bounded linear least
        squares problem, which :func:`scipy.optimize.lsq_linear` solves exactly.

        :return: Where the density is greatest within the box, moved just inside an
            interval that excludes its own end.
        """
        mean = self.untruncated.mean
        if self.support.contains(mean):
            return mean
        intervals = [self.interval_of(variable) for variable in self.variables]
        whitening = np.linalg.cholesky(
            np.linalg.inv(self.untruncated.covariance.matrix)
        ).T
        found = lsq_linear(
            whitening,
            whitening @ mean,
            bounds=(
                [interval.lower for interval in intervals],
                [interval.upper for interval in intervals],
            ),
            method="bvls",
        ).x
        return np.array(
            [
                interval.nearest_contained_value(float(value))
                for value, interval in zip(found, intervals)
            ]
        )

    # %% ruling out more, and fixing a variable

    def log_truncated(
        self, event: Event, singleton_allowed: bool = False
    ) -> Tuple[Optional[ProbabilisticModel], float]:
        """
        Rule out more of the space.

        :param event: What is still to be considered possible.
        :param singleton_allowed: Ignored, since every single point has probability
            zero.
        :return: The further confined distribution and the log-probability of the event
            under this one, or nothing at all if nothing is left.
        :raises EventIsNotABoxError: If the event is not one simple interval per
            variable.
        """
        event.fill_missing_variables(set(self.variables))
        if not event.is_box():
            raise EventIsNotABoxError(model=self, event=event)
        [box] = event.simple_sets
        surviving = box.intersection_with(self.box)
        probability = self.probability_of_simple_event(surviving)
        if probability == 0.0:
            return None, -np.inf
        return (
            type(self)(untruncated=self.untruncated, box=surviving),
            math.log(probability),
        )

    def log_conditional(
        self, point: Dict[Variable, Any]
    ) -> Tuple[Optional[ProbabilisticModel], float]:
        """
        Fix some of the variables at the values given and answer with the distribution
        over the rest, which is the Gaussian conditional confined to the slice the box
        makes at those values.

        :param point: What each fixed variable is known to be.
        :return: That distribution and the log-likelihood of the values given, or
            nothing at all if the box rules them out.
        :raises VariableNotInDistributionError: If a fixed variable is not one of this
            distribution's.
        :raises ProbabilisticCircuitRequiredError: If every variable is fixed, which
            leaves a product of Dirac impulses.
        """
        conditional, log_density = self.untruncated.log_conditional(point)
        free = [variable for variable in self.variables if variable not in point]
        slice_of_the_box = SimpleEvent.from_data(
            {variable: self.box[variable] for variable in free}
        ).as_composite_set()
        confined, log_probability = conditional.log_truncated(slice_of_the_box)

        inside = all(
            self.box[variable].contains(value) for variable, value in point.items()
        )
        log_likelihood = (
            log_density + log_probability - math.log(self.normalizing_constant)
            if inside
            else -np.inf
        )
        if log_likelihood == -np.inf:
            return None, -np.inf
        return confined, log_likelihood

    # %% sampling

    def sample(self, amount: int) -> npt.NDArray:
        """
        :param amount: How many samples to draw.
        :return: That many samples, all of them inside the box.
        """
        if self.untruncated.covariance.is_diagonal:
            return self._sample_each_variable_on_its_own(amount)
        return self.rejection_sample(amount)

    def _sample_each_variable_on_its_own(self, amount: int) -> npt.NDArray:
        """
        Variables that do not co-vary stay independent once the box confines each of
        them separately, so each is drawn from its own :mod:`scipy.stats.truncnorm` and
        no sample is ever thrown away.

        :param amount: How many samples to draw.
        :return: That many samples, all of them inside the box.
        """
        intervals = [self.interval_of(variable) for variable in self.variables]
        mean = self.untruncated.mean
        deviation = np.sqrt(self.untruncated.covariance.variances)
        return truncnorm.rvs(
            a=(np.array([interval.lower for interval in intervals]) - mean) / deviation,
            b=(np.array([interval.upper for interval in intervals]) - mean) / deviation,
            loc=mean,
            scale=deviation,
            size=(amount, len(self.variables)),
        )

    def rejection_sample(self, amount: int) -> npt.NDArray:
        """
        Draw from the untruncated Gaussian and keep what the box allows.

        .. warning::
            How many rounds this needs grows as the reciprocal of the box's
            probability, and there is no bound on it.

        :param amount: How many samples to draw.
        :return: That many samples, all of them inside the box.
        """
        allowed = self.support
        kept = np.empty((0, len(self.variables)))
        while len(kept) < amount:
            drawn = self.untruncated.sample(amount)
            inside = np.array([allowed.contains(sample) for sample in drawn])
            kept = np.concatenate([kept, drawn[inside]])
        return kept[:amount]

    def __copy__(self) -> Self:
        return type(self)(untruncated=copy.copy(self.untruncated), box=self.box)

    def __deepcopy__(self, memo=None) -> Self:
        if memo is None:
            memo = {}
        id_self = id(self)
        if id_self in memo:
            return memo[id_self]
        result = type(self)(
            untruncated=copy.deepcopy(self.untruncated, memo),
            box=self.box.__deepcopy__(),
        )
        memo[id_self] = result
        return result

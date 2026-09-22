from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
from random_events.interval import Bound, SimpleInterval, singleton
from random_events.product_algebra import Event, SimpleEvent, VariableMap
from random_events.variable import Continuous, Variable
from scipy.optimize import minimize
from scipy.stats import multivariate_normal, truncnorm
from typing_extensions import (
    Any,
    Dict,
    Iterable,
    List,
    Optional,
    Self,
    TYPE_CHECKING,
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

if TYPE_CHECKING:
    from scipy.stats._multivariate import multivariate_normal_frozen

# %% a Gaussian over several variables at once


@dataclass
class MultivariateGaussianDistribution(ProbabilisticModel):
    """
    A multivariate Gaussian distribution over continuous random variables.

    Every tractable query is answered by :mod:`scipy.stats.multivariate_normal`, the
    same way :class:`~probabilistic_model.distributions.gaussian.GaussianDistribution`
    answers its own through :mod:`scipy.stats.norm`.
    """

    distribution_variables: Tuple[Continuous, ...]
    """
    The variables of the distribution.
    """

    mean: npt.NDArray
    """
    The mean.

    Its dimension corresponds to the variables in the same order.
    """

    covariance_lower_triangle: npt.NDArray
    """
    The entries of the covariance matrix on and below its diagonal, row by row.

    A covariance matrix is symmetric, so these determine all of it.
    """

    def __post_init__(self):
        """
        :raises ShapeMismatchError: If the mean or the covariance is not laid out by
            this distribution's variables.
        """
        self.distribution_variables = tuple(self.distribution_variables)
        self.mean = np.asarray(self.mean, dtype=float)
        self.covariance_lower_triangle = np.asarray(
            self.covariance_lower_triangle, dtype=float
        )

        amount = len(self.distribution_variables)
        if self.mean.shape != (amount,):
            raise ShapeMismatchError(self.mean.shape, (amount,))
        entries = amount * (amount + 1) // 2
        if self.covariance_lower_triangle.shape != (entries,):
            raise ShapeMismatchError(self.covariance_lower_triangle.shape, (entries,))

    @classmethod
    def from_mean_and_covariance(
        cls,
        distribution_variables: Iterable[Continuous],
        mean: npt.ArrayLike,
        covariance: npt.ArrayLike,
    ) -> Self:
        """
        Build the distribution from a full covariance matrix, of which only the entries
        on and below the diagonal are read.

        :param distribution_variables: The variables of the distribution.
        :param mean: The mean, laid out by the variables.
        :param covariance: The covariance matrix, both of whose dimensions are laid out
            by the variables.
        :return: The distribution.
        :raises ShapeMismatchError: If the mean or the covariance is not laid out by the
            variables.
        """
        distribution_variables = tuple(distribution_variables)
        covariance = np.asarray(covariance, dtype=float)
        amount = len(distribution_variables)
        if covariance.shape != (amount, amount):
            raise ShapeMismatchError(covariance.shape, (amount, amount))
        return cls(
            distribution_variables=distribution_variables,
            mean=mean,
            covariance_lower_triangle=covariance[np.tril_indices(amount)],
        )

    @property
    def variables(self) -> Tuple[Continuous, ...]:
        return tuple(self.distribution_variables)

    @property
    def covariance(self) -> npt.NDArray:
        """
        :return: The covariance matrix. Both of its dimensions correspond to the
            variables in the same order.
        """
        rows, columns = np.tril_indices(len(self.distribution_variables))
        covariance = np.empty((len(self.distribution_variables),) * 2)
        covariance[rows, columns] = self.covariance_lower_triangle
        covariance[columns, rows] = self.covariance_lower_triangle
        return covariance

    @property
    def support(self) -> Event:
        return self.universal_simple_event().as_composite_set()

    @property
    def scipy_distribution(self) -> multivariate_normal_frozen:
        """
        :return: The scipy distribution every tractable query is answered by.
        """
        return multivariate_normal(mean=self.mean, cov=self.covariance)

    # %% reading it by variable

    def index_of(self, variable: Continuous) -> int:
        """
        :param variable: The variable to locate.
        :return: The row it occupies in the mean and the covariance.
        :raises VariableNotInDistributionError: If this distribution is not over it.
        """
        if variable not in self.distribution_variables:
            raise VariableNotInDistributionError(
                variable=variable, variables=list(self.distribution_variables)
            )
        return self.distribution_variables.index(variable)

    def mean_of(self, variable: Continuous) -> float:
        """
        :param variable: The variable to read.
        :return: Its mean.
        :raises VariableNotInDistributionError: If this distribution is not over it.
        """
        return float(self.mean[self.index_of(variable)])

    def variance_of(self, variable: Continuous) -> float:
        """
        :param variable: The variable to read.
        :return: Its variance.
        :raises VariableNotInDistributionError: If this distribution is not over it.
        """
        return self.covariance_between(variable, variable)

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
        return float(self.covariance[self.index_of(first), self.index_of(second)])

    # %% density and probability

    def log_likelihood(self, events: npt.NDArray) -> npt.NDArray:
        return np.atleast_1d(self.scipy_distribution.logpdf(events))

    def cumulative_distribution_function(self, events: npt.NDArray) -> npt.NDArray:
        return np.atleast_1d(self.scipy_distribution.cdf(events))

    def probability_of_simple_event(self, event: SimpleEvent) -> float:
        """
        The probability of an axis-aligned box under a correlated Gaussian has no closed
        form, so it is integrated numerically. A variable confined to several stretches
        makes several boxes, and their probabilities add.

        :param event: The box, or boxes, to measure.
        :return: How probable it is.
        """
        stretches_per_variable = [
            tuple(event[variable].simple_sets) for variable in self.variables
        ]
        return float(
            sum(
                self._probability_of_box(box)
                for box in itertools.product(*stretches_per_variable)
            )
        )

    def _probability_of_box(self, box: Tuple[SimpleInterval, ...]) -> float:
        """
        :param box: One unbroken stretch per variable, in this distribution's order.
        :return: How probable it is that every variable falls in its own stretch.
        """
        probability = multivariate_normal.cdf(
            np.array([stretch.upper for stretch in box]),
            mean=self.mean,
            cov=self.covariance,
            lower_limit=np.array([stretch.lower for stretch in box]),
        )
        return max(float(probability), 0.0)

    def log_mode(self) -> Tuple[Event, float]:
        """
        A Gaussian is most dense exactly at its mean.

        :return: The mean, and the log-density there.
        """
        mode = SimpleEvent.from_data(
            {variable: singleton(self.mean_of(variable)) for variable in self.variables}
        ).as_composite_set()
        return mode, float(self.log_likelihood(self.mean.reshape(1, -1))[0])

    # %% reading fewer variables

    def marginal(self, variables: Iterable[Variable]) -> Optional[Self]:
        """
        :param variables: The variables to keep. They are kept in this distribution's
            own order, whatever order they are asked for in.
        :return: The Gaussian over only those variables.
        :raises VariableNotInDistributionError: If this distribution is not over one of
            them.
        """
        kept = set(variables)
        return self._marginal_over_variable_indices(
            [self.index_of(variable) for variable in self.variables if variable in kept]
        )

    def _marginal_over_variable_indices(self, rows: List[int]) -> Self:
        """
        :param rows: The rows to keep, in this distribution's own order.
        :return: The Gaussian over the variables those rows belong to.
        """
        return self.from_mean_and_covariance(
            distribution_variables=tuple(
                self.distribution_variables[row] for row in rows
            ),
            mean=self.mean[rows],
            covariance=self.covariance[np.ix_(rows, rows)],
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
        fixed_rows = [self.index_of(variable) for variable in point]
        free_rows = [
            row for row in range(len(self.variables)) if row not in set(fixed_rows)
        ]
        if not free_rows:
            raise ProbabilisticCircuitRequiredError(model=self)

        fixed_at = np.array([float(point[variable]) for variable in point])
        log_density = float(
            self._marginal_over_variable_indices(fixed_rows).log_likelihood(
                fixed_at.reshape(1, -1)
            )[0]
        )

        return self._conditioned(free_rows, fixed_rows, fixed_at), log_density

    def _conditioned(
        self,
        free_rows: List[int],
        fixed_rows: List[int],
        fixed_at: npt.NDArray,
    ) -> Self:
        """
        :param free_rows: The rows the answer is over, in this distribution's order.
        :param fixed_rows: The rows held at a value, in the order ``fixed_at`` uses.
        :param fixed_at: What those rows are held at.
        :return: The Gaussian over ``free_rows``, narrowed by what the fixed rows say.
        """
        free = self._marginal_over_variable_indices(free_rows)
        cross = self.covariance[np.ix_(free_rows, fixed_rows)]
        explained = cross @ np.linalg.inv(
            self.covariance[np.ix_(fixed_rows, fixed_rows)]
        )
        return self.from_mean_and_covariance(
            distribution_variables=free.distribution_variables,
            mean=free.mean + explained @ (fixed_at - self.mean[fixed_rows]),
            covariance=free.covariance - explained @ cross.T,
        )

    def product_with_gaussian_likelihood(
        self,
        observation_matrix: npt.NDArray,
        observed: npt.NDArray,
        observation_covariance: npt.NDArray,
    ) -> Self:
        """
        Multiply this density by the Gaussian likelihood of an observation and normalize
        the product.

        The observation is ``observation_matrix`` applied to the variables plus Gaussian
        noise with covariance ``observation_covariance``. Its likelihood as a function
        of the variables is a Gaussian density, and so is the normalized product of two
        Gaussian densities. That product is the Gaussian over these variables
        conditioned on ``observed`` in their joint distribution with the observation.

        :param observation_matrix: How much each variable contributes to each observed
            number, with one row per observed number.
        :param observed: The numbers observed, one per row of ``observation_matrix``.
        :param observation_covariance: The covariance of the observation noise, one row
            and column per observed number.
        :return: The normalized product, over the same variables.
        :raises ShapeMismatchError: If the three do not describe one observation of
            these variables.
        """
        observation_matrix = np.atleast_2d(np.asarray(observation_matrix, dtype=float))
        observed = np.atleast_1d(np.asarray(observed, dtype=float))
        observation_covariance = np.atleast_2d(
            np.asarray(observation_covariance, dtype=float)
        )

        amount = len(observation_matrix)
        if observation_matrix.shape != (amount, len(self.variables)):
            raise ShapeMismatchError(
                observation_matrix.shape, (amount, len(self.variables))
            )
        if observed.shape != (amount,):
            raise ShapeMismatchError(observed.shape, (amount,))
        if observation_covariance.shape != (amount, amount):
            raise ShapeMismatchError(observation_covariance.shape, (amount, amount))

        if amount == 0:
            return self

        joint = self._joint_with_observation(observation_matrix, observation_covariance)
        return joint._conditioned(
            list(range(len(self.variables))),
            list(range(len(self.variables), len(joint.variables))),
            observed,
        )

    def _joint_with_observation(
        self, observation_matrix: npt.NDArray, observation_covariance: npt.NDArray
    ) -> Self:
        """
        :param observation_matrix: How much each variable contributes to each observed
            number.
        :param observation_covariance: The covariance of the observation noise.
        :return: The Gaussian over these variables followed by the observed numbers.
        """
        covariance = self.covariance
        return self.from_mean_and_covariance(
            distribution_variables=(
                *self.distribution_variables,
                *self._variables_for_observation(len(observation_matrix)),
            ),
            mean=np.concatenate([self.mean, observation_matrix @ self.mean]),
            covariance=np.block(
                [
                    [covariance, covariance @ observation_matrix.T],
                    [
                        observation_matrix @ covariance,
                        observation_matrix @ covariance @ observation_matrix.T
                        + observation_covariance,
                    ],
                ]
            ),
        )

    def _variables_for_observation(self, amount: int) -> List[Continuous]:
        """
        The observed numbers are variables of the joint only while the product is being
        formed, so they are named here rather than asked of the caller.

        :param amount: How many observed numbers need a name.
        :return: That many names, none of which this distribution already uses.
        """
        taken = {variable.name for variable in self.variables}
        names = []
        for position in range(amount):
            name = f"observation {position}"
            while name in taken:
                name = f"{name} "
            taken.add(name)
            names.append(Continuous(name))
        return names

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
        :raises EventIsNotABoxError: If the event is not one unbroken stretch per
            variable.
        """
        event.fill_missing_variables(set(self.variables))
        box = self.require_box(event)
        probability = self.probability_of_simple_event(box)
        if probability == 0.0:
            return None, -np.inf
        return (
            TruncatedMultivariateGaussianDistribution(untruncated=self, box=box),
            math.log(probability),
        )

    def require_box(self, event: Event) -> SimpleEvent:
        """
        :param event: The event to read as a box.
        :return: The one box it is.
        :raises EventIsNotABoxError: If it is more than one box, or leaves a variable on
            several separate stretches.
        """
        if len(event.simple_sets) != 1:
            raise EventIsNotABoxError(model=self, event=event)
        box = event.simple_sets[0]
        if any(len(box[variable].simple_sets) != 1 for variable in self.variables):
            raise EventIsNotABoxError(model=self, event=event)
        return box

    # %% moments

    def moment(self, order: OrderType, center: CenterType) -> MomentType:
        """
        Every moment asked for here is of one variable on its own, so each is answered
        by that variable's own marginal.

        :param order: The order of the moment of each variable to answer for.
        :param center: What to take each of those moments about.
        :return: The moment of each variable asked for.
        """
        from probabilistic_model.distributions.gaussian import GaussianDistribution

        moments = VariableMap()
        for variable in order:
            marginal = GaussianDistribution(
                variable=variable,
                location=self.mean_of(variable),
                scale=math.sqrt(self.variance_of(variable)),
            )
            moments[variable] = marginal.moment(
                VariableMap({variable: order[variable]}),
                VariableMap({variable: center[variable]}),
            )[variable]
        return moments

    # %% moving and stretching

    def apply_translation(self, translation: Dict[Variable, float]):
        """
        Move the mean, leaving the covariance as it is.

        :param translation: How far to move each variable; one left out does not move.
        :raises VariableNotInDistributionError: If it names a variable this distribution
            is not over.
        """
        for variable, distance in translation.items():
            self.mean[self.index_of(variable)] += distance

    def apply_scaling(self, scaling: Dict[Variable, float]):
        """
        Stretch the variables, which stretches the mean once and the covariance once per
        variable it relates.

        :param scaling: What to multiply each variable by; one left out keeps its size.
        :raises VariableNotInDistributionError: If it names a variable this distribution
            is not over.
        """
        factors = np.ones(len(self.variables))
        for variable, factor in scaling.items():
            factors[self.index_of(variable)] = factor
        self.mean = self.mean * factors
        self.covariance_lower_triangle = (
            self.covariance_lower_triangle
            * np.outer(factors, factors)[np.tril_indices(len(self.variables))]
        )

    # %% sampling

    def sample(self, amount: int) -> npt.NDArray:
        return self.scipy_distribution.rvs(size=amount).reshape(
            amount, len(self.variables)
        )

    def __copy__(self) -> Self:
        return type(self)(
            distribution_variables=self.distribution_variables,
            mean=self.mean.copy(),
            covariance_lower_triangle=self.covariance_lower_triangle.copy(),
        )


# %% a Gaussian that has been confined to a box


@dataclass
class TruncatedMultivariateGaussianDistribution(ProbabilisticModel):
    """
    A Gaussian confined to a box, which is what is left of one once part of the space is
    ruled out.

    It is not itself a Gaussian: cutting a correlated Gaussian along an axis leaves a
    shape no Gaussian has. What it keeps is the shape of the original inside the box,
    scaled up so that the box is certain.

    A box is one unbroken stretch per variable, which is as far as one such shape
    reaches: ruling out a hole in the middle of the space leaves several of them, which
    is a circuit rather than a distribution.
    """

    untruncated: MultivariateGaussianDistribution
    """
    The Gaussian before anything was ruled out.
    """

    box: SimpleEvent
    """
    Everything still considered possible, one stretch per variable.
    """

    @property
    def variables(self) -> Tuple[Variable, ...]:
        return self.untruncated.variables

    @property
    def support(self) -> Event:
        return self.box.as_composite_set()

    @property
    def probability_of_the_box(self) -> float:
        """
        :return: How probable the box was before it was the only thing left, which is
            what every density here is scaled up by.
        """
        return self.untruncated.probability_of_simple_event(self.box)

    def stretch_of(self, variable: Variable) -> SimpleInterval:
        """
        :param variable: The variable to read.
        :return: The one stretch the box leaves it.
        """
        return self.box[variable].simple_sets[0]

    def log_likelihood(self, events: npt.NDArray) -> npt.NDArray:
        inside = np.array([self.support.contains(event) for event in events])
        return np.where(
            inside,
            self.untruncated.log_likelihood(events)
            - math.log(self.probability_of_the_box),
            -np.inf,
        )

    def probability_of_simple_event(self, event: SimpleEvent) -> float:
        surviving = event.intersection_with(self.box)
        if surviving.is_empty():
            return 0.0
        return (
            self.untruncated.probability_of_simple_event(surviving)
            / self.probability_of_the_box
        )

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
        :return: Where the density is greatest within the box, pulled just inside a
            stretch that excludes its own end.
        """
        mean = self.untruncated.mean
        if self.support.contains(mean):
            return mean
        stretches = [self.stretch_of(variable) for variable in self.variables]
        precision = np.linalg.inv(self.untruncated.covariance)

        def distance(point: npt.NDArray) -> float:
            difference = point - mean
            return float(difference @ precision @ difference)

        def gradient(point: npt.NDArray) -> npt.NDArray:
            return 2 * precision @ (point - mean)

        bounds = [(stretch.lower, stretch.upper) for stretch in stretches]
        started_at = np.array(
            [
                min(max(value, stretch.lower), stretch.upper)
                for value, stretch in zip(mean, stretches)
            ]
        )
        found = minimize(
            distance, started_at, jac=gradient, bounds=bounds, method="L-BFGS-B"
        ).x
        return np.array(
            [self._inside(value, stretch) for value, stretch in zip(found, stretches)]
        )

    @staticmethod
    def _inside(value: float, stretch: SimpleInterval) -> float:
        """
        A stretch that excludes its own end has no nearest point to anything beyond it,
        so the next value there is stands in for the end itself.

        :param value: Where the density is greatest along this stretch.
        :param stretch: The stretch it has to stay in.
        :return: That value, moved off an excluded end.
        """
        if value == stretch.lower and stretch.left == Bound.OPEN:
            return float(np.nextafter(value, np.inf))
        if value == stretch.upper and stretch.right == Bound.OPEN:
            return float(np.nextafter(value, -np.inf))
        return float(value)

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
        :raises EventIsNotABoxError: If the event is not one unbroken stretch per
            variable.
        """
        event.fill_missing_variables(set(self.variables))
        surviving = self.untruncated.require_box(event).intersection_with(self.box)
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
        :return: That distribution and the log-density of the values given, or nothing
            at all if the box rules them out.
        :raises VariableNotInDistributionError: If a fixed variable is not one of this
            distribution's.
        :raises ProbabilisticCircuitRequiredError: If every variable is fixed, which
            leaves a product of Dirac impulses.
        """
        if any(
            not self.box[variable].contains(value) for variable, value in point.items()
        ):
            return None, -np.inf

        conditional, log_density = self.untruncated.log_conditional(point)
        log_density -= math.log(self.probability_of_the_box)

        free = [variable for variable in self.variables if variable not in point]
        slice_of_the_box = SimpleEvent.from_data(
            {variable: self.box[variable] for variable in free}
        ).as_composite_set()
        confined, log_probability = conditional.log_truncated(slice_of_the_box)
        if confined is None:
            return None, -np.inf
        return confined, log_density + log_probability

    # %% sampling

    def sample(self, amount: int) -> npt.NDArray:
        """
        :param amount: How many samples to draw.
        :return: That many samples, all of them inside the box.
        """
        if self._variables_co_vary:
            return self._rejection_sample(amount)
        return self._sample_each_variable_on_its_own(amount)

    @property
    def _variables_co_vary(self) -> bool:
        """
        :return: Whether any two variables move together, which is what stops each of
            them from being drawn from its own stretch.
        """
        covariance = self.untruncated.covariance
        return bool(np.any(covariance - np.diag(np.diag(covariance))))

    def _sample_each_variable_on_its_own(self, amount: int) -> npt.NDArray:
        """
        Variables that do not co-vary stay independent once the box confines each of
        them separately, so each is drawn from its own :mod:`scipy.stats.truncnorm` and
        no sample is ever thrown away.

        :param amount: How many samples to draw.
        :return: That many samples, all of them inside the box.
        """
        stretches = [self.stretch_of(variable) for variable in self.variables]
        mean = self.untruncated.mean
        deviation = np.sqrt(np.diag(self.untruncated.covariance))
        return truncnorm.rvs(
            a=(np.array([stretch.lower for stretch in stretches]) - mean) / deviation,
            b=(np.array([stretch.upper for stretch in stretches]) - mean) / deviation,
            loc=mean,
            scale=deviation,
            size=(amount, len(self.variables)),
        )

    def _rejection_sample(self, amount: int) -> npt.NDArray:
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
        from copy import copy

        return type(self)(untruncated=copy(self.untruncated), box=self.box)

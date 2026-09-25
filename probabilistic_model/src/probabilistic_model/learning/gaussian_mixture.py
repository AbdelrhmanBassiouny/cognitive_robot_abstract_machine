"""
Fitting probabilistic circuits as Gaussian mixtures.
"""

from __future__ import annotations

import enum
import math
from abc import ABC
from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt
import pandas as pd
from random_events.variable import Continuous, Integer, Symbolic, Variable
from sklearn.base import clone
from sklearn.mixture import GaussianMixture
from stepmix.stepmix import StepMix
from typing_extensions import Any, Dict, Iterable, List, Optional, Sequence, Union

from probabilistic_model.distributions.distributions import (
    IntegerDistribution,
    SymbolicDistribution,
)
from probabilistic_model.distributions.gaussian import GaussianDistribution
from probabilistic_model.distributions.multivariate_gaussian import (
    Covariance,
    MultivariateGaussianDistribution,
)
from probabilistic_model.exceptions import NonContinuousVariableError
from probabilistic_model.learning.jpt.variables import (
    AnnotatedVariable,
    infer_variables_from_dataframe,
)
from probabilistic_model.learning.learning_method import LearningMethod
from probabilistic_model.probabilistic_circuit.rx.probabilistic_circuit import (
    ProbabilisticCircuit,
    ProductUnit,
    SumUnit,
    Unit,
    leaf,
)
from probabilistic_model.utils import MissingDict

DiscreteVariable = Union[Symbolic, Integer]
DiscreteDistribution = Union[SymbolicDistribution, IntegerDistribution]


class CovarianceType(enum.StrEnum):
    """
    The shape of each component's covariance, named as in scikit-learn.
    """

    FULL = "full"
    """
    Every component has its own covariance matrix.
    """

    TIED = "tied"
    """
    All components share one covariance matrix.
    """

    DIAG = "diag"
    """
    Every component has its own diagonal covariance matrix.
    """

    SPHERICAL = "spherical"
    """
    Every component has its own single variance.
    """

    @property
    def stepmix_model(self) -> str:
        """
        :return: The name of StepMix's measurement model for this type.
        """
        return f"gaussian_{self.value}"

    @property
    def is_diagonal(self) -> bool:
        """
        :return: Whether the variables of a component are uncorrelated.
        """
        return self in (CovarianceType.DIAG, CovarianceType.SPHERICAL)

    def full_covariances(
        self, covariances: npt.NDArray, n_components: int, n_features: int
    ) -> npt.NDArray:
        """
        :param covariances: The covariances in scikit-learn's layout for this type.
        :param n_components: The number of components.
        :param n_features: The number of continuous variables.
        :return: The covariance matrix of each component, of shape
            ``(n_components, n_features, n_features)``.
        """
        match self:
            case CovarianceType.FULL:
                return covariances
            case CovarianceType.TIED:
                return np.broadcast_to(
                    covariances, (n_components, n_features, n_features)
                )
            case CovarianceType.DIAG:
                return np.stack([np.diag(variances) for variances in covariances])
            case CovarianceType.SPHERICAL:
                return np.stack(
                    [np.eye(n_features) * variance for variance in covariances]
                )


@dataclass
class GaussianMixtureLearningMethod(LearningMethod, ABC):
    """
    A learning method whose circuit is a sum unit over one product per component.

    Uncorrelated or univariate Gaussians become products of univariate Gaussian
    leaves; all others become one multivariate Gaussian leaf.
    """

    @staticmethod
    def _variables(
        data: pd.DataFrame, variables: Optional[Iterable[AnnotatedVariable]]
    ) -> List[Variable]:
        """
        :return: The given variables, or those inferred from the data.
        """
        if variables is None:
            variables = infer_variables_from_dataframe(data)
        return [annotated_variable.variable for annotated_variable in variables]

    @staticmethod
    def _continuous_values(
        data: pd.DataFrame, continuous: Sequence[Continuous]
    ) -> npt.NDArray:
        """
        :return: The columns of the continuous variables, in their order, as floats.
        """
        return data[[variable.name for variable in continuous]].to_numpy(dtype=float)

    @classmethod
    def _circuit(
        cls,
        covariance_type: CovarianceType,
        continuous: Sequence[Continuous],
        weights: npt.NDArray,
        means: Optional[npt.NDArray],
        covariances: Optional[npt.NDArray],
        discrete_distributions: Sequence[Sequence[DiscreteDistribution]],
    ) -> ProbabilisticCircuit:
        """
        :param covariance_type: The layout of the covariances.
        :param continuous: The continuous variables, in the order of the means.
        :param weights: The weight of each component.
        :param means: The mean of each component, or ``None`` without continuous
            variables.
        :param covariances: The covariances, or ``None`` without continuous variables.
        :param discrete_distributions: For each component, the distributions of the
            discrete variables.
        :return: The mixture as a circuit.
        """
        continuous = tuple(continuous)
        if continuous:
            covariances = covariance_type.full_covariances(
                covariances, len(weights), len(continuous)
            )
        circuit = ProbabilisticCircuit()
        root = SumUnit(probabilistic_circuit=circuit)
        for component, (weight, discrete) in enumerate(
            zip(weights, discrete_distributions)
        ):
            factors = []
            if continuous and (covariance_type.is_diagonal or len(continuous) == 1):
                factors += cls._univariate_gaussian_leaves(
                    continuous,
                    means[component],
                    np.diag(covariances[component]),
                    circuit,
                )
            elif continuous:
                factors.append(
                    leaf(
                        MultivariateGaussianDistribution(
                            variables=continuous,
                            mean=means[component],
                            covariance=Covariance.from_matrix(covariances[component]),
                        ),
                        circuit,
                    )
                )
            factors += [leaf(distribution, circuit) for distribution in discrete]
            root.add_subcircuit(cls._product(factors, circuit), math.log(weight))
        return circuit

    @staticmethod
    def _univariate_gaussian_leaves(
        variables: Sequence[Continuous],
        mean: npt.NDArray,
        variances: npt.NDArray,
        circuit: ProbabilisticCircuit,
    ) -> List[Unit]:
        """
        :return: One univariate Gaussian leaf per variable.
        """
        return [
            leaf(
                GaussianDistribution(
                    variable=variable,
                    location=float(location),
                    scale=math.sqrt(float(variance)),
                ),
                circuit,
            )
            for variable, location, variance in zip(variables, mean, variances)
        ]

    @staticmethod
    def _product(factors: List[Unit], circuit: ProbabilisticCircuit) -> Unit:
        """
        :return: The only factor, or a product unit over all of them.
        """
        if len(factors) == 1:
            return factors[0]
        product = ProductUnit(probabilistic_circuit=circuit)
        for factor in factors:
            product.add_subcircuit(factor)
        return product


@dataclass
class GaussianMixtureModel(GaussianMixtureLearningMethod):
    """
    Fits continuous variables with a scikit-learn :class:`GaussianMixture`.
    """

    model: GaussianMixture = field(default_factory=GaussianMixture)
    """
    The mixture to fit.
    """

    def fit(
        self,
        data: pd.DataFrame,
        variables: Optional[Iterable[AnnotatedVariable]] = None,
    ) -> ProbabilisticCircuit:
        """
        :raises NonContinuousVariableError: If a variable is not continuous.
        """
        variables = self._variables(data, variables)
        non_continuous = [
            variable for variable in variables if not isinstance(variable, Continuous)
        ]
        if non_continuous:
            raise NonContinuousVariableError(non_continuous)
        self.model.fit(self._continuous_values(data, variables))
        return self.to_probabilistic_circuit(variables)

    def to_probabilistic_circuit(
        self, variables: Sequence[Continuous]
    ) -> ProbabilisticCircuit:
        """
        Convert the fitted mixture, also one fitted outside of :meth:`fit`.

        :param variables: The variables, in the order of the columns it was fitted on.
        :return: The mixture as a circuit.
        """
        return self._circuit(
            CovarianceType(self.model.covariance_type),
            variables,
            self.model.weights_,
            self.model.means_,
            self.model.covariances_,
            [[] for _ in self.model.weights_],
        )


def default_stepmix() -> StepMix:
    """
    :return: A StepMix model started from the best of ten k-means runs, since a single
        random start often ends in a poor local optimum.
    """
    return StepMix(init_params="kmeans", n_init=10, verbose=0, progress_bar=0)


@dataclass
class StepMixModel(GaussianMixtureLearningMethod):
    """
    Fits continuous, symbolic and integer variables with a :class:`StepMix` mixture.

    A component is a Gaussian over the continuous variables times one categorical
    distribution per discrete variable.
    """

    model: StepMix = field(default_factory=default_stepmix)
    """
    The mixture to fit. Each :meth:`fit` replaces it by a copy fitted on the data.
    """

    covariance_type: CovarianceType = CovarianceType.FULL
    """
    The shape of the Gaussians' covariances.
    """

    reg_covar: float = 1e-6
    """
    The regularization added to the diagonal of the covariances.
    """

    clipped_probability: float = 1e-12
    """
    StepMix clips categorical probabilities to at least ``1e-15``; probabilities up
    to this are read as zero.
    """

    def fit(
        self,
        data: pd.DataFrame,
        variables: Optional[Iterable[AnnotatedVariable]] = None,
    ) -> ProbabilisticCircuit:
        variables = self._variables(data, variables)
        continuous = [
            variable for variable in variables if isinstance(variable, Continuous)
        ]
        discrete = [
            variable for variable in variables if not isinstance(variable, Continuous)
        ]
        columns = [self._continuous_values(data, continuous)] if continuous else []
        outcomes = []
        for variable in discrete:
            codes, keys = self._outcome_codes(variable, data[variable.name])
            columns.append(codes.reshape(-1, 1))
            outcomes.append(keys)

        # StepMix keeps the outcomes it saw in a previous fit, so refit a fresh copy
        self.model = clone(self.model).set_params(
            measurement=self._measurement(len(continuous), len(discrete))
        )
        self.model.fit(np.column_stack(columns))

        parameters = self.model.get_parameters()
        measurement = parameters["measurement"]
        discrete_distributions = [
            [
                self._distribution(
                    variable,
                    measurement[f"discrete_{index}"]["pis"][component],
                    outcomes[index],
                )
                for index, variable in enumerate(discrete)
            ]
            for component in range(self.model.n_components)
        ]
        gaussian = measurement.get("continuous", {})
        return self._circuit(
            self.covariance_type,
            continuous,
            parameters["weights"],
            gaussian.get("means"),
            gaussian.get("covariances"),
            discrete_distributions,
        )

    def _measurement(
        self, continuous_columns: int, discrete_columns: int
    ) -> Dict[str, Dict[str, Any]]:
        """
        :return: StepMix's description of one Gaussian block over the continuous
            columns, followed by one categorical block per discrete column.
        """
        measurement = {}
        if continuous_columns:
            measurement["continuous"] = {
                "model": self.covariance_type.stepmix_model,
                "n_columns": continuous_columns,
                "reg_covar": self.reg_covar,
            }
        for index in range(discrete_columns):
            measurement[f"discrete_{index}"] = {"model": "categorical", "n_columns": 1}
        return measurement

    @staticmethod
    def _outcome_codes(
        variable: DiscreteVariable, values: pd.Series
    ) -> tuple[npt.NDArray, List[Any]]:
        """
        :return: The code ``0, 1, ...`` of every row's outcome, which StepMix reads,
            and the key of each code in a distribution of the variable.
        """
        if isinstance(variable, Symbolic):
            elements = list(variable.domain.all_elements)
            index_of = {element: index for index, element in enumerate(elements)}
            codes = np.array([index_of[value] for value in values])
            keys = [hash(element) for element in variable.domain.simple_sets]
            return codes, keys
        unique, codes = np.unique(values.to_numpy(), return_inverse=True)
        return codes, [hash(value) for value in unique]

    def _distribution(
        self, variable: DiscreteVariable, probabilities: npt.NDArray, keys: List[Any]
    ) -> DiscreteDistribution:
        """
        :param probabilities: One component's probability of each outcome code.
        :param keys: The key of each outcome code.
        :return: The distribution, without the outcomes StepMix only kept by clipping.
        """
        kept = probabilities > self.clipped_probability
        total = probabilities[kept].sum()
        result = MissingDict(float)
        for key, probability in zip(
            np.asarray(keys)[: len(probabilities)][kept], probabilities[kept]
        ):
            result[key] = float(probability / total)
        distribution_class = (
            SymbolicDistribution
            if isinstance(variable, Symbolic)
            else IntegerDistribution
        )
        return distribution_class(variable=variable, probabilities=result)

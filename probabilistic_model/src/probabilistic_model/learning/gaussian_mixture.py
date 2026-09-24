"""
Fitting a probabilistic circuit as a Gaussian mixture: with the expectation-maximization
of :class:`sklearn.mixture.GaussianMixture` for continuous data, and of
:class:`stepmix.stepmix.StepMix` for data that also has symbolic or integer columns.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt
import pandas as pd
from random_events.variable import Continuous, Integer, Symbolic, Variable
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

STEPMIX_COVARIANCE_MODELS = {
    "full": "gaussian_full",
    "tied": "gaussian_tied",
    "diag": "gaussian_diag",
    "spherical": "gaussian_spherical",
}
"""
The StepMix measurement model for each scikit-learn covariance type.
"""

CLIPPED_PROBABILITY = 1e-12
"""
StepMix clips every categorical probability to at least ``1e-15`` to keep its
logarithm finite; a probability at most this is one it clipped, and is read as zero.
"""


@dataclass
class GaussianMixtureModel(LearningMethod):
    """
    Fits a Gaussian mixture and represents it as a probabilistic circuit: a sum unit
    weighing one subcircuit per component.

    Data with only continuous variables is fitted with :class:`GaussianMixture`. Data
    that also has symbolic or integer variables is fitted with :class:`StepMix`,
    whose components multiply the Gaussian by one categorical distribution per such
    variable, so that every variable takes part in choosing the components. Within a
    component the discrete variables are independent of the continuous ones and of
    each other; across components, the mixture relates them.

    A component whose covariance is diagonal (``covariance_type`` ``"diag"`` or
    ``"spherical"``) becomes a product of univariate Gaussian leaves, whose box
    probabilities are exact. Any other component becomes a single leaf holding a
    :class:`MultivariateGaussianDistribution`.
    """

    model: GaussianMixture = field(default_factory=GaussianMixture)
    """
    The scikit-learn mixture fitted on continuous data. Its number of components,
    covariance type, covariance regularization, iteration limit and random state also
    configure the fit of mixed data.
    """

    mixed_initializations: int = 10
    """
    How many k-means initializations the fit of mixed data runs, keeping the best.

    Unlike :attr:`model`'s own ``n_init``, this defaults to several, since a single
    initialization of the mixed fit often ends in a poor local optimum.
    """

    mixed_model: Optional[StepMix] = field(default=None, init=False)
    """
    The StepMix model of the last fit of mixed data.
    """

    def fit(
        self,
        data: pd.DataFrame,
        variables: Optional[Iterable[AnnotatedVariable]] = None,
    ) -> ProbabilisticCircuit:
        """
        Fit the mixture on the rows of a dataframe.

        :param data: The training rows, one column per variable.
        :param variables: The variables to fit over, each read from the column of its
            name. ``None`` infers them from the data.
        :return: The fitted mixture, as a circuit of its own.
        """
        if variables is None:
            variables = infer_variables_from_dataframe(data)
        variables = [annotated_variable.variable for annotated_variable in variables]
        continuous = [
            variable for variable in variables if isinstance(variable, Continuous)
        ]
        discrete = [
            variable for variable in variables if not isinstance(variable, Continuous)
        ]
        if not discrete:
            self.model.fit(self._continuous_values(data, continuous))
            return self.to_probabilistic_circuit(continuous)
        return self._fit_mixed(data, continuous, discrete)

    @staticmethod
    def _continuous_values(
        data: pd.DataFrame, continuous: Sequence[Continuous]
    ) -> npt.NDArray:
        """
        :return: The columns of the continuous variables, in their order, as floats.
        """
        return data[[variable.name for variable in continuous]].to_numpy(dtype=float)

    def to_probabilistic_circuit(
        self, variables: Sequence[Continuous]
    ) -> ProbabilisticCircuit:
        """
        Represent the fitted scikit-learn mixture as a probabilistic circuit.

        This also converts a mixture that was fitted outside of :meth:`fit`.

        :param variables: The variables the mixture is over, in the order of the
            columns it was fitted on.
        :return: A circuit whose root sum weighs one subcircuit per component.
        :raises sklearn.exceptions.NotFittedError: If the mixture is not fitted yet.
        """
        return self._circuit(
            variables,
            self.model.weights_,
            self.model.means_,
            self.model.covariances_,
            [[] for _ in self.model.weights_],
        )

    # %% mixed data

    def _fit_mixed(
        self,
        data: pd.DataFrame,
        continuous: Sequence[Continuous],
        discrete: Sequence[DiscreteVariable],
    ) -> ProbabilisticCircuit:
        """
        Fit continuous and discrete variables together with StepMix.

        :param data: The training rows.
        :param continuous: The continuous variables, possibly none.
        :param discrete: The symbolic and integer variables.
        :return: The fitted mixture, as a circuit of its own.
        """
        codes, outcomes = zip(
            *(
                self._outcome_codes(variable, data[variable.name])
                for variable in discrete
            )
        )
        blocks = [self._continuous_values(data, continuous)] if continuous else []
        blocks += [code.reshape(-1, 1) for code in codes]

        self.mixed_model = StepMix(
            n_components=self.model.n_components,
            measurement=self._measurement(len(continuous), len(discrete)),
            init_params="kmeans",
            n_init=self.mixed_initializations,
            max_iter=self.model.max_iter,
            random_state=self.model.random_state,
            verbose=0,
            progress_bar=0,
        )
        self.mixed_model.fit(np.column_stack(blocks))

        parameters = self.mixed_model.get_parameters()
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
        if not continuous:
            return self._circuit(
                (), parameters["weights"], None, None, discrete_distributions
            )
        return self._circuit(
            continuous,
            parameters["weights"],
            measurement["continuous"]["means"],
            measurement["continuous"]["covariances"],
            discrete_distributions,
        )

    def _measurement(
        self, continuous_columns: int, discrete_columns: int
    ) -> Dict[str, Dict[str, Any]]:
        """
        :param continuous_columns: How many continuous columns lead the data.
        :param discrete_columns: How many discrete columns follow them.
        :return: The StepMix description of those columns, in their order: one
            Gaussian block over all continuous columns, then one categorical block per
            discrete column.
        """
        measurement = {}
        if continuous_columns:
            measurement["continuous"] = {
                "model": STEPMIX_COVARIANCE_MODELS[self.model.covariance_type],
                "n_columns": continuous_columns,
                "reg_covar": self.model.reg_covar,
            }
        for index in range(discrete_columns):
            measurement[f"discrete_{index}"] = {"model": "categorical", "n_columns": 1}
        return measurement

    @staticmethod
    def _outcome_codes(
        variable: DiscreteVariable, values: pd.Series
    ) -> tuple[npt.NDArray, List[Any]]:
        """
        StepMix reads a categorical column as the codes ``0, 1, ...`` of its outcomes.

        :param variable: The variable of the column.
        :param values: The column.
        :return: The code of every row, and the key of each code's outcome in a
            distribution of the variable, keyed the way
            :class:`~probabilistic_model.learning.jpt.jpt.JointProbabilityTree` keys
            its own leaves.
        """
        if isinstance(variable, Symbolic):
            elements = list(variable.domain.all_elements)
            index_of = {element: index for index, element in enumerate(elements)}
            codes = np.array([index_of[value] for value in values])
            keys = [hash(element) for element in variable.domain.simple_sets]
            return codes, keys
        unique, codes = np.unique(values.to_numpy(), return_inverse=True)
        return codes, [hash(value) for value in unique]

    @staticmethod
    def _distribution(
        variable: DiscreteVariable, probabilities: npt.NDArray, keys: List[Any]
    ) -> DiscreteDistribution:
        """
        :param variable: The variable of the distribution.
        :param probabilities: The probability of each outcome code, as StepMix
            estimated it for one component.
        :param keys: The key of each outcome code.
        :return: The distribution, without the outcomes StepMix only kept above zero
            by clipping.
        """
        kept = probabilities > CLIPPED_PROBABILITY
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

    # %% building the circuit

    def _circuit(
        self,
        continuous: Sequence[Continuous],
        weights: npt.NDArray,
        means: Optional[npt.NDArray],
        covariances: Optional[npt.NDArray],
        discrete_distributions: Sequence[Sequence[DiscreteDistribution]],
    ) -> ProbabilisticCircuit:
        """
        :param continuous: The continuous variables, in the order of the means.
        :param weights: The weight of each component.
        :param means: The mean of each component, or nothing without continuous
            variables.
        :param covariances: The covariances in scikit-learn's layout for
            :attr:`model`'s covariance type, or nothing without continuous variables.
        :param discrete_distributions: For each component, the distributions of the
            discrete variables to multiply it with.
        :return: A circuit whose root sum weighs one subcircuit per component.
        """
        continuous = tuple(continuous)
        diagonal = self.model.covariance_type in ("diag", "spherical")
        if continuous:
            covariances = self.full_covariances(
                self.model.covariance_type, covariances, len(weights), len(continuous)
            )
        circuit = ProbabilisticCircuit()
        root = SumUnit(probabilistic_circuit=circuit)
        for component, (weight, discrete) in enumerate(
            zip(weights, discrete_distributions)
        ):
            factors = []
            if continuous and (diagonal or len(continuous) == 1):
                factors += self._univariate_gaussian_leaves(
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
            root.add_subcircuit(self._product(factors, circuit), math.log(weight))
        return circuit

    @staticmethod
    def full_covariances(
        covariance_type: str,
        covariances: npt.NDArray,
        n_components: int,
        n_features: int,
    ) -> npt.NDArray:
        """
        scikit-learn, and StepMix after it, store the covariances in a layout that
        depends on the covariance type; this spells out every component's full matrix.

        :param covariance_type: ``"full"``, ``"tied"``, ``"diag"`` or ``"spherical"``.
        :param covariances: The covariances in that type's layout.
        :param n_components: How many components the mixture has.
        :param n_features: How many continuous variables it is over.
        :return: The covariance matrix of each component, of shape
            ``(n_components, n_features, n_features)``.
        """
        match covariance_type:
            case "full":
                return covariances
            case "tied":
                return np.broadcast_to(
                    covariances, (n_components, n_features, n_features)
                )
            case "diag":
                return np.stack([np.diag(variances) for variances in covariances])
            case "spherical":
                return np.stack(
                    [np.eye(n_features) * variance for variance in covariances]
                )
        raise ValueError(f"Unknown covariance type {covariance_type!r}.")

    @staticmethod
    def _univariate_gaussian_leaves(
        variables: Sequence[Continuous],
        mean: npt.NDArray,
        variances: npt.NDArray,
        circuit: ProbabilisticCircuit,
    ) -> List[Unit]:
        """
        :param variables: The variables of the component.
        :param mean: The mean of each variable.
        :param variances: The variance of each variable.
        :param circuit: The circuit to build the leaves in.
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
        :param factors: The units to multiply.
        :param circuit: The circuit to build the product in.
        :return: The only factor, or a product unit over all of them.
        """
        if len(factors) == 1:
            return factors[0]
        product = ProductUnit(probabilistic_circuit=circuit)
        for factor in factors:
            product.add_subcircuit(factor)
        return product

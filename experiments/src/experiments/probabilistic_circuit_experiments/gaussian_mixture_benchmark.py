"""
How well a Gaussian mixture and a joint probability tree describe the same data, when
both are represented as probabilistic circuits.

Every method is fitted on a whole dataset and scored on the same rows, so the numbers
say how well a method can describe the data, not how well it generalizes. Two
quantities are reported per fit:

- the average log-likelihood of a row, over all of its columns;
- for datasets with a symbolic column, the average log-probability of that column given
  the others, i.e. how well the circuit predicts it.

The continuous columns are standardized and cast to single precision.
:class:`~random_events.interval.SimpleInterval` stores the bounds it is built with from
Python at single precision, so a support a tree fits around double precision data can
leave out the extreme rows it was fitted on, which would score them as impossible.

Circuit sizes are reported for reference only: a component of a mixture and a leaf of a
tree are not the same amount of model, so the node counts of the two methods are not
comparable.
"""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd
import tqdm
from sklearn import datasets
from sklearn.mixture import GaussianMixture
from typing_extensions import Optional, Sequence, Tuple

from experiments.experiment_definitions import (
    ExperimentResult,
    ExperimentsTable,
    TypstRenderer,
)
from probabilistic_model.learning.gaussian_mixture import GaussianMixtureModel
from probabilistic_model.learning.jpt.jpt import JointProbabilityTree
from probabilistic_model.learning.learning_method import LearningMethod
from probabilistic_model.probabilistic_circuit.rx.probabilistic_circuit import (
    ProbabilisticCircuit,
)


class Dataset(enum.StrEnum):
    """
    The scikit-learn datasets the methods are compared on.
    """

    IRIS = "iris"
    """
    Four measurements of 150 flowers, labelled with one of three species.
    """

    WINE = "wine"
    """
    Thirteen chemical measurements of 178 wines, labelled with one of three cultivars.
    """

    BREAST_CANCER = "breast_cancer"
    """
    Thirty measurements of 569 tumours, labelled benign or malignant.
    """

    DIABETES = "diabetes"
    """
    Nine measurements of 442 patients, with their sex as the symbolic column.
    """

    CALIFORNIA_HOUSING = "california_housing"
    """
    Eight measurements of 20640 districts, without a symbolic column. Downloaded by
    scikit-learn on first use.
    """

    def load(self) -> Tuple[pd.DataFrame, Optional[str]]:
        """
        :return: The dataset with its continuous columns standardized and cast to single
            precision, and the name of its symbolic column, if it has one.
        """
        loader = getattr(datasets, f"fetch_{self.value}", None) or getattr(
            datasets, f"load_{self.value}"
        )
        bunch = loader(as_frame=True)
        features = bunch.data.astype(float)
        if self is Dataset.CALIFORNIA_HOUSING:
            return standardized(features), None
        if self is Dataset.DIABETES:
            symbolic = np.where(features.pop("sex") > 0, "first", "second")
            return standardized(features).assign(sex=symbolic), "sex"
        labels = np.asarray(bunch.target_names)[bunch.target.to_numpy()]
        return standardized(features).assign(label=labels.astype(str)), "label"


def standardized(features: pd.DataFrame) -> pd.DataFrame:
    """
    :param features: Continuous columns.
    :return: The columns with zero mean and unit standard deviation, at single
        precision.
    """
    return ((features - features.mean()) / features.std()).astype(np.float32)


class Method(enum.StrEnum):
    """
    The learning methods compared.
    """

    GAUSSIAN_MIXTURE = "Gaussian mixture"
    """
    :class:`GaussianMixtureModel` with full covariances.
    """

    JOINT_PROBABILITY_TREE = "Joint probability tree"
    """
    :class:`JointProbabilityTree`.
    """


@dataclass
class Setting:
    """
    One configuration of a method.
    """

    method: Method
    """
    The method configured.
    """

    size: float
    """
    The number of components of a mixture, or the minimum share of the rows in a leaf
    of a tree.
    """

    def learning_method(self) -> LearningMethod:
        """
        :return: A method configured this way, not yet fitted.
        """
        if self.method is Method.GAUSSIAN_MIXTURE:
            return GaussianMixtureModel(
                GaussianMixture(n_components=int(self.size), random_state=0)
            )
        return JointProbabilityTree(min_samples_per_leaf=self.size)

    def __str__(self) -> str:
        if self.method is Method.GAUSSIAN_MIXTURE:
            components = int(self.size)
            return f"{components} component{'' if components == 1 else 's'}"
        return f"leaves of at least {self.size:.0%} of the rows"


SETTINGS = [
    *(Setting(Method.GAUSSIAN_MIXTURE, components) for components in (1, 3, 5, 10)),
    *(
        Setting(Method.JOINT_PROBABILITY_TREE, share)
        for share in (0.2, 0.1, 0.05, 0.02)
    ),
]
"""
The configurations every dataset is fitted with.
"""


@dataclass
class GaussianMixtureBenchmarkResult(ExperimentResult):
    """
    One method, in one configuration, fitted on one dataset.
    """

    dataset: Dataset
    """
    The dataset fitted and scored on.
    """

    method: Method
    """
    The method fitted.
    """

    setting: str
    """
    How the method was configured.
    """

    average_log_likelihood: float
    """
    The mean log-likelihood of a row, over all of its columns.
    """

    symbolic_given_rest: Optional[float]
    """
    The mean log-probability of the symbolic column given the other columns, or nothing
    for a dataset without one. Zero means the circuit predicts it perfectly.
    """

    impossible_rows: int
    """
    How many of the rows the circuit it fitted on gives no density at all.
    """

    nodes: int
    """
    How many units the fitted circuit has.
    """

    duration: float
    """
    Time spent fitting, in seconds.
    """


def measure(
    dataset: Dataset,
    data: pd.DataFrame,
    symbolic: Optional[str],
    setting: Setting,
) -> GaussianMixtureBenchmarkResult:
    """
    Fit one configuration of a method on a dataset and score it on the same rows.

    :param dataset: The dataset the rows are from.
    :param data: The rows, as :meth:`Dataset.load` returns them.
    :param symbolic: The name of the symbolic column, if there is one.
    :param setting: The configuration to fit.
    :return: The measurement.
    """
    start = time.perf_counter()
    circuit = setting.learning_method().fit(data)
    duration = time.perf_counter() - start

    joint = log_likelihood(circuit, data)
    symbolic_given_rest = None
    if symbolic is not None:
        rest = circuit.marginal(
            [variable for variable in circuit.variables if variable.name != symbolic]
        )
        symbolic_given_rest = float(np.mean(joint - log_likelihood(rest, data)))

    return GaussianMixtureBenchmarkResult(
        dataset=dataset,
        method=setting.method,
        setting=str(setting),
        average_log_likelihood=float(np.mean(joint)),
        symbolic_given_rest=symbolic_given_rest,
        impossible_rows=int(np.sum(~np.isfinite(joint))),
        nodes=len(circuit.nodes()),
        duration=duration,
    )


def log_likelihood(circuit: ProbabilisticCircuit, data: pd.DataFrame) -> np.ndarray:
    """
    :param circuit: The circuit to score with.
    :param data: The rows to score, with at least a column per variable of the circuit.
    :return: The log-likelihood of every row under the circuit.
    """
    columns = [variable.name for variable in circuit.variables]
    return circuit.log_likelihood(data[columns].to_numpy())


def benchmark(
    dataset: Dataset, settings: Sequence[Setting] = tuple(SETTINGS)
) -> ExperimentsTable:
    """
    :param dataset: The dataset to fit on.
    :param settings: The configurations to fit.
    :return: One row per configuration.
    """
    data, symbolic = dataset.load()
    return ExperimentsTable(
        [
            measure(dataset, data, symbolic, setting)
            for setting in tqdm.tqdm(settings, desc=str(dataset))
        ]
    )


def main(datasets_to_run: Sequence[Dataset] = tuple(Dataset)):
    for dataset in datasets_to_run:
        print(
            TypstRenderer(benchmark(dataset)).render_figure(
                f"Gaussian mixtures and joint probability trees fitted on the whole "
                f"{dataset} dataset and scored on the same rows, with the continuous "
                f"columns standardized. Higher log-likelihoods are better; the "
                f"log-probability of the symbolic column given the rest is at most 0, "
                f"and 0 means a perfect prediction. Node counts are not comparable "
                f"across methods."
            )
        )
        print()


if __name__ == "__main__":
    main()

"""
The ways a probabilistic circuit is fitted on a dataframe, so that a model owning a
circuit can be told how to fit it instead of fitting it itself.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import pandas as pd
from typing_extensions import List, Sequence

from probabilistic_model.learning.jpt.jpt import JointProbabilityTree
from probabilistic_model.learning.jpt.variables import AnnotatedVariable
from probabilistic_model.probabilistic_circuit.rx.probabilistic_circuit import (
    ProbabilisticCircuit,
    SumUnit,
)


@dataclass
class LearningMethod(ABC):
    """
    A way of fitting a probabilistic circuit on a dataframe.
    """

    @abstractmethod
    def fit(
        self, dataframe: pd.DataFrame, variables: List[AnnotatedVariable]
    ) -> ProbabilisticCircuit:
        """
        Fit a circuit on the rows of a dataframe.

        :param dataframe: The training rows, one column per variable.
        :param variables: The variables inferred over the dataframe, one per column,
            carrying the annotation (mean, standard deviation, split thresholds) the
            fit is guided by.
        :return: The fitted circuit.
        """


@dataclass
class JointProbabilityTreeLearning(LearningMethod):
    """
    Fits a :class:`~probabilistic_model.learning.jpt.jpt.JointProbabilityTree`.
    """

    min_samples_per_leaf: float = 1
    """
    The fewest training rows a leaf may hold, or, below one, that number as a fraction
    of the training rows. The default lets the tree split down to one row per leaf,
    which pins every continuous attribute to the training values it saw.
    """

    def fit(
        self, dataframe: pd.DataFrame, variables: List[AnnotatedVariable]
    ) -> ProbabilisticCircuit:
        return JointProbabilityTree(
            annotated_variables=variables, min_samples_per_leaf=self.min_samples_per_leaf
        ).fit(dataframe)


@dataclass
class StratifiedLearning(LearningMethod):
    """
    Fits one circuit per distinct joint value of some columns with another learning
    method, and combines them under a sum weighted by each value's relative frequency.

    Every row of one partition shares the same value of those columns, so within its
    circuit their distribution is a single point by construction, however the wrapped
    method splits on the remaining columns: the fitted circuit is support-deterministic
    over the columns, the precondition a causal query on them needs. A single
    unconstrained fit could instead spread rows sharing a value across sibling leaves.
    """

    columns: Sequence[str]
    """
    The columns whose joint value the rows are partitioned by; a single column is a
    one-element sequence.
    """

    method: LearningMethod = field(default_factory=JointProbabilityTreeLearning)
    """
    What every partition is fitted with.
    """

    def fit(
        self, dataframe: pd.DataFrame, variables: List[AnnotatedVariable]
    ) -> ProbabilisticCircuit:
        result = ProbabilisticCircuit()
        root = SumUnit(probabilistic_circuit=result)
        total_row_count = len(dataframe)
        for _, partition in dataframe.groupby(list(self.columns), sort=False):
            partition_circuit = self.method.fit(
                partition.reset_index(drop=True), variables
            )
            node_index_map = result.mount(partition_circuit.root)
            root.add_subcircuit(
                node_index_map[partition_circuit.root.index],
                math.log(len(partition) / total_row_count),
            )
        return result

from __future__ import annotations
from collections import deque
import enum
from dataclasses import dataclass
import numpy as np
import pandas as pd
from typing import (
    Any,
    Dict,
    Iterator,
    List,
    Optional,
    Tuple,
    Type,
    Set,
    Union,
    Iterable,
)

from sqlalchemy import Column

from krrood.entity_query_language.core.mapped_variable import MappedVariable, Attribute
from krrood.entity_query_language.core.variable import Variable
from krrood.entity_query_language.factories import variable
from krrood.ormatic.data_access_objects.dao import DataAccessObject
from krrood.ormatic.data_access_objects.helper import (
    get_alternative_mapping,
    get_dao_class,
)
from krrood.ormatic.exceptions import UnsupportedColumnType
from probabilistic_model.learning.jpt.jpt import JointProbabilityTree
from probabilistic_model.learning.jpt.variables import infer_variables_from_dataframe
from probabilistic_model.probabilistic_circuit.relational.rspns import (
    RSPNTemplate,
    RSPNSpecification,
)
from random_events.variable import variable_from_name_and_type, compatible_types
from krrood_test.dataset.ormatic_interface import Base


def get_aggregate_statistics(instance: Any) -> List[Tuple[Any, str]]:
    statistics = []
    for name in dir(instance):
        if name.startswith("__"):
            continue

        attr = getattr(instance, name)

        if not callable(attr):
            continue

        if not hasattr(attr, "_statistic_name"):
            continue

        statistics.append((attr(), attr._statistic_name))

    return statistics


def get_python_type_from_sqlalchemy_column(column: Column):
    try:
        python_type = [column.type.python_type]
    except NotImplementedError:
        python_type = [
            key
            for key, value in Base.type_mappings.items()
            if value == type(column.type)
        ]

    if not python_type:
        raise UnsupportedColumnType(column.type)

    if len(python_type) > 1:
        raise TypeError(f"Multiple types found for column {column.name}")

    python_type = python_type[0]

    return python_type


@dataclass
class FeatureExtractor:
    """
    A class to extract features from a given class. Features are all attributes of the class, propagating custom types/objects down. The features are represented as symbolic variables.
    """

    instances: Union[Any, List[Any]]
    """
    The instances to extract features from. Can be a single instance or a list.
    """

    symbolic_root: Optional[Variable] = None
    """
    The root symbolic variable to use when traversing the object graph. Defaults to variable(type(instances[0]), []).
    """

    def __post_init__(self):
        if not isinstance(self.instances, list):
            self.instances = [self.instances]

    @property
    def features(self) -> List[MappedVariable]:
        root = self.symbolic_root or variable(type(self.instances[0]), [])
        return self._extract_features(self.instances[0], root)

    def _extract_features(
        self, example_instance: DataAccessObject, symbolic_root: Variable
    ) -> List[MappedVariable]:
        result = []
        seen = set()
        queue = deque()
        queue.append((example_instance, symbolic_root))

        while queue:
            current_instance, current_symbolic = queue.popleft()

            if id(current_instance) in seen:
                continue
            seen.add(id(current_instance))

            specification = RSPNSpecification(type(current_instance))

            for attribute in specification.attributes:
                value = getattr(current_instance, attribute.key)

                if not isinstance(value, compatible_types):
                    continue

                symbolic_attribute = getattr(current_symbolic, attribute.name)
                symbolic_attribute._type_ = get_python_type_from_sqlalchemy_column(
                    attribute
                )
                result.append(symbolic_attribute)

            for part in specification.unique_parts:
                value = getattr(current_instance, part)

                if value is None:
                    continue

                queue.append((value, getattr(current_symbolic, part)))

        return result

    def __iter__(self) -> Iterator[MappedVariable]:
        return iter(self.features)

    def apply_mapping(self, instance: Any) -> List:
        return [
            feature.apply_mapping_on_external_root(instance)
            for feature in self.features
        ]

    def create_dataframe(self, instances: List[DataAccessObject]) -> pd.DataFrame:
        """
        Create a dataframe from the given instances.
        """
        result = []
        for instance in instances:
            result.append(self.apply_mapping(instance))
        features_names = [f._name_ for f in self.features]
        return pd.DataFrame(columns=features_names, data=result)


def preprocess_dataframe(
    features: List[MappedVariable], df: pd.DataFrame
) -> pd.DataFrame:
    feature_map = dict(zip(df.columns, features))
    for column in df.columns:
        feature = feature_map[column]
        if feature._type_ is bool:
            df[column] = df[column].astype(int)
        elif isinstance(feature._type_, enum.EnumType):
            df[column] = df[column].apply(lambda x: hash(x))
        elif feature._type_ not in compatible_types and feature._type_ is not None:
            raise TypeError(f"Unsupported type {feature._type_} for column {column}")
    return df


def LearnRSPN(cls: Any, instances: List[DataAccessObject]) -> RSPNTemplate:
    """
    Learn an RSPN for class C.

    - Attributes become univariate leaves (Gaussian for numeric, Bernoulli for boolean)
    - Relation aggregates become Bernoulli leaves over presence (1 if present, else 0)
    - Parts recurse into their class (unique part: map one-to-one; exchangeable part: flatten list)
    - Independent partitions become product nodes; clustering on instances becomes sum nodes with weights

    Returns the root node (ProductUnit or SumUnit) within a ProbabilisticCircuit.
    """

    feature_extractor = FeatureExtractor(instances)

    if not feature_extractor.features:
        raise ValueError(f"No features found for class {cls}")

    df: pd.DataFrame = feature_extractor.create_dataframe(instances)
    df = preprocess_dataframe(feature_extractor.features, df)
    df = df.sort_index(axis=1)
    variables = infer_variables_from_dataframe(df)

    jpt = JointProbabilityTree(variables, min_samples_per_leaf=2)
    jpt = jpt.fit(df)
    rspn = RSPNTemplate(RSPNSpecification(get_dao_class(cls)), jpt)
    return rspn

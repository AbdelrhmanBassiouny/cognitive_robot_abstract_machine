from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing_extensions import Type, Dict, Union

from krrood.parametrization.parameterizer import (
    UnderspecifiedParameters,
    SelectedAttributesParameters,
    ConditionParameters,
)
from krrood.utils import get_class_and_attribute_name
from probabilistic_model.probabilistic_circuit.causal.causal_circuit import (
    CausalCircuit,
)
from probabilistic_model.probabilistic_circuit.relational.rspn import (
    RelationalProbabilisticCircuit,
)
from probabilistic_model.probabilistic_circuit.rx.helper import fully_factorized
from probabilistic_model.probabilistic_model import ProbabilisticModel

ModelResolutionParameters = Union[
    UnderspecifiedParameters,
    SelectedAttributesParameters,
    ConditionParameters,
]
"""
Whatever a :class:`ModelRegistry` needs to resolve a model: a full
:class:`~krrood.parametrization.parameterizer.UnderspecifiedParameters` (for a
``Match`` or a ``distribution(...)``, which wraps one), or one of the lighter parameter
classes for the other probabilistic query constructs (``moment``, ``probability``) --
all of them expose ``.variables`` and ``.queried_class``.
"""


@dataclass
class ModelRegistry(ABC):
    """
    A registry that selects probabilistic models for given underspecified parameters of
    match-queries (or other probabilistic queries).
    """

    @abstractmethod
    def get_model(self, parameters: ModelResolutionParameters) -> ProbabilisticModel:
        """
        :param parameters: The parameters to get a model for.
        :return: A probabilistic model that can be used to generate answers for the given expression.
        """


@dataclass
class FullyFactorizedRegistry(ModelRegistry):
    """
    A registry that always returns a fully factorized model.
    """

    def get_model(self, parameters: ModelResolutionParameters) -> ProbabilisticModel:
        return fully_factorized(parameters.variables.values())


@dataclass
class DictRegistry(ModelRegistry):
    """
    A registry that uses a dictionary to keep all models.
    """

    models: Dict[Type, ProbabilisticModel]
    """
    A dictionary that maps classes to probabilistic models.
    """

    def get_model(self, parameters: ModelResolutionParameters) -> ProbabilisticModel:
        return self.models[parameters.queried_class]


@dataclass
class RelationalCircuitRegistry(ModelRegistry):
    """
    A registry that grounds a RelationalProbabilisticCircuit for the queried statement
    and aligns its variable names to the UnderspecifiedParameters convention before
    returning.

    Only supports :class:`~krrood.parametrization.parameterizer.UnderspecifiedParameters`
    (i.e. a ``Match``, directly or wrapped by ``distribution(...)``): grounding needs
    the full match statement, which ``moment``'s/``probability``'s lighter parameter
    classes don't carry.
    """

    relational_probabilistic_circuit: RelationalProbabilisticCircuit
    """
    The trained relational probabilistic circuit to ground.
    """

    def get_model(self, parameters: UnderspecifiedParameters) -> ProbabilisticModel:
        grounded = self.relational_probabilistic_circuit.ground(parameters.statement)
        class_prefix = self.relational_probabilistic_circuit.class_.__name__
        rename_map = {}
        for circuit_var in grounded.variables:
            qualified_name = get_class_and_attribute_name(
                class_prefix, circuit_var.name
            )
            if qualified_name in parameters.variables:
                rename_map[circuit_var] = parameters.variables[qualified_name]
        grounded.update_variables(rename_map)
        return grounded


@dataclass
class CausalCircuitRegistry(ModelRegistry):
    """
    A registry that maps target classes directly to pre-built causal circuits, so a
    ``cause``/``causes_effect()`` query can be routed through that circuit's
    ``backdoor_adjustment`` method.

    See
    :class:`~probabilistic_model.probabilistic_circuit.causal.causal_circuit.CausalCircuit`.
    """

    circuits: Dict[Type, CausalCircuit]
    """
    A dictionary that maps classes to pre-built causal circuits.
    """

    def get_model(self, parameters: ModelResolutionParameters) -> ProbabilisticModel:
        return self.circuits[parameters.queried_class]

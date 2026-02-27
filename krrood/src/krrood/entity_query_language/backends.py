from abc import abstractmethod, ABC
from dataclasses import dataclass
from typing import Any, Iterable, TypeVar

from krrood.entity_query_language.failures import NoSolutionFound
from krrood.entity_query_language.query.match import Match
from krrood.entity_query_language.query.query import Query
from krrood.ormatic.eql_interface import eql_to_sql
from krrood.probabilistic_knowledge.parameterizer import (
    MatchParameterizer,
    copy_partial_object,
)
from krrood.probabilistic_knowledge.probable_variable import (
    MatchToInstanceTranslator,
    QueryToRandomEventTranslator,
)
from probabilistic_model.probabilistic_model import ProbabilisticModel

T = TypeVar("T")


@dataclass
class QueryBackend(ABC):
    """
    Base class for all domains.
    Domains are generators for data.
    """

    @abstractmethod
    def evaluate(self, expression: Query) -> Iterable[T]: ...


@dataclass
class SelectiveBackend(QueryBackend, ABC):
    """
    Selective backends are backends that select elements from existing data.
    """


@dataclass
class GenerativeBackend(QueryBackend, ABC):
    """
    Generative backends are backends that generate new elements.
    """


@dataclass
class DatabaseBackend(SelectiveBackend):
    """
    A domain that selects elements from a database.
    """

    session_maker: Any

    def evaluate(self, expression: Query) -> Iterable:
        session = self.session_maker()
        translator = eql_to_sql(expression, session)
        yield from translator.evaluate()


@dataclass
class PythonBackend(SelectiveBackend):
    """
    A domain that selects elements from a python process.
    """

    def evaluate(self, expression: Query) -> Iterable:
        yield from expression.evaluate()


@dataclass
class ProbabilisticBackend(GenerativeBackend):
    """
    A domain that generates elements from a probabilistic model.
    """

    model: ProbabilisticModel
    number_of_samples: int = 50

    def evaluate(self, expression: Match[T]) -> Iterable[T]:
        match_translator = MatchToInstanceTranslator(expression)
        example_instance = match_translator.translate()
        random_events_translator = QueryToRandomEventTranslator(expression.expression)
        truncation_event = random_events_translator.translate()

        instance_parameterizer = MatchParameterizer(example_instance)
        parameters = instance_parameterizer.parameterize()

        conditioned, _ = self.model.conditional(parameters.assignments_for_conditioning)

        if conditioned is None:
            raise NoSolutionFound(expression.expression)

        truncated, _ = conditioned.truncated(truncation_event)

        if truncated is None:
            raise NoSolutionFound(expression.expression)

        samples = truncated.sample(self.number_of_samples)

        for sample in samples:

            sample_dict = parameters.create_assignment_from_variables_and_sample(
                truncated.variables, sample
            )

            current_example_instance = copy_partial_object(example_instance)

            instance = parameters.parameterize_object_with_sample(
                current_example_instance, sample_dict
            )
            yield instance

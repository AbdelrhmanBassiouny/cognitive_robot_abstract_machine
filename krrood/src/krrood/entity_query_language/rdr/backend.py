"""
RDR backend for underspecified EQL queries.

An underspecified ``Match`` marks the attribute to infer with ``...``, filters the
domain with its concrete keyword arguments, and supplies the instances to complete —
``an(Animal)(milk=True, species=...).from_(animals)``. This backend answers such a query
by inferring the marked attribute on each instance the filter keeps.

It keeps one :class:`~krrood.entity_query_language.rdr.single_class.EQLSingleClassRDR`
for each attribute of each type it is asked about, and fits a model it does not have yet
before inferring through it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import (
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    Optional,
    Self,
    Type,
)

from krrood.entity_query_language.core.base_expressions import UnificationDict
from krrood.entity_query_language.core.mapped_variable import Attribute
from krrood.entity_query_language.query.match import Match
from krrood.entity_query_language.rdr.expert import Expert
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR
from krrood.entity_query_language.rdr.underspecified import UnderspecifiedMatch

GroundTruth = Callable[[Any], Any]
"""
Supplies the known conclusion for one case.

A conclusion every case shares is the callable that returns it.
"""

# %% what a model is filed under


@dataclass(frozen=True)
class ModelKey:
    """
    Identifies the RDR that infers one attribute of one type.
    """

    case_type: Type
    """
    The type whose instances the model classifies.
    """

    attribute_name: str
    """
    The attribute of that type the model predicts.
    """

    @classmethod
    def from_attribute(cls, attribute: Attribute) -> Self:
        """
        :param attribute: An EQL attribute expression, e.g. ``animal.species``.
        :return: The key of the model predicting that attribute.
        """
        return cls(attribute._owner_class_, attribute._attribute_name_)


@dataclass(frozen=True)
class InferredCase:
    """
    One instance and what the RDR concluded about it.
    """

    case: Any
    """
    The instance the query kept.
    """

    conclusion: Any
    """
    The value inferred for the underspecified attribute.
    """


# %% the backend


@dataclass
class RDRBackend:
    """
    Infers underspecified (``...``) attributes on existing instances via RDR models.
    """

    expert: Optional[Expert] = None
    """
    Authors each new rule's conditions, and its conclusion when there is no ground
    truth.
    """

    models: Dict[ModelKey, EQLSingleClassRDR] = field(default_factory=dict)
    """
    The RDR the backend has learned for each attribute it has been asked about.
    """

    def fit(self, query: Match, ground_truth: Optional[GroundTruth] = None) -> Self:
        """
        Train the model for ``query``'s ``...`` attribute over the instances its
        concrete constraints keep.

        :param query: An underspecified ``Match`` carrying a domain.
        :param ground_truth: Labels each case; ``None`` has the expert label them.
        :return: This backend, for chaining.
        """
        self._fit(UnderspecifiedMatch(query), ground_truth)
        return self

    def infer(
        self, query: Match, ground_truth: Optional[GroundTruth] = None
    ) -> Iterator[UnificationDict]:
        """
        Lazily infer ``query``'s ``...`` attribute on each instance it keeps, leaving
        those instances untouched.

        :param query: An underspecified ``Match`` carrying a domain.
        :param ground_truth: Used only if there is no model yet and one must be fitted.
        :return: One binding per case, of the query's own variable to the instance and
            of its underspecified attribute to the inferred value.
        """
        statement = UnderspecifiedMatch(query)
        attribute = statement.single_target().attribute
        for inferred in self._inferences(statement, ground_truth):
            yield UnificationDict(
                {statement.variable: inferred.case, attribute: inferred.conclusion}
            )

    def fill(
        self, query: Match, ground_truth: Optional[GroundTruth] = None
    ) -> List[Any]:
        """
        Infer ``query``'s ``...`` attribute and set it on each instance it keeps.

        Every instance is written before this returns, so nothing is left to a caller
        that never reads the result.

        :param query: An underspecified ``Match`` carrying a domain.
        :param ground_truth: Used only if there is no model yet and one must be fitted.
        :return: The instances that were filled, in the order the query yielded them.
        """
        statement = UnderspecifiedMatch(query)
        attribute_name = statement.target_attribute_name
        filled: List[Any] = []
        for inferred in self._inferences(statement, ground_truth):
            setattr(inferred.case, attribute_name, inferred.conclusion)
            filled.append(inferred.case)
        return filled

    def _inferences(
        self, statement: UnderspecifiedMatch, ground_truth: Optional[GroundTruth]
    ) -> Iterator[InferredCase]:
        """
        Classify each case the statement keeps, fitting a model first if there is none.

        :param statement: The underspecified query being answered.
        :param ground_truth: Labels each case if a fit is needed; ``None`` has the
            expert label them.
        :return: Each case paired with what the model concluded about it.
        """
        model = self._fitted_model_for(statement, ground_truth)
        for case in statement.filtered_cases():
            yield InferredCase(case=case, conclusion=model.classify(case))

    def _fitted_model_for(
        self, statement: UnderspecifiedMatch, ground_truth: Optional[GroundTruth]
    ) -> EQLSingleClassRDR:
        """
        :param statement: The underspecified query being answered.
        :param ground_truth: Labels each case if a fit is needed.
        :return: The model for the statement's attribute, fitted if it is new.
        """
        key = self._key_for(statement)
        if key in self.models:
            return self.models[key]
        return self._fit(statement, ground_truth)

    def _fit(
        self, statement: UnderspecifiedMatch, ground_truth: Optional[GroundTruth]
    ) -> EQLSingleClassRDR:
        """
        Fit the statement's model over the cases its concrete constraints keep.

        The whole filtered domain is fitted in one call, so the fit converges against
        its own ground truth and the model is written once rather than once per case.

        :param statement: The underspecified query to train over.
        :param ground_truth: Labels each case; ``None`` has the expert label them.
        :return: The fitted model.
        """
        cases = list(statement.filtered_cases())
        targets = (
            None if ground_truth is None else [ground_truth(case) for case in cases]
        )
        model = self._model_for(statement)
        model.fit(cases, targets, self.expert)
        return model

    def _model_for(self, statement: UnderspecifiedMatch) -> EQLSingleClassRDR:
        """
        :param statement: The underspecified query being answered.
        :return: The model for the statement's attribute, created empty if there is none.
        """
        key = self._key_for(statement)
        if key not in self.models:
            self.models[key] = EQLSingleClassRDR.from_underspecified(statement.match)
        return self.models[key]

    @staticmethod
    def _key_for(statement: UnderspecifiedMatch) -> ModelKey:
        """
        :param statement: The underspecified query being answered.
        :return: The key its model is filed under.
        """
        return ModelKey.from_attribute(statement.single_target().attribute)

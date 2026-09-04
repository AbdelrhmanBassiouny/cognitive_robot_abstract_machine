"""
Tests for the ``@rdr`` decorator: what it builds from a function, what a call to the
decorated function answers with, and what survives being saved and read back.
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import patch

import pytest
from typing_extensions import Any, Callable, Dict, List, Optional

from krrood.code_generation.exceptions import FunctionMissingAnnotationsError
from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.rdr.answer_vocabulary import AnswerName
from krrood.entity_query_language.rdr.decorator import (
    CONCLUSION_ATTRIBUTE_NAME,
    RDRWrapper,
    rdr,
)
from krrood.entity_query_language.rdr.expert import Expert
from krrood.entity_query_language.rdr.function_case import FunctionCase
from krrood.entity_query_language.rdr.interface import (
    AnswerRequest,
    CaseContext,
    FunctionInterface,
)
from krrood.entity_query_language.rdr.serialization import load_rdr
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR

# %% the functions the decorator is applied to

FALLBACK_LABEL: str = "fallback"
"""
What :func:`coordinate_label` returns when no rule has anything better to say.
"""

POSITIVE_DISTANCE_CONCLUSION: float = 99.0
"""
What :func:`positive_x_expert` concludes for a case whose ``x`` is positive.
"""


def distance(x: float, y: float) -> float:
    """
    Compute Euclidean distance.

    Defined at module level, where a decorated function belongs: the model file the
    decorator writes imports the function back by name.

    :param x: Distance along the first axis.
    :param y: Distance along the second axis.
    :return: The distance from the origin.
    """
    return (x**2 + y**2) ** 0.5


def coordinate_label(x: float) -> Optional[str]:
    """
    Label a coordinate, or nothing.

    Its return type admits ``None``, so a rule may conclude ``None`` deliberately.

    :param x: The coordinate to label.
    :return: The fallback label, which a fitted rule may override.
    """
    return FALLBACK_LABEL


def add(first: int, second: int) -> int:
    """
    Add two integers.

    :param first: The first summand.
    :param second: The second summand.
    :return: Their sum.
    """
    return first + second


# %% a scripted expert


@dataclass
class ScriptedAnswer:
    """
    Answers every case with one fixed conclusion and one fixed condition, so a fit
    inserts a rule without a person present.
    """

    conclusion: Any
    """
    The value every case answered for is labelled with.
    """

    condition: Callable[[Any], SymbolicExpression]
    """
    Builds the rule's condition from the rule tree's shared case variable.
    """

    def __call__(
        self, context: CaseContext, requests: List[AnswerRequest]
    ) -> Dict[AnswerName, Any]:
        """
        :param context: The case being fitted.
        :param requests: The answers the engine asked for, in order.
        :return: The conditions, plus the conclusion whenever it was asked for.
        """
        answers: Dict[AnswerName, Any] = {
            AnswerName.CONDITIONS: self.condition(context.case_variable)
        }
        if any(request.name is AnswerName.CONCLUSION for request in requests):
            answers[AnswerName.CONCLUSION] = self.conclusion
        return answers


def scripted_expert(
    conclusion: Any, condition: Callable[[Any], SymbolicExpression]
) -> Expert:
    """
    :param conclusion: The value every case is labelled with.
    :param condition: Builds the rule's condition from the shared case variable.
    :return: An expert answering both of the engine's questions from those two values.
    """
    return Expert(
        interface=FunctionInterface(
            answer_function=ScriptedAnswer(conclusion=conclusion, condition=condition)
        )
    )


# %% fixtures


@pytest.fixture
def distance_wrapper(tmp_path) -> RDRWrapper:
    """
    :return: :func:`distance` decorated with a model file under ``tmp_path``, so nothing
        is written beside this test module.
    """
    return rdr(str(tmp_path / "distance_rdr.py"))(distance)


@pytest.fixture
def fitting_distance_wrapper(tmp_path) -> RDRWrapper:
    """
    :return: :func:`distance` decorated in fit mode.
    """
    return rdr(str(tmp_path / "distance_fit_rdr.py"), fit=True)(distance)


@pytest.fixture
def positive_x_expert() -> Expert:
    """
    :return: An expert concluding :data:`POSITIVE_DISTANCE_CONCLUSION` whenever ``x`` is
        positive.
    """
    return scripted_expert(
        POSITIVE_DISTANCE_CONCLUSION, lambda case_variable: case_variable.x > 0
    )


# %% what the decorator builds


class TestWhatTheDecoratorBuilds:
    """
    Decorating a fully annotated function produces a wrapper carrying that function's
    own rule tree and generated case class.
    """

    def test_decorated_function_is_a_wrapper(self, distance_wrapper):
        """
        The decorator replaces the function with its wrapper, not with the raw function.
        """
        assert isinstance(distance_wrapper, RDRWrapper)

    def test_wrapper_name_is_the_function_name(self, distance_wrapper):
        """
        The wrapper answers to the decorated function's own name.
        """
        assert distance_wrapper.__name__ == distance.__name__

    def test_wrapper_documentation_is_the_function_documentation(
        self, distance_wrapper
    ):
        """
        The wrapper carries the decorated function's own docstring.
        """
        assert distance_wrapper.__doc__ == distance.__doc__

    def test_wrapper_holds_a_rule_tree(self, distance_wrapper):
        """
        The wrapper classifies through a single-class rule tree.
        """
        assert isinstance(distance_wrapper.rdr, EQLSingleClassRDR)

    def test_case_type_is_a_generated_function_case(self, distance_wrapper):
        """
        The case class is generated for this function rather than being the shared base.
        """
        assert issubclass(distance_wrapper.case_type, FunctionCase)
        assert distance_wrapper.case_type is not FunctionCase

    def test_case_type_is_the_rule_tree_own_case_type(self, distance_wrapper):
        """
        The wrapper reports the case class its rule tree actually classifies.
        """
        assert distance_wrapper.case_type is distance_wrapper.rdr.case_type

    def test_case_type_is_bound_to_the_decorated_function(self, distance_wrapper):
        """
        The generated class is rewired to the live callable, not to a re-imported copy.
        """
        assert distance_wrapper.case_type.function is distance

    def test_rule_tree_predicts_the_return_value(self, distance_wrapper):
        """
        The attribute the rule tree predicts is the case field holding the return value.
        """
        assert (
            distance_wrapper.rdr.conclusion_attribute_name == CONCLUSION_ATTRIBUTE_NAME
        )


# %% what a call answers with


class TestWhatACallAnswersWith:
    """
    A call runs the function first, then answers with the rule tree's conclusion
    whenever a rule fires and with the function's own return value otherwise.
    """

    def test_call_without_rules_returns_the_function_output(self, distance_wrapper):
        """
        With no rules fitted yet, the function's own return value comes back.
        """
        assert distance_wrapper(3.0, 4.0) == pytest.approx(distance(3.0, 4.0))

    def test_firing_rule_replaces_the_function_output(
        self, distance_wrapper, positive_x_expert
    ):
        """
        Once a rule fires, its conclusion is the answer rather than what the function
        returned.
        """
        distance_wrapper.fit_case(
            distance_wrapper.case_type(x=1.0, y=0.0, _output=None),
            expert=positive_x_expert,
        )
        assert distance_wrapper(3.0, 4.0) == pytest.approx(POSITIVE_DISTANCE_CONCLUSION)

    def test_no_firing_rule_returns_the_function_output(
        self, distance_wrapper, positive_x_expert
    ):
        """
        A case no rule matches falls through to the function's own return value.
        """
        distance_wrapper.fit_case(
            distance_wrapper.case_type(x=1.0, y=0.0, _output=None),
            expert=positive_x_expert,
        )
        assert distance_wrapper(-1.0, 0.0) == pytest.approx(distance(-1.0, 0.0))

    def test_rule_concluding_none_is_answered_with_none(self, tmp_path):
        """
        ``None`` is a conclusion a rule may reach, not a stand-in for no rule firing.
        """
        wrapper = rdr(str(tmp_path / "coordinate_label_rdr.py"))(coordinate_label)
        wrapper.fit_case(
            wrapper.case_type(x=1.0, _output=FALLBACK_LABEL),
            expert=scripted_expert(None, lambda case_variable: case_variable.x > 0),
        )
        assert wrapper(2.0) is None


# %% fitting on every call


class TestFittingOnEveryCall:
    """
    In fit mode a call is an opportunity to grow the rule tree, and never changes what
    the caller gets back.
    """

    def test_fit_mode_returns_the_function_output(
        self, fitting_distance_wrapper, positive_x_expert
    ):
        """
        Even with a rule that would fire, fit mode answers with the function's own
        value.
        """
        fitting_distance_wrapper.fit_case(
            fitting_distance_wrapper.case_type(x=1.0, y=0.0, _output=None),
            expert=positive_x_expert,
        )
        assert fitting_distance_wrapper(3.0, 4.0) == pytest.approx(distance(3.0, 4.0))

    def test_fit_mode_fits_the_case_it_just_built(
        self, fitting_distance_wrapper, positive_x_expert
    ):
        """
        Each call in fit mode offers exactly one case to the rule tree.
        """
        fitting_distance_wrapper.expert = positive_x_expert
        with patch.object(
            fitting_distance_wrapper.rdr,
            "fit_case",
            wraps=fitting_distance_wrapper.rdr.fit_case,
        ) as fit_case:
            fitting_distance_wrapper(1.0, 0.0)
        fit_case.assert_called_once()

    def test_fit_mode_without_an_expert_does_not_fit(self, fitting_distance_wrapper):
        """
        With nobody to author a rule, a call still runs and leaves the tree untouched.
        """
        assert fitting_distance_wrapper(3.0, 4.0) == pytest.approx(distance(3.0, 4.0))
        assert fitting_distance_wrapper.rdr.query is None


# %% functions the decorator cannot build a case class for


class TestUnannotatedFunctionIsRejected:
    """
    The case class is generated from the annotations, so a function missing one is
    refused at decoration time rather than at its first call.
    """

    def test_missing_return_annotation_is_refused(self, tmp_path):
        """
        A function whose return value is unannotated cannot become a case class.
        """
        with pytest.raises(FunctionMissingAnnotationsError):

            @rdr(str(tmp_path / "unannotated_return_rdr.py"))
            def unannotated_return(first: int, second: int):
                return first + second

    def test_missing_parameter_annotation_is_refused(self, tmp_path):
        """
        A function with an unannotated parameter cannot become a case class.
        """
        with pytest.raises(FunctionMissingAnnotationsError):

            @rdr(str(tmp_path / "unannotated_parameter_rdr.py"))
            def unannotated_parameter(first, second: int) -> int:
                return first + second


# %% what the decorator's arguments wire up


class TestDecoratorArguments:
    """
    Each argument of :func:`rdr` lands on the wrapper it builds.
    """

    def test_filename_alone_produces_a_wrapper(self, tmp_path):
        """
        The filename is the only argument a caller has to supply.
        """
        assert isinstance(rdr(str(tmp_path / "bare_rdr.py"))(add), RDRWrapper)

    def test_expert_is_wired_onto_the_wrapper(self, tmp_path, positive_x_expert):
        """
        The expert named at decoration time is the one the wrapper fits with.
        """
        wrapper = rdr(str(tmp_path / "expert_rdr.py"), expert=positive_x_expert)(add)
        assert wrapper.expert is positive_x_expert

    def test_fit_selects_fit_mode(self, tmp_path):
        """
        ``fit=True`` is what puts the wrapper in fit mode.
        """
        assert rdr(str(tmp_path / "fit_mode_rdr.py"), fit=True)(add).fit_mode is True

    def test_classifying_is_the_default(self, distance_wrapper):
        """
        Omitting ``fit`` leaves the wrapper classifying rather than fitting.
        """
        assert distance_wrapper.fit_mode is False


# %% applying the decorator where a user does


class TestDecoratingAtImportTime:
    """
    ``@rdr`` above a ``def`` is the way the decorator is meant to be used, and it runs
    while the module defining that function is still executing.
    """

    def test_module_applying_the_decorator_imports(self):
        """
        A module can apply ``@rdr`` at its own import time.

        The model file imports the decorated function back by name, and it is read
        before the ``@`` has bound that name, so nothing about this works by accident.
        """
        from .function_decorated_at_import import predict_force

        assert isinstance(predict_force, RDRWrapper)

    def test_decorated_module_level_function_still_answers(self):
        """
        The wrapper a module-level decoration produced classifies calls like any other.
        """
        from .function_decorated_at_import import FALLBACK_FORCE, predict_force

        assert predict_force(0.1, "plastic") == pytest.approx(FALLBACK_FORCE)


# %% the model file the decorator owns


class TestModelFileLifecycle:
    """
    The decorator's store is what the rule tree persists through, so a fit lands in the
    file the decorated function names and is there to be read back.
    """

    def test_the_store_is_the_rule_tree_saver(self, distance_wrapper):
        """
        The rule tree saves through the decorator's own store, not a saver of its own.
        """
        assert distance_wrapper.rdr.model_saver is distance_wrapper.store

    def test_model_file_is_written_at_decoration_time(self, distance_wrapper, tmp_path):
        """
        A never-fitted function still gets its model file, so its case class is
        importable.
        """
        assert distance_wrapper.store.path == str(tmp_path / "distance_rdr.py")
        assert distance_wrapper.store.exists()

    def test_a_fit_persists_to_the_model_file(
        self, distance_wrapper, positive_x_expert
    ):
        """
        The rule a fit inserts is in the file by the time the fit returns.
        """
        distance_wrapper.fit_case(
            distance_wrapper.case_type(x=1.0, y=0.0, _output=None),
            expert=positive_x_expert,
        )
        assert load_rdr(distance_wrapper.store.path).query is not None

    def test_corner_cases_survive_being_read_back(self, tmp_path):
        """
        Every rule's corner case is written to the model file and rebuilt from it, so
        decorating the same function again recovers the provenance of each rule.
        """
        filename = str(tmp_path / "corner_case_round_trip.py")
        wrapper = rdr(filename)(distance)
        wrapper.fit_case(
            wrapper.case_type(x=1.0, y=0.0, _output=1.0),
            expert=scripted_expert(10.0, lambda case_variable: case_variable.x > 0),
        )
        wrapper.fit_case(
            wrapper.case_type(x=-1.0, y=0.0, _output=1.0),
            expert=scripted_expert(20.0, lambda case_variable: case_variable.x < 0),
        )
        assert len(wrapper.rdr.corner_cases.cases) == 2

        read_back = rdr(filename)(distance)
        assert len(read_back.rdr.corner_cases.cases) == len(
            wrapper.rdr.corner_cases.cases
        )

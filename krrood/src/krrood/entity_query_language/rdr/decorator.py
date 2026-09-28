"""
The ``@rdr`` decorator, which classifies every call to a function through a rule tree
grown over that function's own signature.
"""

from __future__ import annotations

import functools
import inspect
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from typing_extensions import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    Optional,
    Tuple,
    Type,
)

from krrood.code_generation.enums import PythonBuiltinParameterNames
from krrood.code_generation.function_case import FunctionCaseGenerator
from krrood.code_generation.generator import CodeGenerator
from krrood.code_generation.naming import camel_case_to_lower_camel_case, to_camel_case
from krrood.entity_query_language.rdr.file_store import RDRFileStore
from krrood.entity_query_language.rdr.function_case import FunctionCase
from krrood.entity_query_language.rdr.serialization import (
    _CLASS_AND_RULES_SEPARATOR,
    _FACTORY_IMPORT,
    _TEMPLATES_DIRECTORY,
    RDR_CASE_TYPE_NAME,
    RDR_CASE_VARIABLE_NAME,
    RDR_CONCLUSION_ATTRIBUTE_NAME,
    RDR_QUERY_NAME,
    load_rdr,
)
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR

if TYPE_CHECKING:
    from krrood.entity_query_language.rdr.expert import Expert

CONCLUSION_ATTRIBUTE_NAME: str = "_output"
"""
The generated case field holding what the function returned, which is the attribute the
rule tree predicts.

Mirrors the field
:class:`~krrood.code_generation.function_case.FunctionCase` declares and
``function_case.py.jinja`` emits for every generated subclass.
"""

EMPTY_RULE_TREE_TEMPLATE_NAME: str = "rdr_empty.py.jinja"
"""
Template rendering the rule-tree section of a model file that has no rules yet.
"""

# %% reading a model file that imports the function back


@contextmanager
def function_bound_to_its_own_name(function: Callable) -> Iterator[None]:
    """
    Bind ``function`` under its own name in the module defining it, for the duration of
    the block, restoring whatever that module held before.

    A model file imports the decorated function back by name, so it is importable on its
    own. Reading one runs that import, and the decorator reads it while the defining
    module is still executing its own body - the ``@`` that binds the name has not run
    yet, so the import would fail on a partially initialized module. Binding the name is
    what the decorator syntax is about to do anyway, one line later, with the wrapper in
    place of the function.

    :param function: The function the model file imports.
    """
    defining_module = sys.modules[function.__module__]
    name = function.__name__
    previously_bound = vars(defining_module).get(name, ...)
    setattr(defining_module, name, function)
    yield
    if previously_bound is ...:
        delattr(defining_module, name)
        return
    setattr(defining_module, name, previously_bound)


# %% the model file a decorated function starts from


def empty_rule_tree_source(case_type_name: str) -> str:
    """
    Render the rule-tree section of a model file for a function that has never been
    fitted.

    :param case_type_name: The generated case class the empty tree ranges over.
    :return: Python source defining the case variable and the loader's stable handles.
    """
    generator = CodeGenerator(template_directory=_TEMPLATES_DIRECTORY)
    return generator.render(
        EMPTY_RULE_TREE_TEMPLATE_NAME,
        factory_import=_FACTORY_IMPORT,
        variable_name=camel_case_to_lower_camel_case(case_type_name),
        case_type_name=case_type_name,
        conclusion_attribute_name=CONCLUSION_ATTRIBUTE_NAME,
        rdr_case_type_name=RDR_CASE_TYPE_NAME,
        rdr_conclusion_attribute_name=RDR_CONCLUSION_ATTRIBUTE_NAME,
        rdr_case_variable_name=RDR_CASE_VARIABLE_NAME,
        rdr_query_name=RDR_QUERY_NAME,
    )


# %% the decorated function


@dataclass
class RDRWrapper:
    """
    A decorated function whose every call is classified - or, in fit mode, fitted - by a
    rule tree over the function's own signature.

    Classifying runs the function, builds a case from the call's arguments and its return
    value, and answers with the rule tree's conclusion whenever a rule fires. Fitting
    always answers with the function's own return value and offers each case to the
    expert instead, so the rule tree grows from real calls.
    """

    function: Callable
    """
    The undecorated function this stands in for.
    """

    store: RDRFileStore
    """
    Where the rule tree and its case type are kept between runs.
    """

    expert: Optional[Expert]
    """
    Authors a rule while fitting; a single call may name a different one.
    """

    fit_mode: bool
    """
    Whether each call fits its case rather than classifying it.
    """

    rdr: EQLSingleClassRDR = field(init=False)
    """
    The rule tree this function's calls are classified by.
    """

    def __post_init__(self) -> None:
        with function_bound_to_its_own_name(self.function):
            self.rdr = self._load_or_generate()
        self.rdr.case_type.function = self.function
        self.rdr.model_saver = self.store
        functools.update_wrapper(self, self.function, updated=[])

    @property
    def case_type(self) -> Type[FunctionCase]:
        """
        :return: The generated case class this function's calls are built into.
        """
        return self.rdr.case_type

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """
        Run the function, then fit or classify the call it just made.

        :return: The function's own return value in fit mode and whenever no rule fires,
            otherwise the conclusion the rule tree reached.
        """
        output = self.function(*args, **kwargs)
        case = self._build_case(args, kwargs, output)
        if self.fit_mode:
            if self.expert is not None:
                self.rdr.fit_case(case, expert=self.expert)
            return output
        conclusion = self.rdr.classify(case)
        return output if conclusion is ... else conclusion

    def fit_case(
        self, case: Any, target: Any = ..., expert: Optional[Expert] = None
    ) -> Any:
        """
        Fit one case, falling back to :attr:`expert` when the caller names none.

        :param case: The case to fit.
        :param target: The known correct conclusion, or ``...`` when the expert labels
            it.
        :param expert: Authors any new rule; :attr:`expert` when ``None``.
        :return: The conclusion the rule tree reaches for ``case`` once fitted.
        """
        return self.rdr.fit_case(
            case, target, expert if expert is not None else self.expert
        )

    def fit(
        self,
        cases: List[Any],
        targets: Optional[List[Any]] = None,
        expert: Optional[Expert] = None,
    ) -> EQLSingleClassRDR:
        """
        Fit a batch of cases, falling back to :attr:`expert` when the caller names none.

        :param cases: The cases to fit, in order.
        :param targets: The known correct conclusion per case, or ``None`` to have the
            expert label every case.
        :param expert: Authors any new rule; :attr:`expert` when ``None``.
        :return: The fitted rule tree.
        """
        return self.rdr.fit(
            cases, targets, expert if expert is not None else self.expert
        )

    def _load_or_generate(self) -> EQLSingleClassRDR:
        """
        Read the rule tree back from the model file, writing an empty model first when
        this function has never been fitted.

        :return: The rule tree over this function's generated case type.
        """
        if self.store.exists():
            return load_rdr(self.store.path)
        self._write_empty_model()
        return EQLSingleClassRDR(self.store.load_case_type(), CONCLUSION_ATTRIBUTE_NAME)

    def _write_empty_model(self) -> None:
        """
        Write the model file a never-fitted function starts from: the case class
        generated from its signature, followed by a rule tree with no rules.
        """
        case_type_name = to_camel_case(self.function.__name__)
        case_source = FunctionCaseGenerator(base_class=FunctionCase).generate(
            self.function, class_name=case_type_name
        )
        source = (
            case_source
            + _CLASS_AND_RULES_SEPARATOR
            + empty_rule_tree_source(case_type_name)
        )
        Path(self.store.path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.store.path).write_text(source)

    def _build_case(
        self,
        positional_arguments: Tuple[Any, ...],
        keyword_arguments: Dict[str, Any],
        output: Any,
    ) -> FunctionCase:
        """
        Bind one call's arguments and its return value into a case.

        :param positional_arguments: The arguments the call passed by position.
        :param keyword_arguments: The arguments the call passed by name.
        :param output: What the function returned for them.
        :return: The case the rule tree classifies or fits.
        """
        bound_arguments = inspect.signature(self.function).bind(
            *positional_arguments, **keyword_arguments
        )
        bound_arguments.apply_defaults()
        arguments = {
            name: value
            for name, value in bound_arguments.arguments.items()
            if name not in PythonBuiltinParameterNames
        }
        arguments[CONCLUSION_ATTRIBUTE_NAME] = output
        return self.case_type(**arguments)


# %% declaring a model on a function


def rdr(
    filename: str,
    *,
    expert: Optional[Expert] = None,
    fit: bool = False,
) -> Callable[[Callable], RDRWrapper]:
    """
    Give a fully annotated function a rule tree over its own signature.

    Usage::

        @rdr("my_model.py")
        def decide(distance: float, state: Machine) -> Action:
            return Action.DEFAULT

        @rdr("my_model.py", fit=True, expert=Expert(interface=IPythonInterface()))
        def decide(distance: float, state: Machine) -> Action:
            return Action.DEFAULT

    :param filename: Where to keep the model. A relative name lands in an ``_rdr_models/``
        directory beside the decorated function's own module; an absolute one is used
        as given.
    :param expert: Authors rules while fitting.
    :param fit: Whether every call fits its case rather than classifying it.
    :raises FunctionMissingAnnotationsError: If a parameter or the return value carries no
        type annotation, since the case class is generated from those annotations.
    :return: The decorator replacing the function with its :class:`RDRWrapper`.
    """

    def decorate(function: Callable) -> RDRWrapper:
        """
        :param function: The function to give a rule tree to.
        :return: The wrapper standing in for it.
        """
        return RDRWrapper(
            function=function,
            store=RDRFileStore(function=function, filename=filename),
            expert=expert,
            fit_mode=fit,
        )

    return decorate

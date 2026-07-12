"""
Persist an EQL-native RDR as a Python module — no JSON, no strings-as-rules.

The rule tree is a live EQL expression DAG. To save it we *unparse* the DAG back into
the same ``with refinement(...) / alternative(...): add(...)`` syntax used to author rule
trees by hand, using the stdlib :mod:`ast` module to guarantee syntactically valid output;
loading is just importing that module and reading the rebuilt DAG.
"""

from __future__ import annotations

import ast
import enum
import operator
import os
from dataclasses import dataclass
from textwrap import indent as _indent
from typing import TYPE_CHECKING

from typing_extensions import Any, Callable, Dict, List

from krrood.code_generation.function_case import FunctionCaseGenerator
from krrood.code_generation.generator import CodeGenerator
from krrood.code_generation.imports import get_imports_from_types
from krrood.code_generation.module_loading import load_module_from_path
from krrood.code_generation.naming import camel_case_to_lower_camel_case
from krrood.entity_query_language.core.mapped_variable import Attribute
from krrood.entity_query_language.core.variable import Literal, Variable
from krrood.entity_query_language.factories import (
    add,
    alternative,
    and_,
    entity,
    next_rule,
    not_,
    or_,
    refinement,
    variable,
)
from krrood.entity_query_language.operators.comparator import Comparator
from krrood.entity_query_language.operators.core_logical_operators import AND, OR, Not
from krrood.entity_query_language.rdr.corner_case import CornerCaseStore
from krrood.entity_query_language.rdr.exceptions import (
    EmptyRuleTreeError,
    UnsupportedNodeForSerialization,
)
from krrood.entity_query_language.rules.conclusion import Add
from krrood.entity_query_language.rules.conclusion_selector import (
    Alternative,
    Next,
    Refinement,
)

if TYPE_CHECKING:
    from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR

_SELECTORS = (Refinement, Alternative, Next)

_SELECTOR_FACTORY: Dict[type, Callable[..., Any]] = {
    Refinement: refinement,
    Alternative: alternative,
    Next: next_rule,
}

_COMPARATOR_AST_OP: Dict[Any, type] = {
    operator.eq: ast.Eq,
    operator.ne: ast.NotEq,
    operator.lt: ast.Lt,
    operator.le: ast.LtE,
    operator.gt: ast.Gt,
    operator.ge: ast.GtE,
}

_FACTORY_IMPORT = "\n".join(
    get_imports_from_types(
        [variable, entity, add, refinement, alternative, next_rule, and_, or_, not_]
    )
)

_CLASS_AND_RULES_SEPARATOR = "\n\n\n"
"""Blank-line separator placed between the generated case class and the rule-tree source."""

_RDR_MODULE_TEMPLATE_NAME = "rdr_module.py.jinja"
"""Filename of the Jinja2 template used to render a saved RDR module."""

RDR_CASE_TYPE_NAME = "RDR_CASE_TYPE"
"""Name of the generated module attribute holding the RDR's case type."""

RDR_CONCLUSION_ATTRIBUTE_NAME = "RDR_CONCLUSION_ATTRIBUTE"
"""Name of the generated module attribute holding the RDR's conclusion attribute name."""

RDR_CASE_VARIABLE_NAME = "RDR_CASE_VARIABLE"
"""Name of the generated module attribute holding the RDR's case ``Variable``."""

RDR_QUERY_NAME = "RDR_QUERY"
"""Name of the generated module attribute holding the RDR's built query."""

RDR_CORNER_CASES_NAME = "RDR_CORNER_CASES"
"""Name of the generated module attribute holding the RDR's corner-case source dict."""

_class_name_to_var_name = camel_case_to_lower_camel_case


# %% DAG decomposition


@dataclass
class SelectorBranch:
    """One reinsertion step: a selector type paired with the branch condition it wraps."""

    selector_type: type
    """The selector class (``Refinement``, ``Alternative``, or ``Next``) this branch belongs to."""

    condition: Any
    """The branch's condition sub-tree (an EQL expression DAG node)."""


@dataclass
class DecomposedRuleTree:
    """The result of flattening a left-nested chain of conclusion selectors."""

    main: Any
    """The base condition node with no selector wrapping."""

    branches: List[SelectorBranch]
    """The selector branches, ordered as the loader must re-insert them."""


def _reorder_branches_for_reinsertion(
    selector_run: List[SelectorBranch],
) -> List[SelectorBranch]:
    """
    Put one same-orientation run of branches into the order the loader must re-insert them.

    ``Refinement`` chains grow *inward* (each new refinement re-anchors at the same fixed
    base node), so walking ``.left`` already yields insertion order. ``Alternative`` /
    ``Next`` chains grow *outward* (each re-anchors at the moving conditions root), so
    walking ``.left`` yields *reverse* insertion order and must be flipped.
    """
    if not selector_run:
        return []
    return (
        list(selector_run)
        if selector_run[0].selector_type is Refinement
        else list(reversed(selector_run))
    )


def _flatten_selector_chain(node: Any) -> DecomposedRuleTree:
    """
    Flatten a left-nested chain of conclusion selectors into a base condition plus an
    ordered list of branches in the order the loader must re-insert them to rebuild the
    identical DAG.

    Because refinement and alternative chains grow in opposite directions (see
    :func:`_reorder_branches_for_reinsertion`), each contiguous same-orientation run is
    oriented independently; a blanket reverse would silently swap sibling refinements on
    every round-trip.
    """
    walk: List[SelectorBranch] = []
    while isinstance(node, _SELECTORS):
        walk.append(SelectorBranch(type(node), node.right))
        node = node.left

    branches: List[SelectorBranch] = []
    run: List[SelectorBranch] = []
    for entry in walk:
        if run and (entry.selector_type is Refinement) != (
            run[0].selector_type is Refinement
        ):
            branches.extend(_reorder_branches_for_reinsertion(run))
            run = []
        run.append(entry)
    branches.extend(_reorder_branches_for_reinsertion(run))
    return DecomposedRuleTree(node, branches)


def walk_rules_in_emission_order(conditions_root: Any) -> List[Any]:
    """
    Return condition (leaf) nodes in the same pre-order that ``_emit_rule_body`` visits.

    This is the single authoritative ordering shared by the serializer (save path) and
    the corner-case-store rebuilder (load path). Both must use this function so the two
    orderings can never drift independently.

    :param conditions_root: The root of the rule-tree condition DAG.
    :return: Leaf condition nodes in the order the serializer emits their ``add(...)``
        calls (i.e. the *i*-th element here corresponds to the *i*-th ``add(`` line in
        the file written by :func:`rdr_to_python`).
    """
    result: List = []

    def _visit(node: Any) -> None:
        decomposed = _flatten_selector_chain(node)
        result.append(decomposed.main)
        for branch in decomposed.branches:
            _visit(branch.condition)

    if conditions_root is not None:
        _visit(conditions_root)
    return result


def _conclusion_value(condition_node: Any) -> Any:
    """:return: The single value concluded at ``condition_node`` (its ``Add``)."""
    for conclusion in condition_node._conclusions_:
        if isinstance(conclusion, Add):
            target = conclusion.right
            return target._value_ if isinstance(target, Literal) else target
    raise UnsupportedNodeForSerialization(condition_node)


# %% Expression -> AST


def _emit_value(value: Any) -> ast.expr:
    """Build the AST expression that reconstructs the literal *value*."""
    if isinstance(value, enum.Enum):
        return ast.Attribute(
            value=ast.Name(id=type(value).__name__, ctx=ast.Load()),
            attr=value.name,
            ctx=ast.Load(),
        )
    if isinstance(value, (bool, int, float, str)) or value is None:
        return ast.Constant(value=value)
    raise UnsupportedNodeForSerialization(value)


def _emit_factory_call(
    factory: Callable[..., Any], operands: List[Any], var_names: Dict[Any, str]
) -> ast.Call:
    """Build the AST call that invokes *factory* on the emitted *operands*."""
    return ast.Call(
        func=ast.Name(id=factory.__name__, ctx=ast.Load()),
        args=[_emit_expr(operand, var_names) for operand in operands],
        keywords=[],
    )


def _emit_expr(node: Any, var_names: Dict[Any, str]) -> ast.expr:
    """Build the AST expression that reconstructs the condition sub-tree at *node*."""
    if isinstance(node, Literal):
        return _emit_value(node._value_)
    if isinstance(node, Attribute):
        return ast.Attribute(
            value=_emit_expr(node._child_, var_names),
            attr=node._attribute_name_,
            ctx=ast.Load(),
        )
    if isinstance(node, Variable):
        if node._id_ not in var_names:
            raise UnsupportedNodeForSerialization(node)
        return ast.Name(id=var_names[node._id_], ctx=ast.Load())
    if isinstance(node, Comparator):
        comparison_op = _COMPARATOR_AST_OP.get(node.operation)
        if comparison_op is None:
            raise UnsupportedNodeForSerialization(node)
        return ast.Compare(
            left=_emit_expr(node.left, var_names),
            ops=[comparison_op()],
            comparators=[_emit_expr(node.right, var_names)],
        )
    if isinstance(node, AND):
        return _emit_factory_call(and_, _condition_operands(node), var_names)
    if isinstance(node, OR):
        return _emit_factory_call(or_, _condition_operands(node), var_names)
    if isinstance(node, Not):
        return _emit_factory_call(not_, [node._children_[0]], var_names)
    raise UnsupportedNodeForSerialization(node)


def _condition_operands(node: Any) -> List[Any]:
    """
    The logical operands of a connective, excluding any conclusions. When a rule's
    condition is the connective itself (e.g. an ``and_`` root), its ``Add`` conclusions are
    attached as children too; those are not part of the boolean expression.
    """
    conclusion_ids = {conclusion._id_ for conclusion in node._conclusions_}
    return [child for child in node._children_ if child._id_ not in conclusion_ids]


# %% Rule tree -> AST


def _emit_rule_body(
    condition_node: Any,
    var_names: Dict[Any, str],
    conclusion_target: ast.expr,
    referenced_types: set,
) -> List[ast.stmt]:
    """Emit the ``add(...)`` statement plus any nested refinement/alternative blocks for a rule."""
    decomposed = _flatten_selector_chain(condition_node)
    value = _conclusion_value(decomposed.main)
    if isinstance(value, enum.Enum):
        referenced_types.add(type(value))

    statements: List[ast.stmt] = [
        ast.Expr(
            value=ast.Call(
                func=ast.Name(id=add.__name__, ctx=ast.Load()),
                args=[conclusion_target, _emit_value(value)],
                keywords=[],
            )
        )
    ]
    for branch in decomposed.branches:
        factory = _SELECTOR_FACTORY[branch.selector_type]
        branch_main = _flatten_selector_chain(branch.condition).main
        with_call = _emit_factory_call(factory, [branch_main], var_names)
        nested_body = _emit_rule_body(
            branch.condition, var_names, conclusion_target, referenced_types
        )
        statements.append(
            ast.With(
                items=[ast.withitem(context_expr=with_call, optional_vars=None)],
                body=nested_body,
            )
        )
    return statements


def rdr_to_python(rdr: EQLSingleClassRDR, case_type_is_local: bool = False) -> str:
    """
    Serialize an :class:`EQLSingleClassRDR` to importable Python source.

    :param rdr: A fitted RDR (must have at least one rule).
    :param case_type_is_local: When ``True``, skip emitting the import for the case type
        itself. Use this when ``save_rdr_with_case`` has already written the class
        definition at the top of the same file.
    :return: Python module source that rebuilds the same rule-tree DAG on import.
    """
    if rdr.query is None:
        raise EmptyRuleTreeError()

    case_type = rdr.case_type
    variable_name = _class_name_to_var_name(case_type.__name__)
    var_names = {rdr.case_variable._id_: variable_name}
    conclusion_target = ast.Attribute(
        value=ast.Name(id=variable_name, ctx=ast.Load()),
        attr=rdr.conclusion_attribute_name,
        ctx=ast.Load(),
    )
    referenced_types = {case_type}

    decomposed = _flatten_selector_chain(rdr.query._conditions_root_)
    base_condition_expr = ast.fix_missing_locations(_emit_expr(decomposed.main, var_names))
    base_condition = ast.unparse(base_condition_expr)
    body_statements = _emit_rule_body(
        rdr.query._conditions_root_, var_names, conclusion_target, referenced_types
    )
    body_module = ast.fix_missing_locations(
        ast.Module(body=body_statements, type_ignores=[])
    )
    body = _indent(ast.unparse(body_module), "    ")

    ordered_nodes = walk_rules_in_emission_order(rdr.query._conditions_root_)
    corner_case_sources = rdr.corner_cases.to_ordered_sources(ordered_nodes)
    for case_source in corner_case_sources.values():
        referenced_types.update(case_source.referenced_types)
    if corner_case_sources:
        entries = ", ".join(
            f"{positional_index}: {case_source.source}"
            for positional_index, case_source in sorted(corner_case_sources.items())
        )
        corner_cases_dict_src = "{" + entries + "}"
    else:
        corner_cases_dict_src = "{}"

    if case_type_is_local:
        types_to_import = [
            referenced_type
            for referenced_type in referenced_types
            if referenced_type is not case_type
        ]
    else:
        types_to_import = list(referenced_types)
    type_imports = "\n".join(get_imports_from_types(types_to_import))

    template_directory = os.path.join(os.path.dirname(__file__), "templates")
    generator = CodeGenerator(template_directory=template_directory)
    return generator.render(
        _RDR_MODULE_TEMPLATE_NAME,
        factory_import=_FACTORY_IMPORT,
        type_imports=type_imports,
        var_name=variable_name,
        case_type_name=case_type.__name__,
        base_condition=base_condition,
        body=body,
        conclusion_attribute_name=rdr.conclusion_attribute_name,
        corner_cases_dict_src=corner_cases_dict_src,
        rdr_case_type_name=RDR_CASE_TYPE_NAME,
        rdr_conclusion_attribute_name=RDR_CONCLUSION_ATTRIBUTE_NAME,
        rdr_case_variable_name=RDR_CASE_VARIABLE_NAME,
        rdr_query_name=RDR_QUERY_NAME,
        rdr_corner_cases_name=RDR_CORNER_CASES_NAME,
    )


def save_rdr(rdr: EQLSingleClassRDR, path: str) -> str:
    """Write the RDR's Python source to ``path`` and return that source."""
    source = rdr_to_python(rdr)
    with open(path, "w") as file:
        file.write(source)
    return source


def save_rdr_with_case(rdr: EQLSingleClassRDR, path: str) -> str:
    """
    Write a combined class-header + rule-tree file to ``path``.

    When ``rdr.case_type`` is a :class:`FunctionCase` subclass the file begins with the
    ``@dataclass`` class definition (generated from the original function stored in
    ``case_type.function``), followed by the rule-tree section which omits the case-type
    import (the class is already defined above). For any other case type the function
    falls back to plain :func:`save_rdr`.

    :param rdr: A fitted :class:`EQLSingleClassRDR`.
    :param path: Destination ``.py`` file path.
    :returns: The source written to disk.
    """
    from krrood.entity_query_language.rdr.function_case import FunctionCase

    if isinstance(rdr.case_type, type) and issubclass(rdr.case_type, FunctionCase):
        class_source = FunctionCaseGenerator().generate(
            rdr.case_type.function,
            class_name=rdr.case_type.__name__,
        )
        rule_source = rdr_to_python(rdr, case_type_is_local=True)
        source = class_source + _CLASS_AND_RULES_SEPARATOR + rule_source
    else:
        source = rdr_to_python(rdr)

    with open(path, "w") as file:
        file.write(source)
    return source


def load_rdr(path: str) -> EQLSingleClassRDR:
    """Load an :class:`EQLSingleClassRDR` from a module previously written by :func:`save_rdr`."""
    from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR

    module = load_module_from_path(path, "_eql_rdr_loaded_")

    case_type = getattr(module, RDR_CASE_TYPE_NAME)
    conclusion_attribute_name = getattr(module, RDR_CONCLUSION_ATTRIBUTE_NAME)
    rdr = EQLSingleClassRDR(case_type, conclusion_attribute_name)
    rdr.case_variable = getattr(module, RDR_CASE_VARIABLE_NAME)
    rdr.conclusion_variable = getattr(rdr.case_variable, conclusion_attribute_name)
    rdr.query = getattr(module, RDR_QUERY_NAME)

    cases_by_index = getattr(module, RDR_CORNER_CASES_NAME, {})
    ordered_nodes = walk_rules_in_emission_order(rdr.conditions_root)
    rdr.corner_cases = CornerCaseStore.from_ordered_cases(ordered_nodes, cases_by_index)

    return rdr

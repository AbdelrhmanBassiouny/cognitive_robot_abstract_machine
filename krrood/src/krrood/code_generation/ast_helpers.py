"""Builders for the :mod:`ast` nodes used when generating Python source.

These wrap the verbose, boilerplate-heavy :mod:`ast` constructors (load contexts,
empty keyword lists, ``with`` item wrapping, location fixups) behind small, intention-
revealing functions so code generators read as *what* they emit rather than *how* the
AST is spelled.
"""

from __future__ import annotations

import ast
import enum

from typing_extensions import Any, Iterable, List, Tuple, Type


def load_name(identifier: str) -> ast.Name:
    """Build a load-context name reference.

    :param identifier: The identifier to reference.
    :return: An :class:`ast.Name` in load context.
    """
    return ast.Name(id=identifier, ctx=ast.Load())


def attribute_access(value: ast.expr, attribute_name: str) -> ast.Attribute:
    """Build a load-context attribute access ``value.attribute_name``.

    :param value: The expression the attribute is read from.
    :param attribute_name: The attribute to read.
    :return: An :class:`ast.Attribute` in load context.
    """
    return ast.Attribute(value=value, attr=attribute_name, ctx=ast.Load())


def constant(value: Any) -> ast.Constant:
    """Build a literal constant node.

    :param value: The literal value to embed.
    :return: An :class:`ast.Constant` wrapping *value*.
    """
    return ast.Constant(value=value)


def enum_member(member: enum.Enum) -> ast.Attribute:
    """Build the attribute access that reconstructs an enum member (``EnumType.MEMBER``).

    :param member: The enum member to reference.
    :return: An :class:`ast.Attribute` accessing the member on its enum class.
    """
    return attribute_access(load_name(type(member).__name__), member.name)


def parse_expression(source: str) -> ast.expr:
    """Parse a source fragment into a single expression node.

    Use this to lift already-rendered source (produced by another generator) into an AST
    being assembled, so it can be spliced into a larger node and unparsed uniformly.

    :param source: A Python expression in source form.
    :return: The parsed expression node.
    """
    return ast.parse(source, mode="eval").body


def dict_literal(items: Iterable[Tuple[ast.expr, ast.expr]]) -> ast.Dict:
    """Build a dict-display node from ordered key/value expression pairs.

    :param items: The ``(key, value)`` expression pairs, in the order they should appear.
    :return: An :class:`ast.Dict` node.
    """
    keys: List[ast.expr] = []
    values: List[ast.expr] = []
    for key, value in items:
        keys.append(key)
        values.append(value)
    return ast.Dict(keys=keys, values=values)


def call(function_name: str, arguments: List[ast.expr]) -> ast.Call:
    """Build a positional-only call of a named function.

    :param function_name: The name of the function to call.
    :param arguments: The positional arguments.
    :return: An :class:`ast.Call` with no keyword arguments.
    """
    return ast.Call(func=load_name(function_name), args=list(arguments), keywords=[])


def compare(left: ast.expr, operator_class: Type[ast.cmpop], right: ast.expr) -> ast.Compare:
    """Build a single binary comparison ``left <op> right``.

    :param left: The left-hand operand.
    :param operator_class: The comparison-operator class (e.g. :class:`ast.Eq`).
    :param right: The right-hand operand.
    :return: An :class:`ast.Compare` with one operator and one comparator.
    """
    return ast.Compare(left=left, ops=[operator_class()], comparators=[right])


def with_block(context: ast.expr, body: List[ast.stmt]) -> ast.With:
    """Build a ``with context:`` statement wrapping *body*.

    :param context: The context-manager expression.
    :param body: The statements nested under the ``with``.
    :return: An :class:`ast.With` with a single unnamed item.
    """
    return ast.With(
        items=[ast.withitem(context_expr=context, optional_vars=None)],
        body=list(body),
    )


def unparse_expression(expression: ast.expr) -> str:
    """Render a single expression to source, filling in required node locations.

    :param expression: The expression to render.
    :return: The unparsed source string.
    """
    return ast.unparse(ast.fix_missing_locations(expression))


def unparse_statements(statements: List[ast.stmt]) -> str:
    """Render a list of statements to source, filling in required node locations.

    :param statements: The statements to render as a module body.
    :return: The unparsed source string.
    """
    module = ast.fix_missing_locations(ast.Module(body=list(statements), type_ignores=[]))
    return ast.unparse(module)

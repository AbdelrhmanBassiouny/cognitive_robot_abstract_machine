"""Contextual example generators for the EQL-RDR interactive expert prompt.

:func:`pick_case_attribute` inspects a concrete case and returns an
:class:`AttributeRef` describing a representative attribute path and value.
:func:`build_conclusion_example` and :func:`build_conditions_example` convert
that into a ready-to-paste magic-command example shown at the bottom of the
expert prompt.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import TYPE_CHECKING, Any, Optional

from krrood.entity_query_language.rdr.case_table import case_items
from krrood.entity_query_language.rdr.interface import CASE_VARIABLE_NAME

if TYPE_CHECKING:
    from krrood.entity_query_language.rdr.prompt_sections import RenderContext


@dataclass(frozen=True)
class AttributeRef:
    """A representative attribute path and its value as a Python literal.

    :param path: Dot-separated access path relative to the case variable
        (e.g. ``"handle.name"`` or ``"milk"``).
    :param literal: The value of the attribute as a Python literal string
        (e.g. ``"'left_handle'"`` or ``"True"``).
    """

    path: str
    literal: str


def pick_case_attribute(case_instance: Any) -> Optional[AttributeRef]:
    """Select a representative attribute from a case instance for use in examples.

    Preference order:

    1. A field whose value has a public ``.name`` attribute — yields
       ``field.name`` as the path and ``repr(value.name)`` as the literal.
    2. The first scalar (non-``None``, non-object) field.
    3. ``None`` when no qualifying field is found (caller uses a generic fallback).

    :param case_instance: The concrete case object to inspect.
    :return: An :class:`AttributeRef`, or ``None`` if no representative field exists.
    """
    items = case_items(case_instance)
    # Pass 1 — prefer nested object with a .name attribute.
    for field_name, value in items:
        if value is not None and hasattr(value, "name") and not callable(value.name):
            try:
                name_val = value.name
            except Exception:
                continue
            return AttributeRef(
                path=f"{field_name}.name",
                literal=repr(name_val),
            )
    # Pass 2 — fallback to first scalar field.
    for field_name, value in items:
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            return AttributeRef(path=field_name, literal=repr(value))
    return None


def build_conclusion_example(ctx: RenderContext) -> str:
    """Build a ``e.g. %conclusion <value>`` hint line from the conclusion domain.

    :param ctx: The current render context (carries the conclusion domain).
    :return: A hint string like ``e.g. %conclusion Species.mammal``.
    """
    domain = ctx.case.conclusion_domain
    if domain is None:
        return "e.g. %conclusion <value>"
    if domain.is_enumerable and domain.members:
        return f"e.g. %conclusion {domain.members[0]!r}"
    return f"e.g. %conclusion <{domain.type_display}>"


def build_conditions_example(ctx: RenderContext) -> str:
    """Build a ``e.g. %conditions case_variable.<path> == <value>`` hint line.

    Uses :func:`pick_case_attribute` to derive a contextual attribute path from
    the concrete case instance.  Falls back to a generic placeholder when no
    suitable attribute is found.

    :param ctx: The current render context (carries the case instance).
    :return: A hint string like ``e.g. %conditions case_variable.handle.name == 'left_handle'``.
    """
    ref = pick_case_attribute(ctx.case.case_instance)
    if ref is None:
        return f"e.g. %conditions {CASE_VARIABLE_NAME}.some_attr == True"
    return f"e.g. %conditions {CASE_VARIABLE_NAME}.{ref.path} == {ref.literal}"

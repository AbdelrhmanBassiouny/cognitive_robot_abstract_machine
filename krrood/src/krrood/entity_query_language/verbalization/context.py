from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, List, TYPE_CHECKING


def _article(type_name: str) -> str:
    return "an" if type_name[0].lower() in "aeiou" else "a"


@dataclass
class VerbalizationContext:
    """
    Carries per-verbalization state: coreference tracking and chain-flattening utilities.

    Pass a single instance through an entire ``EQLVerbalizer.verbalize()`` call so that
    the same variable object is rendered as "a Robot" on first mention and "the Robot" on
    every subsequent mention.
    """

    seen: dict = field(default_factory=dict)
    """Maps expression UUID → type-name string for every expression already verbalized."""

    compact_predicates: bool = False
    """When True, comparators omit the copula "is" (e.g. "greater than" not "is greater than").
    Set by the verbalizer while rendering HAVING conditions."""

    deferred_constraints: List[List[str]] = field(default_factory=list)
    """Stack of constraint-text frames. Each frame belongs to one nesting level of
    InstantiatedVariable verbalization. When an Entity is verbalized as an inline noun
    its where-conditions are deferred into the top frame so the enclosing
    InstantiatedVariable can emit them as a 'such that …' clause."""

    def push_constraint_frame(self) -> None:
        """Open a new constraint frame for the current InstantiatedVariable."""
        self.deferred_constraints.append([])

    def pop_constraint_frame(self) -> List[str]:
        """Close the current frame and return its accumulated constraint strings."""
        return self.deferred_constraints.pop() if self.deferred_constraints else []

    def add_constraint(self, text: str) -> None:
        """Append *text* to the top constraint frame (no-op when no frame is open)."""
        if self.deferred_constraints:
            self.deferred_constraints[-1].append(text)

    def noun_for(self, var) -> str:
        """
        Return the article + type-name noun phrase for *var*.

        First mention: ``"a Robot"`` / ``"an Employee"``.
        Any later mention of the same ``_id_``: ``"the Robot"``.
        Also registers *var* in :attr:`seen`.
        """
        type_name = var._type_.__name__ if getattr(var, "_type_", None) else var.__class__.__name__
        if var._id_ in self.seen:
            return f"the {type_name}"
        self.seen[var._id_] = type_name
        return f"{_article(type_name)} {type_name}"

    def flatten_same_type(self, expr, operator_type) -> List:
        """
        Recursively collect a homogeneous binary chain into a flat list.

        ``AND(AND(a, b), c)`` with ``operator_type=AND`` → ``[a, b, c]``.
        Stops at nodes of a different type, so ``AND(a, OR(b, c))`` yields
        ``[a, OR(b, c)]`` — the inner ``OR`` is left intact.
        """
        if not isinstance(expr, operator_type):
            return [expr]
        left = self.flatten_same_type(expr.left, operator_type)
        right = self.flatten_same_type(expr.right, operator_type)
        return left + right

    def type_name_of_value(self, value: Any) -> str:
        """
        Render a Python value as a readable string.

        * A bare ``type`` object → its ``__name__`` (e.g. ``Apple`` → ``"Apple"``).
        * A tuple of ``type`` objects → ``"A or B or C"``.
        * Anything else → ``repr(value)``.
        """
        if isinstance(value, type):
            return value.__name__
        if isinstance(value, tuple) and all(isinstance(v, type) for v in value):
            return " or ".join(v.__name__ for v in value)
        return repr(value)

"""
Textual, rule-level visualization of an EQL RDR rule tree.

This renders the rule tree the way an RDR expert thinks about it — one line per rule
(``if <conditions> then <conclusion>``), nested by refinement depth — rather than the
per-operation expression graph that :mod:`~krrood.entity_query_language.query_graph`
draws. It is deliberately dependency-light (just ``colorama``), matching the style of
:mod:`~krrood.entity_query_language.rdr.case_table`.

Each rule is coloured by what happened to it during the classification that is being
explained:

* **green**  — the rule *fired* (its condition was satisfied),
* **red**    — the rule was *evaluated* but its condition did not hold,
* **grey**   — the rule was *not evaluated* (a branch the evaluation short-circuited).

The status is read straight from the evaluation observers' id-sets (``satisfied`` /
``evaluated``); see :class:`~krrood.entity_query_language.rdr.observer.ClassificationTrace`.

To keep a large tree readable the rendered rows are *elided*: the first few rules are
shown, then a vertical-dots row, then the few rules ending at the rule that fired (so the
firing rule is always the last visible row).
"""

from __future__ import annotations

import enum

from dataclasses import dataclass, field

from typing_extensions import TYPE_CHECKING, Any, List, Optional
from uuid import UUID

from colorama import Fore, Style
from ordered_set import OrderedSet

from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.core.mapped_variable import Attribute
from krrood.entity_query_language.core.variable import Literal, Variable
from krrood.entity_query_language.operators.comparator import Comparator
from krrood.entity_query_language.operators.core_logical_operators import (
    AND,
    OR,
    LogicalOperator,
    Not,
)
from krrood.entity_query_language.rules.conclusion import Add, Conclusion
from krrood.entity_query_language.rules.conclusion_selector import (
    Alternative,
    ConclusionSelector,
    Next,
    Refinement,
)

if TYPE_CHECKING:
    from krrood.entity_query_language.rdr.observer import ClassificationTrace

#: How many rules to show at the top before eliding the middle.
DEFAULT_HEAD = 3

#: How many rules to show at the bottom (ending on the firing rule) after the elision.
DEFAULT_TAIL = 3


class TreeGlyph(enum.StrEnum):
    """
    The glyphs used to draw the rule tree: nesting connectors and the elision marker.
    """

    VERTICAL_DOTS = "⋮"
    """
    Marks the row where hidden (elided) rules would have been.
    """

    GUIDE = "│  "
    """
    A vertical guide continuing an ancestor's branch past this row.
    """

    GAP = "   "
    """
    Blank space where an ancestor's branch has already ended.
    """
    BRANCH = "├─ "
    """
    Connects to a rule that has later siblings at the same depth.
    """
    BRANCH_LAST = "└─ "
    """
    Connects to the last rule among its siblings at the same depth.
    """


class RuleKind(enum.StrEnum):
    """
    How a rule relates to its predecessor in the rule tree.
    """

    IF = "if"
    """
    A top-level rule, not conditioned on any predecessor.
    """

    ELSE_IF = "else if"
    """
    An alternative, evaluated only when its predecessor did not fire.
    """

    EXCEPT_IF = "except if"
    """
    A refinement, evaluated only when its predecessor fired.
    """


class RuleStatus(enum.StrEnum):
    """
    What happened to a rule during the classification being explained.
    """

    FIRED = "fired"
    """
    The rule's condition was satisfied.
    """

    EVALUATED_NOT_FIRED = "evaluated_not_fired"
    """
    The rule's condition was evaluated but did not hold.
    """

    NOT_EVALUATED = "skipped"
    """
    The rule was never evaluated (its branch was short-circuited).
    """

    @property
    def color(self) -> str:
        """:return: The ANSI colour (colorama) this status is drawn in."""
        return {
            RuleStatus.FIRED: Fore.GREEN,
            RuleStatus.EVALUATED_NOT_FIRED: Fore.RED,
            RuleStatus.NOT_EVALUATED: Fore.LIGHTBLACK_EX,
        }[self]


@dataclass
class RuleView:
    """
    One rule (a condition plus its conclusion(s)) at a place in the rule tree.

    A flat, render-ready projection of a leaf condition node in the ``Refinement`` /
    ``Alternative`` / ``Next`` selector DAG. The ``condition`` is the node whose
    ``_id_`` the evaluation trackers key on, so status resolution is a plain membership
    test.
    """

    condition: SymbolicExpression
    """
    The leaf condition node carrying the rule's conclusion(s).
    """

    conclusions: List[Add]
    """
    The ``Add`` conclusion(s) attached to :attr:`condition` (one for single-class).
    """

    depth: int
    """Refinement-nesting depth (0 = a top-level rule)."""
    kind: RuleKind
    """
    How the rule relates to its predecessor.
    """


def walk_rules(conditions_root: SymbolicExpression) -> List[RuleView]:
    """
    Flatten a rule-tree selector DAG into rules in classic RDR display order.

    A ``Refinement``'s right branch nests one level deeper (an *except-if*); an
    ``Alternative``'s right branch is a same-level sibling (an *else-if*). Leaf
    condition nodes (everything that is not a :class:`ConclusionSelector`) become
    :class:`RuleView` rows.

    :param conditions_root: The root of the rule tree's condition DAG.
    :return: The rules in pre-order, each tagged with its depth and kind.
    """
    rules: List[RuleView] = []

    def visit(node: SymbolicExpression, depth: int, kind: RuleKind) -> None:
        match node:
            case Refinement():
                visit(node.left, depth, kind)
                visit(node.right, depth + 1, RuleKind.EXCEPT_IF)
            case Alternative():
                visit(node.left, depth, kind)
                visit(node.right, depth, RuleKind.ELSE_IF)
            case Next():
                for child in node._operation_children_:
                    visit(child, depth, kind)
            case _:
                rules.append(
                    RuleView(
                        condition=node,
                        conclusions=node.conclusions_of_type(Add),
                        depth=depth,
                        kind=kind,
                    )
                )

    visit(conditions_root, 0, RuleKind.IF)
    return rules


def resolve_status(
    rule: RuleView,
    satisfied_ids: Optional[OrderedSet[UUID]],
    evaluated_ids: Optional[OrderedSet[UUID]],
) -> RuleStatus:
    """
    Classify a rule as fired / evaluated-not-fired / not-evaluated from the observer id-
    sets.

    :param rule: The rule whose ``condition`` node id is looked up.
    :param satisfied_ids: Condition ids whose truth value was True (``None`` ⇒ none).
    :param evaluated_ids: Expression ids that were evaluated at all (``None`` ⇒ none).
    :return: The :class:`RuleStatus` for the rule.
    """
    condition_id = rule.condition._id_
    if satisfied_ids is not None and condition_id in satisfied_ids:
        return RuleStatus.FIRED
    if evaluated_ids is not None and condition_id in evaluated_ids:
        return RuleStatus.EVALUATED_NOT_FIRED
    return RuleStatus.NOT_EVALUATED


def enforce_parent_consistency(
    statuses: List[RuleStatus],
    rules: List[RuleView],
) -> List[RuleStatus]:
    """
    Downgrade refinement FIRED status to NOT_EVALUATED when its visual parent didn't
    fire.

    A refinement (except-if) at depth > 0 can only truly fire when its visual parent
    (the nearest preceding rule at depth-1) also fired — the refinement's selector
    evaluates its right branch only when the left side was satisfied.  A FIRED status on
    the refinement when the parent is not FIRED indicates a node-sharing issue in the
    rule tree (e.g. the same cached condition node appearing in two branches). This
    function corrects the display to avoid a visually nonsensical "green child under a
    red parent".

    :param statuses: One status per rule, aligned index-for-index with ``rules``.
    :param rules: The rules in display order.
    :return: Corrected statuses with the invariant enforced.
    """
    result = list(statuses)
    for rule_index, (rule, status) in enumerate(zip(rules, result)):
        if rule.depth == 0 or status != RuleStatus.FIRED:
            continue
        parent_index = next(
            (
                candidate_index
                for candidate_index in range(rule_index - 1, -1, -1)
                if rules[candidate_index].depth == rule.depth - 1
            ),
            None,
        )
        if parent_index is not None and result[parent_index] != RuleStatus.FIRED:
            result[rule_index] = RuleStatus.NOT_EVALUATED
    return result


# %% Compact symbolic formatting of conditions and conclusions


def _format_value(value: Any) -> str:
    """:return: A compact, human-readable rendering of a leaf value."""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, enum.Enum):
        return value.name
    return str(value)


def _attribute_path(attribute: Attribute) -> str:
    """
    :param attribute: The attribute-access node to render.
    :return: The attribute access path with the root subject variable dropped.
    """
    child = attribute._child_
    if isinstance(child, Variable):
        return attribute._attribute_name_
    return f"{format_condition(child)}.{attribute._attribute_name_}"


def _format_conclusion_selector(expression: ConclusionSelector) -> str:
    """
    Render a :class:`ConclusionSelector` in a compact, readable form.

    ConclusionSelectors (Alternative, Refinement, Next) are control-flow nodes, not
    conditions. When they appear as guard expressions in backward-inference output the
    default dataclass ``repr`` is unreadable — it dumps all internal fields including
    ``_conclusions_``, parent references, and evaluation flags.

    This helper renders them via their child expressions instead.

    :param expression: The selector node to render.
    :return: The compact rendering.
    """
    match expression:
        case Alternative():
            return f"({format_condition(expression.left)} else {format_condition(expression.right)})"
        case Refinement():
            return f"({format_condition(expression.left)} except if {format_condition(expression.right)})"
        case Next():
            children = ", ".join(
                format_condition(c) for c in expression._operation_children_
            )
            return f"next ({children})"
        case _:
            return expression.__class__.__name__


def format_condition(expression: Any) -> str:
    """
    Render a condition expression as a compact, prefix-stripped string.

    e.g. ``case_variable.legs == 4`` becomes ``legs == 4``; an ``AND`` of comparators is
    joined with ``and``. Anything unrecognised falls back to its ``repr``.

    :param expression: The condition expression to render.
    :return: The compact rendering.
    """
    match expression:
        case ConclusionSelector():
            return _format_conclusion_selector(expression)
        case Comparator():
            return f"{format_condition(expression.left)} {expression._name_} {format_condition(expression.right)}"
        case AND():
            return f"{format_condition(expression.left)} and {format_condition(expression.right)}"
        case OR():
            return f"{format_condition(expression.left)} or {format_condition(expression.right)}"
        case Not():
            return f"not {format_condition(expression._child_)}"
        case Attribute():
            return _attribute_path(expression)
        case Literal():
            return _format_value(expression._value_)
        case Variable():
            return expression._name_
        case _:
            return repr(expression)


def format_conclusion(add: Add) -> str:
    """
    :param add: The conclusion node to render.
    :return: A compact ``attribute = value`` rendering of an ``Add`` conclusion.
    """
    variable = add.variable
    name = (
        variable._attribute_name_
        if isinstance(variable, Attribute)
        else format_condition(variable)
    )
    value = add.value
    if isinstance(value, Literal):
        value_str = _format_value(value._value_)
    elif isinstance(value, Variable):
        value_str = value._name_
    else:
        value_str = _format_value(value)
    return f"{name} = {value_str}"


def _format_conclusions(rule: RuleView) -> str:
    """
    :param rule: The rule whose conclusions are rendered.
    :return: The rule's conclusions rendered and joined, or ``"?"`` if it has none.
    """
    if not rule.conclusions:
        return "?"
    return ", ".join(format_conclusion(add) for add in rule.conclusions)


# %% Tree connectors, elision, and the renderer


def _continues_at(depths: List[int], index: int, level: int) -> bool:
    """
    :param depths: The depth of every rule, in display order.
    :param index: The rule currently being drawn.
    :param level: The ancestor nesting level being checked.
    :return: True if the ancestor at ``level`` has a later sibling (draw a guide).
    """
    for depth_index in range(index + 1, len(depths)):
        if depths[depth_index] < level:
            return False
        if depths[depth_index] == level:
            return True
    return False


def _is_last_at(depths: List[int], index: int, level: int) -> bool:
    """
    :param depths: The depth of every rule, in display order.
    :param index: The rule currently being drawn.
    :param level: The nesting level being checked.
    :return: True if the node at ``index`` is the last of its siblings at ``level``.
    """
    for depth_index in range(index + 1, len(depths)):
        if depths[depth_index] < level:
            return True
        if depths[depth_index] == level:
            return False
    return True


def _connector(depths: List[int], index: int) -> str:
    """
    Build the ``│ ├─ └─`` prefix for a node from the flat list of depths.

    :param depths: The depth of every rule, in display order.
    :param index: The rule to build the connector prefix for.
    :return: The connector prefix.
    """
    depth = depths[index]
    if depth == 0:
        return ""
    parts = [
        TreeGlyph.GUIDE if _continues_at(depths, index, level) else TreeGlyph.GAP
        for level in range(1, depth)
    ]
    parts.append(
        TreeGlyph.BRANCH_LAST if _is_last_at(depths, index, depth) else TreeGlyph.BRANCH
    )
    return "".join(parts)


@dataclass
class RuleTreeRenderer:
    """
    Renders a flat list of :class:`RuleView` rows as a coloured, elided text tree.
    """

    head: int = DEFAULT_HEAD
    """
    How many rules to show before the elision marker.
    """

    tail: int = DEFAULT_TAIL
    """
    How many rules (ending on the firing rule) to show after the elision marker.
    """

    use_color: bool = True
    """
    Whether to wrap each rule line in its status colour.
    """

    def render(
        self,
        rules: List[RuleView],
        satisfied_ids: Optional[OrderedSet[UUID]],
        evaluated_ids: Optional[OrderedSet[UUID]],
        fired_index: Optional[int],
    ) -> str:
        """
        :param rules: The rules in display order (from :func:`walk_rules`).
        :param satisfied_ids: Satisfied condition ids (for green).
        :param evaluated_ids: Evaluated expression ids (for red vs grey).
        :param fired_index: Index of the rule that fired; the elided tail ends here.
        :return: The multi-line rendered tree.
        """
        if not rules:
            return ""
        depths = [rule.depth for rule in rules]
        statuses = [
            resolve_status(rule, satisfied_ids, evaluated_ids) for rule in rules
        ]
        statuses = enforce_parent_consistency(statuses, rules)
        lines = [
            self._render_row(rule, _connector(depths, index), statuses[index])
            for index, rule in enumerate(rules)
        ]
        return "\n".join(self._elide(lines, len(rules), fired_index))

    def _render_row(
        self,
        rule: RuleView,
        connector: str,
        status: RuleStatus,
    ) -> str:
        """
        :param rule: The rule to render.
        :param connector: The nesting-connector prefix for this row (from :func:`_connector`).
        :param status: The rule's status, driving the row's colour.
        :return: The rendered, single-line row.
        """
        text = f"{rule.kind} {format_condition(rule.condition)}  →  {_format_conclusions(rule)}"
        if self.use_color:
            text = f"{status.color}{text}{Style.RESET_ALL}"
        return f"{connector}{text}"

    def _elide(
        self, lines: List[str], total: int, fired_index: Optional[int]
    ) -> List[str]:
        """
        Keep the first :attr:`head` rows + the :attr:`tail` rows ending on the fired
        row.

        :param lines: The fully rendered rows, in display order.
        :param total: The total number of rows.
        :param fired_index: Index of the fired row; the elided tail ends here (defaults
            to the last row when nothing fired).
        :return: The elided list of rows, with a hidden-count marker in place of any
            rows dropped from the middle.
        """
        anchor = fired_index if fired_index is not None else total - 1
        tail_start = max(0, anchor - self.tail + 1)
        # Contiguous (head reaches the tail window): show straight through to the anchor.
        if tail_start <= self.head:
            return lines[: anchor + 1]
        hidden = tail_start - self.head
        marker = f"{Fore.LIGHTBLACK_EX}{TreeGlyph.GAP}{TreeGlyph.VERTICAL_DOTS}  ({hidden} hidden){Style.RESET_ALL}"
        return lines[: self.head] + [marker] + lines[tail_start : anchor + 1]


def _fired_index(
    rules: List[RuleView], firing_anchor_id: Optional[UUID]
) -> Optional[int]:
    """
    :param rules: The rules in display order.
    :param firing_anchor_id: The id of the condition node that fired, or ``None``.
    :return: The index of the fired rule in ``rules``, or ``None`` if none fired.
    """
    if firing_anchor_id is None:
        return None
    for index, rule in enumerate(rules):
        if rule.condition._id_ == firing_anchor_id:
            return index
    return None


def render_rule_tree(
    trace: ClassificationTrace,
    *,
    head: int = DEFAULT_HEAD,
    tail: int = DEFAULT_TAIL,
    use_color: bool = True,
) -> str:
    """
    Render the rule tree described by a :class:`ClassificationTrace` as coloured text.

    :param trace: The classification trace carrying the rule-tree root and the observer
        id-sets that drive the colours and the elision anchor.
    :param head: Rules to show before the elision marker.
    :param tail: Rules to show after it (ending on the firing rule).
    :param use_color: Whether to colour rows by status.
    :return: The rendered tree, or ``""`` when the tree is empty.
    """
    if trace.rule_tree_root is None:
        return ""
    rules = walk_rules(trace.rule_tree_root)
    fired_index = _fired_index(rules, trace.firing_anchor_id)
    renderer = RuleTreeRenderer(head=head, tail=tail, use_color=use_color)
    return renderer.render(
        rules,
        trace.satisfied_condition_ids,
        trace.evaluated_expression_ids,
        fired_index,
    )

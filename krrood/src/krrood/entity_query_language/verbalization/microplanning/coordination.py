from __future__ import annotations

import operator
from dataclasses import dataclass
from enum import Enum, auto
from typing_extensions import (
    TYPE_CHECKING,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    Union,
)

from krrood.entity_query_language.core.mapped_variable import Attribute, MappedVariable
from krrood.entity_query_language.core.variable import Variable
from krrood.entity_query_language.operators.comparator import Comparator
from krrood.entity_query_language.verbalization.chain_utils import walk_chain
from krrood.entity_query_language.verbalization.fragments.base import (
    oxford_comma,
    PhraseFragment,
    Fragment,
)
from krrood.entity_query_language.verbalization.vocabulary.english import (
    Conjunctions,
    RangePhrases,
)

if TYPE_CHECKING:
    from krrood.entity_query_language.core.base_expressions import SymbolicExpression

#: Hashable identity of a pure attribute chain: ``(root variable id, ((name, owner), …))``.
ChainKey = Tuple


@dataclass
class RangeFold:
    """A folded lower/upper bound pair on one attribute chain."""

    chain_expression: SymbolicExpression
    """The shared attribute chain (e.g. ``t.booking_date``)."""

    lower_expression: SymbolicExpression
    """The lower-bound value expression (the ``>=`` / ``>`` right operand)."""

    upper_expression: SymbolicExpression
    """The upper-bound value expression (the ``<=`` / ``<`` right operand)."""


class _Bound(Enum):
    """Internal marker for the direction of a bound comparison in range folding."""

    LOWER = auto()
    UPPER = auto()


def _chain_key(expression: SymbolicExpression) -> Optional[ChainKey]:
    """:return: The hashable identity of a pure attribute chain — ``(root_id, ((name, owner),
    …))`` — or ``None``."""
    if not isinstance(expression, MappedVariable):
        return None
    chain, root = walk_chain(expression)
    if not isinstance(root, Variable):
        return None
    parts = []
    for node in chain:
        if not isinstance(node, Attribute):
            return None  # only pure attribute chains fold cleanly
        parts.append((node._attribute_name_, node._owner_class_))
    return (root._id_, tuple(parts))


def _classify(conjunct: SymbolicExpression) -> Optional[Tuple[ChainKey, _Bound]]:
    """
    :param conjunct: A candidate conjunct.
    :return: ``(chain_key, _Bound)`` when *conjunct* is a bound comparison, else ``None``.
    """
    if not isinstance(conjunct, Comparator):
        return None
    key = _chain_key(conjunct.left)
    if key is None:
        return None
    if conjunct.operation in (operator.gt, operator.ge):
        return key, _Bound.LOWER
    if conjunct.operation in (operator.lt, operator.le):
        return key, _Bound.UPPER
    return None


def fold_range_pairs(
    conjuncts: List[SymbolicExpression],
) -> List[Union[SymbolicExpression, RangeFold]]:
    """
    Fold complementary lower/upper bound comparisons on the same chain into range items,
    preserving the order of everything else.

    This is the coordination (aggregation) microplanning task — conjunction reduction folding
    ``x >= low`` and ``x <= high`` into ``x is between low and high``. Direction (not position) decides
    which operand is the lower vs upper bound, so ``t.x <= high`` written before ``t.x >= low`` still
    yields ``between low and high``.

    References:

    * Reiter, E. & Dale, R. (2000), "Building Natural Language Generation Systems", CUP —
      aggregation as a microplanning task.
    * Dalianis, H. (1999), "Aggregation in Natural Language Generation", *Computational
      Intelligence* 15(4) — aggregation realised via coordination / conjunction reduction.

    :param conjuncts: A flat list of conjuncts (e.g. the operands of an ``AND``).
    :return: A list whose items are either the original expressions or range folds.
    """
    classifications = [_classify(conjunct) for conjunct in conjuncts]
    slots: List[Union[SymbolicExpression, RangeFold]] = list(conjuncts)
    dropped = [False] * len(conjuncts)
    # chain_key -> indices of bounds awaiting a complement (always one direction at a time).
    awaiting: Dict[ChainKey, List[int]] = {}
    for i, classification in enumerate(classifications):
        if classification is None:
            continue
        key, bound = classification
        queue = awaiting.setdefault(key, [])
        # A waiting bound of the opposite direction → fold the pair; else enqueue and wait.
        if queue and classifications[queue[0]][1] is not bound:
            j = queue.pop(0)
            lower, upper = (
                (conjuncts[j], conjuncts[i])
                if bound is _Bound.UPPER
                else (conjuncts[i], conjuncts[j])
            )
            slots[min(i, j)] = RangeFold(
                chain_expression=lower.left,
                lower_expression=lower.right,
                upper_expression=upper.right,
            )
            dropped[max(i, j)] = True
        else:
            queue.append(i)
    return [slot for index, slot in enumerate(slots) if not dropped[index]]


def has_pair(conjuncts: List[SymbolicExpression]) -> bool:
    """
    :param conjuncts: A flat list of conjuncts.
    :return: ``True`` when range folding would produce at least one range fold.
    """
    return any(isinstance(item, RangeFold) for item in fold_range_pairs(conjuncts))


def fragment_for_folded_conjunct(
    item: Union[SymbolicExpression, RangeFold],
    child: Callable[[SymbolicExpression], Fragment],
    *,
    compact: bool,
) -> Fragment:
    """
    Render one folded conjunct: a range fold becomes a *between* phrase; any other conjunct is
    rendered via *child*.

    :param item: A folded conjunct (a range fold or a raw expression).
    :param child: The fold continuation rendering a raw expression.
    :param compact: Drop the copula in the *between* phrase (HAVING / post-nominal contexts).
    :return: The fragment for *item*.
    """
    if isinstance(item, RangeFold):
        return build_between(
            child(item.chain_expression),
            child(item.lower_expression),
            child(item.upper_expression),
            compact=compact,
        )
    return child(item)


def build_between(
    left_fragment: Fragment,
    lower_fragment: Fragment,
    upper_fragment: Fragment,
    *,
    compact: bool,
) -> Fragment:
    """
    Build *"<left> is between <low> and <high>"* (or copula-less *"<left> between …"* when *compact*).

    :param left_fragment: The already-rendered left side (a full chain, or a bare attribute).
    :param lower_fragment: Rendered lower-bound value.
    :param upper_fragment: Rendered upper-bound value.
    :param compact: Drop the copula (for HAVING / post-nominal contexts).
    :return: The range phrase fragment.
    """
    op = (RangePhrases.BETWEEN if compact else RangePhrases.IS_BETWEEN).as_fragment()
    bounds = oxford_comma(
        [lower_fragment, upper_fragment], Conjunctions.AND.as_fragment()
    )
    return PhraseFragment(parts=[left_fragment, op, bounds])

from __future__ import annotations

from krrood.entity_query_language.query.operations import GroupedBy, OrderedBy
from krrood.entity_query_language.verbalization.fragments.base import (
    VerbalizationFragment,
)
from krrood.entity_query_language.verbalization.grammar.clauses.assembler import (
    GroupedByAssembler,
    OrderedByAssembler,
)
from krrood.entity_query_language.verbalization.grammar.framework.phrase_rule import (
    PhraseRule,
    RuleContext,
)


class GroupedByRule(PhraseRule):
    """GroupedBy → *"grouped by <key1>, <key2>, …"* (or *"grouped"* when keyless).

    >>> employee = variable(Employee, [])
    >>> verbalize_expression(
    ...     a(set_of(employee.department, sum(employee.salary)).grouped_by(employee.department))
    ... )
    'For each department, report the sum of salaries of Employees'
    """

    construct = GroupedBy

    def build(self, node: GroupedBy, context: RuleContext) -> VerbalizationFragment:
        """:return: The *"grouped by …"* clause for the GROUP BY node.

        It produces the grouping span by delegating to the grouped-by assembler, which fronts the key
        as *"For each department, report"* so the grouping frames the whole report.
        """
        return GroupedByAssembler(context).assemble(node)


class OrderedByRule(PhraseRule):
    """OrderedBy → *"ordered by <variable> from lowest to highest / from highest to lowest"*.

    >>> employee = variable(Employee, [])
    >>> verbalize_expression(a(set_of(employee).ordered_by(employee.salary, descending=True)))
    'Report Employees ordered by their salaries from highest to lowest'
    """

    construct = OrderedBy

    def build(self, node: OrderedBy, context: RuleContext) -> VerbalizationFragment:
        """:return: The *"ordered by …"* clause for the ORDER BY node.

        It produces the trailing ordering span *"ordered by their salaries from highest to lowest"*
        by delegating to the ordered-by assembler; the rest of the sentence comes from the query.
        """
        return OrderedByAssembler(context).assemble(node)

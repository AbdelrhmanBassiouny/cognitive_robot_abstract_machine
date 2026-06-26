from __future__ import annotations

from krrood.entity_query_language.operators.aggregators import Aggregator
from krrood.entity_query_language.verbalization.fragments.base import (
    Fragment,
    NounPhrase,
)
from krrood.entity_query_language.verbalization.fragments.features import Definiteness
from krrood.entity_query_language.verbalization.grammar.aggregation.kinds import (
    AGGREGATION_KIND,
)
from krrood.entity_query_language.verbalization.grammar.framework.phrase_rule import (
    PhraseRule,
    RuleContext,
)


class AggregatorRule(PhraseRule):
    """*"the <aggregation> <plural child>"* (or *"the <aggregation> of <child>"*).

    >>> verbalize_expression(max(variable(Robot, []).battery))
    'the maximum of the battery of a Robot'
    """

    construct = Aggregator
    name = "aggregator"
    # The aggregate counts/sums over a population, so a child that is itself a query is rendered as a
    # nested noun phrase ("ints such that ...") rather than a top-level imperative ("Find an int such
    # that ..."), which would read as "the number of Find an int such that ...".
    enters_query_scope = True

    def build(self, node: Aggregator, context: RuleContext) -> Fragment:
        """:return: the definite noun phrase for *node* — *"the <aggregation> of <child>"* — or the
        bare aggregation word for a childless aggregate.

        >>> verbalize_expression(max(variable(BankTransaction, []).amount_details.amount))
        'the maximum of the amount of the amount_details of a BankTransaction'

        A child that is itself a query is rendered as the counted population — a plural noun with its
        restriction folded in — never an imperative *"Find …"* clause (which would read as *"the
        number of Find a Robot …"*):

        >>> robot = variable(Robot, [])
        >>> verbalize_expression(count(entity(robot).where(robot.battery > 50)))
        'the number of Robots whose battery is greater than 50'
        """
        # The aggregation word owns its complement realisation (the "of" and the child's number);
        # the rule only chooses the structure — a childless aggregate is the bare word, otherwise a
        # definite noun phrase around the lexicon-built complement.
        kind = AGGREGATION_KIND[type(node)]
        if not kind.has_child:
            return kind.as_fragment()  # childless aggregate, e.g. "count of all"
        child_fragment = context.child(node._child_, number=kind.child_number)
        # A computed quantity is a referring expression: named in full when first introduced (the
        # reported column), a later mention of the same aggregate (a HAVING / ordering on it) is the
        # general repeat-reduction's job — "the sum of salaries of Employees" → "the sum".
        return NounPhrase(
            head=kind.as_fragment(),
            definiteness=Definiteness.DEFINITE,
            modifiers=kind.complement(child_fragment),
            referent_id=node._id_,
            subject_of_modifiers=False,
        )

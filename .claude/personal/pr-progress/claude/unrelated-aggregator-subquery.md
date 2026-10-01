## PR #480 — aggregator over unrelated variables in a where is a subquery

Branch `claude/unrelated-aggregator-subquery`, draft, off `main`. Asked for by the developer
while reviewing #479 (probability as an aggregator), which merges it in.

Done 2026-10-01 (e9ea05375): `WhereBuilder` replaces an aggregator whose variables are disjoint
from the query's selected variables and its non-aggregator condition variables with
`aggregator._as_subquery_()` at where-time; a related one is still refused.
`FilterBuilder.add_conditions` re-checks on a later `.where()` (previously `conditions +=`
skipped the check), and the builder remembers replaced aggregators so a later relating condition
is refused. `_replace_child_` now embeds via `_as_embeddable_child_` (a query swapped in was
embedded uncompiled -> NoExpressionFoundForGivenID). Doc in aggregators.md. krrood 2036 passed.

Next: nothing pending.

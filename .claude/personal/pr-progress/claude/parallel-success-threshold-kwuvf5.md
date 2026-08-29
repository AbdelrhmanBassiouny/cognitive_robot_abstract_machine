## /add-plan-item: the "at least k of n" threshold connective (2026-08-29)

**No branch, no code, no pull request.** This branch only ever ran
`/add-plan-item`, which decides where work belongs and stops there. Nothing
is outstanding on it, and it should not be pushed.

**Question asked.** Whether giskardpy's `Parallel` / coraplex's parallel
nodes - "succeed if at least k children succeed" - generalize EQL's `Or`,
so a superclass parameterized by a minimum success count could be the base
of both.

**Answer.** Yes, but it generalizes `And` too: k=1 is `Or`, k=n is `And`.
It is a *connective*, not a quantifier, and adds no expressive power (the
k-subset expansion is propositional). EQL's own `AtLeast`
(`query/quantifiers.py`) is the neighbouring counting *quantifier*, so that
name is taken.

**Outcome.** New item `threshold-connective` in `eql-existential-semantics`
(#137), `disjunction-safety` track, `depends_on:
[disjunction-range-restriction]`, `not_started`. A cross-plan note went on
`eql-performatives`' (#108) `language-nodes-and-bridge`, which already owns
the giskardpy/coraplex unification. Both plans saved, both tracking issues
commented, both dashboards republished.

**Resolved.** `eql-existential-semantics`' roadmap carried a 2026-08-03
decision: *"Counting quantifiers are out of scope. Do not generalize
`exists` into it."* The new item is a connective and does not touch
`exists`, so it never contradicted that - but it sat next to it, which left
a future reader to re-derive the distinction. User chose (2026-08-29) to
restate rather than move the item: the decision rules on `exists` and calls
counting *a different operator*, and this item is that operator built
separately, as the decision implies. The bullet was amended in place (not
reversed), the item's own section gained the reverse pointer, #137 has the
record, and the dashboard is republished.

**Next.** Nothing on this branch. The item starts with
`/plan-item-kickoff eql-existential-semantics threshold-connective`, once
`disjunction-range-restriction` has landed.

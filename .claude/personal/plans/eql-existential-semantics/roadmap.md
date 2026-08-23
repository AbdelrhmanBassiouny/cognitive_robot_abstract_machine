# EQL existential semantics — roadmap

Narrative, findings and design rationale for the `eql-existential-semantics` plan.
Structured state lives in the sibling `plan.yaml`; per-branch review history will live in
`.claude/personal/pr-progress/<branch>.md` as each item opens a PR, exactly as the other
plans in this directory do.

Created 2026-08-03 from session
<https://claude.ai/code/session_01WntvmhgA9PggAdpJFQVv2n>, which did the whole
investigation below empirically before any code was written. No implementation exists
yet — every item is `not_started` or `blocked`.

## How this started

The question was narrow: *does `exists()` need to take the quantified variable as its
first argument, or is the condition enough?* The answer turned out to be "the condition
is enough", but chasing it uncovered three defects underneath, and the argument itself is
the least important of them.

## What was measured, not assumed

Every finding below was reproduced against a live engine in that session (probe scripts
were scratch-only and are not committed; the queries are reproduced verbatim in the
relevant `plan.yaml` items so they can be re-derived as failing tests).

**1. `exists` drops matching rows.** Over three boxes where two contain an apple:

```
an(entity(box).where(exists(fruit, HasType(fruit, Apple))))   →  ['two_apples']
```

`one_apple` is missing. The `return` after the first witness in `Exists._evaluate__` is
global, not per outer binding. Every existing `exists` test in the repo happens to have
exactly one matching row, which is why this survived. Prefixing a condition that binds
the outer variable fixes it:

```
.where(HasType(box, Box), exists(fruit, HasType(fruit, Apple)))  →  ['two_apples', 'one_apple']
```

**2. `not_(exists(...))` returns nothing, and `for_all` fails identically.** Same cause,
same workaround. Neither is covered by any existing test.

**3. A correlated existential becomes a cross product.** The yield reads `val.bindings`
— the quantified *variable's* bindings — never `cond_val.bindings`. An outer selected
variable bound only inside the condition is therefore dropped:

```
set_of(box, shelf).where(exists(fruit, and_(apple, shelf.box_name == box.name)))
  → [('two_apples','shelf_A'), ('two_apples','shelf_B'), ('two_apples','shelf_C')]
```

**4. The first argument is dead information at every call site.** All five in-repo uses
already mention it inside the condition. Passing the condition itself as the "variable",
`Exists(cond, cond)`, gives the correct answer.

**5. But it is not inert.** It is a real binder with semantic force:
`exists(unrelated_variable, cond)` returns wrong rows; `exists(empty_domain_variable,
cond)` makes everything false; `exists(selected_variable, cond)` returns everything. The
middle two are *correct* bounded-quantifier semantics — `∃v∈∅.φ` is false — which is
precisely why an unrelated variable is dangerous rather than harmless.

A correction worth recording, because the first pass of this analysis got it wrong: (5)'s
middle two cases were initially written up as bugs. They are not. Reading the first
argument as a bounded quantifier `∃v ∈ dom(v). φ` makes them the defined behaviour. That
sharpens the argument for removing it instead of weakening it.

## The literature framing that settled the design

Existential operators across formal query languages fall into three families, decided by
**where the quantified variable's range comes from**.

- **Range supplied by the quantifier ⇒ the variable is mandatory.** Tuple relational
  calculus (`∃t ∈ R`), Z (`∃ x : T | P`), Alloy (`some x: X | F`), OCL
  (`coll->exists(v | body)`), XQuery (`some $x in E satisfies P`), LINQ
  (`source.Any(x => …)`).
- **Range supplied by the body ⇒ no variable.** SQL's `EXISTS (subquery)`, SPARQL's
  `FILTER EXISTS { pattern }`, Cypher's `EXISTS { … }`, Datalog and Prolog rule bodies,
  and description logic's `∃R.C`, which has no variables in its syntax at all. Relational
  algebra likewise expresses ∃ purely as projection.
- **The variable named only to control projection.** Prolog's `bagof/3` groups by the
  goal's free variables, and `Y^Goal` marks `Y` existential so it stops participating in
  the grouping; `findall/3` is `bagof` with every free variable so marked. Explicitly
  about *which variables escape*, not *whether the goal is true*.

EQL is unusual: `variable(Cabinet, world.views)` carries its own domain, so every
variable is range-restricted at declaration — the property Van Gelder & Topor's safety
work exists to *establish* for calculus queries. Neither reason to name the variable
therefore applies. **EQL's `exists` is semantically in the body-supplies-the-range family
but was given the other family's syntax.** That mismatch is the whole issue.

Both OCL and Alloy show the same drift: OCL permits an implicit iterator
(`coll->exists(body)`), Alloy has the variable-free `some expr` alongside
`some x: X | F`.

## The design: semi-join, and why nothing escapes

> For each distinct assignment to the outer-visible variables (already bound, or selected
> by the enclosing query), yield it once if at least one assignment to the remaining
> variables satisfies the condition. The remaining variables never escape.

This is `R ⋉ S = π_R(R ⋈ S)` — the textbook operator, not a novel design. The important
consequence: because **no new bindings are emitted at all**, there is no witness to
choose, so the "why only the first answer?" question does not need an answer — it stops
being askable. The only reason the current code has to pick a witness is that it tries to
export bindings from inside.

The local/outer split is decided lexically: a variable is local iff it occurs *only*
within the exists subtree. Cypher states the same rule in one sentence — *"any variable
defined within the subquery will not be available outside of the expression"* — and the
computation is identical to Prolog's `bagof` free-variable rule.

Two consequences to accept deliberately:

- **It is mildly non-compositional.** A condition's local set depends on the query around
  it. SQL has the same property. It means the set must be computed at build/plan time
  against the root, and *the same condition object reused in two queries can have two
  different local sets*. The codebase already fights this class of problem — see the
  `ActiveConditionsRoot` comment in `base_expressions.py` about a node reused as the
  condition of more than one `Filter`.
- **If you want the inner rows, don't use `exists`.** That is SQL's story unchanged:
  `EXISTS` is a boolean filter; wanting the apples means writing the join.

### What to avoid

SPARQL 1.1's `FILTER EXISTS` is the one body-supplies-the-range design that got scoping
wrong, and the W3C has been unpicking it for years: its substitution-based semantics
diverges from bottom-up evaluation, variables get replaced even when they contribute
nothing to the inner results, and substitution can flip `MINUS` into its disjoint-domain
case. **Define `exists` by evaluating the condition under the outer bindings as an
environment, never by substituting outer values into the condition tree.**

## Why binding order is the prerequisite, not an optimization

This is the single most important structural fact in the plan, and it reversed the
sequencing the session first proposed.

A correct semi-join implementation was written and run both ways:

```
semi_join_exists(apple.color == 'green')                    → ['two_green','no_green','one_green','empty']
HasType(box, AppleBox) then semi_join_exists(...)           → ['two_green','one_green']
```

Without a bound outer relation the filter is evaluated once against an empty context,
answers "true", and every box then passes. **A semi-join is only meaningful relative to
an outer relation, and EQL's bottom-up evaluation does not have one at the point the
condition runs.** Shipping the quantifier change first would make `exists` *more* wrong.

The literature names all of this. Applying negation to a goal whose non-local variables
are unbound is **floundering** (Clark 1978), which is exactly why `not_(exists(...))`
needs a hand-placed binding condition in front of it. Datalog's structural answer is
stratified negation plus an ordering discipline. The canonical way to get top-down
binding propagation *inside* a bottom-up engine — without switching to top-down — is
**magic sets / sideways information passing** with adorned predicates (Bancilhon, Maier,
Sagiv & Ullman, PODS 1986). The relational-engine equivalent is that the optimizer
guarantees the outer relation drives the semi-join.

Note what the `HasType(box, Box)` workaround actually is: **the user hand-writing a magic
predicate.** That it works confirms the diagnosis and locates the fix — in the planner,
as a constraint on evaluation order, not in the user's `.where(...)` argument order.

## The disjunction side-finding

`core_logical_operators.py` documents `OR` as an *ElseIf* that evaluates the right
operand only when the left is false. Measured behaviour is classical disjunction — the
union of both branches' solution sets — because selected variables are enumerated
independently of the condition:

```
set_of(box, tag).where(or_(box.name == 'green_box', tag.name == 't1'))
  → [('green_box','t1'), ('green_box','t2'), ('red_box','t1')]     # exactly the union
```

Correct, but *incidentally* correct: nothing states or enforces it and the docstring says
otherwise. The classical rule is `rr(φ ∨ ψ) = rr(φ) ∩ rr(ψ)` — a variable is
range-restricted in a disjunction only if restricted in both branches. Branch-specific
variables are fine as long as they stay local.

Inside a semi-join `exists` the hazard is structurally neutralized, because nothing
escapes — verified: an OR over two independent local variables inside a semi-join exists
loses no rows. So this is a `where()`-level concern, which is why it is a parallel track
rather than part of the spine.

Three established designs exist for the unsafe case: Datalog-style rejection, SPARQL's
partial solution mappings, or today's enumeration-order accident. The user chose
rejection (2026-08-03), which also matches `AGENTS.md`'s "programs in illegal states
should raise".

## Cross-plan dependency on PR #99

PR **#99** (`rdr-refactor` plan, branch `claude/eql-truth-unification-refactor-pfux7f`,
open, labelled `in-review` / `needs-resolution`) refactors `base_expressions.py`,
`logical_quantifiers.py` and `core_logical_operators.py` — the same functions this plan's
wave 1 touches. It also renamed the quantifier locals this analysis quotes.

Its description defers an `exists` defect explicitly:

> *"Also preserved deliberately: `evaluate_condition` on a satisfied bare `exists(...)`
> returns `False`, matching `main`. That looks like a genuine pre-existing bug, but
> changing it inside a refactor is how downstream packages break — it deserves its own
> change."*

This plan is that change, and the deferred defect is a named TDD case on
`exists-semijoin`. The user chose (2026-08-03) to **block wave 1 on #99 merging** rather
than stack on its branch or absorb the conflict.

#99 also carries the in-repo precedent for the benchmarking track: it published a
truth-read-count table measured against an `origin/main` worktree, and its history is the
warning that motivates measuring downstream — its cost regression was invisible to
krrood's own suite (cheap comparators) and broke coraplex twice before reaching parity.

## Decisions on record

All 2026-08-03, in the creating session:

- **Sequence against #99**: block wave 1 on it merging.
- **OR / safe-range**: own parallel track — characterize, then enforce.
- **API migration**: hard break, all five call sites in one PR, no deprecation shim.
- **Tracking issue**: yes (#137).
- **`for_all` keeps its variable.** The ∀/∃ split among a condition's free variables is
  not derivable and interleaved quantifier order is meaningful. `Exists` and `ForAll`
  sharing `QuantifiedConditional`'s `(left, right)` shape is a false symmetry, and it is
  what pulled the redundant argument in.
- **Counting quantifiers are out of scope.** `∃≥n` is a graded/qualified number
  restriction, cannot stop at the first witness, and is `count(...) >= n` — a different
  operator. Do not generalize `exists` into it.

## Bibliography

Cited in the items; collected here so no item has to repeat a full reference.

**Semi-join and decorrelation**
- Bernstein & Chiu, *Using semi-joins to solve relational queries*, JACM 1981.
- Kim, *On optimizing an SQL-like nested query*, ACM TODS 7(3), 1982.
- Ganski & Wong, *Optimization of nested SQL queries revisited*, SIGMOD 1987 — the
  **count bug**: a witness search not grouped by the outer binding, the same failure class
  as finding (1) above.
- Dayal, *Of nests and trees*, VLDB 1987.
- Seshadri, Pirahesh & Leung, *Complex query decorrelation*, ICDE 1996.
- Neumann & Kemper, *Unnesting arbitrary queries*.

**Safety and range restriction**
- Codd, *Relational completeness of data base sublanguages*, 1972.
- Chandra & Merlin, *Optimal implementation of conjunctive queries*, 1977 — conjunctive
  queries as ∃-quantified conjunctions where projection *is* the quantifier.
- Van Gelder & Topor, *Safety and translation of relational calculus queries*, ACM TODS
  16(2), 1991.
- Abiteboul, Hull & Vianu, *Foundations of Databases*, ch. 5 — safe-range normal form.

**Negation, binding propagation, evaluation strategy**
- Clark, *Negation as failure*, 1978 — floundering.
- Lloyd, *Foundations of Logic Programming*.
- Bancilhon, Maier, Sagiv & Ullman, *Magic sets and other strange ways to implement logic
  programs*, PODS 1986.
- Beeri & Ramakrishnan, *On the power of magic*.

**Language surfaces**
- Neo4j Cypher manual, *EXISTS subqueries* —
  <https://neo4j.com/docs/cypher-manual/current/subqueries/existential/>
- W3C, *SPARQL EXISTS report* — <https://w3c.github.io/sparql-exists/docs/sparql-exists.html>
- *The Problem of Correlation and Substitution in SPARQL* — <https://arxiv.org/pdf/1801.04387>
- Seaborne, *Substitution of Variables in SPARQL* — <https://afs.github.io/substitute.html>
- Patel-Schneider & Martin, *EXISTStential Aspects of SPARQL* —
  <https://ceur-ws.org/Vol-1690/paper72.pdf>
- Apache Jena ARQ, *Negation* — <https://jena.apache.org/documentation/query/negation.html>
- Prolog `bagof`/`setof`/`findall` and the `^` existential marker —
  <https://en.wikibooks.org/wiki/Prolog/Bagof,_Setof_and_Findall>
- OCL iterator forms — <https://sunye.github.io/ocl/>
- Baader et al., *The Description Logic Handbook* — variable-free `∃R.C`, and `≥n R.C`
  for the counting quantifier noted above.

## Argument-position correlation, raised from match-query-ergonomics (2026-08-23)

`argument-position-correlation` was added to the `binding-order` track from outside this
plan: krrood PR #192 (plan `match-query-ergonomics`, issue #181) gives an EQL `Match` the
full symbolic surface, and while measuring what a match may be used *as*, it found that a
plain query given as a predicate argument shows this plan's own mechanism with no
quantifier anywhere:

| written | result |
| --- | --- |
| `entity(body).where(HasType(entity(body), Handle))` | both rows |
| `entity(body).where(HasType(body, Handle))` | only the `Handle` |

`binding-order-planner`'s notes already describe that mechanism exactly - evaluated once
against an empty context, answers true, the selected variable then enumerates freely - but
its test list is all `exists()` / `not_(exists(...))`, and it is not known whether binding
the outer relation first also correlates an argument that is itself a query. The new item
depends on it and starts by re-measuring, closing as already-fixed if the planner covers
it.

Consequence recorded on both plans: #192 deliberately refuses to let a match reach a
predicate (`HasType(match, ...)` raises `LiteralConditionError`), because coercing it would
replace that loud error with the silent every-row answer above. The refusal can be lifted
once this item closes.

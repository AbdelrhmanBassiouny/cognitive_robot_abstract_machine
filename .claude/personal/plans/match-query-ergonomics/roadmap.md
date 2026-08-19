# match-query-ergonomics — roadmap

## 1. Origin (2026-08-19, investigation session)

The developer disliked that writing match queries sometimes requires
`query.expression` or `query.variable`. An investigation session (branch
`claude/match-query-access-patterns-p79fya`, no PR) swept every consumer,
root-caused the design gap, and — critically — found the situation is a
correctness problem, not just verbosity. Full findings are in
`pr-progress/claude/match-query-access-patterns-p79fya.md`; the load-bearing
facts are repeated here because they drive the plan's structure.

## 2. Root cause

EQL solves "object attributes vs framework attributes" with the
underscore-sandwich convention: `Query` inherits `CanBehaveLikeAVariable`
and keeps its real state behind `_selected_variables_`-style names, leaving
the plain attribute namespace free for symbolic `__getattr__` access
(`core/mapped_variable.py:99`). `Match`
(`entity_query_language/query/match.py`) is the one query-facing class that
does not participate: it is a plain dataclass whose public fields (`parent`,
`variable`, `type`, `conditions`, `domain`, `children`, plus
`HasFactoryAndKwargs.factory`/`kwargs`) collide with domain attribute names
— `FixedConnection.parent` being the motivating example — so symbolic access
cannot be forwarded and users are taught two escape hatches instead.

## 3. The escape hatches silently diverge (the reason for wave 1)

Verified empirically on main `90c241168` (2026-08-19):

- `q.where(q.expression.battery >= 50)` **does not filter at all** — the
  full domain comes back, no error. Only `q.variable.battery` works inside
  `where`. A condition rooted at the query itself is evaluated uncorrelated
  with that query's own bindings. This is a latent correctness bug on its
  own (hard-to-misuse violation) and plausibly shares a root cause with the
  uncorrelated-evaluation family the `eql-existential-semantics` plan
  (issue #137) is rebuilding the evaluation model for.
- `set_of(match.variable.parent, ...)` **silently drops the match's
  conditions** — only `match.expression.parent` carries them (repro:
  `the(...)` raised `MultipleSolutionFound` because `name == "Container1"`
  vanished).

So the current API forces users to memorize "`.variable` inside `where`,
`.expression` inside selection", and the wrong pick produces wrong results
rather than an exception. Any forwarding design must sit on one handle that
works in both contexts — which is why the bug fix is wave 1 and a hard
dependency of the refactor, not an optional cleanup.

## 4. Design decisions taken at plan creation

- **Forwarding target is the lowered query, not the bare variable**: the
  lowered `Entity` carries the match's conditions (the `set_of` semantics
  users rely on today via `.expression`); the variable does not. This only
  becomes safe once wave 1 makes query-rooted attributes correlate (or
  raise) inside `where`.
- **Item 2 stays krrood-internal and keeps `expression`/`variable` as
  working public properties** so every intermediate state ships green;
  item 3 does the cross-package + docs migration and then decides (with the
  developer) whether the properties are removed or kept as documented
  escape hatches. This split keeps each PR shippable alone, per the
  fold-vs-stack rules in the personal notes.
- **Fluent verbs stay public** (`where`, `from_`, `tolist`, `first`,
  `construct_instance`): the same accepted shadowing trade-off `Query`
  already makes for `where`/`having`/`ordered_by`.
- **Bug home**: the developer chose (AskUserQuestion, 2026-08-19) to track
  the no-filter bug in this plan rather than in `eql-existential-semantics`
  or after a further investigation round — it is provable with a failing
  test today and the refactor depends on it. Kickoff of item 1 must still
  check whether #137's evaluation-model wave subsumes the fix, and record
  the outcome on both mailboxes.

## 5. Known consumer surface (from the 2026-08-19 sweep)

- `.expression` detour (~30 user-facing sites): `test_match.py`,
  `test_explanation.py`, `test_meta_queries.py`, verbalization tests,
  `experiments` (`sage10k_actions.py:91`, `reliability.py:108`), `coraplex`
  (`training_environment.py:210`), plus `the(match.expression)` /
  `QueryGraph(query.expression)` quantification sites.
- `.variable` detour (~20 sites): `test_match.py:201`,
  `test_backends.py:205,224`, `test_match_verbalization.py`,
  underspecified-knowledge tests, `semantic_digital_twin` tests
  (`test_spatial_types.py:2012,2021`).
- Internal consumers of the fields being renamed: `backends.py`,
  `parametrization/parameterizer.py`, verbalization match/inference
  planners and assembler, `exceptions.py`, `coraplex/plans/plan_node.py:434`
  (`.type` used as a Python class at runtime), `probabilistic_model`
  `rspn.py:146,487` (`.variable`, `.kwargs`, `construct_instance`).
- Docs teaching the detours: `doc/eql/user/underspecified.md` (`.variable`
  idiom), `doc/eql/user/inference_explanation.md` (`.expression` idiom),
  `doc/eql/developer/graph_and_visualization.md`, `doc/eql/user/match.md`.
- Zero-consumer fields safe to rename freely: `parent`, `children`,
  `resolved`, `id`, `name`, `root`, `descendants`.

## 6. Coordination hazards

- **In-flight D-core stack (rdr-refactor plan, PRs #63–#67)** adds
  `test_underspecified_match.py` consuming the current Match API on every
  branch of the stack. Landing the rename either waits for the stack to
  cascade or relies on item 2's compatibility surface; check the stack's
  state at item-2 kickoff.
- **`eql-existential-semantics` (#137)**: shared uncorrelated-evaluation
  territory with item 1; see §4.
- After forwarding exists, a missed rename fails *silently* (the miss
  becomes a symbolic `Attribute` named e.g. `"variable"` — truthy, chainable,
  wrong) instead of raising `AttributeError`. Item 2's krrood-internal
  migration must therefore be exhaustive in the same PR, and its test plan
  should include a guard that the old names are really gone.

## 7. 2026-08-19: item 2 landed on a branch ahead of order (IDE-typing session)

A session answering a separate developer request — "the IDE doesn't treat
`a/an/the(ClassName)` like an instance of ClassName" — implemented item 2
near-verbatim on `claude/ide-type-inference-instances-dc6l6e` (commit
`147d098d2`, full krrood suite green, no PR) without knowing this plan
existed: it independently re-derived the same root cause (§2) and the same
design decisions (§4 — forward to the lowered query, underscore-sandwich
rename, fluent verbs stay public). It additionally delivered the static
half this plan had not scoped: the type/factory overloads of
`an()`/`a()`/`the()` now return `Union[T, Match[T]]` and
`Match.__call__` returns `Union[T, Self]`, pinned by the mypy fixture in
`test_typing/`, plus `__dir__` completion and a `CalledMatchAfterResolution`
guard for kwargs-after-lowering.

**The wave-1 dependency proved load-bearing, empirically.** On that branch:

- `q.where(q.battery >= 50)` (the new forwarded spelling) silently returns
  the whole domain — the §3 no-filter bug, now under the natural syntax;
- `q.where(q._variable_.battery >= 50)` filters correctly;
- selection (`set_of(q.parent, q.child)`) via forwarding is correct and
  covered by new tests.

So the branch must not land before item 1. Its own tests stayed green only
because the `where`-side tests it migrated use `_variable_`-rooted
conditions and the new forwarding tests exercise selection, not `where`.

**Deviations from the item-2 notes, to reconcile before a PR:**

- `variable` and `matches_with_variables` were renamed outright with all
  in-repo consumers migrated, instead of being kept as public compatibility
  properties. The D-core stack's `test_underspecified_match.py` (verified
  present on `D-core-underspecified` .. `D-core-expert`) uses
  `match.variable` and `match.matches_with_variables`, so its cascade will
  break loudly (iteration is blocked and the identity assert fails) when
  the two lines meet.
- The old-names-are-really-gone guard test (§6, silent-miss hazard) is not
  yet added.

**One new data point for the verbalizer:** a forwarded attribute
verbalizes as "the battery of the Robot" where a `_variable_`-rooted one
says "its battery" — cosmetic divergence noted for whenever item 3
modernizes docs/doctests.

## 8. 2026-08-19: item 1 kickoff — the fix is a self-reference rewrite, not an evaluation-model change

Branch `claude/match-query-ergonomics-where-rooted-b876wm`, PR #182 (draft),
off `main` at `90c241168`. The item was implemented directly at the
developer's instruction rather than through the usual plan-mode approval.

**Re-confirmed the bug and pinned its mechanism.** On `main`, both spellings
of a query-rooted `where` condition are uncorrelated:

- `query.where(query.battery >= 50)` returns the full domain;
- `query.where(query.battery >= 1000)` returns `[]`;
- `query.where(query.battery >= -1)` returns **four** rows over a two-robot
  domain.

So it is not "the condition is ignored" but existential-plus-cross-product:
the chain `query.battery` is rooted at the query, and inside that query's own
`Where` it re-evaluates the query as a nested (cached, uncorrelated) subquery,
answering "some row satisfies this" once and then letting the selected
variable enumerate freely. The row multiplication at `>= -1` is the tell.

**#137 does not subsume this (the cross-check §4 asked for).** The
`binding-order-planner` item of `eql-existential-semantics` covers the same
"uncorrelated condition returns every row" family, and its own notes describe
the identical symptom for `exists`. But binding the outer relation first does
not make `query.battery` mean "this row's battery": the chain would still be
rooted at the query and still evaluate it as a subquery. The self-reference has
to be resolved structurally. The two fixes are complementary, not overlapping,
and neither blocks the other. Recorded on both plans.

**Design chosen.** Conditions attached to a query have every attribute chain
rooted at that same query re-rooted onto the variable the query selects. The
rewrite happens at the point conditions are attached (`Query.where` /
`Query.having`), which confines it to the query's own conditions and leaves the
two things §4 depends on untouched: a chain rooted at a *different* query stays
an uncorrelated subquery, and the same chain used as a *selection*
(`set_of(match.expression.parent, ...)`, which is what carries the match's
conditions) is not rewritten at all.

Correlating rather than raising is what §4 requires: item 2 forwards
`match.<attr>` to the lowered query, so raising would make the natural spelling
an error rather than the default.

A query selecting more than one variable has no single subject for such an
attribute, so it raises `AmbiguousQueryAttribute` rather than guessing —
the "or raises" half of the item's brief, kept for the case correlation cannot
cover.

Chain rebuilding is a new `MappedVariable._reroot_on_`, with each mapping
subclass reporting the constructor arguments after the child that reproduce it,
so a new mapping type cannot silently be skipped by the rewrite.

**Detection is by expression id, not identity.** Attaching a mapped variable to
a query copies the query node while preserving `_id_`, and `Query._compile_`
replays the conditions onto a product sharing the specification's `_id_`. Any
self-reference test that used `is` would miss both.

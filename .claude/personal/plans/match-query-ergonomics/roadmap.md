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
so a new mapping type cannot silently be skipped by the rewrite. (The
constructor-arguments half of that is superseded by §10.)

**Detection is by expression id, not identity.** Attaching a mapped variable to
a query copies the query node while preserving `_id_`, and `Query._compile_`
replays the conditions onto a product sharing the specification's `_id_`. Any
self-reference test that used `is` would miss both.

## 9. 2026-08-20: review round on #182 — why the rebuild is not `apply_mapping_on_external_root`

The developer asked, on `_reroot_on_`, why it does not reuse
`MappedVariable.apply_mapping_on_external_root`, and — if it could — whether
`_mapping_arguments_` is needed at all.

Measured on the branch. `apply_mapping_on_external_root(root)` walks
`_access_path_` applying `_apply_mapping_` at each step, and with a *symbolic*
root those value-level mappings do rebuild the chain, because the operators
they use are traced: `getattr` gives an `Attribute`, `value[key]` an `Index`,
`value(...)` a `Call`. All three re-root correctly onto the selected variable.

`FlatVariable` is the one that does not. Its mapping is `yield from value`, and
`CanBehaveLikeAVariable.__iter__` is `None` deliberately, so re-rooting
`flat_variable(query.drawers).handle.name` raises
`TypeError: 'Attribute' object is not iterable`. Underneath that:
`apply_mapping_on_external_root` takes `next(...)` of each mapping — the first
value along the path — while re-rooting needs the structural node, and for
flattening the two differ even on real values.

The six tests already on the PR all pass with the simpler version, so the gap
was uncovered rather than absent.
`test_query_rooted_condition_through_a_flattened_attribute_filters` (commit
`c1206318`) pins it: it is the only one of the seven that fails when
`_reroot_on_` is replaced by the reuse.

Dropping `_mapping_arguments_` therefore costs either an `_apply_mapping_` that
knows about symbolic values or a re-enabled `__iter__`. The structural rebuild
stays for now and the review thread is left open — this answers the question
rather than doing what it asked, so the choice is the developer's.

**CI on #182**: one failure, `test_each_lib (experiments)` —
`test_real_stretch_demo_process_boundary.py` timing out after 300s waiting for
the ROS `/semantic_digital_twin/fetch_world` service. `main` at the same base
(`90c241168`) was green, so it is not red-on-base, but nothing in this diff
leaves `krrood/entity_query_language`; the push of `c1206318` re-runs it.

## 10. 2026-08-20: the reviewer's smell was real — flattenings are iteration variables

Asked to be critical about whether `flat_variable` or `CanBehaveLikeAVariable`
smelled, and whether `__iter__` should be implemented. Measured all three, and
the investigation found a correctness bug in §8's own rebuild.

**Why `FlatVariable` is an outlier — two independent reasons.**

1. It is the only *one-to-many* mapping. `apply_mapping_on_external_root` takes
   `next(...)` of each step, so it is a first-value walk, not a chain walk. That
   is already lossy for flattening on real values today: over a cabinet with
   drawers `['Handle1', 'Handle3']`, `flat_variable(cabinet.drawers).handle.name`
   returns `'Handle1'` and drops the other. Its docstring (`:return: An iterable
   of the mapped values`) describes what it should do, not what it does.
   Note the direction: fixing that method moves it *further* from a structural
   rebuild, since the rebuild wants exactly one node.
2. It has no traced operator. The other three re-root under that method only
   because `getattr` / `[]` / `()` happen to be intercepted, an unstated
   invariant that nothing enforces.

**`__iter__ = None` is a guard, not a smell.** Removing it does not yield a
`TypeError`; it re-enables Python's legacy `__getitem__` sequence protocol,
because `CanBehaveLikeAVariable` defines `__getitem__` — measured:
`iter(cabinet_var)` then yields `Cabinet[0]`, `Cabinet[1]`, … forever. Writing a
real `__iter__` yielding one symbolic element would make `for x in variable` run
exactly once — a quiet wrong answer replacing a loud error — and would give
flattening two spellings.

**The real distinction, and the bug.** A projection (`Attribute`, `Index`,
`Call`) is deterministic, so shared identity is correct and is what
`_get_mapped_variable_` gives. A flattening is an *iteration variable*, so each
one written must be its own variable — which is why `flat_variable` constructs
`FlatVariable(var)` directly rather than through the cache, and why
`explanation.py` can write `child1 = flat_variable(...)`,
`child2 = flat_variable(...)`, `node_id(child1) != node_id(child2)`.

§8's `_reroot_on_` rebuilt *everything* through `_get_mapped_variable_`, which
keys on the child plus the mapping's arguments — and a flattening has none. So
two flattenings collapsed into one node and `a != b` silently became `a != a`.
Measured over the two-cabinet fixture:

| spelling | variable-rooted | query-rooted before the fix |
| --- | --- | --- |
| two flattenings, `handle.name` of one drawer vs `container.name` of another | 1 cabinet | **0** |
| one flattening used by two conditions | 1 cabinet | 1 cabinet |

The second row rules out the naive fix of always constructing fresh: sharing has
to survive too.

**Fixed in `b88a7e81`**, both rows pinned as tests: a flattening rebuilds as a
fresh node, and every mapping is rebuilt once per root (memoized on the node,
keyed by the root's identifier) so chains that shared one still share it.
`_mapping_arguments_` is replaced by a per-subclass `_rebuild_on_`, which also
removes a fragility nobody had noticed: the old property returned a *positional*
tuple that silently had to match its own constructor's field order.

So the reviewer's second comment was right — the property should not exist — but
not by the route it proposed: any mechanism built on `_apply_mapping_` can only
express projections, because the projection/iteration distinction lives in
identity, which `_apply_mapping_` never sees.

**Two things left open on the thread for the developer:**

- `apply_mapping_on_external_root`'s `next(...)` truncation is a latent bug for
  its five callers in `parametrization/feature_extraction`: a feature chain
  containing a flattening reads only the first element. Possibly its own issue.
- The projection/iteration split is still implicit in the hierarchy. Making it
  explicit is a wider refactor than this bug fix.

Full krrood suite green (2157 passed; the two `test_object_diagram` failures are
this container missing the Graphviz `dot` binary, which CI installs).

## 11. 2026-08-20: naming one selection of a multi-variable query

The developer asked whether a condition may constrain one selection of a
`set_of` query through `query[variable].attribute`, and said to handle it if
not. It did not work, and the pre-existing behaviour was the same bug this item
is about. Over a two-selection query whose correct answer is three rows:

| spelling | `main` | branch before | after |
| --- | --- | --- | --- |
| `set_of(body, handle).where(body.size > 1)` | 3 | 3 | 3 |
| `query.where(query[body].size > 1)` | **54** | `AmbiguousQueryAttribute` | 3 |

So §8's `AmbiguousQueryAttribute` had converted a silent cross product into a
loud rejection of a spelling that should work.

**Why indexing is the right reference.** A `set_of` result is a
`UnificationDict` keyed by the selected variables, and that is how rows are
already read in the tests (`result[container].name`). `query[body]` symbolically
mirrors `row[body]`, so it is an existing reference rather than a new
convention. Indexing by a name string is not a spelling the language has:
`UnificationDict.__getitem__` reads `key._id_`, so `query["Body"]` raises
`AttributeError` at evaluation on `main` today. Left as a question on the
thread rather than invented here.

**The generalisation.** Re-rooting replaced the chain's base. It now replaces
whichever expression stands for the row: the query itself, or — when the chain's
first step indexes the query by one of its selected variables — that step, which
drops out as the chain re-roots onto the variable it names. `_reroot_on_`
therefore takes the expression the new root replaces, and the per-node rebuild
memo is keyed by that pair rather than by the root alone.

`AmbiguousQueryAttribute` still fires for a bare attribute of a multi-selection
query and for an index by a variable the query does not select; its suggestion
now offers `query[body].name` as the second way out.

**Boundaries confirmed by measurement, not assumed:** `where` and `having` both
correlate; `having` on a `set_of` fails identically for both spellings (a
separate pre-existing limitation, untouched); selection-side chains are still
not rewritten.

Full krrood suite green (2159 passed; the two `test_object_diagram` failures are
this container missing the Graphviz `dot` binary).

## 12. 2026-08-20: indexing belongs to `set_of`, and is checked where it is written

Three review comments on §11's implementation, all acted on in `62ec184aa`.

**Indexing a single-variable query is a value operation.** §11 gave every `Query`
the rule "an index by a selected variable names that variable", which was wrong
for `entity`: a single-variable query stands for the value its variable takes, so
`entity(body)[body]` means `body[body]`, not `body`. Measured before the fix, the
index step was silently dropped and the condition filtered as though it had been
written `body.size > 1`.

Made polymorphic rather than conditional: `Query._selection_indexed_by_` returns
`None`, and `SetOf` overrides it — only a query yielding rows of several
variables has a selection to pick out. Pinned by a test that the entity spelling
now raises `TypeError` at evaluation, because a `Body` is not subscriptable,
which is what indexing its value means.

**The index is where the mistake is made.** Indexing a `set_of` by something it
does not select used to reach `AmbiguousQueryAttribute` only once the condition
was attached. `SetOf.__getitem__` now validates the key and raises a new
`UnselectedQueryVariable`, whose suggestion lists the variables the query does
select. It rejects any key that is not a selected variable, since a row is a
`UnificationDict` keyed by exactly those.

That settles §11's open question about name strings: `query["Body"]` now fails at
the point of writing instead of reaching evaluation and dying on
`AttributeError: 'str' object has no attribute '_id_'`. Name-based selection
remains a language addition nobody has asked for yet, not a correlation fix.

`AmbiguousQueryAttribute` keeps only the case it is really about — a bare
attribute of a query that selects several variables.

**The rebuild memo key is a `Rerooting` dataclass** rather than a pair of
identifiers, `kw_only` because both fields are `UUID` and would otherwise be
silently swappable. Its docstring records why the expressions are identified
rather than held: comparing two symbolic expressions builds a `Comparator`
instead of answering whether they are the same.

Full krrood suite green (2160 passed; the two `test_object_diagram` failures are
this container missing the Graphviz `dot` binary).

## 13. 2026-08-21: the truncation flagged in section 10 is fixed, and it needed a hierarchy

Section 10 left two things for the developer: the `next(...)` truncation in
`apply_mapping_on_external_root`, and whether to make the projection/iteration
split explicit. The developer took both, so they landed together as PR #186 on
`claude/match-query-ergonomics-idk9w2`, off `main`.

**The truncation was real.** Measured on `main`, over a cabinet with two
drawers, `flat_variable(cabinet_variable.drawers).handle.name` followed from
that cabinet returned `'Handle1'` and dropped `'Handle3'`, while the method's
docstring promised every mapped value. All five callers in
`parametrization/feature_extraction` read the result as one value, so the
contract is one value and the method should say so.

**The first fix counted values per step; the split made it a property of the
chain.** That matters twice: a per-value check runs for every step of every
feature for every instance, and it answers a question about the chain at the
wrong altitude.

**Instrumenting the live code corrected the premise.** Section 12 had recorded
that `Index` straddles the single-value line. Logging which branch of
`Index._apply_mapping_` runs, across the EQL and feature-extraction suites, all
three are live: 14 literal-key, 5 row-lookup, 4 expression-key. So none could
be dropped, and the split had to accommodate the row lookup rather than assume
it away.

**The hierarchy that resulted:**

```
MappedVariable
├── Projection (abstract)     reaches exactly one value
│   ├── Attribute, Call
│   └── IndexByValue          also an Index
├── Index (abstract)          holds the key, its naming and instance-set
│   ├── IndexByValue
│   └── IndexByExpression     one value per value the key expression takes
└── FlatVariable              an iteration of its own, naming no element
```

Keeping `Index` abstract is what kept the change cheap: `query_graph`'s
`case Index()`, `navigation_path`, and #182's `isinstance(step, Index)` all
still match both kinds unchanged.

`IndexByExpression` covers the row-lookup case conservatively - a row is keyed
by the expressions it binds, so indexing it by one reaches a single value - and
that costs nothing, since a feature chain never contains one.

**Identity is the other axis, and it is the one that has type-level structure.**
A projection is determined by its child and its arguments, so two occurrences
share one node; indexing twice by one key variable therefore follows that key
together, and independence is written with a second key variable. A flattening
names no element, so the node itself is the iteration variable. `flat_variable`
already constructed directly rather than through the cache for this reason;
that is now stated, and a test guards it - making it cached broke nothing in the
suite beforehand, which is exactly the silent-tidy-up hazard.

**Deliberate consequences:** `dao.py` moved from constructing `Index` to
`IndexByValue`, since the base is now abstract; and a flattening over a
single-element collection used to return that element and now raises, because
single-valuedness is decided by the mappings a chain is built from, not by what
one instance happens to hold.

**A note on measurement discipline.** Two full-suite runs on this branch
reported a third failure, `test_ormatic/test_generation.py::test_generation_process`.
It was not a regression: both runs were ones where source files were rewritten
while pytest was collecting and executing against them. Clean runs pass from
both a populated and an empty generated file, and `main`'s baseline shows the
same two Graphviz failures. Do not edit the tree while a suite is running.

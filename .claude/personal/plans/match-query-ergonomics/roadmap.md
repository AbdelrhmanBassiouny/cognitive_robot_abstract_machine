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

## 14. 2026-08-22: the memo key needed only the root, and the reason is structural

The one review comment left open on #182 asked whether `_rerooted_chains_`, being an
instance field, needs `replaced_id` in its key at all — and said to verify it rather
than reason about it.

**Measured.** Instrumented `_reroot_on_` to record `(node, replaced, root)` per call and
ran the whole krrood suite: 27 calls over 25 distinct nodes, and **no node ever saw two
different `replaced` expressions**. (No node saw two different roots either.) So no
lookup in the suite can change by dropping `replaced_id`.

**Why it is not a coincidence of these tests.** Counting alone only says "it did not
happen here", so the probe also recorded *what* `replaced` was. In all 27 calls it was
one of exactly two things — the node's own `_chain_root_` (25) or the first step of its
`_access_path_` (2) — which are the two call sites in `_rerooted_on_selection_`. Both
are fixed properties of the node: `_get_mapped_variable_` keys its cache on the child,
so a node's ancestry, its chain root and its first step are all settled the moment the
node exists, and `_selection_indexed_by_(first_step)` then picks the same branch every
time. `replaced` therefore *cannot* vary per node.

**Done in `b9825b9e`**: `Rerooting` is gone and `_rerooted_chains_` is
`Dict[uuid.UUID, MappedVariable]`, keyed by the root's identifier, with the invariant
recorded as a note on `_reroot_on_`. The root stays the key even though it did not vary
either — it is the parameter a caller chooses, whereas `replaced` is derived from the
node. §10's two tests (`..._keeps_one_flattening_shared`,
`..._keeps_two_flattenings_independent`) are what pin the memo's behaviour and both
still pass, so no new test was warranted for a behaviour-preserving key change.

Thread replied to and resolved — this is what it asked for, unlike §9's and §10's
rounds.

**A landing-order correction to §13.** That section says #186's keeping `Index` abstract
leaves #182's `isinstance(step, Index)` matching unchanged, which is true. But #182 also
*constructs* `Index`, in `Index._rebuild_on_`
(`child._get_mapped_variable_(Index, _key_=self._key_)`), and an abstract `Index` cannot
be instantiated. So the adjustment the second-lander carries is a little wider than
either PR's description says: move `_rebuild_on_` onto `IndexByValue` /
`IndexByExpression`, exactly as #186 already does for `dao.py`. Recorded on #182's
description.

**CI position on #182.** The `experiments` ROS-service timeout recorded in §9 has
cleared. The run on `62ec184aa` was red on one job only —
`semantic_digital_twin`'s `test_multi_sim.py::test_world_sim_state_sync`, a MuJoCo
wall-clock test that sets a box's origin, sleeps 2.5s and asserts where it landed. It
reported `final_pos=[~0, ~0, 0.1499]`: the box settled at exactly the right *height* but
at x=y=0, i.e. the origin update never reached the simulator before it settled — a
state-sync race under load. `main` at this PR's exact base `90c24116` was fully green
(run 32138086038), and the diff touches no simulator, world-sync or spatial-types code,
so it is not this PR's failure and the diff was not widened for it.

**Environment note.** This session's container started with *no* project dependencies
installed at all, and Debian's patched setuptools cannot build
`antlr4-python3-runtime` (an `omegaconf` dependency). A scratch venv on Python 3.12
fixes both — 3.11 is too old, since `class_diagram.py` calls `make_dataclass(module=...)`,
which is 3.12+. Three krrood test modules need `casadi` / `semantic_digital_twin` and
were skipped; neither can reach `_reroot_on_`.

## 15. 2026-08-21/22: review rounds on #186

**Return types name what they build.** The operators that trace a mapping said
only `CanBehaveLikeAVariable[T]`, so a reader had to open the body to learn
which mapping came back. They now say `Attribute[T]`, `Index[T]`, `Call[T]`;
the arithmetic dunders say `ArithmeticOperation`; `apply_mapping_on_external_root`
says `T`; `_chain_root_` says `CanBehaveLikeAVariable`; and every
`_apply_mapping_` says `Iterable[T]`. That last one required `Index`,
`IndexByValue`, `IndexByExpression` and `Call` to become generic in `T` - they
were plain `MappedVariable` subclasses, so the value type had nowhere to come
from (`436514635`).

**The write-back was wrong for an expression key, and silently so.**
`_set_child_instance_value_` on the `Index` base did `instance[self._key_] = value`,
which stores under whatever the key holds. For `IndexByExpression` that is the
expression object rather than the value it takes: a `TypeError` on a list, and
on a `UnificationDict` a write that lands where the read will not find it, since
`__setitem__` is not overridden while `__getitem__` resolves through a cached
`_id_` map. The write moved to `IndexByValue`, the only kind whose key names
where the element is stored; `IndexByExpression` now inherits the base's
`NotImplementedError`, the same refusal `Call` and `FlatVariable` give.

**Chasing that found the other half of section 13's truncation.**
`_set_external_root_instance_value_` still walked its intermediate steps with
`next(...)`, so writing through a flattened chain set the first element
silently. It now carries the same `Projection` guard as the reader
(`b5b084522`). Section 13 fixed the reading walk and left its sibling
untouched - a reminder to look for the same shape nearby rather than only where
the symptom was reported.

**Two questions left open on the PR, deliberately:**

- Is `Projection` the right term? I argue not, in this codebase: it already
  speaks SQL, where the projection *is* the select list, and we have that
  concept as `Query._selected_variables_`. Proposed `SingleValueMapping`, with
  the caveat that the honest guarantee is *at most* one value.
- `query/match.py:661` walks an access path with
  `current_value = current_value[step._key_]` under `isinstance(step, Index)`,
  carrying the same expression-key assumption. Pre-existing, not worsened by
  the split, but now expressible - left for the developer to route.

## 16. 2026-08-22: naming, the write-back's error, and a caveat that was wrong

Five more comments on #186, all acted on, plus one correction I owed the reviewer.

**`Projection` became `SingleValueMapping`.** The developer took the proposal from §15
and later asked whether `OneToOneMapping` would fit better. It would fit worse, for the
same reason `Projection` did: the phrase is already ORM relationship vocabulary in this
repo — `create_one_to_one_relationship` and `is_many_to_one_relationship` in
`ormatic/wrapped_table.py`, `is_many_to_one_relationship` in
`class_diagrams/wrapped_field.py` — and the collision would sit next door, since
`feature_extraction/feature_extractor.py` has `_process_many_to_one` and feature
extraction is what calls the guarded method. It also overclaims: one-to-one normally
means injective, and `cabinet.container.name` is many-to-one. `SingleValueMapping`
claims only the direction relied on. Kept.

The rename went in as `1ce18ca3c` and had to be finished in `4a9eec6e5`: it renamed the
identifier but left the class docstring saying "a **projection** may still map a value to
several — indexing by a symbolic key…", which is the pre-split behaviour and the opposite
of the guarantee the class now makes. I had told the reviewer the docstring carried the
at-most-one caveat before checking that it did; posting the correction is what found it.

**`NotImplementedError` said a feature was missing without saying which.** It is now
`ReadOnlyMapping`, naming the step: *"Flatten(Cabinet.drawers).handle.name does not name
where its value is kept, so a value cannot be written through it."* Asked which mappings
those are, the base docstring now lists all five rather than leaving it to be worked out —
`Attribute` and `IndexByValue` name a place, `Call`, `IndexByExpression` and
`FlatVariable` do not.

**`Call` is what keeps the two questions apart.** Asked whether the refusal was about
read-only-ness or about one-to-many, the answer is read-only: a call reaches exactly one
value and still cannot be written through, because it computes that value rather than
reading it from somewhere. That is why the two errors stay distinct —
`MultipleValuesAlongAccessPath` is about cardinality along the walk, `ReadOnlyMapping`
about the final step having no place to write.

**The match-walk caveat was wrong, and the mistake is worth keeping.** Fixing
`AttributeMatch._update_kwargs_from` to make the same index distinction, I reported it as
a guard rather than a live fix, on the reasoning that `index_access` is only ever set from
`enumerate(value)` and so is always an integer. That is true and irrelevant: `index_access`
is not the only producer of that path. `AttributeMatch.variable` is its own field, typed

```python
variable: Union[Attribute, FlatVariable] = field(default=None, kw_only=True)
```

so a flattening there is exactly what the field declares to be valid — and the old code's
`assert_never(step)` was firing on it, saying *"Expected code to be unreachable, but got:
Flatten(Cabinet.drawers)"*. The test is `b8b9c1434`. The general shape: reachability was
argued from one call site rather than from the type, and the type was right there.

## 17. 2026-08-23: item 2 reparented onto #182, and the two interfaces it was missing

`/plan-item-resolve match-query-ergonomics match-underscore-rename-and-forwarding`, in
auto mode. The item had been sitting `in_progress` with its work done on
`claude/ide-type-inference-instances-dc6l6e` (one commit, `147d098d2`, off `main` at
`90c24116`) and no pull request, held back by the recorded blocker "must not land before
`where-query-rooted-attribute-no-filter`".

**The blocker was a landing-order constraint, not an unsolved problem, so stacking
discharges it.** #182 is open, out of draft and ready
(`check_dependency_readiness.py`: `open_ready`, `is_ready: true`), which in this repo's
workflow is what a branch stacks on. The work moved onto this session's designated branch
`claude/match-query-interface-refactor-l55jym`, which starts from #182's head with
`147d098d2` cherry-picked on top, and its pull request #192 is based on #182's branch.
One conflict, in `core/mapped_variable.py`'s `__dir__`: #182 had reflowed the same lines
the item replaces with a call to its extracted `attribute_names_for_completion`; resolved
in favour of the extraction. `test/krrood_test/test_eql` is green on the result (1197
passed, 3 skipped), which is the reparenting verified rather than assumed.

**Why the branch changed.** The item's own branch was an IDE-typing session's branch that
happened to carry this item's work (§7); it was never this session's to push to, and its
name says nothing about the item. The manifest now records the designated branch.

**The developer's two additions to the item's scope**, taken as direction rather than as a
question:

1. Reparent onto the pull requests the work needs, done as above.
2. *"See if we can make a common parent between Match and Query that segregates the
   interface that they both have, like `where()`, `limit()`, ... and also with
   `CanBehaveLikeAVariable`."*

**The second one is not cosmetic — the forwarding this item introduces has a hole the
common parent closes.** `Match.__getattr__` forwards with `getattr(self.expression, name)`,
so the *whole public namespace of `Query`* stands between a match and its matched class:
`match.limit` returns `Query.limit` bound to the lowered query, and a matched class with a
field named `limit`, `distinct`, `having`, `evaluate`, `build` or `tolist` gets that method
instead of a symbolic attribute. That is the same shadowing §2 diagnoses as the item's root
cause, moved one level down and made silent. Forwarding to the lowered query's *attribute
construction* rather than to its namespace removes it, and that hook is exactly the
interface `Match` and `CanBehaveLikeAVariable` share.

The plan, settled before implementing:

- **`HasSymbolicAttributes`** (`core/mapped_variable.py`) — what a thing that stands for a
  value of type `T` and offers that type's attributes symbolically must provide: `_type_`,
  and `_get_symbolic_attribute_(name)`. It owns the `__getattr__` guards (dunders raise
  `SymbolicDunderAccessError`, other underscore names are genuine `AttributeError`s) and
  `__dir__`, both of which `CanBehaveLikeAVariable` and `Match` currently duplicate.
  `CanBehaveLikeAVariable` builds an `Attribute` on itself; `Match` asks its lowered query
  for the same thing, so no `Query` member can be reached by attribute access on a match.
- **`HasQueryModifiers`** (`query/query_modifiers.py`) — the fluent verbs both types offer:
  `where`, `having`, `ordered_by`, `distinct`, `grouped_by`, `limit`. `Query` already
  implements all six; `Match` implemented only `where` and lost the rest to the accidental
  delegation above, so it gains the other five as forwarders that return the match, keeping
  a chain on the match rather than silently switching to the lowered query. Kept separate
  from `Evaluable` rather than folded into it: a thing can be evaluable without being
  narrowable, and both classes already inherit `Evaluable` directly.
- **The §7 deviation is reconciled the way §4 decided**, not the way the branch did:
  `variable` and `matches_with_variables` come back as public read-only compatibility
  properties (like `expression`, which the branch did keep), so the in-flight D-core stack's
  `test_underspecified_match.py` — live on four open pull requests, #67/#68/#98/#159 — keeps
  working. Item 3 removes them with the rest of the detours.
- **The §6 guard test is added**: after forwarding exists, a missed rename fails silently
  (the miss becomes a symbolic attribute named e.g. `"conditions"` — truthy, chainable,
  wrong), so the old public names are pinned as forwarding to the matched class rather than
  returning match internals.
- **The blocker's own repro becomes a test**: `match.where(match.<attribute> >= x)` filters,
  which is what §7 measured as broken on the item's branch and is only true stacked on #182.

Not taken into this item: #186 (`chain-outside-evaluation-truncates-silently`) is not a
parent. It is independent of this item, and the one file both touch,
`core/mapped_variable.py`, they touch for unrelated reasons — this item extracts one
completion helper, #186 splits the mapping hierarchy. The landing-order adjustment §14
records stays between #182 and #186.

**Outcome, same day.** All of the above landed on #192 in two commits: the cherry-picked
`147d098d2` (as `e6cbfa5d`), then `f9501c70` for the two interfaces, the compatibility
properties and the tests. Three things the implementation settled that the plan above did
not:

- **The name policy could not be unified, and the attempt found a bug.** The first
  version put both guards - dunders and other underscore names - in
  `HasSymbolicAttributes`, making a variable reject `variable._missing_` the way a match
  already did. That is a language-wide semantic change, and the suite showed why it is
  not this item's to make: `verbalization/grammar/query/assembler.py:285` reads
  `expression._chain_expression_` on an `Aggregator`, which has no such attribute, so
  under the lax policy it silently becomes a symbolic attribute of the aggregator itself.
  Measured on this branch: `_expression_signature` returns
  `('Sum', None, (('_chain_expression_', None),))` for *every* `Sum`, so `_is_order_key`
  treats any two aggregates of one kind as the same column - seven ranking tests only
  passed because both sides of the comparison were equally wrong. A second test,
  `test_backends.py::test_underspecified_parameters_with_full_symbolic_expression`,
  pins the `TypeError` that unpacking such a bogus attribute raises, so the strict policy
  changed a pinned exception type too. Both are pre-existing and neither is this item's,
  so the policy became `_is_own_name_`, stated per class: a match claims every
  underscore-prefixed name, a variable claims none, since the value type may define any
  of them. The assembler bug is reported on #181 for the developer to route.
- **The modifiers return the match, not the instance-mimicking union.** The interface
  declares `Union[T, Self]`, which is the loosest statement true of both implementations
  (`Query.distinct` and `Query.grouped_by` already returned it). Match narrows to `Self`,
  because the mypy fixture pins `scoped.where(...)` as `Match[Robot]` and widening it
  there would lose the chaining the item's static half exists to give. The fixture now
  also pins `ordered_by` and `limit`.
- **`Match.where` no longer builds the lowered query eagerly.** `build` is idempotent and
  every evaluation path calls it, so the five new modifiers would each have had to repeat
  it for no gain. Full suite green without it.

Verification: `test/krrood_test` 2079 passed, 6 skipped, excluding `test_rustworkx_utils`
and `test_ripple_down_rules/test_object_diagram.py` - 24 failures from this container
missing the Graphviz `dot` binary and `flask`, confirmed identical with the diff stashed.

Left for item 3, and now visible where it was not before: `coraplex`'s
`training_environment.py:210` and `experiments`' `reliability.py:108` reach through
`.expression` only to call `limit`, which is now a method on the match itself.
`update_fields` and `create_or_update_variable` are still public names on `Match` that
the underscore convention would cover; they are machinery rather than fluent verbs, so
they are deliberately left to whichever pass removes the detours.

## 18. 2026-08-23: the forwarding was one operation wide, and the developer said so

Reviewing section 17's result, the developer raised two things, both right.

**First: `Match.__call__` collides with a callable matched class**, and the collision had
no stated resolution. **Second: only attribute access was forwarded**, where a
`CanBehaveLikeAVariable` offers twenty-five operations - indexing, calling, the six
comparisons, arithmetic, negation.

**Why it happened, since the reason matters more than the gap.** Section 17 extracted the
shape of *the code that existed* - the inherited commit forwarded `__getattr__` and
nothing else - rather than asking what the protocol is. Worse, it named the result
`HasSymbolicAttributes` and wrote its docstring as though attributes were the whole
story, baking the incompleteness into the abstraction's own name, where the next reader
would have read it as complete.

**Measured before deciding.** On the branch, `match[0]`, `match + 1`, `match > 1`,
`-match` and `iter(match)` all raised `TypeError`; `match == robot` returned the plain
`bool` `False`, from `AbstractMatchExpression`'s identity comparison, which reaches the
query as a `Literal` and dies in `LiteralConditionError` - a loud error a long way from
the mistake, and the only one of the set that was silent at the point of writing.

**The operations are now written once.** Every one of them is `<Constructor>(self, ...)`
or `self._get_mapped_variable_(<Type>, ...)`; the *only* thing that differs between a
variable and a match is which expression is the operand. So `CanBehaveLikeAValue` holds
all of them, each built on the one expression an implementation reports as
`_symbolic_expression_` - a variable reports itself, a match reports its lowered query.
`CanBehaveLikeAVariable` keeps the mapped-variable cache and loses the operator bodies;
no behaviour of a variable changes. This is what the developer's "common parent, also
with `CanBehaveLikeAVariable`" asks for, and it costs one hook instead of twenty-five
forwarders.

`__iter__ = None` moves up with the rest, and is now load-bearing for the match too:
`__getitem__` would otherwise hand Python its legacy sequence protocol, iterating a match
endlessly since every index is a valid expression - the trap section 10 recorded for
variables.

**The parentheses rule is the developer's, and it is better than what this session
argued for.** The proposal: the first parentheses after `a(Type)` state the pattern, the
next call the instance - `a(Adder)(offset=1)(2)`, and `a(Adder)()(2)` where the pattern
is empty. The objection this session had raised - that the same syntax means different
things depending on hidden state - is answered by a check: a matched class whose
instances are *not* callable has nothing a second call could mean, so it keeps raising
`CalledMatchMultipleTimes` / `CalledMatchAfterResolution` exactly as before. The new
meaning exists only where the class defines `__call__`, so no existing behaviour changes
at all, and the guard survives where it has value. Positional arguments where the pattern
is stated now raise `PositionalArgumentsInMatchPattern` rather than Python's
argument-count error, since that is where the rule is most likely to be met.

**Two gaps had to close for the new operations to mean anything.** Both were found by
writing the tests, not by reading:

- *A condition comparing the match itself did not filter.* `where(match == robot)`
  returned every row - section 3's bug, in the shape #182 had not covered: #182 re-roots
  attribute *chains* taken from a query, and a bare query operand is not a chain, so the
  walk treated it as a nested subquery scope. It is the same rule one step more general,
  so it went in the same place: a query standing as a value in its own condition is
  replaced by the variable it selects, and one selecting several raises the new
  `AmbiguousQuerySubject`. Shipping symbolic comparison without this would have replaced
  a loud error with a silent wrong answer, which is the trade this plan exists to undo.
- *Calling a callable instance raised `KeyError('return')`.* `Call._update_type_` read
  the return hint off the called type itself, which for an instance carries none - the
  hint is on its `__call__`. Pre-existing and not match-specific:
  `variable(Adder, ...)(10)` failed identically on `main`. It now reads `__call__`'s hints
  in that case, and leaves the type unknown rather than raising when the callable is
  unannotated.

**A test caught the very hazard this item is about, on this session.** An assertion
written as `doubled._operands_[0] is match.expression` failed, and the reason was not the
code: `ArithmeticOperation` has no `_operands_`, so the lax name policy turned it into a
symbolic attribute of the operation, and the test was asserting on `Index(Attribute(op,
'_operands_'), 0)`. The real field is `left`. This is the assembler bug of section 17 in
miniature, in a test written the same day by the session that had just documented it.

Verification: `test/krrood_test` 2087 passed, 6 skipped, excluding the Graphviz- and
flask-dependent modules that fail identically with the diff stashed.
`krrood/doc/eql/user/match.md` gains a short section on the instance-like surface and the
parentheses rule; the wholesale docs migration stays item 3's.

## 19. 2026-08-23: naming the two halves, and the operand direction nobody had tried

Two questions from the developer, one about structure and one the structure had hidden.

**"Should the cache move up, and should `CanBehaveLikeAVariable` stop inheriting
`Selectable`?"** No to both, for reasons that are mechanical rather than aesthetic. The
cache does not memoize an answer - `_get_mapped_variable_` *constructs* mappings whose
child is the caching object, and `MappedVariable` is a `UnaryExpression` whose `_child_`
must be a `SymbolicExpression`, which a match is not. A second cache on the match would
also make `match.x` and `match.expression.x` two different nodes, which is exactly the
identity #182's sharing tests and `_reroot_on_`'s memo depend on. And dropping
`Selectable` from the bases would replace a declared dependency with an assumed one: the
mappings this class builds read `_child_._type_` and `._var_`, both `Selectable`'s, so a
future subclass that inherited it alone would break at runtime rather than at class
creation. `Selectable` has one other subclass in the whole repository (`CaseWhen`), so
the orthogonal mixin it would become has no second customer.

**But the names were wrong, and the developer was right to press.** `CanBehaveLikeAValue`
and `CanBehaveLikeAVariable` differ by one word whose distinction is not in this
language's vocabulary - nothing in the pair says which one holds the cache, or why a
match implements one and not the other, which is the AGENTS rule about a name whose
meaning has to be looked up elsewhere. They are not two flavours of one thing:

- `HasSymbolicOperations` - *what can be written*: every operation builds an expression
  instead of computing an answer. Implemented by anything standing for a value, including
  something outside the expression graph, which is the whole reason it exists.
- `CanBehaveLikeAVariable` - *what it is written on*: the expression that reports itself,
  holding the mappings taken from it.

The new class was twelve references old, all from this PR, so the rename was free; the
established one means the node in all eighty-three of its references and keeps its name.
`doc/eql/developer/variable_system.md` described the dunder capture under the old name
and now describes both halves.

**The asymmetry the rename discussion surfaced.** Asked whether a match can be selected,
compared or given to a predicate, the answer was measured rather than argued, and one
case was silent:

| written | before |
| --- | --- |
| `match == robot`, `match.x >= 5` | correct (section 18) |
| `variable == match` | **passed every row** - the match reached the comparator as a `Literal` |
| `entity(match)` / `set_of(match, ...)` | `KeyError(<uuid>)` at evaluation |
| `the(match)` / `an(match)` | `assert_never` |
| `HasType(match, ...)` | `LiteralConditionError` |

So the instance-likeness was one-directional: operations *on* a match worked, a match
*as an operand* did not. Everything downstream accepts a `SymbolicExpression`, and a
match is not one.

One place reads a value as a child expression - `SymbolicExpression._update_children_`,
which wrapped every non-expression in a `Literal` - so the rule is stated there as
`_as_operand_`: a value that stands for an expression contributes it, and only a value
standing for nothing symbolic is a literal. `variable == match` now filters correctly.
`InstantiatedVariable`'s kwargs walk was the second copy of the same wrapping and now
calls the same rule.

**What is deliberately still refused.** A match given to a predicate keeps raising as it
did, because the fix there is not the coercion: measured on this branch,
`HasType(entity(variable), Handle)` - a plain query, no match involved - returns *every*
row, since the argument is evaluated as an uncorrelated subquery. That is section 3's
family, wave 1's territory, and making a match reach it quietly would trade a loud error
for a silent wrong answer. Selecting a match (`entity(match)`, `the(match)`) stays item
3's, which is the item that teaches the factories to unwrap one.

## 20. 2026-08-23: two findings became items, because a note is not a queue entry

The developer's correction: recording something in an item's `notes` or a pull request
description does not make it happen - only a plan item or a blocker does. Section 19 left
two measured findings as prose, so both are now items.

**`aggregate-signature-reads-a-missing-attribute` (this plan, `mapping-semantics`).** The
assembler bug section 17 found and section 18 re-measured: `assembler.py:285` reads
`_chain_expression_` on an `Aggregator`, which does not define it, so under the name
policy a variable keeps (it claims no underscore-prefixed name) the read becomes a
symbolic attribute of the aggregator, and every `Sum` gets the signature
`('Sum', None, (('_chain_expression_', None),))`. It is tracked here rather than in
`eql-verbalization`, whose single track is the framework migration, on the precedent of
`chain-outside-evaluation-truncates-silently`: a pre-existing bug found while doing this
plan's work, independent of every item here, kept in the plan whose refactor exposed it.

**`argument-position-correlation` (`eql-existential-semantics`, `binding-order` track,
depends on `binding-order-planner`).** A query given as an *argument* is evaluated
uncorrelated with no quantifier involved. It is an item rather than a third repro on
`binding-order-planner` because it is genuinely unknown whether binding the outer relation
first also correlates an argument that is itself a query - so the item's first job is to
re-measure once that lands and close as already-fixed if it is. That is a checkable unit of
work; a bullet in someone else's test list is not.

Neither blocks #192, which refuses both cases loudly rather than shipping a silent wrong
answer. `factories-unwrap-match-and-migrate` already owns the third finding (selecting a
match) and needed no new item, only the measurement section 19 added to it.

## 21. 2026-08-24: the aggregate signature, and the second read one line below it

`/plan-item-kickoff match-query-ergonomics aggregate-signature-reads-a-missing-attribute`,
in auto mode. Branch `claude/plan-item-kickoff-match-query-npzr78`, PR #196 (draft, `bug`),
off `main` at `2b44f1e5`. `depends_on` is empty and the scope check
(`check_scope_overlap.py`, base `origin/main`) reports no path shared with #182 or #192, so
the item is independent exactly as section 20 recorded.

**Re-measured on today's `main`, not taken on trust.** Two `Sum`s over different chains:

```
sum(statement.revenue.money.amount)  ->  ('Sum', None, (('_chain_expression_', None),))
sum(statement.revenue.money.tax)     ->  ('Sum', None, (('_chain_expression_', None),))
```

and the user-visible consequence, which section 20 named but nobody had written down:

```
For the Statement with the highest sum of the amount of money of its revenue,
report the month of its period, the sum, and the sum of the tax of money of its revenue
```

The query is ordered by the *tax* sum. The ranking frame names the *amount* sum, and the
body reduces that one to "the sum" while spelling the ranked one out — the two are exactly
swapped, because `_ranked_aggregate_column` returns the first selected aggregate whose
signature "matches" and every `Sum` matches every other.

**Why the seven ranking tests never caught it.** Each of them either ranks by the only
aggregate selected, or — `test_ranked_report_reduces_only_the_ranked_aggregate` — by an
aggregate of a *different kind*, where `kind` alone separates the signatures. So the
failing case needs two aggregates of one kind, which no test had.

**The fix is the field the class defines.** `Aggregator` is a `UnaryExpression`; the
aggregated expression is its `_child_`, which is what `_source_root_` and
`_leaf_attribute_` already read. One word.

**A second read of the same shape, one line below, deliberately not fixed here.** The path
is built as `(step._attribute_name_, step._owner_class_)` for every step, and both names
belong to `Attribute` alone — so an `Index`, `Call` or `FlatVariable` step takes the same
silent-symbolic read. Measured on `main`:

```
order.lines[0].price  and  order.lines[1].price   ->  equal signatures
```

It is the same root cause, but not the same fix. No existing name is a sound structural key
for a step: `_name_` is a display name and `Call._name_` drops the call's arguments
entirely, so a faithful key needs each mapping subclass to report its own constructor
arguments — the shape #182 is reintroducing as `_rebuild_on_` and #186 landed as the
hierarchy. That is core API in `mapped_variable.py`, which #182 is rewriting right now, and
adding it would both widen a focused bug-fix PR past one root cause and collide with an
in-flight branch. Per section 20's own rule, it is an item rather than a paragraph:
`chain-signature-reads-attribute-only-names`, `mapping-semantics`, blocked on #182 landing.
`get_clean_name_from_mapped_variable` already guards the identical read with
`isinstance(step, Attribute)`, so the guard is established in this codebase, not invented.

The consequence to be honest about: this PR routes aggregates through that path walk for
the first time, so `sum(o.lines[0].price)` and `sum(o.lines[1].price)` still collide after
it. That is not a regression — it is the pre-existing defect the new item owns — but it is
why this PR's fix is necessary and not sufficient.

**A plan-state correction found on the way.** #186
(`chain-outside-evaluation-truncates-silently`) merged on 2026-08-24 while the manifest
still read `in_progress`; its status is corrected to `done` in the same save.

## 22. 2026-08-24: the stall was upstream, and it was one word

`/plan-item-resolve match-query-ergonomics where-query-rooted-attribute-no-filter`, in
auto mode. Nothing on the fork said the item was stuck: #182 is open, out of draft, all
six of its review threads resolved, and all 23 checks green on `15f31d1e`. The block was
on the upstream pull request, cram2#563, which none of the fork-side calls can see.

**What the upstream review says.** LucaKro approved; **tomsch420 requested changes**
(2026-08-24T11:20:29Z) with one unresolved thread, on
`query.py:297`:

> is correlate the correct wording? To me correlate is statistics, but what you do seems
> to me as moving related conditions where they belong.

and the developer's own reply on that thread: *"yeah true, the name is misleading"*. So the
change requested is a rename, and it was already agreed before this session started.

**The name the code already had.** `correlate` is SQL's word for the *subquery* semantics
this fix works against, not for what the fix does, so it named the problem rather than the
operation - which is why it reads as misleading. Everything else this PR wrote already
speaks one plain word for the operation: `MappedVariable._reroot_on_`,
`_rerooted_chains_`, `Query._rerooted_on_selection_`, both docstrings ("Re-root the
attribute chains ..."), and the PR description. The two methods were the only readers left
using a second word for it, so `_correlate_conditions_` / `_correlate_condition_` become
`_reroot_conditions_` / `_reroot_condition_` and the module says one thing once.
`query.py:111`'s "uncorrelated subquery" stays: it is pre-existing on `main`, and there the
SQL term is the accurate one, naming the subquery semantics rather than this operation.

The one other place the word had spread was the test file's section header, "conditions
that must keep their uncorrelated meaning", now "conditions that must keep their subquery
meaning" - which is what its one test is already named after
(`test_condition_rooted_at_another_query_stays_a_subquery`).

No behaviour changes: both methods are private to `Query` and a repository-wide search
finds no reader of either old name left, docs included.

Verification: `test/krrood_test/test_eql` 1191 passed, 3 skipped.

**Environment note, extending section 14's.** The container again started with no project
dependencies. A Python 3.12 venv with `krrood`, `probabilistic_model`,
`semantic_digital_twin` and `giskardpy` installed editable, plus `objgraph`, `mujoco`,
`giskardpy_bullet_bindings` and `mypy`, is what `test/conftest.py` needs before any krrood
test can be collected at all. Also worth knowing: running the verbalization tests rewrites
`test_verbalization/verbalization_results.py`, so check `git status` before committing -
that edit is the suite's, not yours.

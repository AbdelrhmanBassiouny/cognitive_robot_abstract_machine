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

**And the landing-order hazard came due in the same session.** After the rename was
pushed, #182 read `mergeable_state: dirty` and carried the `needs-resolution` label a
maintenance pass had added: #186 merged to `main` earlier that day, which is the second
half of the constraint sections 13 and 14 recorded. So this branch is the second lander,
and it carries the adjustment both PRs' descriptions name.

Two conflicts, both exactly as predicted:

- `core/mapped_variable.py`: `Index` is now abstract, and this branch's
  `Index._rebuild_on_` constructed it directly. The abstract base keeps neither the
  pre-split `_apply_mapping_` nor a constructor of itself; `_rebuild_on_` moved onto
  `IndexByValue` and `IndexByExpression`, each naming its own class - the same shape
  `Attribute._rebuild_on_` has, and the same change #186 already made for `dao.py`.
  Writing it once on the base as `type(self)` would have been shorter and wrong for the
  reason the hook exists (sections 8 and 10): a new mapping type must not be able to
  inherit a rebuild it never wrote.
- `exceptions.py`: additive only - both sides appended new exception classes at the same
  point. All four are kept (`AmbiguousQueryAttribute`, `UnselectedQueryVariable` from
  here; `MultipleValuesAlongAccessPath`, `ReadOnlyMapping` from #186).

`query.py`'s `isinstance(step, Index)` needed nothing, as section 13 said. Verification
after the merge: `test/krrood_test/test_eql` 1202 passed, 3 skipped - the count rises
because #186's own tests arrive with it.

The `needs-resolution` label is left in place: the stack tooling clears it itself once
the branch merges cleanly again, and hand-clearing it would be managing a signal that is
not this session's.

## 23. 2026-08-30: #192's parent had landed and nothing had noticed

The stacked-pr-maintenance pass of 2026-08-30, run from PR #198's tooling rather than
main's, reported #192 as needing a reparent: its base
`claude/match-query-ergonomics-where-rooted-b876wm` (#182, `where-query-rooted-attribute-no-filter`)
merged upstream on 2026-08-24 and #192 had been sitting on it since.

**Why no earlier pass saw it.** `load_stack()` on main fetches only the *head* branches of
the open pull requests on the board, so a parent that is no longer an open pull request is
never fetched; `is_merged` then runs `git merge-base --is-ancestor` through a helper that
cannot tell exit 128 (the ref does not exist) from exit 1 (not an ancestor), and answers
"has not landed". That is `workflow-unification`'s `unfetched-parent-branches` (PR #198),
still unlanded. Two of this repository's plans were losing reparents to it silently; the
other was `rdr-refactor`'s #64.

**What was done.** #192 is retargeted at `main`. GitHub stack 195 held it together with the
merged #182, and a stack member's base cannot be changed, so the stack was dissolved first
(its membership recorded beforehand); it could not be re-created afterwards because a stack
needs at least two members and #192 was the only open one left. #192 is now a plain pull
request based on `main`.

It is still `needs-resolution`: it conflicted against its old base before this pass and
conflicts against `main` after it, and the maintenance pass never resolves a conflict on
somebody else's branch. The item's blocker was rewritten to name the new base, since the
one it carried described a parent that no longer exists.

## 24. 2026-09-01: self-review on #196 — the reduction is correct by identity, but ambiguous to a reader

`/plan-item-resolve match-query-ergonomics aggregate-signature-reads-a-missing-attribute`.
The item had no live blocker — PR #196 is green, out of draft's CI, `mergeable_state:
clean` — but carried one unresolved review thread, left by the developer on
`test_set_of_ranking.py:337`, the closing line of
`test_ranking_names_the_ordered_by_aggregate_not_the_first_selected`: the current assert
ends `"...the sum of the amount of its net, and the sum"`, and the comment's body is the
string `", and the sum of the amount of its tax."` — proposing the trailing mention be
spelled out in full instead of reduced.

**Measured before replying, not assumed.** Built an isolated Python 3.12 venv (`pip
install -e krrood -e random_events -e probabilistic_model`, running the test file with
`--confcutdir` to skip the workspace-wide root `conftest.py`, which needs packages this
plan does not touch): all 17 tests in the file pass as written, this one included. The
reduction is correct by the mechanism that produces it — `AggregatorRule.build`
(`verbalization/grammar/aggregation/rules.py`) keys the coreference on object identity
(`referent_id=node._id_`), and in this test `tax` is the literal same object in both
`.ordered_by(tax, ...)` and the selection, so the trailing bare "the sum" resolves back to
the frame's first, full mention of `tax` — exactly what `_highest_aggregate_modifier`'s
docstring documents.

**The comment is still onto something, just not a code bug.** To a reader, "the sum of the
amount of its net, and the sum" reads as though the trailing "the sum" refers to the
noun phrase right before it (net) — proximity is how anaphora normally resolves in
English, and the true antecedent (tax) is three clauses back, named only in the opening
superlative frame. That ambiguity is latent in `AggregatorRule.build`'s identity-only
reduction and only becomes visible once two aggregates of *one kind* are both selected —
precisely the case #196 adds coverage for. Fixing it needs the reduction to know when an
identity match is one of several same-kind aggregates in scope and spell it out in full in
that case, which is a second root cause layered on the one #196 closes, not a one-line
change to it.

**Left open rather than guessed at.** Replied on the thread
(https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/196#discussion_r3908782904)
with the measurement above and asked whether the developer wants the assert changed in
this PR anyway, or the ambiguity carved into its own `mapping-semantics` item the way
`chain-signature-reads-attribute-only-names` was carved out of this same PR's own
description. Per the personal-notes review-comment convention, the thread stays
unresolved until that answer lands — resolving it now would claim work not yet done or
agreed to. No plan.yaml status change: PR #196 is otherwise unblocked, so `in_progress`
still describes it accurately.

## 25. 2026-09-01: the steps of a chain now say what they are

`/plan-item-resolve match-query-ergonomics chain-signature-reads-attribute-only-names`, in
auto mode. Branch `claude/match-query-ergonomics-chain-tozhhq`, PR #248 (draft, `bug`), off
`main` at `2318e206`.

**The blocker was discharged rather than solved.** The item recorded "needs #182's
per-subclass `_rebuild_on_` to have landed"; #182 merged on 2026-08-24, so the hook and
#186's mapping hierarchy are both on `main` and the dependency check reports
`merged` / `is_ready: true`. Nothing else was blocking it - the item had simply not been
looked at since section 21 wrote the blocker.

**Re-measured on today's `main` before changing anything**, and the mechanism is worse
than "the names do not exist":

```
order.lines[0].price -> ('', <root>, (('lines', Order), (Order.lines[0]._attribute_name_, …), ('price', Line)))
order.lines[1].price -> ('', <root>, (('lines', Order), (Order.lines[1]._attribute_name_, …), ('price', Line)))
equal: True
```

The two printed paths *differ* and still compare equal, because the reads on the index step
produce symbolic attributes and comparing two of those builds a `Comparator`, which is
truthy. So the signature was not merely coarse; it answered a question it had never
evaluated.

**Each kind of mapping now states its own `_structural_key_`** - its kind together with the
arguments it was written with - abstract on `MappedVariable` for the reason section 22 gave
for `_rebuild_on_`: a mapping added later must not be able to inherit a key that says
nothing about what distinguishes it. `Attribute` states its name and owning class,
`IndexByValue` its key, `IndexByExpression` the identifier of its key expression, `Call` its
arguments, and `FlatVariable` its own identity - the identity axis section 13 established,
since a flattening names no element and each one written ranges over the elements on its
own. Expression-valued arguments are identified rather than held, the same rule
`_rerooted_chains_` already records for its memo key.

**A test that could not fail first, and why that is the plan's own subject.** The core
tests written against `_structural_key_` *passed* before the property existed: the missing
name became a symbolic attribute and `== <tuple>` built a truthy `Comparator`. Only the
four assembler-level tests failed on `main`, so those are what pinned the bug first. This
is section 18's hazard again, met while fixing the very read that causes it.

**What this pull request cannot show, stated rather than papered over.**
`_expression_signature` is reachable only through `_is_order_key`, whose caller requires an
`Aggregator` order key, and on `main` every aggregate's chain is still the bogus
`_chain_expression_` read #196 fixes. So `sum(o.lines[0].price)` vs `sum(o.lines[1].price)`
becomes separable only once both land: #248 closes the chain half, #196 the aggregate half.
Not stacked on #196 either, since it is a draft, which is not what this workflow stacks on;
the two touch adjacent lines of one method, so whichever lands second resolves that hunk.

Verification: `test/krrood_test/test_eql` 1276 passed, 3 skipped.

## 26. 2026-09-01: #192's conflict was the landing order, one branch late

`/plan-item-resolve match-query-ergonomics match-underscore-rename-and-forwarding`, in
auto mode. The item had been `blocked` since 2026-08-28 on a conflict that six identical
stacked-pr-maintenance comments reported and nobody diagnosed.

**Nothing else was stalling it, and that is worth stating because the blocker did not.**
#192 has *no* review threads at all (`get_review_comments` returns `totalCount 0`); it
carries no `in-review` label and was never promoted, so unlike section 22's stall there is
no upstream pull request whose review could be the cause; its dependency
`where-query-rooted-attribute-no-filter` is merged and `is_ready: true`; and its last CI
run was all 23 checks green — but on `e9aae10be` of 2026-08-24, against a base nine days
stale, which says nothing about the merged result. The conflict was the whole of it.

**The cause is the constraint sections 13, 14 and 22 all wrote down, reaching one branch
further than any of them said.** #192's merge base with `main` is `15f31d1e4` — #182's
branch *before* #182 merged `main` to take #186's `Index` split (section 22). So #192 was
cut from a parent that had not yet absorbed #186, and carried none of the mapping
hierarchy (`SingleValueMapping`, `IndexByValue`, `IndexByExpression`) while rewriting the
same `mapped_variable.py` into `HasSymbolicOperations` / `CanBehaveLikeAVariable`. Section
14 recorded that "whichever lands second moves `_rebuild_on_` onto the concrete
subclasses"; what it did not anticipate is that a *third* branch, stacked on the first,
inherits the same adjustment a second time. `main` had also taken 199 commits since, three
of them squarely in the conflicting files: `3b4fb1477` (narrow `Index._type_` to a
`List[X]` element type), `24664a748` (move `number_like_field` off
`CanBehaveLikeAVariable` onto `Attribute`) and `bc8785b70`, plus the `do()` operator work
in `match.py`.

**All three conflicts resolved by taking both sides, because neither pair actually
disagreed.**

- `core/mapped_variable.py`: `HasSymbolicOperations.__getattr__`, `__getitem__` and
  `__call__` keep this item's routing through `_symbolic_expression_` — the whole point,
  since a match must *build* the operation on its lowered query rather than read it off
  that query's namespace — and take `main`'s `Attribute[T]` / `Index[T]` / `Call[T]`
  return types and the `IndexByValue` / `IndexByExpression` split. Where an operator lives
  is orthogonal to what it is declared to build, so both sides' intent survives intact.
- `query/match.py`: `has_cause_attributes` and `causes()` arrive from `main`'s `do()`
  operator and now read `_matches_with_variables_` rather than the public compatibility
  property, since section 17 migrated every krrood-internal consumer;
  `AttributeMatch.assigned_variable` keeps `main`'s fresh-copy branch for a shared
  `Cause`/`Confounder` beside this item's `_variable_` / `_type_` names; and
  `_update_kwargs_from` takes `main`'s `IndexByValue` distinction, which is the section-16
  fix that replaced its `assert_never` with `ReadOnlyMapping`.
- `test_eql/test_match.py`: both sides' tests kept, `main`'s `ReadOnlyMapping` test
  rewritten against the renamed `AttributeMatch` fields.

**One pin moved, and the roadmap is what decided it.** The merged `__getattr__` failed the
mypy fixture, which asserted `a(Robot).battery` as `CanBehaveLikeAVariable[Robot]` — the
pre-#186 type. Two readings were available: revert to the wider type to keep the test
untouched, or narrow the assertion to what `main` landed. Sections 15 and 16 settle it:
"return types name what they build" is this plan's own established convention, taken by
the developer on #186, so reverting it would have been this branch quietly undoing a
landed improvement. The fixture now asserts `Attribute[Robot]`. What the fixture exists to
pin — that the overloads return `Union[T, Match[T]]` and that attribute access stays
symbolic — is unchanged; only its precision moved, and upward.

**Two findings routed to item 3 rather than fixed here**, per section 20's rule that a
note is not a queue entry. `exceptions.py`'s two new `causes_effect` suggestion strings
teach `match.variable.status` — `main`'s `do()` operator added `.variable` detour text
*after* this plan set out to remove it. The spelling still works through the compatibility
property, and rewriting user-facing detour text is `factories-unwrap-match-and-migrate`'s
scope. `has_cause_attributes` likewise joins `update_fields` and
`create_or_update_variable` as a public machinery name on `Match` the underscore
convention would cover, left to the same pass.

**A stale-save revert, caught mid-run.** The blockers written at the start of this run were
overwritten by a concurrent session saving a manifest copy loaded before that write, and
the re-fetch before the second save is the only reason it was noticed. This is the third
occurrence on record; the recheck-before-save rule earns its keep.

Verification: `test/krrood_test/test_eql` 1287 passed, 3 skipped (up from section 22's
1202, `main`'s own new tests arriving with it). Full `test/krrood_test`: 2269 passed, 5
skipped; the two `test_ripple_down_rules/test_object_diagram.py` failures are this
container having no Graphviz `dot` binary, confirmed by `which dot` finding none.

**Environment note, extending sections 14 and 22.** The container again started with no
project dependencies. A Python 3.12 venv (3.11 is still too old) with `krrood`,
`probabilistic_model`, `random_events`, `giskardpy`, `physics_simulators` and
`semantic_digital_twin` installed editable, plus `objgraph` and `mypy`, is the full set
`test/conftest.py` and the typing fixture need. `semantic_digital_twin` must be installed
in the same `pip install` as `giskardpy` and `physics_simulators`, since it declares them
as requirements and pip cannot resolve them from an index.

## 27. 2026-09-02: a third interface on the same class statement

`/plan-item-resolve match-query-ergonomics match-underscore-rename-and-forwarding`, in
auto mode. One day after section 26 merged `main` into #192, the branch was conflicted
again and carrying `needs-resolution` for the seventh time.

**The whole of the stall was one class statement.** `main` took cram2#575 (probabilistic
queries) on 2026-09-01, whose `HasExpression` mixin adds a base to `class Match(...)` -
the very statement this item rewrites with `HasQueryModifiers` and
`HasSymbolicOperations`. Of the 1,518 lines that arrived with #575, that line is the only
conflict; `backends.py`, `base_expressions.py`, `exceptions.py`, `factories.py` and
`parameterizer.py` all merged cleanly.

Everything else was checked before touching it, since the previous section's lesson is
that a blocker which does not name its cause is what keeps an item still: #192 has no
review threads (`get_review_comments` returns `totalCount 0`), carries no `in-review`
label and was never promoted, so there is no upstream review to read; its dependency
`where-query-rooted-attribute-no-filter` is merged and `is_ready: true`; and all 23
checks were green on its head `ff5414e0`.

**Both sides kept, because `Match` owes both answers.** `HasSymbolicOperations` and
`HasQueryModifiers` say what can be *written on* a match; `HasExpression` says what a
match *resolves to* for a caller that only wants the expression to scan or build - which
is how #575's verbalization and parametrization steps reach a match, a
`ProbabilisticQuery` and a plain expression through one call instead of an `isinstance`
chain. `Match._get_expression_` arrived from `main` returning the lowered query, which is
the same object `_symbolic_expression_` reports.

**Nothing else needed adjusting, and that was measured rather than assumed.** #575's new
code reads a match only through `expression`, which this branch keeps as a public
compatibility property - so section 6's silent-miss hazard (a missed rename becomes a
truthy symbolic attribute rather than an `AttributeError`) had nothing to catch here. The
sweep also found no new reader of the fields this item renamed without a compatibility
property.

**Two names for one value, left as a question rather than a commit.**
`HasExpression._get_expression_` and `HasSymbolicOperations._symbolic_expression_` return
the same object on every class that has both: a variable and a `SymbolicExpression` report
themselves, a match reports its lowered query. Their declared contracts differ -
`_symbolic_expression_` must be variable-like, since `_get_mapped_variable_` builds on it,
while `_get_expression_` may be any expression, which is how `ProbabilisticQuery`
implements it - so they are not simply one operation under two names, and the AGENTS rule
does not settle it either way. What is true is that a class implementing both can make
them disagree and nothing says it may not. Unifying them would change an interface `main`
landed the day before, which is above the bar auto mode decides on its own, so it is on
#192 and on #181 for the developer.

**Three more `.variable` detour sites for item 3, found the same way section 26 found the
two in `exceptions.py`.** #575's docs for `marginalize_for` teach
`distribution_of(match, marginalize_for=(match.variable.outcome,))` in three places -
`factories.py:149`, `operators/probabilistic_queries.py:153` and
`verbalization/grammar/probabilistic_queries/rules.py:73`. This item is what makes
`match.outcome` the spelling, so the text is stale the moment it lands; rewriting
user-facing detour prose is `factories-unwrap-match-and-migrate`'s scope, and recorded in
its notes rather than fixed here.

Verification: `test/krrood_test/test_eql` 1310 passed, 3 skipped - up from section 26's
1287 because #575's own `test_probabilistic_queries` arrive with it - the mypy typing
fixture included. Full `test/krrood_test` 1916 passed, 5 skipped, excluding
`test_rustworkx_utils` and `test_symbolic_math`, which need `flask` and `casadi`; the two
`test_ripple_down_rules/test_object_diagram.py` failures are this container having no
Graphviz `dot` binary, `which dot` finding none.

**Environment note, narrowing sections 14, 22 and 26.** A Python 3.12 venv with
`random_events`, `probabilistic_model` and `krrood` installed editable plus `mypy` is
enough for the whole of `test/krrood_test` when pytest is given
`--confcutdir=test/krrood_test`, which skips the workspace-root `conftest.py` and its
`semantic_digital_twin` / `objgraph` imports. The heavier set the previous sections
installed is only needed when that root conftest is in play.
## 28. 2026-09-03: the first real review of #192, and it ended the detours

`/plan-item-resolve match-query-ergonomics match-underscore-rename-and-forwarding`, in
auto mode. Sections 26 and 27 both found the stall was a conflict and both recorded that
#192 had *no* review threads. That stopped being true fourteen minutes after section 27's
own report went up: between 22:55 and 23:05 on 2026-09-02 the developer left six, and the
manifest still said `blockers: []`. They were the whole of the stall. Everything else was
ruled out first, as section 26's lesson requires - `mergeable_state` clean, all 23 checks
green on `9482a62c`, the dependency `where-query-rooted-attribute-no-filter` merged and
`is_ready: true`, still no `in-review` label and so no upstream pull request to read.

**Three of the six had a plausible reason to refuse, so each was measured rather than
argued.**

*The `_variable_` detour is genuinely redundant, and section 7's note that it is not is
obsolete.* Section 7 recorded a cosmetic divergence - a forwarded attribute verbalizing as
"the battery of the Robot" where a `_variable_`-rooted one says "its battery" - which would
have made the assembler-doctest comment a change of expected output rather than a
simplification. Measured on this branch, the two spellings produce the *identical* string,
because #182 re-roots a chain taken from a query onto the variable that query selects, so
they are one node. The observation was made before #182 and does not survive its parent.

*The empty pattern parentheses really are optional.* `a(Position).from_(positions)` builds
and filters exactly as `a(Position)().from_(positions)` does, because `from_` and the
modifiers create the variable lazily. Seventeen sites lost them; three keep them, where the
parentheses rule of section 18 needs an empty pattern stated before a second call reaches a
callable instance, and where the test's own subject is the eagerly created subject variable.

*`_is_own_name_` is load-bearing.* With `Match`'s override deleted, `_chain_expression_`,
`_missing_` and `_operands_` all come back as symbolic `Attribute`s instead of raising -
section 6's silent miss, in exactly the shape that produced #196, #248 and the `_operands_`
assertion section 18 caught in a test written the same day it was documented. Answered on
the thread and left open, since the question asked for a reason rather than a change.

**The developer extended the first comment to all three compatibility properties, and that
is what ended item 3.** The comment said "remove this and migrate the callers" on
`matches_with_variables`; asked how far it went, the answer was all three -
`variable`, `matches_with_variables` and `expression`. Sections 4 and 17 had kept them
precisely so the in-flight D-core stack keeps working, and that cost is real and was
recorded before the removal rather than discovered at the merge: #159 (`D-core-single-class`,
open and out of draft) still reads `match.matches_with_variables` at
`test/krrood_test/test_eql_rdr/test_underspecified_match.py:60,67` and `match.variable` at
line 80.

**Removing `expression` forced two changes it had been standing in for, which is why the
removal is not a rename.**

- *The factories now unwrap a match.* `the(match.expression)` was the only spelling for
  quantifying or selecting a match: `the(match)` raised `assert_never` at the point of
  writing, and `entity(match)` / `set_of(match, ...)` constructed and then died with
  `KeyError(<uuid>)` at evaluation - the measurement section 19 put in item 3's notes. They
  now read the match through `SymbolicExpression._as_operand_`, the rule section 19 already
  established for operands, applied at its two remaining boundaries: `Query`'s selected
  variables, so a selection reads the query the match stands for, and
  `UnificationDict.__getitem__`, so `row[match]` reads the value back. That is one rule at
  three boundaries rather than three unwrappings.
- *`marginalize_for` looked its attributes up by the chain's display name*, which only ever
  matched a variable-rooted one, so `distribution_of(match, marginalize_for=(match.outcome,))`
  - the spelling the docs now teach - raised `KeyError('(Coin).a')`. A chain taken from the
  match's own query is re-rooted onto its selection, the same rule and the same
  point-of-attachment #182 established for conditions. Found by the migrated test failing,
  not by reading.

`expression` was also the name the match hierarchy's own *abstract* member carried, so it
moves to `_symbolic_expression_` on `AbstractMatchExpression` and `AttributeMatch` as well,
and `Match` holds the lowering there rather than under a third name both
`_symbolic_expression_` and `_get_expression_` delegated to. That settles half of section
27's open question by removing the public handle standing under the two protocol members;
whether the two should themselves be one is still the developer's. Left as a finding rather
than a change: `AttributeMatch._symbolic_expression_` has no reader anywhere and exists only
as the hierarchy's abstract member.

**Item 3 is folded, because nothing was left of it.** `factories-unwrap-match-and-migrate`
was scoped to the factory unwrapping, the ~30 `.expression` sites, the `.variable` sites, the
docs that teach the detours, and the decision about whether `expression` survives. All of it
happened here, so applying the personal notes' own fold test - what would the pull request be
if these edits were removed - leaves nothing. The three public machinery names section 17
deferred to "whichever pass removes the detours" went with it: `update_fields`,
`create_or_update_variable` and `has_cause_attributes` are now underscore-sandwiched, since a
matched class with a field of any of those names was still getting the method, which is this
item's own subject in the three places it was still open.

Migrated in full: the five user docs (`underspecified.md`, `causality.md`,
`probabilistic_queries.md`, `inference_explanation.md`, `graph_and_visualization.md`), the
`causes_effect` suggestion strings section 26 routed to item 3, and the three `marginalize_for`
sites section 27 routed there. `QueryGraph(query.expression)` becomes
`QueryGraph(query._get_expression_())`, the protocol member #575 landed for exactly that
caller.

Two files became duplicates or dead and were removed rather than migrated:
`test_expression_gives_symbolic_access` became a character-for-character duplicate of the
test beside it once the detour it was named for was gone, and a bare `pose.expression`
statement in `test_match_verbalization.py` existed to force the lowering, which `where` does
itself - it was already a no-op, and the exhaustive grep is what found it rather than the
suite, which is section 6's hazard behaving exactly as predicted.

Verification: `test/krrood_test` 1919 passed, 5 skipped, excluding `test_rustworkx_utils` and
`test_symbolic_math` (`flask`/`casadi`); the two `test_object_diagram` failures are this
container having no Graphviz `dot` binary, `which dot` finding none. The mypy typing fixture
and `test_rule_doctests` both run in that total. `test_gcs.py` and `test_spatial_types.py`
were edited but need `semantic_digital_twin`, which this venv does not carry; both edits are
one-line spelling changes and were syntax-checked.


## 29. 2026-09-03: the kind of a step is read off the step

The developer's review of #248 left six threads, and five of them are one question asked
five times: why does each `_structural_key_` name its own class literally, rather than
`type(self)`?

Taken. The literal is the weaker spelling for exactly the reason the property exists: a
class subclassing `Attribute` and not restating its key would report `Attribute` and so
compare equal to a plain attribute step - the collision this pull request closes, one
level down. `type(self)` reports the concrete kind, so the worst a subclass that forgets
to restate its key can do is drop its own new argument; it can no longer be mistaken for
its base. Behaviour is unchanged today, since a repository-wide search finds no subclass
of any of the five, and the tests keep asserting against the class member they already
did. `test_eql` 1299 passed, 3 skipped.

**The sixth is a question, and the answer is three differences, one of them deliberate.**
Asked whether the structural key duplicates `CanBehaveLikeAVariable`'s cache keys, or
whether the cache should use it, measured rather than argued:

```
world.bodies[1]
  _structural_key_          (IndexByValue, 1)
  MappedVariableCacheItem   (IndexByValue, ('_child_', World.bodies), ('_key_', 1))

flat_variable(cabinet.drawers) vs flat_variable(cabinet.drawers)
  structural keys equal?    False
  cache keys equal?         True
```

The cache key holds the child, because it answers "has this mapping on *this* child been
built"; the signature compares chains step by step, so a step must say only what that step
does. The cache key is computed from the constructor arguments *before* the node exists,
so it cannot call an instance property of a thing it may not construct. And they disagree
on `FlatVariable` on purpose - which is why `flat_variable` constructs outside the cache
(section 13): keying the cache on the structural key would give every flattening its own
entry, and keying the signature on the cache key would collapse two flattenings into one
step, the bug #186 fixed.

What they *could* share is `identify_argument`: the structural key identifies an
expression-valued argument by `_id_`, the cache holds the object and hashes it by
identity, so the cache misses a rebuilt copy that preserves `_id_` where the structural
key matches it. That widens what is shared at query-build time, which is not a signature
bug fix, so it is on the thread for the developer rather than in the diff.

**The CI red became its own pull request.** The `test_each_lib (krrood)` failure recorded
on this item was measured to be a second root cause in the RDR test suite:
`test_draw_evaluated_tree_for_drawer_cabinet_rdr` loads the model
`test_save_and_load_drawer_cabinet_rdr` writes, `test_results/` is gitignored, and CI runs
`pytest -n auto`, so the reader can start before the writer has written. At the developer's
instruction it is fixed on `claude/rdr-world-saved-model-fixture` (PR #251, draft, `bug`):
a `saved_drawer_cabinet_rdr` fixture writes the classifier into a directory named after the
test asking for it, so neither test waits on another having run and two tests running side
by side no longer write one path. The module under `-n 4` from a clean state goes from
1 failed 5/5 runs to green 5/5. It is not a plan item - one pull request, in a suite this
plan does not otherwise touch.

## 30. 2026-09-03: main's first arrival after the detours came out

`/plan-item-resolve match-query-ergonomics match-underscore-rename-and-forwarding`, in
auto mode. Two things were live and the manifest recorded neither: the eighth
`needs-resolution` conflict, and a second review round left at 14:45-14:54 on the same
day section 28's own report went up at 06:01. That is the second consecutive round in
which the developer's review arrived within hours of a report saying there was none -
section 28 recorded it happening fourteen minutes later, this one nine hours - so it is
a pattern rather than an accident, and re-reading the threads is now the first thing a
resolve on this item should do rather than a step it can reach after the conflict.

**The conflict was one hunk, and main's side is simply better.** `main` took cram2#590
(a Markov-chain template), which extracted the part-prefix logic out of `rspn.py` into
`RelationalDistributionTemplate._prefix_for_part` and turned the module-level
`_rename_variables_with_part_prefix` into a circuit method. This branch had renamed
`part.variable` to `part._variable_` on those same lines. Nothing disagreed: main
restructured where the prefix is computed, this branch changed what it reads, so the
resolution takes main's extraction and the extracted helper reads `_variable_`.

**Section 6's hazard finally had something to catch, in a test main landed.** Sections
26 and 27 both swept for new readers of the renamed fields and both found none, because
#575's code reached a match only through the public `expression` this branch still kept.
#590 is the first arrival after section 28 removed all three properties, and it reads two
of the renamed names:

- `test_markov_chain.py:146` builds its parts from `room_query.kwargs["objects"]`. With
  `kwargs` behind the convention, that is a symbolic `Attribute` indexed by a string, so
  `ground` was handed an `IndexByValue` and died on `len()` - loud, and only because
  `ground` happens to measure its argument first.
- `test_markov_chain.py:186,217,255` interpolate `f"{part.variable}.type"` into a
  variable name. That one is silent: the f-string renders the repr of a symbolic
  attribute, so the lookup finds nothing and the test fails on an empty match rather
  than on the name being wrong.
- `template.py:52` reads `str(part.variable)` for the namespace prefix. Silent in the
  same way, and in production code rather than a test.

All three now read `_variable_` / `_kwargs_`. The lesson is the sweep's, not the
hazard's: a clean sweep on one merge says nothing about the next one, and it was clean
twice only because the property removal had not landed yet.

**The review round: three threads taken, one refused with a measurement.**

*The `_variable_` detour in `test_causes_effect.py` was a rename that should have been a
migration.* The round that migrated that file's evaluation tests to read the match
directly left its six construction tests spelled `._variable_`, which is the mechanical
`.variable` -> `._variable_` rename applied where the migration was meant to go. All six
read the match now and all six still pass, the four `rejects` ones proving it rather than
the two `accepts` ones, since only a rejection pins that the comparator was really built
and really validated. The binding is also renamed `arm` -> `pick`: it was never an arm,
and `arm.arm == 0.3` is what a wrong name reads like once it is written twice.

*The `.resolve()` statements divide in two, and only measuring separates them.* In the
match-verbalization tests they are redundant - `MatchPlanner` calls `match.resolve()`
itself, so the test was forcing a lowering the code under test forces - and all three
come out with every expected string unchanged. In the feature-extraction tests they are
load-bearing: without `room_query.resolve()` the grounded circuit carries `SceneObject.type`
instead of the per-position `SceneRoom.objects[i].type`, and seven tests fail. One of
those, `test_feature_extraction_with_aggregations`, keeps its call while asserting only
`model.is_valid()`, which passes either way - so removing it there would have changed
what is grounded without anything noticing, which is why "it still passes" was not
accepted as the answer.

**What a query-rooted chain still cannot do, measured rather than assumed.** The
developer's "remove `_variable_` in all similar ones" does not reach the four
`translate()` sites in `test_random_events_translator.py`, and the reason is not the
match. `Query._type_` is `None` - `SymbolicExpression._type__` delegates to `self._var_`
and a query *is* its own `_var_`, so the delegation never fires - and therefore every
attribute chain built on a query carries no type. `WhereExpressionToRandomEventTranslator`
reads `comparator.left._type_` to build its random-events variable, so a match-rooted
chain reaches it with `_type_ = None` and it raises `TypeError: issubclass() arg 1 must
be a class`. Confirmed pre-existing on `main`, with no match involved:
`entity(v).position.x._type_` is `None` there too, and so is
`a(Pose).expression.position.x._type_`. Inside a `where` it never shows, because #182
re-roots the chain onto the variable at attachment and the re-rooted chain has the type;
it shows exactly where a chain is used away from the query it was taken from - the same
place section 28's `marginalize_for` bug lived, one layer down. Fixing it means teaching
`Query` to report the type of the variable it selects, which changes a class `main` owns
for every query in the language, so per section 20's rule it is left as a finding for the
developer to route rather than folded in here.

Verification: full `test/krrood_test` 1925 passed, 5 skipped, excluding
`test_rustworkx_utils` and `test_symbolic_math` (`flask`/`casadi`); the two
`test_object_diagram` failures are this container having no Graphviz `dot` binary,
`which dot` finding none.

## 31. 2026-09-03: the type a query reports, and the name it does not

The developer's answer to the question section 30 left open: teach `Query` to report the
type of the variable it selects, in its own pull request off `main`, then merge it into
#192 and drop the `_variable_` it was standing in for. Done as
`query-reports-its-selection-type`, PR #254 (draft, `bug`), off `main` at `69b2395a2`;
merged into #192 as `4f1edbd6d`, the six bindings removed in `e1d8076aa`.

**The bug had been carrying a workaround on `main` since before this plan started, which
is what settles that it was one.** `Selectable._type__` delegates to `self._var_`, and
`Query.__post_init__` sets `_var_ = self`, so the delegation never fires and every query
reports no type - even though `_var_`'s own docstring names "queries ... that operate on
a single selected variable" as the case it exists for. `Attribute` reads its owning class
off its child, so every chain built on a query carried `_type_ = None`.
`Attribute.number_like_field` already re-rooted the chain onto the query's selection to
get a type out of it; the random-events translator had no such workaround and raised
`TypeError: issubclass() arg 1 must be a class` instead.

**The fix is polymorphic, on the split section 12 already established.** `Entity` reports
its selected variable's type; `SetOf` does not, since a row binding several variables is
not a value of any one type.

**And it needed section 6's own guard, in the fix for a bug section 6's hazard caused.**
The first version read `selected._type_` unconditionally. A selection is not always a
`Selectable` - `entity(value > 5)` selects a `Comparator`, which declares none - and a
variable claims no underscore-prefixed name, so the read was captured as a symbolic
attribute rather than raising. Building that attribute compiles the query that is still
inside its own `__post_init__`, and `test_explanation.py`'s filterless-query test
recursed until the stack ended. The read is now guarded by `isinstance(selected,
Selectable)` and the case has its own test. That is the third time this hazard has been
met while fixing something it caused (sections 18 and 25 are the others), and the second
time the fix's own first draft was the thing it caught.

**The type was necessary and not sufficient, which the plan-mode answer had not
anticipated.** A random-events variable is identified by its *name*, and the two
spellings still differed - `Body.size` against `(Body).size` - so a model fitted through
one would not have matched a query written in the other. The symmetric fix was tried and
is unsound: naming an `Entity` after its selection makes `entity(condition)` ask a
`Comparator` for a name that walks back through the query, and the suite recurses again.
A query is genuinely a different node from its selection and its `(...)` name is honest.

So the name is fixed where it is read, which is what section 28's `marginalize_for` fix
and #182's condition re-rooting both already do. That made three inline copies of one
rule, so it is now written once as `query.variable_rooted` and both `number_like_field`
and the translator call it.

Verification: `test/krrood_test` 1903 passed, 5 skipped on #254 alone, 1930 passed on
#192 with it merged and the six bindings removed; the two `test_object_diagram` failures
are this container having no Graphviz `dot` binary.

## The ICRA convergence pass, 2026-09-06

The whole set is now carried by one branch: #192 (both `match-underscore-rename-and-forwarding` and `factories-unwrap-match-and-migrate`), #196, #248 and #254, which arrived with #192. #186 and #182 were already on `main`.

The pass merged every one of them into the ICRA integration branch (#265,
`claude/icra-experiments-simulation-pipeline-w4ep7n`) rather than into each other,
so each conflict set was resolved once. Each item keeps its own branch and pull
request and its own status here; what changed is that its work now also stands on a
tree with everything else, which is what the ICRA experiments run on.

Merge order, resolutions, the duplication removed and the two collisions git could
not flag are recorded once, in `icra-foundation`'s `roadmap.md` under *The
convergence pass, 2026-09-06*. Read it there rather than re-deriving it here.

The exclusion that kept #192 off the ICRA branch is reversed: it removes
`Match.variable`, which #159 and therefore #239, #266 and #275 read, and the
developer had asked for it to stay out until that was dealt with. It is dealt with
now, in a commit of its own after the merge.

Worth recording for anyone migrating past this rename: because #192 also gives
`Match` symbolic attribute delegation, a stale read of a retired name does **not**
raise - it quietly builds an `Attribute` expression for a field of that name. The
reads were found by making `Match._is_own_name_` refuse the retired spellings
temporarily, running the suites, and migrating every hit; the guard was then removed,
since #192 deliberately leaves every public name to the matched class.

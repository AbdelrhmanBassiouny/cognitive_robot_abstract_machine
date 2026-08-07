# DAG-vs-tree façade hardening in `SymbolicExpression`

## Why this exists

EQL's `SymbolicExpression` (`krrood/src/krrood/entity_query_language/core/base_expressions.py`)
is a genuine **rooted DAG**: a node carries `_parents_` as a *list*, and subexpressions are
deliberately shared (`MappedVariable` singletons, a condition reused across two queries). Yet
its public navigation is **tree-shaped**:

- `_parent_` returns a single **primary** parent (`_parent__`) — whichever was attached *first*.
- `_root_` walks *only that primary-parent chain* up to one root.

Per the NLG/compiler/query-plan literature, a DAG's defining property versus a tree is exactly
that a node has *many* parents (common-subexpression sharing, LLVM's plural `users()`), and a
shared node's "parent"/"root" is only well-defined **relative to who is asking**. So singular
`_parent_`/`_root_` answer a *construction-history* question where callers usually need a
*context/ownership* one. This mismatch has produced a family of real, separately-fixed bugs.

## What the in-flight stack already did (Wave 0)

The maintainer has been fixing the individual leaks, each by resolving the owner from
**evaluation-scoped context** rather than the structural pointer — which is precisely the
design the literature points to (dynamic context / inherited attributes), and which the
codebase already had the machinery for (`ActiveConditionsRoot`, `OutermostQueryClaim`,
`TruthValueOperatorChildren` in `evaluation_context.py`):

- **#90** (`bug`): `is_condition_participant` read a shared node's structural `_parent_` →
  dropped `satisfied_condition_ids`. Fixed with a per-pass `TruthValueOperatorChildren` record.
- **#89**: removed the dead `_last_parent_of_type_` recovery; extended `ActiveConditionsRoot`
  with `has_condition()` decided once at claim time.
- **#92** (`bug`): `_root_`'s single-parent walk *was* a real bug in
  `InferenceExplanation.query_root` (fixed via `OutermostQueryClaim` storing the claimed query
  node) plus a `QueryGraph` memoization order-bug.

Key fact established while designing this plan: evaluation is **top-down recursion over
`_children_`** — nothing walks *up* `_parent_` to drive evaluation. The structural pointer is
only construction bookkeeping plus a documented fallback for when no evaluation context is
active. That is what makes the hardening below low-risk.

## What this plan adds (Wave 1)

The point-fixes above leave two things open, which this plan closes:

1. **The root cause is untreated.** Every fix is local ("resolve from context *here*"). The
   façade itself (`_parent_`, `_root_`) is still public and un-renamed, so it keeps *inviting*
   the next semantic misuse. The hardening is to (A) rename the structural accessors to
   `_structural_parent_`/`_structural_root_` so their name announces "construction/layout shape,
   not authoritative ownership", keeping `_parents_` as the real relation; (B) consolidate the
   repeated "use context else structural fallback" dance into one reusable `EvaluationContext`
   accessor; and add a name-based **guard test** so semantic modules physically can't reach the
   structural accessor again.

2. **One known bug remains**, flagged out-of-scope in #92:
   `QuantifiedConditional._ids_of_variables_to_add_to_sources_` (`logical_quantifiers.py:147`)
   is a `@cached_property` over `_root_query_._selected_variables_` — a shared `Exists`/`ForAll`
   node caches the *first* query's answer and reuses it in the second. This is a *different
   class* of problem (a query-dependent value cached per node at all), fixed by resolving the
   owning query from context per pass and keying any cache by owning-query id.

### Sequencing and positioning

Work composes **on top of** the #89/#90/#92 stack and must not redo or conflict with it. The
bug + audit item (`quantified-conditional-and-audit`) depends on all three landing; the rename
item (`facade-rename-and-guard`) is deliberately **sequenced last** because it is the largest
diff and collides most with the stack — doing it after the bug PR lets it rebase cleanly. The
name-based guard test lives with the rename item, since it can only assert on the renamed
`_structural_*` accessors.

## Conventions and verification

- TDD throughout (AGENTS.md): each fix begins with a failing shared-node regression test in the
  #90/#92 shape (a node shared across two independent queries, asserting the second query's own
  evaluation is correct). krrood-internal mimics only — no cross-package imports.
- Run with the project interpreter via pytest: `test_eql`, `test_ormatic`, `test_class_diagrams`,
  `test_ripple_down_rules`; expect the #89/#90/#92 baselines to stay green with new tests added.
- `black` + `docformatter` (`scripts/format_docstrings.py`) on touched files; RST field
  docstrings; absolute/top-level imports; no `getattr`; guard clauses; SOLID.
- Commits authored as the human identity, no assistant trailers; "Made with the help of Claude."
  note permitted.

## Design origin

This plan was migrated from an approved Claude Code plan-mode plan produced in the session that
first raised the "isn't it weird for a DAG to ask for a root / a node to ask for the parent?"
question, then cross-checked against the live #89/#90/#92 stack. Per-branch working notes, when
branches exist, live in `.claude/personal/pr-progress/<branch>.md` as usual and are not
duplicated here.

## Addendum (2026-07-31) — the `insert_at` splice is this defect, on `main`, today

A `/plan-item-resolve` session working `rdr-refactor`'s `D-core-support` (#67) hit a
review thread calling `enforce_parent_consistency` in `rdr/rule_tree_view.py` a code
smell — *"why isn't it consistent in the first place?"* Tracing that question led
here, and turned up a concrete instance of this plan's defect class sitting on `main`.

`ConclusionSelector.insert_at` (`rules/conclusion_selector.py:67`) splices a new branch
above `anchor._parent_`:

```python
# Splice above the anchor's structural parent — a ConclusionSelector for a node already
# in a rule tree, or a Filter for a direct WHERE condition.
previous_parent = anchor._parent_
```

That is first-attached-wins on a node that is routinely shared. When a rule tree first
uses an attribute inside a `Comparator` in one branch (`refinement(eggs == False)`) and
later refines on it bare (`refinement(eggs)`) in a sibling branch, `anchor._parent_`
points at the incidental `Comparator`; the splice rewires that comparator's operand and
drags the new refinement chain out of the tree. Measured consequence, from #78: loading
a human-fitted zoo model dropped 12 of its 21 rules (accuracy 101/101 → 71/101).

Three things make this worth its own item rather than folding into Phase D:

- **It is construction-time, not evaluation-time.** Wave 0's machinery
  (`ActiveConditionsRoot`, `OutermostQueryClaim`, `TruthValueOperatorChildren`) is all
  evaluation-scoped, and nothing is evaluating when a rule tree is spliced. The fix uses
  the *other* context that already exists: the `with`-context stack
  `create_and_update_rule_tree` resolves its anchor from via
  `_get_current_context_condition`. Same principle — parent relative to who is asking —
  applied at the other end of the lifecycle. So it needs none of Wave 0 and is
  `depends_on: []`.
- **It is reproducible on `main` with core EQL plus `rules/` alone.** No RDR layer, no
  mimic of another package: build a node attached under two parents, splice, assert the
  splice took the asking branch's edge rather than the first-attached one. A genuine
  failing-first test at the accessor's own contract level.
- **Leaving it to Phase D would land it after the rename, which is backwards.** The
  rename is sequenced last precisely because it is the largest diff; this fix is small,
  wanted now, and removes work from another plan.

### Why this supersedes `rdr-refactor`'s #78

PR #78 (`D-ui-splice-fix`, `bug`) fixes the same bug the other way: it reintroduces
`SymbolicExpression._last_parent_of_type_` and has `insert_at` walk up to the anchor's
most recent `ConclusionSelector`/`Filter` parent. That is a heuristic over `_parents_` —
a semantic module reading structural parentage, which is exactly what Phase D's guard
test is meant to forbid and what Phase A's rename would break. It also re-adds the
symbol **#89 deleted from `main`** (verified absent there), so the programme would delete
it, re-add it, and delete it again.

#78's scope note says it is based on `D-core-engine` rather than `main` "because
`insert_at` does not exist on `main` yet". That was true when written on 2026-07-16 and
is now stale: `rules/` has since landed on `main`, `insert_at` with it. Nothing about
this fix needs the RDR stack.

So #78 reduces to its regression test, re-pointed at the fixed API, or closes as
superseded — a call for whoever picks up either item first.

### Effect on the programme's sequencing

`rdr-refactor`'s Wave-0 stack still goes first overall: `facade-rename-and-guard` is a
repo-wide rename in `base_expressions.py`, the file that 12-PR stack contests most, and
every merge to `main` while it is open costs a full cascade restack. This item is the
exception that jumps the queue — it is small, lands off `main`, and *removes* a future
cascade instead of adding one.

### How it was fixed (#118, 2026-07-31)

The addendum's premise held: a kickoff session reproduced the bug on `main` with core
EQL plus `rules/` alone, no RDR layer and no serializer — the earlier sibling's
`Comparator` ends up with a `Refinement` as its left operand.

Two findings shaped the design, both of which rule out the obvious shapes:

- **The owning edge cannot be read off the node when the block is entered.** At
  `with refinement(shared_node)`, the node's `_parent_` is *already* the unrelated
  comparator — that is the bug itself. The edge has to be inherited from the enclosing
  context, whose own owning parent is the selector `insert_at` just created and is a
  parent of the new branch too.
- **It cannot be captured once, either.** Repeated edits inside one block re-splice the
  same anchor, replacing that edge each time, so a write-once record goes stale after the
  first nested statement. `insert_at` refreshes it after splicing.

So the context stack now holds `RuleTreeContext(condition, owning_parent)` instead of
bare expressions, and `insert_at` splices above the recorded parent, falling back to the
structural one only when no enclosing context anchors on the anchor — which keeps the
explicit-anchor API working outside any `with` block. No `_parents_` heuristic is
involved, so Phase A's rename and Phase D's guard test stay compatible with it.

#78 was **closed as superseded** the same day. Of the two options the section above
offers, only one was actually available: "re-point its regression test at the fixed API"
is not, since `TestAttributeReusedInEarlierSiblingBranch` lives in
`test/krrood_test/test_eql_rdr/` — a directory that does not exist on `main` — and
asserts through `walk_rules`/`classify_case` from the RDR layer. #118 covers the same
defect DSL-only at the accessor's own contract level instead, so no coverage is lost on
`main`; the RDR-level test can be re-added against the fixed API once `test_eql_rdr/`
lands, with no production change needed for it to pass.

One consequence for the other plan: `rdr-refactor`'s #79 (`D-ui-rendering`) is based on
the `D-ui-splice-fix` branch. Closing the PR does not delete that branch, so #79 is not
broken, but it can no longer land through #78 and needs re-targeting onto
`D-core-engine`. Left to #79's own session; recorded in `rdr-refactor`'s manifest.

## Addendum (2026-08-01) — rustworkx considered and declined; ownership collaborator watch-item

The #90 review summary asked whether the growing evaluation-context machinery
(`ActiveConditionsRoot`, `TruthValueOperatorChildren`, `EvaluatedExpressionIds`,
`OutermostQueryClaim`, `SubqueryResultCache` — five parallel record classes in
`evaluation_context.py`) should be replaced by a graph library such as rustworkx, with
its traversal algorithms and queries. Discussed in-session and accepted: **no**, for the
evaluation-time machinery — with one structural conclusion and one escape hatch.

Why a materialized graph does not fit the recurring bugs:

- Every bug in this plan's family (#89, #90, #92, #118) was an **ownership** bug —
  "which of a shared node's several parents/roots is relevant to the party asking right
  now" — never a **traversal** bug. A rustworkx graph answers traversal questions
  (ancestors, paths, reachability) and would faithfully return *all* of a shared node's
  parent edges; choosing among them requires knowing which query/pass/rule-tree block is
  currently executing, which is dynamic state a static graph cannot hold. The contextvar
  machinery would still be needed to pick — the graph adds nothing to the picking.
- Evaluation is lazy, streaming, top-down recursion over `_children_` with
  short-circuiting and per-pass state. Mirroring it into a `PyDiGraph` means a build
  step plus node-index bookkeeping per pass and a parallel mutable annotation store kept
  in sync — which is exactly what `EvaluationContext` already is, minus a graph copy
  nothing would query.
- Where the questions *are* structural and post-hoc, rustworkx **is** already the
  implementation: `QueryGraph` materializes the expression DAG for visualization and
  satisfaction coloring. The accepted split: static/structural questions → materialized
  rustworkx graph; dynamic/"who is asking" questions → evaluation-scoped context.

What *does* deserve refactoring is the record-class sprawl itself, and that is Phase B:
consolidate the repeated "resolve from context, else structural fallback" dance into
reusable `EvaluationContext` accessors. `is_child_of_truth_value_operator` (added in
#90's review round) is deliberately its first slice. Related accepted conclusion:
`is_condition_participant` stays — its question is positional/per-edge (a bare
`Variable` is a condition only *as* a direct child of a `TruthValueOperator`), so it can
be neither a type property nor a construction-time node tag; its final shape is a thin
dispatcher (explicit caller-known parent → evaluation context → structural fallback).

Watch-item (recorded on `quantified-conditional-and-audit`): if Phase C's
per-owning-query caching multiplies the records further, fold them into a single
ownership collaborator on `EvaluationContext` rather than adding a sixth parallel class.

Escape hatch: revisit a per-pass materialized view only if evaluation-time code ever
needs *bulk* structural queries on hot paths (e.g. "all conditions in this query's
subtree relative to a given owner"); no current call site does.

## Addendum (2026-08-03) — `non-mutating-negation`, filed from rdr-refactor's #41

A `/plan-item-resolve` session on `rdr-refactor`'s `rdr-backward-inference` (#41) was asked
to settle a review question: should `GuardCondition.negated` be dropped in favour of wrapping
the guard expression in `Not()`, so a guard's expression is always required to be true?

The answer turned on this plan's defect class, which is why the item lands here.

`Not()`-wrapping is genuinely the cleaner representation — cleaner at four of six concrete
use sites across that plan (it deletes `_materialize` outright, simplifies `holds_for`, and
reduces `_active_path`'s positive-occurrence check to an identity test). It loses on exactly
one point: `factories.not_` → `SymbolicExpression._invert_` → `Not(self)` →
`base_expressions.py:299` `child._parent_ = self`. Negating a node that belongs to a live
tree reparents it. That is the tree-shaped-facade-over-a-DAG problem this plan exists to
close, at construction time rather than evaluation time — the same shape as
`insert-at-ownership-parentage`.

The developer kept the flag on that basis and asked for the underlying defect to be tracked
here rather than bundled into #41 (the bottom of a seven-PR stack, where every extra commit
costs a cascade restack).

The concrete instance is `rdr/condition_resolver.py:104`: `_materialize` calls
`not_(guard.expression)` on a live rule-tree node — so the no-mutation rule is honoured
during traversal and violated at rule-insertion time. That call site is not on `main` yet;
it arrives with #41. So the item's real content is the first half — a way to build a negated
view without adopting the operand — and the call site is repointed whenever the RDR stack
lands, in whichever order the two merge.

Worth carrying forward: **once this lands, `rdr-refactor` should revisit
`GuardCondition.negated`.** The recommendation recorded on #41 was explicitly conditional —
"keep the flag now, revisit when #96 lands a safe constructor" — and this item is that
condition. Its own analysis is in `rdr-refactor`'s roadmap §12; the short version is that
verbalization does not decide the question (the verbalizer already handles both an
`(expression, polarity)` pair and a native `Not(Comparator)`), so the hazard is the whole
argument.

## Addendum (2026-08-04) — `rule-tree-context-stack-ownership`, stacked on #118

Looking at #118, the developer asked whether the `with`-context stack still needs to be a
class variable: *"if we make the root `with`-block expression itself own and create a new
stack instance, then inner `with` blocks can take that context by checking their root
`with`-block stack and updating it."*

### The first half of the idea is impossible, and the reason is this plan's own defect class

Every reader of the stack was traced on #118's tip. Four of them are reached from objects
that have never been related to the enclosing block:

- `Conclusion.__post_init__` (`rules/conclusion.py`) — an `add(...)` written in a block body
  is a brand-new node whose only links are downward.
- `Refinement`/`Alternative`/`Next._get_current_context_condition` — reached from
  `create_and_update_rule_tree`, a **classmethod**. There is no instance at all, only `cls`
  and freshly built conditions that are by construction not yet in the rule tree.

The only route from any of them to an enclosing root is `_conditions_root_` → `_root_`, the
single first-attached primary-parent walk that Phase A renames and Phase D's guard test
forbids. Using it to locate the builder's stack would be unreliable on shared nodes *and*
be deleted by this plan's own end state. The other escape — changing the DSL so the block
object is the receiver (`with query as tree: tree.add(...)`) — does make instance ownership
work, and was rejected: it rewrites every doc example and every rule test for no behavioural
gain.

So some ambient lookup is unavoidable. What the item removes is the *process-global mutable
list*, not the ambience.

### The second half of the idea is right, and the repo already does it at the other end

`evaluation_context.py` holds `_evaluation_context_var: ContextVar[Optional[EvaluationContext]]`,
and `SymbolicExpression._evaluate_` has the *outermost* evaluation create the context, install
it, and reset the token in `finally` (`owns_an_evaluation_context`). Construction-time context
now mirrors it exactly: a `RuleTreeContextStack` created by the outermost `with` block, held
in a `ContextVar`, discarded when that block closes. Evaluation-time and construction-time
context finally have the same shape, which is the framing this plan has used since its
2026-07-31 addendum.

Honest about what a `ContextVar` is and is not: it is still module-level state. What changes
is its *scope* (per-thread, per-task) and its *lifetime* (bounded by the outermost block, not
the process). It does not isolate a task spawned inside a block, and it does not unwind a
suspended generator that abandoned one. Both are documented on the class rather than designed
around.

### What the block record has to carry, and why

The obvious shape — one anchor hook used by both `__enter__` and `__exit__` — is wrong for
`Query`. Inside `with query:`, a top-level `refinement(...)` splices a `Refinement` above the
conditions root and rewires the `Filter`'s child, so `query._conditions_root_` afterwards
returns a *different* node than it did at entry; recomputing the anchor at exit would raise a
false imbalance. So a `RuleTreeBlock` records the expression whose `__enter__` opened it,
separately from the `RuleTreeContext` the block contributes — and `RuleTreeContext` keeps
#118's two fields untouched, both to minimise rebase pain and to keep the value object
`insert_at` mutates distinct from the frame record.

The knock-on is the cleanest part of the change: `Query.__enter__` disappears entirely.
`Query` overrides only `_rule_tree_anchor_`, so a query module no longer reaches into
base-class state, and the enter/exit asymmetry (`Query` pushed but never defined `__exit__`)
is gone.

### Known defect shipped uncovered, on the developer's call

With two threads inside `with` blocks, one thread's blind `__exit__` pops the *other*
thread's frame, after which its `add(...)` lands in the wrong rule tree. It is real and
deterministically expressible with `threading.Event` barriers (in-repo precedent:
`test_isolated_expert_answers_path_is_safe_under_concurrent_use`), and the `ContextVar`
fixes it. The developer chose to scope this item to the encapsulation plus the meaningful
exceptions, so the regression test is **not** written and the item does **not** carry the
`bug` label. Recorded here so the gap is deliberate rather than forgotten.

### Landed as #142 (draft, 2026-08-04)

Nine failing-first tests, then the move: `rule_tree_context.py`, the two new
exceptions, and the five call sites. `test_eql` + `test_ormatic` +
`test_class_diagram` + `test_ripple_down_rules` at 1415 passed, 6 skipped; the two
`test_object_diagram` failures are the missing Graphviz `dot` binary #118 already
recorded. #118's two splice regression tests pass unmodified, which is the evidence
that `anchored_on` still hands back the live `RuleTreeContext` that `insert_at`
mutates.

Its base was #118's branch, not `main`. **#118 merged on 2026-08-05**, so GitHub
auto-retargeted #142 onto `main`, and `main` was merged into the branch. That merge
was clean: a stack-maintenance routine had reported a conflict, but its comment named
no conflicting files and none existed — the branch already contained #118's commits,
so `main`'s merge of them had nothing to conflict with. The `needs-resolution` label
it added was cleared, since a labelled branch is skipped by later passes and would
otherwise have stayed stuck. Promotion is no longer gated on #118; it waits only on
the PR leaving draft, which is this workflow's author sign-off.

### Positioning

Stacked on `insert-at-ownership-parentage` (#118) because it collides textually with that
PR in `__enter__`/`__exit__`, not because it needs it: the `ClassVar` predates #118, which
only changed its element type, so the work stands alone once #118 lands. Filed under the
`facade-rename` track rather than `bugs-and-audit` — it is the construction-time counterpart
of Phase B's "one reusable accessor", not a bug fix. No dependency was added to
`facade-rename-and-guard`; that item is sequenced last and rebases over this one.

## Addendum (2026-08-07) — #92's fix 2 was dissolved by #90's own review round

#92 sat blocked from 2026-08-03 to 2026-08-07 with a `needs-resolution` label and a
merge conflict in `query_graph.py`. Not CI — all 20 checks were green — and not review:
the PR has **zero** review threads, and all three of its comments are automated
stack-maintenance reports naming that same one file and declining to guess.

### Why it conflicted

#92's branch merged an *earlier* state of #90's branch. Verified: #90's final tip
`d63dce6b` is **not** an ancestor of #92's head, but **is** an ancestor of `main`.
#90's 2026-08-01 review round then changed `query_graph.py` in ways that delete the
machinery #92's fix 2 was built on — the `is_condition_participant` call in
`construct_graph`'s `is_satisfied`, the `parent` threading, and the not-supplied
sentinel.

This is exactly the hazard already recorded on `pr-90-is-condition-participant`
("#92 … must re-merge tip 58671190; construct_graph parent-param revert may
conflict"). The warning was right, and the item it was recorded on is the one that
came true.

### The finding: fix 2 is dead code on `main`

`construct_graph`'s satisfaction check on `main` is now

```python
is_satisfied = (
    self.satisfied_condition_ids is not None
    and expression._id_ in self.satisfied_condition_ids
)
```

— **position-independent**. Fix 2's bug required a position-dependent term to be
computed at the first-visited position and then memoized. With that term gone, the
first visit computes what every later visit would, so the memoization cannot stale.

Verified empirically rather than argued: applied to a clean `main`, #92's fix-2 test
**passes** unmodified, and #92's fix-1 test **fails** with a genuine assertion error.
So fix 1 is still needed and fix 2 is not.

The trap avoided: keeping #92's `_is_satisfied()` helper would have reinstated the
very check #90's review removed as redundant, with the `or`-fold over the memoized
node existing only to work around the check it reinstates. A "keep both sides"
resolution was also not viable on its own terms — the auto-merge is broken *outside*
the conflict markers, since `construct_graph`'s signature loses `parent` (main's side)
while the body still passes `parent` to `self._is_satisfied(...)` twice.

### How it was resolved

`query_graph.py` taken from `main` wholesale, so the branch no longer touches that
file at all. Fix 2's regression test kept, retargeted as a guard that the
classification stays independent of visit order, and renamed after that behaviour
rather than after the mechanism it used to exercise — it passes on `main`, which is
what makes it a guard rather than a fix. #92 now reduces to fix 1: `OutermostQueryClaim`
gaining the claimed node, the `query.py` call site, and `_resolve_query_root`.

Full run on the resolved tip: `test_eql` + `test_ormatic` + `test_class_diagram` +
`test_class_diagrams` + `test_ripple_down_rules` at **1437 passed, 7 skipped**, zero
failures. Unlike the runs recorded for #118 and #142, the two `test_object_diagram`
tests pass here — the Graphviz `dot` binary was installed in this session's
environment, so that long-standing pair of failures is confirmed environmental rather
than a real defect.

### One item handed to Phase D

`_is_faded_gate` reads `node.parent`, while `_add_children_to_graph` reassigns
`child_node.parent` on *every* visit — so for a node reached through two parents, the
faded BFS sees only the last-assigned one. Same defect class as everything else in
this plan, but no failing test was constructed for it and it is outside #92's proven
scope, so it is recorded on `quantified-conditional-and-audit` rather than folded in.

### A note on the generic lesson

The plan's own machinery caught this: the cross-item warning recorded on #90 named
both the file and the mechanism, and it was accurate months before it fired. What it
could not do was update #92's manifest entry, which still read "mergeable clean" four
days after the branch went `dirty`. Live PR state belongs in the manifest as soon as
it is fact — a stale "clean" is what made this look like an idle item rather than a
blocked one.

### Review round (2026-08-07) — the ownership accessor landed early, on `SymbolicExpression`

#92's review round was three naming-and-placement threads, but one of them moves this
plan's own end state forward and is worth recording.

The developer asked of `_resolve_query_root` (then a module-private function in
`explanation.py`): *"Is this method not general for all expressions? If it is generally
useful to all expressions then it should be moved to the core base expressions inside
SymbolicExpression."* It is, and it was. It now lives as
`SymbolicExpression._evaluating_query_root_`, directly beside `_root_` and `_root_query_`.

That placement matters beyond tidiness: **`_root_` and `_evaluating_query_root_` are now
the structural and ownership answers to the same question, sitting side by side on the
same class.** Phase A renames the first to `_structural_root_`; the second is already
named for what it resolves from. So the pair reads as the contrast this plan exists to
draw, rather than one accessor silently doing both jobs — and Phase B's "one reusable
accessor" gains a second concrete slice on the *expression* side, after
`is_child_of_truth_value_operator`'s slice on the `EvaluationContext` side.

Two smaller outcomes:

- `OutermostQueryClaim` → `OutermostQuery`, and `EvaluationContext.outermost_query_claim`
  → `outermost_query`; the word "claim" is gone from the class, its field docstrings and
  `is_nested`'s. The record classes named in the 2026-08-01 addendum should be read under
  the new name from here on.
- `OutermostQuery._query_id` collapsed into `node`. Fix 1 added `node` and left the id
  beside it, so the class briefly tracked one fact twice; `node is None` is exactly
  "nothing recorded yet". Worth noting for the Phase C watch-item: when the records are
  folded into a single ownership collaborator, this one is already down to one field.

No production behaviour changed in this round — the fix-1 regression test passes
unmodified across it, which is what makes it a refactor rather than a second fix.

### Second review round (2026-08-07) — `Role[Query]` declined, and the merge deferred to Phase C

Two design questions on #92's new accessor, both settled by the developer in session.

**`OutermostQuery` as `Role[Query]` — declined.** The naming genuinely fits; "outermost
query" is role-shaped language, and `krrood.patterns.role.Role` is the repo's own pattern
for it. It fails on the import graph. `class OutermostQuery(Role[Query])` evaluates `Query`
at class-creation time — a base-class expression, which `from __future__ import
annotations` does not defer — and `Role.get_role_taker_type` resolves the parameter at
runtime as well. But `evaluation_context.py` deliberately keeps *every* expression type
behind `TYPE_CHECKING`: it is a leaf that `query.py` and `base_expressions.py` both import
at runtime and that imports nothing back. Requiring `Query` at runtime closes that into a
cycle.

Two further reasons, either of which would matter on its own:

- `Role.role_taker` is required and keyword-only, but this record is created empty by
  `EvaluationContext`'s `default_factory` and filling it *is* its job. A role cannot exist
  un-taken, so adopting one means `Optional[OutermostQuery] = None` plus moving the
  first-wins arbitration onto `EvaluationContext` — a restructure, not a change of base.
- `Role.__eq__` is identity-only and a role is never equal to its taker. This plan is about
  ownership *identity*, and the path ends in `explanation.query_root is second_query._root_`.
  A role there either gets unwrapped to `.role_taker` at every use site, earning nothing, or
  silently breaks identity comparisons.

Underneath all three: after `_query_id` collapsed away, the class is one optional reference
plus arbitration, with no role-specific fields. "Outermost in this pass" is a fact the
*pass* owns, which is why it belongs on `EvaluationContext` beside `ActiveConditionsRoot`
and `TruthValueOperatorChildren` rather than on the query. Noted for anyone revisiting: there
is no `Role[...]` subclass anywhere in `krrood/src` today, so this would have been the
pattern's first production use, on the evaluation hot path.

**The merge with `_root_query_` is Phase C's, not #92's.** The developer asked whether the
new accessor should replace `_root_query_` outright. It should, eventually — but not as a
refactor. `_root_query_`'s only consumer is
`QuantifiedConditional._ids_of_variables_to_add_to_sources_`, which needs a real `Query` for
`_selected_variables_`; `_evaluation_root_query_` falls back to `_root_`, which is any
expression. Merging therefore means narrowing the fallback to a `Query`-typed lookup — which
is the *same edit* as fixing that consumer's shared-quantifier cache staleness, this plan's
Phase C. Doing it in #92 would have made it a two-bug PR without the failing-first
shared-quantifier test that fix requires.

So #92 keeps the rename only: `_evaluating_query_root_` → `_evaluation_root_query_`, taking
the neighbouring `_root_query_`'s phrasing. Phase C collapses the two into one property named
`_root_query_`, and this name disappears.

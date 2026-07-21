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

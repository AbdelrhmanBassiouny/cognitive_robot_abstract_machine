PR #186 (draft, `bug`) — item `chain-outside-evaluation-truncates-silently`, track
`mapping-semantics` of the `match-query-ergonomics` plan. Off `main`, independent of #182.

**What it does**
1. `9587ca1c4` — `apply_mapping_on_external_root` took `next(...)` of each step, so a step
   reaching several values contributed only its first (measured on `main`: a flattened
   chain returned one drawer's handle and dropped the other). Now reports instead.
2. `21bbc73c9` — `Projection` separates mappings determined by their child and arguments
   from anonymous iteration; `flat_variable`'s cache bypass is stated and guarded.
3. `bd3aab87a` — `Index` split into `IndexByValue` (a `Projection`) and
   `IndexByExpression`, so `Projection` means exactly one value and the walk checks the
   chain's mappings instead of counting values per step.

**Verified**
- Instrumented `Index._apply_mapping_`: all three behaviours live (14 literal-key,
  5 row-lookup, 4 expression-key), so none could be dropped.
- Full krrood suite 2155 passed; the 2 `test_object_diagram` failures are this container
  missing the Graphviz `dot` binary and fail identically on `main` (baseline: 2148 passed).
- Making `flat_variable` cached broke nothing in the suite beforehand — the identity
  invariant was unguarded, and now has a test.

**Lesson recorded in roadmap §13**: two earlier runs reported a third failure
(`test_generation_process`) purely because I rewrote source files while pytest was running.
Never edit the tree during a suite run.

**Next / outstanding**
- #186 awaits review. Whichever of #186 / #182 lands second adjusts #182's
  `isinstance(step, Index)` to name both index kinds.
- Still open for the developer, raised but not acted on:
  (a) `having` without `grouped_by` crashes on a `None` deref (`query.py:628`) on any query
  type; one-line fix verified, offered as its own focused PR;
  (b) name-based selection (`query["Body"]`) as a language feature, if wanted.

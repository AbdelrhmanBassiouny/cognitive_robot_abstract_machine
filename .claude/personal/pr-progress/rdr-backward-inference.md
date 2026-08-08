# `rdr-backward-inference` (#41) — branch-semantics family

## Round 1 (19e387a9) — the family landed

Developer chose "strategy family in `rdr/`" over methods-on-selectors and
leave-as-is; implemented onto #41 per the fold-don't-stack rule. Full account in
`roadmap.md` §15.

## Round 2 (b0107c76) — review fixes

11 threads. **10 applied and resolved; 1 left open deliberately** — the "is this
overkill?" thread, where the developer kept the family against my own
recommendation to collapse it. Standing rule: a thread answered differently from
its ask is theirs to close.

Applied:
- `ClassVar` → bound generic via `SubClassSafeGeneric`. `frozen=True` had to go
  (frozen cannot inherit from non-frozen).
- All methods are classmethods; `most_specific_for` returns the class.
- `GuardCondition` → `rdr/guard_condition.py`, which is what let the type alias
  drop its quotes (the reverse import was a real cycle).
- Abstract methods take `ConclusionSelector`; `GuardedBranch.node` →
  `child_expression`; docstring cross-references cut.
- **Real defect fixed**: `==` on symbolic expressions builds a truthy
  `Comparator`, so 9 assertions asserted nothing. Now compare `_id_`;
  re-mutation-checked with 3 mutants, each failing exactly one test.

## Next

- #41 is **draft**, head `b0107c76`, `mergeable_state: unstable` (CI in flight).
  **Still cannot subscribe to #41** — both tools refuse — so CI needs a manual check.
- **PR #148** (`claude/agents-subclass-safe-generic`, draft, off `main`): the
  AGENTS.md `SubClassSafeGeneric` rule. Open question left for the developer there:
  should it also mandate migrating `PhraseRule.construct` and the `SpecificityRule`
  families, or stay guidance for new code?
- One open thread on #41 for the developer to close.

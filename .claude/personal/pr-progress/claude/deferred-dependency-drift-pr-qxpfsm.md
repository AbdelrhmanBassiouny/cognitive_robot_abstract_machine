## PR #184 — `deferred-dependency-drift-check` (workflow-unification / dashboards)

Draft PR #184 off `main`, `bug` label. Branch
`claude/deferred-dependency-drift-pr-qxpfsm`, head `453795a6`. Full reasoning in the
plan's `roadmap.md` entries of 2026-08-20 (kickoff + implementation) and 2026-08-22
(this review round).

**The bug.** `build_dashboard.py` had no cross-item check: `_drift_description_of`
only compared an item's own `status` against its own live PR state, so an item
stacked on a dependency that will never land was never flagged.

**Design calls already settled — do not re-litigate**
- The stall predicate is *deferred, or PR closed unmerged*. Deliberately **not** a
  reuse of `is_ready_to_unblock_dependents()`, which is also false for a not-started
  or open-draft dependency; the item's original notes were wrong on this and the
  manifest no longer preserves that half.
- Drift is a **list**, because an item can carry manifest drift and a stalled
  dependency at once; `DashboardSummary.drift_flag_count` exists because the banner
  counts flags, not items.
- **Direct** `depends_on` only, naming the stalled dependency's own `depends_on` as
  the reparent target.
- Out of scope, checked rather than assumed: `_compute_next_steps` (no change
  needed), the `example/` fixture and screenshots (no new flag there),
  `check_dependency_readiness.py`.

**Review, 2026-08-22 — first round, eight threads, all resolved (`453795a6`)**
- Seven were one finding: the tests retyped the drift sentences production builds.
  `drift_descriptions` became `drift_flags` — a `ManifestDrift` carrying the
  `ManifestDriftCause` its `match` decides, or a `StalledDependencyDrift` carrying
  the dependency, its `StallReason` and the reparent targets — with the wording on
  `DriftFlag.description`. `_drift_description_of` split into
  `ManifestDrift._cause_of` + `.description`, the `match` and its case ordering
  untouched.

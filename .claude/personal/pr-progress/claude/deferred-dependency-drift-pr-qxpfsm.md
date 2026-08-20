## PR #184 — `deferred-dependency-drift-check` (workflow-unification / dashboards)

Draft PR #184 off `main`, `bug` label. Branch
`claude/deferred-dependency-drift-pr-qxpfsm`, commit `40d9d6dd`. Plan approved
2026-08-20; full reasoning in the plan's `roadmap.md` entry of the same date.

**The bug.** `build_dashboard.py` had no cross-item check: `_drift_description_of`
only compared an item's own `status` against its own live PR state, so an item
stacked on a dependency that will never land was never flagged.

**The design (both calls confirmed with the user, do not re-litigate):**
- `Item.is_stalled()` — deferred, or PR closed unmerged. Deliberately *not* a reuse
  of `is_ready_to_unblock_dependents()`, which is also false for a not-started or
  open-draft dependency; the item's own notes are wrong on this point.
- `Item.drift_description: str | None` → `drift_descriptions: list[str]`, plus
  `DashboardSummary.drift_flag_count` (the banner counts flags, not items).
- `_stalled_dependency_descriptions_of` — **direct** `depends_on` only, naming the
  stalled dependency's own `depends_on` as the reparent target.
- Out of scope, checked rather than assumed: `_compute_next_steps` (no change
  needed), the `example/` fixture and screenshots (no new flag there),
  `check_dependency_readiness.py`.

**Done — the item's work is complete and pushed**
- Branch cut off `main`, draft PR #184 opened with the `bug` label.
- Manifest recorded (`branch`/`session`/`pull_request_number`/`in_progress`);
  roadmap entry appended (2026-08-20 kickoff).
- TDD: 22 failing tests first, then the implementation. Suite green —
  `.claude/skills/plan-dashboard/tests/` **239 passed**, `.claude/hooks/tests/`
  **107 passed**. `scripts/format_docstrings.py` run on both touched Python files.
- Incidental DRY: `_resolved_dependencies_of` replaces the same `depends_on`
  resolution comprehension in `_compute_next_steps`, `_compute_ready_to_review`
  and `_dependencies_are_ready`.
- Verified end-to-end on the real case: building `rdr-refactor` flags
  `D-ui-rendering` and only it —
  `depends on 'D-ui-splice-fix', which is deferred - consider reparenting onto d-core-backend`.
  `D-ui` correctly unflagged. That plan reported **zero** drift before this change.
- Both dashboards republished (workflow-unification, rdr-refactor).

**Outstanding**
- CI not yet observed on #184. Nothing else known to be blocking.
- Conflict-adjacent with #157 (same test file, sidebar template region) — both
  additive; whichever-lands-second merges.
- PR is a draft and stays one until the user marks it ready.

**Watch out**
- Never subscribe to PR activity. Subscribing to tracking-issue #102 was refused by
  the permission classifier this session, so this session is not on that channel.
- This container needed `pip install pytest tqdm black docformatter typing_extensions`
  before the suite and the formatter would run.

## PR #184 — `deferred-dependency-drift-check` (workflow-unification / dashboards)

Draft PR #184 off `main`, `bug` label. Branch
`claude/deferred-dependency-drift-pr-qxpfsm`. Plan approved 2026-08-20; full
reasoning is in the plan's `roadmap.md` entry of the same date.

**The bug.** `build_dashboard.py` has no cross-item check: `_drift_description_of`
only compares an item's own `status` against its own live PR state, so an item
stacked on a dependency that will never land is never flagged. Real case:
`rdr-refactor`'s `D-ui-rendering` (in_progress) still depends on the deferred
`D-ui-splice-fix`.

**The design (both calls confirmed with the user, do not re-litigate):**
- `Item.is_stalled()` — new named predicate (deferred, or PR closed unmerged).
  Deliberately *not* a reuse of `is_ready_to_unblock_dependents()`, which is also
  false for not-started and open-draft dependencies; the item's own notes are wrong
  on this point.
- `Item.drift_description: str | None` → `drift_descriptions: list[str]`, plus
  `DashboardSummary.drift_flag_count` (banner counts flags, not items).
- `DashboardRenderer._stalled_dependency_descriptions_of` — **direct** `depends_on`
  only, naming the stalled dependency's own `depends_on` as the reparent target.
- Out of scope, already checked: `_compute_next_steps` (no change needed), the
  `example/` fixture and screenshots (no new flag there), `check_dependency_readiness.py`.

**Done**
- Branch cut off `main`, pushed; draft PR #184 opened with `bug` label.
- Manifest: `branch` / `session` / `pull_request_number` / `status: in_progress` recorded.
- Roadmap entry appended (2026-08-20 kickoff).
- `pytest` installed into this container; baseline `test_build_dashboard.py` = 142 passed.

**Next**
1. Failing tests first, new `# %% DashboardRenderer - stalled dependency drift` section —
   including the open-draft-dependency-does-not-flag guard and the both-drifts-at-once case.
2. Implement `is_stalled()`, `_stalled_dependency_descriptions_of`, the field rename.
3. Update existing `drift_description` readers (test ~line 420, template lines 667/751-754/796),
   plus one sentence in `SKILL.md`'s drift paragraph.
4. `scripts/format_docstrings.py` on touched Python files; run the full
   `.claude/skills/plan-dashboard/tests/` suite.
5. End-to-end: build `rdr-refactor`'s dashboard and confirm only `D-ui-rendering` is flagged,
   naming `d-core-backend`. Republish `/plan-dashboard` for both plans.
6. Re-draft PR #184 after any push.

**Watch out**
- Conflict-adjacent with #157 (same test file, sidebar template region) — both additive;
  whichever-lands-second merges.
- Never subscribe to PR activity. Tracking-issue #102 subscription was refused by the
  permission classifier this session.

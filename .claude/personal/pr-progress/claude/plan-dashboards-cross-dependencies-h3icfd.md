# claude/plan-dashboards-cross-dependencies-h3icfd — PR #253

`cross-plan-dependencies` in the `plan-dashboards` plan (#102), kicked off in `auto`
mode. Off `main`. Full reasoning is in that plan's `roadmap.md` section
"cross-plan-dependencies: the settled plan, 2026-09-03".

## Plan

1. Branch, draft PR #253, manifest state, roadmap section, this note. **done**
2. `DependencyReference` + validation: unknown plan, unknown foreign item, self-plan
   reference, malformed reference, missing plans directory, union-graph cycle check.
3. `items_by_reference` as the one resolver behind `_dependencies_are_ready`,
   `_dependency_chips_of`, `_compute_next_steps`, `_compute_ready_to_review`; foreign
   items classified against their own plan's repository; the silent-ready fault fixed;
   stacking depth left same-plan.
4. The chip: `plan-id/item-id`, tooltip with the foreign item's title, plan and live
   state, linked to that plan's dashboard when the URL cache has one.
5. `--plans-dir` on `build_dashboard.py`, `check_dependency_readiness.py` and
   `sync_manifest_status.py`, passed through by `refresh_dashboard.sh`.
6. Documents: `plan-schema.md`, `pr-data-fetching.md`, `dependency-readiness.md`,
   `plan-dashboard/SKILL.md`.
7. Three test suites green, `format_docstrings.py` a no-op on every touched file, push,
   description updated to match.

Tests first at every step, per TDD.

## Next

Step 2.

## Outstanding

- The five recorded cross-plan blockers are converted **after this lands**, not in this
  pull request: a manifest carrying a reference `main` cannot resolve fails validation on
  every dashboard run.
- `main`'s `plan_item_bootstrap.py` mis-indents fields when a manifest writes its items
  flush with `items:` (this plan's does), so the bootstrap write was done with the fixed
  copy that lives on `integration` (commit 8f80228f, branch not otherwise fetched). Not
  this item's bug to fix; worth knowing it is unlanded.
- Tracking-issue subscription for #102 was refused by this session's permission
  classifier, so no structural change on it will reach this session as an event.

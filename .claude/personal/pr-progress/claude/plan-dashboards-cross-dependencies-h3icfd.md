# claude/plan-dashboards-cross-dependencies-h3icfd — PR #253

`cross-plan-dependencies` in the `plan-dashboards` plan (#102), worked in `auto`
mode. Off `main`. Full reasoning is in that plan's `roadmap.md` section
"cross-plan-dependencies: the settled plan, 2026-09-03".

## Plan — all steps done

1. Branch, draft PR #253, manifest state, roadmap section, this note.
2. `DependencyReference` + validation: unknown plan, unknown foreign item,
   self-plan reference, malformed reference, missing plans directory,
   union-graph cycle check.
3. `items_by_reference` as the one resolver behind `_dependencies_are_ready`,
   the chips and both sidebar lists; foreign items classified against their own
   plan's repository; the silent-ready fault fixed; stacking left same-plan.
4. The chip: `plan-id/item-id`, tooltip with the foreign item's title, plan and
   live state, linked to that plan's dashboard when the URL cache has one.
5. `--plans-dir` on `build_dashboard.py`, `check_dependency_readiness.py` and
   `sync_manifest_status.py`, forwarded by `refresh_dashboard.sh`.
6. Documents: `plan-schema.md`, `pr-data-fetching.md`, `dependency-readiness.md`,
   `plan-dashboard/SKILL.md`.
7. Verified: plan-dashboard 287 tests (242 before), hooks + stack + add-plan-item
   318; `black --check` clean, `format_docstrings.py` a no-op on every touched
   file. Pushed at e2417d8e; description rewritten to match.

## Next

Nothing on this branch. It is a draft waiting on review.

## Outstanding

- **After this lands**, convert the recorded cross-plan blockers into references:
  `icra-experiments`' `integrated-simulation-pipeline` →
  `montessori-eql-stack/montessori_fast_inline_monitor`, its
  `failure-taxonomy-and-typing` and `experiment-c-in-simulation` →
  `knowledge-directed-perception/expectations-from-events`, this plan's
  `shared-pr-state-chips` → `bastler-package/bastler-package`, and
  `rdr-explanation`'s `rdr-why-answer` → `rdr-core-engine/d-core-backend`. Not
  before: a manifest carrying a reference `main` cannot resolve fails validation
  on every dashboard run for those plans.
- Landing hazard: #185 moves this file into `bastler`, and #184/#157/#206/#111
  also edit it. Whichever lands second merges. #184's `_resolved_dependencies_of`
  and this branch's `items_by_reference` should become one path in that merge.
- `main`'s `plan_item_bootstrap.py` mis-indents fields when a manifest writes its
  items flush with `items:` (this plan's does), so the bootstrap write used the
  fixed copy on `integration` (commit 8f80228f). Not this item's bug to fix.
- The tracking-issue subscription for #102 was refused by this session's
  permission classifier, so structural changes there reach no event here.

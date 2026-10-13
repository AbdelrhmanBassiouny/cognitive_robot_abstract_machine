## Next
Nothing on this branch. It is a draft waiting on review.


## Outstanding
- **After this lands**, convert the recorded cross-plan blockers into references:
  `icra-experiments`' `integrated-simulation-pipeline` →
  `montessori-eql-stack/montessori_fast_inline_monitor`, its
  `failure-taxonomy-and-typing` and `experiment-c-in-simulation` →
  `knowledge-directed-perception/expectations-from-events`, this plan's
  `shared-pr-state-chips` → `basstler-package/basstler-package`, and
  `rdr-explanation`'s `rdr-why-answer` → `rdr-core-engine/d-core-backend`. Not
  before: a manifest carrying a reference `main` cannot resolve fails validation
  on every dashboard run for those plans.
- Landing hazard: #185 moves this file into `basstler`, and #184/#157/#206/#111
  also edit it. Whichever lands second merges. #184's `_resolved_dependencies_of`
  and this branch's `DependencyResolver` should become one path in that merge.
- `main`'s `plan_item_bootstrap.py` mis-indents fields when a manifest writes its
  items flush with `items:` (this plan's does), so the bootstrap write used the
  fixed copy on `integration` (commit 8f80228f). Not this item's bug to fix.
- The tracking-issue subscription for #102 was refused by this session's
  permission classifier, so structural changes there reach no event here.

# claude/plan-dashboards-cross-dependencies-h3icfd — PR #253
`cross-plan-dependencies` in the `plan-dashboards` plan (#102), worked in `auto`
mode. Off `main`. Full reasoning is in that plan's `roadmap.md`, sections
"cross-plan-dependencies: the settled plan, 2026-09-03" and "What the review
round settled, 2026-09-03".


## Plan — all steps done
1. Branch, draft PR #253, manifest state, roadmap section, this note.
2. `DependencyReference` + validation: unknown plan, unknown foreign item,
   self-plan reference, malformed reference, missing plans directory,
   union-graph cycle check.

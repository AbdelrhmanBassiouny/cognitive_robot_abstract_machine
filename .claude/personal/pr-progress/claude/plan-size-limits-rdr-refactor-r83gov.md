# `plan-size-limits` / `split-rdr-refactor`

Personal-notes data only, so there is no branch and no pull request — the
designated branch `claude/plan-size-limits-rdr-refactor-r83gov` stays empty.
Precedent: the sibling `split-workflow-unification`.

## Plan

Split `rdr-refactor` (49 items, 4,372 lines) into plans each under the
15-item / 2,000-line budget, regenerate the branch index and drop the stale
cached dashboard URL, then record the item and republish.

## Done

- Measured the seam rather than taking the item's note. A by-wave split does
  not work: wave 0 alone is 26 items and 92% of the roadmap. Cut on subject
  instead, inside wave 0.
- Seven successors built by a script that copies every item field-for-field:
  `eql-core-and-code-generation` (6), `rdr-core-engine` (14),
  `rdr-interface-and-decorator` (5), `test-suite-fixes` (3),
  `rdr-explanation` (8), `rdr-engine-extensions` (10),
  `rdr-expert-framework` (3).
- 3 `depends_on` edges onto merged items dropped into notes; 7 live cross-plan
  edges recorded as blockers. That cost is larger than the sibling's 3 because
  `d-core-backend`/`d-core-single-class` are the trunk six items hang off.
- Seven roadmaps rewritten rather than sliced; the programme's working method
  is recorded once in `rdr-core-engine`'s and referenced from the others.
- Verified: 49 items each in exactly one plan, every successor passes
  `build_dashboard.validate_plan`, every carried field byte-identical to the
  source, branch index 125 → 125 with none unmapped and 42 remapped.
- Pushed as `397532690`. Item recorded `done` with its roadmap section.
- Measured after: **0 of 22 plans over budget**.

## Next

- Republish dashboards for the seven new plans and `plan-size-limits`, and
  record their URLs.
- `refuse-oversized-save` is now unblocked — both splits are done, which was
  its only gate.

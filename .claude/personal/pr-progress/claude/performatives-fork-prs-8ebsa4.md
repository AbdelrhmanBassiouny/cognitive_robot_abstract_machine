# Session: capture the performatives PR stack as a plan

Not a code branch — this session only authored plan data on
`claude/personal-notes`. No commits belong on this branch.

## Plan

Find every open/draft PR in the fork related to performatives, create a
`plan-create` plan for them, and publish its dashboard.

## Done

- Identified the stack: `main` → #55 (agreement) → #54 (cardinality) → #14
  (performatives core) → #15 (`PlanNode` is-a `Performable`). #11 (arithmetic)
  was split out of the same original PR and is already merged.
- Confirmed no existing plan (`rdr-refactor`, `dag-facade-hardening`,
  `workflow-unification`, `eql-verbalization`) covers any of them.
- Structure confirmed with the user: 2 waves (grammar prerequisites →
  performative layer), 1 track each, deferred follow-ups tracked as items.
- Created tracking issue #108 and subscribed this session to it.
- Pushed `plans/eql-performatives/{plan.yaml,roadmap.md}` (8 items) via
  `save-plan.sh`; validation clean, 0 drift.
- Published the dashboard:
  https://claude.ai/code/artifact/81c0f6c6-9f54-4c0d-afe2-01178ab57322
  and recorded its URL in `_generated/dashboard-urls.yaml`.

## Next

- Nothing pending in this session. The plan's own first actionable item is
  #55's three-file conflict against `main` (`coreference_processor.py`,
  `realization.py`, `parts_of_speech.py`), which blocks the whole stack —
  `/plan-item-resolve eql-performatives agreement`.
- The master index was not refreshed; `/plan-dashboard` with no argument
  would add `eql-performatives` to it.

## Noticed, not fixed

`save-plan.sh` warns that branch `conditions-root-drop-dead-parent-recovery`
(PR #89) is listed in both `rdr-refactor` and `dag-facade-hardening`. Pre-existing,
unrelated to this plan; the index keeps the first plan it sees.

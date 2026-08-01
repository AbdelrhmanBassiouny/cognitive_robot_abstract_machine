# PR #122 — ready-to-review-merged-dependency (workflow-unification / dashboards)

Draft PR #122, `bug` label, based on fork `main`, subscribed. Session:
https://claude.ai/code/session_01Ltrz1G8qwSHgo6jyfeV1EU

## Plan

Kicked off via `/plan-item-kickoff`; user confirmed the oversight reading, then
approved implementing in this session. Fix `_compute_ready_to_review` so a merged
dependency stops excluding its dependent, TDD, one root cause.

## Done

- Failing tests first (`assert [] == ['b']`), then the fix.
- `Item.is_ready_for_dependent_review()` = `has_open_pull_request or is_effectively_done()`,
  beside `is_ready_to_unblock_dependents()`; `_compute_ready_to_review` calls it.
- 7 new tests, 229 green (was 222). One existing assertion changed deliberately: the
  example-locking test, whose own docstring says it exists to fail rather than let the
  walkthrough go stale.
- Walkthrough prose + `dashboard-overview.png` regenerated (`Ready to review (2)`).
- Manifest + roadmap saved (notes `bd2f3f19`), tracking issue #102 commented, dashboard
  republished.

## Rejected, do not revive

Consolidating onto `is_ready_to_unblock_dependents()` — suggested in the item notes, the
roadmap and issue #102's comment, all three wrong. It excludes `OPEN_DRAFT`, which
ready-to-review deliberately includes. The two predicates differ by exactly that state.

## Next

- Await review on #122; convert back to draft after any push.
- Binary conflict with #120 on `dashboard-overview.png` is expected — whoever lands
  second re-regenerates. Recipe (no script exists): render `example/` with
  `build_dashboard.py`, headless Chromium
  `--blink-settings=preferredColorScheme=0 --window-size=1280,…`, crop to a 100px bottom
  margin.
- Flagged for `git-identity-from-personal-notes`: its diagnosis says `GIT_AUTHOR_*` is
  unset; in this environment it is set, so the env-var route it names is already in force.
  Recorded in the roadmap and on #102.

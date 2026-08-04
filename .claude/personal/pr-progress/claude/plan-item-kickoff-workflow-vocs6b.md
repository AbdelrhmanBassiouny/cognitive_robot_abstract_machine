# plan-item-bootstrap — draft PR #143

Item `plan-item-bootstrap` (plan `workflow-unification`, track `personal-data`),
based on fork `main`, `depends_on: []`.

## Plan

Two operations in one module, each caller taking only what it needs:

- **record** — write/update the item's `plan.yaml` entry + `roadmap.md` section,
  set its status, run `save-plan.sh`. `/add-plan-item` and `/plan-item-kickoff`.
- **open** — create + push the branch, open the draft PR, write `branch`,
  `session`, `pull_request_number` back and flip to `in_progress`.
  `/plan-item-kickoff` only.

Files: `.claude/hooks/plan_item_bootstrap.py`, its test module under
`.claude/hooks/tests/`, one appended constant block in
`resolve-personal-notes-config.sh`, a new post-approval step 6 in
`plan-item-kickoff/SKILL.md` (whose opening promise is rewritten), one line in
`.claude/hooks/README.md`, and one line on #135's branch (permission granted).

## Done — implementation complete

- Bootstrapped by hand in the order the item prescribes: branch, draft PR #143,
  manifest, roadmap, dashboard, then code. Subscribed to #143 and to #102.
- `plan_item_bootstrap.py` + 21 tests (57 under `.claude/hooks/tests`, was 36;
  194 plan-dashboard, unaffected). Each test mutation-checked.
- Constant, `plan-item-kickoff` step 6 + rewritten opening promise, README line.
- Live probe (#144, closed): creation succeeds, `draft: true` honoured, but the
  script's PR is attributed to `claude[bot]` while the session's tool attributes
  it to the user. Design changed for it — `open` takes `--pull-request-number`
  for a PR the caller already made; the creating path stays for unattended runs.
- One line pushed to #135's branch (`4186b3f7`) with a comment explaining it.
- Plan manifest + roadmap updated with the probe findings; dashboard republished;
  #143's description rewritten to match what it now does.

## Review round 2026-08-04 — 19 comments, applied in `1b95bee8`

- The manifest's vocabulary now has one home: `PlanField`, `PlanDocument`,
  `HookScript`, `ItemStatus`, `ItemFieldLine`. Tests import them and assert on
  rendered lines; `FOLDED_FIELD_PATTERN` is generated from `FOLDED_PLAN_FIELDS`;
  test paths resolve through the production `PlanLocation`.
- Test manifest/roadmap moved to `tests/fixtures/` as real `.yaml`/`.md`.
- Refusals are dataclasses with typed context + `suggest_correction()`, per
  krrood's `DataclassException` idiom in a stdlib-only base (decision 12).
- Step 6 now names both places the approved plan is written: `roadmap.md` via
  `record`, and the PR-progress note via `save-pr-progress.sh`.
- 60 tests under `.claude/hooks/tests` (was 36 at branch start). 17 of 18
  threads replied to and resolved.

## Next

- **One open thread, waiting on the user**: whether to re-base this item onto
  the upstream chain to unify `ItemStatus` with `build_dashboard.py`. Replied
  that basing on #111 would *not* unify it (that file only moves in
  `dev-tooling-python-package`, `not_started`), and recommended leaving the
  five-member overlap to that migration. Do not act until they answer.
- CI on #143 was red at the empty bootstrap commit for an apt breakage in
  container setup (`xvfb` deps), unrelated and noted on the PR; watch whether it
  clears on the implementation commits.
- Residue needing out-of-harness deletion: the remote branch
  `claude/plan-item-bootstrap-probe-vocs6b` (sessions cannot delete branches).

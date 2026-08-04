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

## Done

- Bootstrapped by hand in the order the item prescribes: branch pushed, draft
  PR #143 opened, manifest updated (branch/session/PR/`in_progress`), roadmap
  section added, `save-plan.sh` run, dashboard republished. Subscribed to #143
  and to tracking issue #102.

## Next

1. Failing tests first, then `plan_item_bootstrap.py`.
2. Skill/README/constant wiring.
3. `pytest .claude/hooks/tests` + the plan-dashboard suite.
4. One throwaway live PR creation against the fork — settles whether creation
   succeeds, `draft: true` is honoured, and which identity it is attributed to
   (the 2026-08-04 probe stopped at a 422 on `head`).
5. The one line on #135's branch, with a comment on #135.

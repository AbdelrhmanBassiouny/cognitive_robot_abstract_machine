# PR 154 manifest dependency

Manifest-only task, no code and no pull request on this branch. Make
`integration-branch` (#154) depend on `manifest-currency-first` (#151) in the
`workflow-unification` plan, then republish the dashboard.

## Done

- Confirmed the intended chain from the roadmap's 08-11 entry: #151 rebased onto
  #139, so `#139 → #151 → #154` is linear and the recorded
  `depends_on: [stack-maintenance-executor]` was the kickoff-time parent.
- `depends_on` set to `[manifest-currency-first]` — direct parent only, matching
  how every other item in this manifest states one edge.
- Item `notes` and a `roadmap.md` entry record the correction and the outstanding
  reparent.
- Saved with `save-plan.sh` (personal-notes `0ff24881..127d9c42`).
- Dashboard rebuilt against live GitHub (0 drift, 0 auto-corrections) and
  republished to the cached URL; the item now renders `needs
  manifest-currency-first` at indent level 4.
- Structural record posted on tracking issue #102.

## Next

Nothing outstanding on this branch. Outside it, and deliberately not done here:
#154's base ref on GitHub is still `claude/plan-item-kickoff-workflow-koufa6`
(#139's branch), so the pull request itself is not yet reparented onto #151's
branch.

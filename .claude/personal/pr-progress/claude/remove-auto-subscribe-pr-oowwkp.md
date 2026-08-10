# Remove the "subscribe to your own PRs" rule

## Plan

Two halves, because the rule lives in two places:

- **Part A - personal notes** (`claude/personal-notes`, not this branch):
  replace "always subscribe to every PR you open" with "never subscribe to a
  PR", and fix the three sections written around that assumption
  (Scheduled checks, Comment routing, When your PR's job ends).
- **Part B - repo-tracked files** (this branch): the same flip in the
  `/setup-personal-notes` starter notes, plus the wording elsewhere that
  assumed a session holds an item-PR subscription.

Scope decision: pull requests only. Plan **tracking-issue** subscriptions use
the same tool but are a coordination mailbox, not a PR a session owns, so
`/plan-create`, `/plan-item-kickoff` and `/plan-item-resolve` keep theirs.

## Done

- Part A: `cram-notes.md` updated and saved (notes branch `8079fa0b6`).
- Part B, commit `ad6dfb869`, pushed:
  - `setup-personal-notes/starter-notes.md` - never-subscribe default.
  - `plan-dashboard/plan-schema.md`, `hooks/session-start.sh` - dropped
    "(in addition to your own item's PR)".
  - `stack/README.md`, `stacked-pr-maintenance/SKILL.md` - reworded the two
    passages that explained behaviour via a session being subscribed to a PR.
- Verified: `bash -n session-start.sh` clean; every surviving `subscrib` hit
  under `.claude/` is a tracking-issue subscription, an unsubscribe, or a
  prohibition. `.claude/hooks/tests` never referenced the changed strings
  (pytest is not installed in this container, so the suite was not run).

## Next

- No PR opened yet - waiting on the user to ask for one. If asked: draft,
  `bug` label not applicable, session link in the description.
- Per the new rule itself: do not subscribe to that PR once it exists.

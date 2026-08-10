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

- Draft PR #153 opened against `main`, session link in the description, no
  `bug` label (not a bug fix). Not subscribed, per the rule it introduces.
- Tracked as plan item `no-pr-subscriptions` in `workflow-unification`
  (track `personal-data`, status `in_progress`, PR #153), recorded via
  `plan_item_bootstrap.py record` + `open`, with a roadmap section and a
  `notes` entry. Dashboard republished.

## Next

- Nothing outstanding. CI on #153 was not checked from here; the repository-
  wide `greenlet` 3.5.5 resolve failure noted on #151 affects every PR until
  it is constrained.
- The dashboard URL cache was stale: it held
  `07123af6-...` for this plan, which no longer resolves. Republished to the
  live page `af60607f-...` and corrected the cache. That is the same failure
  the plan's own `dashboard-url-recording` item exists to fix.

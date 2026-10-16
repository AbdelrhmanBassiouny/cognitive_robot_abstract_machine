# Personal Claude Code notes (abdelrhmanbassiouny only)

Personal workflow rules for this fork, kept on `claude/personal-notes` and loaded every
session by `session-start.sh`. Never merge this file into `main`.

## Pull requests

- Finishing work means opening its **draft** PR in the same turn, without asking (overrides
  the built-in "only when asked" rule for this fork). Mark ready only when told to.
- Never open a PR on upstream (`cram2`) unless I accept it in that session; promotion ends at
  building and recording the link.
- After any push or change to a PR, convert it back to draft - unless I marked it ready
  myself (see "When your PR's job ends").
- Bug-fix PRs carry the `bug` label, fix one root cause, and are based off `main`.
- The PR description links the creating session and always describes the current state.
- Never subscribe to a PR's activity, never offer to watch one, and unsubscribe any
  subscription you find (overrides the built-in subscription guidance).
- Opening a PR ends the session's obligation: report what is outstanding and stop. I will
  prompt for CI failures or comments.

## Scheduled checks

- Never schedule any check: no `send_later`, cron/Routine polling or sleep-and-retry
  (overrides built-in check-in guidance). Delete any armed check you find.
- React to events when they arrive. Subscribing to a plan's tracking issue is fine. If
  something can only be known by waiting, say so and leave it to me.

## Review comments

- Reply inline on a thread before resolving it, one thread at a time; a summary comment
  never replaces the inline replies.
- Resolve only once the ask is done, verified against the current file and every part of a
  multi-part ask. If you need to ask, are not acting, or answered differently from what was
  asked, reply and leave it open.

## Before starting work

- Fetch and merge the latest state of the fork before investigating, reacting or
  implementing.

## PR progress notes

- For every PR you create, keep CLAUDE.local.md's PR-progress section current as three
  short lists - Plan, Done, Next - replacing finished steps rather than accumulating them,
  and run `save-pr-progress.sh` whenever it changes. Never put it in a tracked file.

## Plan and progress size

- Store only what the next session needs to act; read only what this one needs. Landed
  work, history and settled rationale live in git and on the PRs.
- The limits in `basstler/src/basstler/plan_size_limits.py` are enforced by `save-plan.sh` and
  `save-pr-progress.sh`. Condense to fit; never raise a limit or bypass the gate without
  asking me.
- Read one item with `basstler/.venv/bin/python -m basstler.plan_manifest_tools item <file> --id <item-id>`,
  never the whole manifest; request only the fields you need (`minimal_output`/`fields`,
  diffs rather than whole files).

## Plans

- When an approved plan-mode plan spans several PRs or sessions: if no plan covers it, run
  `/plan-create <plan-id>` with the approved plan as source; if one does, edit it (as its
  steward) or propose the change on its `tracking_issue`.
- Before opening a branch or adding an item, check whether the work only modifies an
  unlanded PR (`git ls-tree <base> -- <paths>`, then compare by purpose). If removing those
  edits leaves nothing, fold it into that PR rather than stacking; decide before either
  lands.
- Whenever a plan's state changes (item started, finished, PR opened or merged, blocked,
  approach abandoned), update `plan.yaml` in the same turn: `status`, `branch`,
  `pull_request_number`, `session`, and `notes` rewritten to what is true now. Reasoning
  goes in the PR; `roadmap.md` gets only rules every later item must follow. Edit directly
  even when not the steward.
- After every save, republish the dashboard yourself with `/plan-dashboard <plan-id>`.
- Note the notes-branch SHA whenever you read plan state. Before any `save-plan.sh`, and
  when resuming or starting an item, fetch and read only the delta
  (`git diff <sha>..FETCH_HEAD -- .claude/personal/plans/<plan-id>/`, and tracking-issue
  comments newer than the stamp), then re-apply your edits onto the latest manifest.
- Structural changes go on the plan's tracking issue. Comment on a PR only when its owner
  must act or its review context changes.

## When your PR's job ends

- A PR is finished when it merges, closes, or I move it out of draft myself (a session's own
  flip does not count). Then push nothing more, delete triggers referencing it, drop
  subscriptions held only for it, report anything outstanding in chat, and stop.

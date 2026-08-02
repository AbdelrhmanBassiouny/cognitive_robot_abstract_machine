# Personal Claude Code notes (abdelrhmanbassiouny only)

These are personal workflow preferences for working on this fork, not project
conventions. They live on the `claude/personal-notes` branch only and are pulled
into every session by the `.claude/hooks/session-start.sh` hook on `main`; this
file itself must never be merged into `main`.

## Pull requests

- Always open pull requests as **drafts**. Never open a PR as ready-for-review
  by default; mark it ready only when explicitly told to.
- Always convert a PR back to **draft** after pushing any commit to it or
  otherwise modifying it, even if it was previously marked ready for review.
  Mark it ready again only when explicitly told to.
- Bug-fix PRs must always carry the **`bug`** label.
- Keep bug-fix PRs focused: one root cause per PR, based off `main`, no
  unrelated cleanup bundled in.
- Always include a link to the session that created the PR in the PR
  description.
- Keep the PR description up to date: after pushing any change that alters
  what the PR does, update the description to match. Never leave it
  describing an earlier state of the PR.
- Always subscribe to all events on every PR you open - including plain
  conversation comments, not just inline review comments - and handle each
  event with an explanation summary in the session chat.

## Scheduled checks

- **Never set up a regular or scheduled check of any kind.** No `send_later`
  self check-ins, no cron/Routine polling, no "re-arm silently in an hour",
  no `sleep`-and-retry loops waiting for CI or a review. This overrides any
  standing instruction to schedule a follow-up check-in - including the
  built-in PR-subscription guidance that asks for one roughly an hour out.
- React to events when they actually arrive (webhook activity, or my asking),
  not on a timer. Event subscriptions themselves are fine and wanted - it is
  the timed polling that is not.
- If something genuinely cannot be known without waiting, say so and leave it
  to me rather than arming a check.
- If you find a scheduled check already armed from an earlier session, delete
  it rather than letting it fire or re-arming it.

## Review comments

- Resolve a review comment thread only once you have genuinely done what it
  asked. If instead you need to ask what to do, or you are not taking an
  action, do not resolve it — reply explaining the situation and asking the
  question.
- Always reply to a PR comment explaining what you did before resolving it.

## Before starting work

- Always fetch, pull, and merge from the original repository you cloned (the
  user-owned repository, whether it is a fork of another or not) before
  investigating problems, reacting to events, or implementing features, so
  you are always working from its latest state.

## PR plan and progress tracking

- For every PR you create, maintain a plan/progress/next-steps note in
  CLAUDE.local.md's PR-progress section (the block between the
  BEGIN-PR-PROGRESS/END-PR-PROGRESS markers, written automatically by
  session-start.sh). Initialize it with a short plan as soon as you start
  real work on the PR.
- Keep it current: update it whenever the plan changes, whenever you update
  your task list, and before ending any turn that changed either. Run
  `save-pr-progress.sh` whenever you update it.
- Never write this plan into any file tracked on the PR branch itself. It
  must live only in the PR-progress section, which is stored on the
  `claude/personal-notes` branch and is never merged.

## Plan-mode approval → persistent plans

- The moment a normal Claude Code plan-mode plan is approved, before implementing, judge whether
  the work spans multiple PRs/branches/sessions to complete. If it's contained in one PR from this
  session, just implement it - do not invoke anything below for it.
- If it spans multiple PRs/sessions:
  - **No existing plan covers it**: invoke `/plan-create <plan-id>`, handing it the just-approved
    plan-mode markdown directly as source material - it's valid input under that skill's "existing
    freeform doc to migrate" case even though it only lives in this conversation, not a file.
  - **An existing plan covers/extends it** (check auto-discovery on the current branch, or ask):
    if this session is that plan's designated planning/steward session, edit `plan.yaml` directly
    and run `save-plan.sh` + `/plan-dashboard <plan-id>`; otherwise comment-propose it on the
    plan's `tracking_issue` instead of editing directly - see
    `.claude/personal/plans/README.md`'s "Proposing structural changes" section.
- This is the moment that decides whether the plan gets captured durably or evaporates once the
  session ends - do not let it pass by default.

## New PR/item, or a change to one already in flight?

- **Ask this before opening any branch or adding any plan item, and prefer the change.** Something
  is genuinely new only if it still stands alone once the work before it lands. If it *modifies*
  what an unlanded PR/item introduces, it is that PR's work - stacking it reflects the order I
  wrote things in, not a real dependency.
- The test is mechanical, so run it rather than judging by feel:
  `git ls-tree <base-branch> -- <paths the work touches>`. Empty output means those files do not
  exist on the base yet, so whichever PR introduces them owns them, and from the base's point of
  view the two are one addition.
- Costs of splitting anyway, all of which we have now paid: the earlier PR ships a state nobody
  should run; the later one spends its review re-explaining the first; if the earlier one is live
  infrastructure, landing it alone regresses that infrastructure until the later one follows; and
  two PRs both touching unlanded files can independently build the same file without noticing.
- When it has already happened, fold rather than sequence - and decide *before* either lands,
  because afterwards a duplicate is a merge conflict instead of a choice.
- Split on what the work *is*, never on when I thought of it. One PR with a coherent story beats
  two that only make sense read in order.
- Precedent: #133 folded into #117, #117 folded into #106, and #110 turned out to be building
  `.claude/stack/routine-prompt.md` while #106 was building `POINTER.md` - the same artifact,
  twice, because nobody ran the check above.

## Keeping plan state current

- **Whenever anything happens that changes a tracked plan's state, update that plan's
  `plan.yaml` and its data - immediately, in the same turn.** Starting an item, finishing
  it, opening or merging its PR, blocking on something, abandoning an approach, or reaching
  a conclusion that changes what an item means: all of it goes into the manifest, not only
  into the chat.
- What to write: the item's `status`, `branch`, `pull_request_number` and `session` as soon
  as each is known, plus `notes` when a conclusion changes the item's substance. Record the
  narrative and the reasoning in the sibling `roadmap.md` - especially a premise that turned
  out to be wrong, a decision I overrode, or a dependency rule that no longer applies.
- Then run `save-plan.sh <plan-id>` so it lands on the personal-notes branch, and immediately
  run `/plan-dashboard <plan-id>` yourself to republish the dashboard. A script cannot call
  the Artifact tool, so only a live session can - do not stop at telling me it needs doing.
- **Always republish the dashboard whenever a plan's data changes, whatever changed it and
  whichever session did it**: `save-plan.sh`, `/plan-create`, a refresh's manifest
  auto-correction, or a hand edit on the personal-notes branch. Republish in the same turn
  as the change, so a published dashboard is never older than the manifest behind it.
- Do this even when the session is not the plan's steward. Prefer editing `plan.yaml`
  directly and saying so over leaving the manifest stale; a comment on the `tracking_issue`
  is a useful record of *why*, but it is not a substitute for the state itself being right.
  This overrides the propose-don't-edit guidance above for state that is already fact.
- A plan whose manifest lags behind reality is worse than no plan: every dashboard, kickoff
  and resolve run downstream reads it as truth.

<!--
Add new personal-only rules below this line. Keep each rule short and
imperative, same style as above.
-->

## Plan updates: recheck deltas, don't reread

- Note the personal-notes commit SHA whenever you read plan state (the fetch you read it
  from); it is your staleness stamp.
- Recheck for plan/tracking-issue updates at these moments: (a) when I prompt you after
  you have been idle or stale for a while, (b) when starting a new task or plan item, and
  (c) **always immediately before any `save-plan.sh` write** - fetch first and re-apply
  your edits onto the latest manifest, never write back a copy loaded earlier (two silent
  stale-save reverts are already on record in workflow-unification's roadmap).
- Recheck means reading the *delta only*: fetch the notes branch, then
  `git diff <last-seen-sha>..FETCH_HEAD -- .claude/personal/plans/<plan-id>/`; for the
  plan's tracking issue, read only comments newer than your stamp. Do not reread whole
  files that a diff can summarize.
- Keep tracking-issue subscriptions where they exist: events are the push channel for
  structural changes; this recheck is the pull channel for everything else (most manifest
  edits produce no event at all). Neither replaces the other.

## Comment routing for plan changes

- The plan's tracking issue always gets the structural record.
- Comment on a PR only when that PR's owner must act or its review context materially
  changes (scope change, landing hazard). Pure FYIs go in the manifest/roadmap only - PR
  comments wake subscribed sessions, so keep them action-only.

## When your branch merges or closes

- The moment a PR your session owns is merged or closed: unsubscribe from its activity
  (`unsubscribe_pr_activity`), delete any armed triggers or check-ins that reference it
  (`list_triggers` → `delete_trigger`), and stop any polling or monitoring tied to it.
  Nothing may stay armed or subscribed for a finished branch.
- This includes subscriptions taken out only for that branch's sake (e.g. a tracking-issue
  subscription held solely to steward that one item).


---
name: plan-item-kickoff
description: Gather everything available about one tracked plan item (its plan.yaml entry, roadmap.md history/design context, its dependency chain's live GitHub state, and patterns from sibling items in the same track - landed or still in flight) and propose a concrete implementation plan via plan mode, without writing any code. Invoke as "/plan-item-kickoff <plan-id> <item-id>". Use when starting work on a specific item from a plan-dashboard's "Start now" link, or when the user asks to "start", "kick off", or "plan out" a specific tracked item.
allowed-tools: Bash, Read, Grep, Glob, Skill, EnterPlanMode, ExitPlanMode, mcp__github__list_pull_requests, mcp__github__pull_request_read, mcp__github__get_file_contents, mcp__Claude_Code_Remote__subscribe_pr_activity
---

# Plan Item Kickoff

Generic, plan-agnostic — nothing here may hardcode a specific plan id, item,
or branch. Gathers everything a session doing this item's work would
actually want before starting, then hands the user a concrete
implementation plan via plan mode. **This skill never writes code, creates a
branch, or pushes anything** — it is a research-and-planning skill, not an
implementation one. Whether to implement the approved plan in this session
or a fresh one is the user's call, made after they see it.

## 1. Resolve the item

Source the shared config script — it resolves the personal-notes
remote/branch precedence and defines `DEPENDENCY_READINESS_DOCUMENT` (used in
step 2):

```bash
source .claude/hooks/resolve-personal-notes-config.sh
git fetch "${NOTES_REMOTE}" "${NOTES_BRANCH}" --quiet
```

Load `<plan-id>/plan.yaml` + `roadmap.md` off `FETCH_HEAD` (same resolution
`plan-dashboard`'s own step 1 uses — read `resolve-personal-notes-config.sh`
if the precedence is unclear rather than re-deriving it). Find the item by
`id` (or `branch` if `id` is unset) among `items[]`.

If the plan id or item id doesn't resolve, stop and list what's actually
available (every plan id under `plans/*/plan.yaml`, or every item id in the
named plan) rather than guessing which one was meant.

If the plan has a `tracking_issue`, subscribe to it now via
`mcp__Claude_Code_Remote__subscribe_pr_activity` (it takes a plain issue
number the same way it takes a PR number). This session may go on to create
this item's branch and PR without a fresh session ever starting — the
subscription `session-start.sh` sets up for an already-checked-out item
branch never fires in that case — so subscribing here, before gathering
context, is what actually covers a kickoff that turns into an
uninterrupted implementation session. Skip this step entirely if the plan
has no `tracking_issue`. The call is idempotent, so it's safe to run even
if something already subscribed this session. If it errors, don't let that
fail the skill: mention it in passing when presenting the plan (step 5) and
continue — subscribing is a convenience for staying aware of concurrent
structural changes, not a precondition for planning this item.

## 2. Gather the item's own context

- `title`, `notes`, `blockers`, `track` (and that track's own `name` +
  `description`), `wave`.
- `depends_on`: follow `${DEPENDENCY_READINESS_DOCUMENT}`'s bulk-fetch-and-check
  procedure, for `--item <item-id>`. The plan needs to know exactly what
  branch to base new work on, and whether it's actually safe to build on
  yet: flag any dependency the script reports not ready for explicitly in
  the proposed plan's assumptions, instead of quietly proceeding as if it
  were ready.
- Whether the dependency branch actually **carries the files this item
  builds on**. Readiness answers "is it safe to stack on this?", not "is
  what I need here?" — and in a repository where several siblings are in
  flight at once, the helper, fixture or config file the item's `notes`
  assume can easily live on a *different* sibling than the one
  `depends_on` names. Enumerate what the item needs (from its own `notes`,
  and from any cross-note a sibling's PR description or the roadmap
  addressed to it), then confirm on which branch each one exists — a
  `git fetch` plus `git ls-tree`/`git show` answers this directly. If they
  turn out to be split across branches, that is a base/stacking decision,
  not an implementation detail: surface it as an explicit choice in step 5
  rather than silently picking one branch and working around what's
  missing from it.
- Read `roadmap.md` **in full** — do not stop at grepping for this item's
  id/branch/title. A roadmap routinely records decisions, conventions, and
  design rationale in sections that don't name every item individually
  (e.g. "Finalized design decisions", "Decisions locked in", a track's own
  design notes, a prior review round's resolution) — those decisions bind
  this item just as much as a direct mention would, and missing one means
  either proposing a plan that contradicts an already-settled call or
  asking the user something they've already answered. After the full read,
  also grep for the item's id/branch/title specifically, to catch any
  focused mention a full read might skim past. If `roadmap.md` is large
  enough that a full read is genuinely impractical, say so explicitly and
  name which sections you read in full versus grepped — don't silently
  read only part of it and present the plan as if it were comprehensive.

## 3. Gather sibling context from the codebase

Read what other items in the **same track** actually changed —
`mcp__github__pull_request_read` for the diff/description, or
`mcp__github__get_file_contents` for the result — to learn the real
pattern this item should follow, rather than inventing a shape from
roadmap prose alone. Note file layout, testing conventions, and any
review-driven design decisions recorded in those PRs' descriptions that
this item should also honor (a later sibling in a stack often encodes a
correction the reviewer made on an earlier one).

Siblings that are `done` are the obvious sources, but do not stop there:
read every sibling this item stacks on or sits beside, whether or not its
pull request has landed. In a stacked-PR repository the pattern to copy
routinely hasn't merged yet — a whole wave can be in flight at once, in
which case a `done`-only reading gathers nothing at all and the plan gets
invented from prose.

If the item's own branch already exists (partial work, e.g. from a false
start), read what's actually there via `mcp__github__get_file_contents` or
a local `git fetch` + `git show` before proposing anything — the plan must
build on real state, not restate a fresh start over existing work.

## 4. Cross-check the standing conventions

Read `roadmap.md`'s standing-conventions section (however it's titled in
this plan) and this repository's own `AGENTS.md`. Every step in the
proposed plan must honor both — SOLID, TDD, no abbreviations, dataclasses,
docstring conventions, whatever the repo's own rules are — not just what
the item's own `notes` happen to mention.

## 5. Propose the plan — plan mode, no code

Before drafting the plan or raising any open question with the user, check
whether the question is already answered: re-read the relevant part of
`roadmap.md`, the item's own `notes`, and any cited sibling PR — a design
call, a naming convention, or a scope boundary is very often already
decided somewhere in that material. Only surface something as an open
question if, after that check, it's genuinely still unresolved; asking the
user something the roadmap already answered means the read wasn't thorough
enough. If you do ask, say what you checked and why it still looks open, so
the user can correct you quickly with a pointer if you missed it.

Search the **consumer** side too, not only the planning documents. "Should
this item produce X?" is usually settled by whether something would read
X: grep the dependency branches for a document, script or prompt that
already points at the artifact in question, or that plainly needs one. A
file that nothing consumes is the YAGNI the plan should drop; a file two
callers already assume is not an open question at all.

Enter plan mode and present, via `ExitPlanMode`, a concrete implementation
plan: what changes, in which files, in what order, and how each part will
be verified (tests first, per TDD). Cite where each part of the plan came
from (the item's own notes, a specific sibling PR, a `roadmap.md` section)
so the user can sanity-check it against the source instead of just trusting
it. Flag explicitly, never silently paper over:

- Any dependency that isn't actually ready to build on yet (step 2).
- Any conflict between the item's `notes` and what a sibling PR or
  `roadmap.md` actually says.
- Anything the gathered context left genuinely unresolved after the check
  above — say so rather than filling the gap with an assumption.

End the plan with the bookkeeping that keeps the plan itself true: setting
the item's `status`, `branch`, `pull_request_number` and `session` in
`plan.yaml`, running `${SAVE_PLAN_SCRIPT}`, republishing the dashboard via
`/plan-dashboard <plan-id>`, and recording the PR-progress note. The
session that implements this plan may be a fresh one that never read the
user's own conventions, and a plan whose manifest lags behind reality is
read as truth by every dashboard and kickoff downstream.

Do not touch git, create a branch, or write any code in this skill — its
only output is the plan itself.

# Keeping a plan's manifest current, at every transition

Shared by every skill that can change what a plan records: `plan-create`,
`add-plan-item`, `plan-item-kickoff`, `plan-item-resolve`, `plan-dashboard` and
`stacked-pr-maintenance`. The rule lives here once rather than being restated in
each of them.

## The rule

**Write the manifest and republish the dashboard first, at every point that makes
a recorded field stale** — not at the end of the work that made it stale.

A transition is any moment one of these stops being true: the item's `status`, its
`branch`, its `pull_request_number`, its `session`, its `notes`, its `blockers`, or
the plan's own shape. Starting work, opening a pull request, finding a blocker,
clearing one, changing what an item means, adding an item, adding a plan.

None of that waits on the work, because none of it depends on the work. Doing it
afterwards leaves a window — often the whole length of an implementation — in which
`plan.yaml` says something that is not true, and every dashboard, kickoff and
resolve run downstream reads it as truth.

This generalizes what `plan-item-kickoff`'s bootstrap step already does for one
moment. It is the same argument, applied to every other transition.

## Run this rather than editing by hand

```bash
source .claude/hooks/resolve-personal-notes-config.sh

# Set any recorded field. No roadmap section required.
python3 "${PLAN_ITEM_BOOTSTRAP_SCRIPT}" update \
    --plan <plan-id> --item <item-id> \
    [--status <status>] [--branch <branch>] [--pull-request-number <number>] \
    [--session <url>] [--notes <file>] [--blockers <file> ...]

# Ask what local git contradicts, before or after a transition.
python3 "${PLAN_ITEM_BOOTSTRAP_SCRIPT}" check --plan <plan-id> --item <item-id>
```

`update` writes prose from files because a note is routinely longer than a shell
invocation should carry. `check` exits `manifest_is_stale` when anything is stale
and prints one finding per contradicted field, so a caller can act on the status
alone.

**Extending an existing note needs one conversion.** A folded scalar hands its
paragraph breaks back as *single* newlines, and the file `--notes` reads marks them
with *blank* lines — so appending to a note read out of `plan.yaml` and writing it
straight back collapses the whole thing into one paragraph. Replace each newline in
what you read with a blank line before you append to it.

Use `record` instead when the transition also deserves a roadmap section — a
decision, a reversal, a conclusion that changes what the item means. `update` is
for the state; `record` is for the story.

## What `check` does and does not cover

It compares the manifest against **local git only**: a recorded branch that was
never published, an item still `not_started` while its branch exists, a published
branch with no session or pull request recorded.

It deliberately does not ask GitHub. The dashboard already compares the manifest
against live pull request state on every refresh, and duplicating that would be a
second implementation of it. What nothing else can see is the window *before* a
push, which is exactly where a session works.

## What a script cannot do, and so stays yours

- **Publishing the dashboard.** Only a live session can call the `Artifact` tool, so
  every operation hands back `/plan-dashboard <plan-id>` rather than pretending it
  ran. Run it in the same turn as the write — every session does, unattended ones
  included. A published dashboard older than the manifest behind it is the staleness
  this rule exists to close.
- **Creating the pull request.** One the script creates is attributed to the app its
  requests are proxied through rather than to you; create it yourself and pass
  `--pull-request-number`.
- **Knowing the session's own URL.** A session cannot ask its environment which
  session it is, so pass it rather than expecting it to be derived.
- **Judgement.** What the notes should say, and which status a non-mechanical
  transition means — `blocked` when something outside the item must move first,
  `deferred` when it was parked deliberately.

## For a pass that changes state without owning it

`stacked-pr-maintenance` reparents pull requests, promotes branches, restacks and
moves labels. All of that changes what a tracked item's recorded fields should say,
and none of it happens in the session that owns the item.

It holds a branch rather than an item id, so every operation below is keyed on the
branch and resolves the rest itself:

```bash
source .claude/hooks/resolve-personal-notes-config.sh

# Which plan and items does this branch belong to?
python3 "${PLAN_ITEM_BOOTSTRAP_SCRIPT}" resolve --branch <branch>

# Block every item on it, under this pass's own name.
python3 "${PLAN_ITEM_BOOTSTRAP_SCRIPT}" block --branch <branch> \
    --owner "${MAINTENANCE_BLOCKER_OWNER}" --reason <file>

# Withdraw that blocker once the pass finds the branch clean again.
python3 "${PLAN_ITEM_BOOTSTRAP_SCRIPT}" unblock --branch <branch> \
    --owner "${MAINTENANCE_BLOCKER_OWNER}"
```

A branch can carry more than one item, so each writes all of them; a branch no plan
claims exits `branch_tracks_no_item` and writes nothing, which is a finding to report
rather than a failure — every fork pull request is supposed to belong to a plan.

**What it writes is only what it decided itself.** A branch it labels
`needs-resolution` is blocked because this pass concluded so; one whose label it
clears is not. The blocker carries the owner it was written under, so the pass
replaces and withdraws its own entry and never one a person wrote, and an item left
carrying somebody else's blocker stays blocked.

**What it reports rather than writes** is everything whose status is a reading rather
than a mechanical fact: a reparent, a promotion, a landed branch. A landed branch
needs no write at all — the refresh below corrects merged to `done` on its own.

Then republish, once per plan it wrote to, at the transition rather than in the
finish summary. The finish summary still names every item touched, which of them were
written, and which plans were republished.

It publishes rather than handing the command back because it runs as a session like
any other: `--non-interactive` suppresses asking the user a question, not writing a
file or calling a tool. The write is a script call precisely so it survives
`routine-cutover`, after which the pass is a plain Action with no session in it and
publishing moves to the built site.

## In auto mode

Autonomy removes the approval, not the record. `execution-modes.md` (next to this
file) states what `auto` still obliges — including writing the plan down before
implementing it. This rule is unchanged by the mode: a transition that happens
without being asked about still gets written before the next thing starts.

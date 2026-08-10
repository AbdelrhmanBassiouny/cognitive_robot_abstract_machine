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
python3 -m "${PLAN_ITEM_BOOTSTRAP_MODULE}" update \
    --plan <plan-id> --item <item-id> \
    [--status <status>] [--branch <branch>] [--pull-request-number <number>] \
    [--session <url>] [--notes <file>] [--blockers <file> ...]

# Ask what local git contradicts, before or after a transition.
python3 -m "${PLAN_ITEM_BOOTSTRAP_MODULE}" check --plan <plan-id> --item <item-id>
```

`update` writes prose from files because a note is routinely longer than a shell
invocation should carry. `check` exits `manifest_is_stale` when anything is stale
and prints one finding per contradicted field, so a caller can act on the status
alone.

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
  ran. Run it in the same turn as the write. A published dashboard older than the
  manifest behind it is the staleness this rule exists to close.
- **Creating the pull request.** One the script creates is attributed to the app its
  requests are proxied through rather than to you; create it yourself and pass
  `--pull-request-number`.
- **Knowing the session's own URL.** A session cannot ask its environment which
  session it is, so pass it rather than expecting it to be derived.
- **Judgement.** What the notes should say, and which status a non-mechanical
  transition means — `blocked` when something outside the item must move first,
  `deferred` when it was parked deliberately.

## For a pass that changes state without owning it

`stacked-pr-maintenance` reparents pull requests, promotes branches and moves
labels. All of that changes what a tracked item's recorded fields should say, while
touching no manifest.

Its obligation therefore runs the other way: **report the items it just made stale**,
rather than write them. Map each branch it moved to its item through the generated
branch index (`${PLAN_BRANCH_INDEX_PATH}` on the personal-notes branch) and name
them in the finish summary, with what changed.

It reports rather than writes for two reasons, and both matter: it runs unattended
under `--non-interactive`, where its own doctrine forbids opening a discussion; and
*why* a status changed is judgement, which the section above keeps with a session.
A pass that guessed would write a manifest nobody had decided.

## In auto mode

Autonomy removes the approval, not the record. `execution-modes.md` (next to this
file) states what `auto` still obliges — including writing the plan down before
implementing it. This rule is unchanged by the mode: a transition that happens
without being asked about still gets written before the next thing starts.

# Gathering a tracked plan item's context

Shared by `plan-item-kickoff` and `plan-item-resolve`. Both have to answer
the same question before they can act — *what is already known and already
decided about this item?* — so the procedure lives here once instead of
being restated in each skill.

Each skill runs everything below, then adds only what its own situation
needs: `plan-item-kickoff` reads the merged pull requests that set the pattern to follow;
`plan-item-resolve` reads the item's pull request state and the tracking
issue's discussion. Neither should re-derive anything on this page.

## Check the setup is in place, and offer it if not

The item's manifest entry and roadmap live on the personal-notes branch,
which the user may not have set up yet. Follow
`.claude/skills/setup-personal-notes/prerequisite-check.md` first: run the
check, and if it reports anything missing, offer `/setup-personal-notes`
rather than failing later on a branch that isn't there.

## Resolve the item

Source the shared config script — it resolves the personal-notes
remote/branch precedence and defines every other constant referenced below
(this has to stay a literal path: it's the one file that defines all the
others, so nothing "more shared" exists yet for it to point at):

```bash
source .claude/hooks/resolve-personal-notes-config.sh
git fetch "${NOTES_REMOTE}" "${NOTES_BRANCH}" --quiet
```

Read only what this item needs. Copy `<plan-id>/plan.yaml` off `FETCH_HEAD`
to a scratch file and print just this item with
`"${BASSTLER_PYTHON}" -m "${PLAN_MANIFEST_TOOLS_MODULE}" item <file> --id <item-id>` (or
`--branch <branch>`); do the same for each item it `depends_on` when the
readiness check below leaves a question. Never read the whole manifest to
find one item - every other item is another session's work and costs this
one context. Read `${PLAN_SCHEMA_DOCUMENT}` only if a field's meaning is
unclear.

Given a pull request number instead of the two ids, find the item from the
pull request's branch: read its head branch with
`${GITHUB_PULL_REQUEST_READ_TOOL}` (`method: "get"`), take the plan id from
`plan_id_for_branch <branch>` (it reads the fetch above), and print the item
with `--branch <branch>`. If no plan tracks that branch, say so and stop.

If the plan id or item id doesn't resolve, stop and list what's actually
available — every plan id under `plans/*/plan.yaml`, or every item id in
the named plan — rather than guessing which one was meant.

## Subscribe to the plan's tracking issue

If the plan has a `tracking_issue`, subscribe to it now via
`mcp__Claude_Code_Remote__subscribe_pr_activity` (it takes a plain issue
number the same way it takes a PR number).

Do it here, before gathering anything else. Either skill may go on to push
real work without a fresh session ever starting, and the subscription
`session-start.sh` sets up for an already-checked-out item branch never
fires in that case — so subscribing at the start is what actually covers a
run that turns into an uninterrupted working session.

Skip this entirely if the plan has no `tracking_issue`. The call is
idempotent, so it's safe even if something already subscribed this session.
If it errors, don't let that fail the skill: mention it in passing when
presenting the plan and continue — subscribing is a convenience for staying
aware of concurrent structural changes, not a precondition for anything
here.

## Read the item's recorded state

`title`, `status`, `notes`, `blockers`, `track` (and that track's own `name`
and `description`), `wave`, and `session` — a link to whatever session
previously worked this, if recorded. Read that link as context, not as
something to redirect to or wait on.

`blockers` is free text and is often the most direct statement of what is
actually wrong; `notes` routinely carries design calls that were settled
long before this run.

## Read the plan's standing rules

`roadmap.md` holds only the plan's standing rules - a title and at most a
dozen short entries (see `${PLAN_SIZE_LIMITS_MODULE}`) - so read it whole;
it is small by construction. Each rule binds this item as much as its own
`notes` do.

There is no older narrative to read. Landed items and session history are
not kept in the plan: what was built is in the code, and why is on its pull
request. If the item's `notes` leave a question the code and its pull
request do not answer, ask the user rather than digging through the
personal-notes branch's history.

## Check the dependency chain

For the item's `depends_on`, follow `${DEPENDENCY_READINESS_DOCUMENT}`'s
bulk-fetch-and-check procedure, for `--item <item-id>`.

A dependency the script reports not ready for is a real and common cause of
a stall, and it decides what a new branch can even be based on. Flag it
explicitly in whatever gets proposed, rather than quietly proceeding as if
it were ready.

## Cross-check the standing conventions

Read this repository's own `AGENTS.md` alongside the roadmap's rules. Whatever is proposed must
honor both — SOLID, TDD, no abbreviations, dataclasses, docstring
conventions, whatever the repo's own rules are — not just what the item's
own `notes` happen to mention.

## Before raising an open question, check whether it is already answered

A design call, a naming convention, or a scope boundary is very often
already decided somewhere in the material just gathered. Re-read the
roadmap's rules, the item's own `notes`/`blockers`, and any
cited sibling pull request or comment thread before surfacing anything as an
open question.

Only surface something if, after that check, it is genuinely still
unresolved; asking the user something the roadmap already answered means the
read wasn't thorough enough. If you do ask, say what you checked and why it
still looks open, so the user can correct you quickly with a pointer if you
missed it.

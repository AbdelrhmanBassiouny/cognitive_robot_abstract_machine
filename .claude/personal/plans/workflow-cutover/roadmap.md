# workflow-cutover — Roadmap

Narrative companion to `plan.yaml`. Kept short on purpose: the size budget this split was made
under counts these lines.

## Where this plan came from

Split out of `workflow-unification` on 2026-08-30, under `plan-size-limits`'
`split-workflow-unification`. That plan had reached 59 items and 16,917 lines across its manifest
and roadmap, well past the 15-item / 2,000-line budget, and became seven plans seamed on subject:
`stack-tooling-install`, `stack-maintenance`, `plan-tracking-skills`,
`session-notes-infrastructure`, `plan-dashboards`, `bastler-package` and this one.

This plan is the `cutover` track, carried across unchanged. Every item keeps its branch, pull
request number, status and session verbatim.

**The full 11,788-line predecessor roadmap is not lost** - it remains in the personal-notes
branch's own history, at `.claude/personal/plans/workflow-unification/roadmap.md` before the split
commit. What is kept here is what binds future work; the per-round implementation narrative of
merged items lives in the pull requests themselves, which each item's notes link.

## Why this work exists

The workflow machinery had grown into four storage locations plus a live scheduled LLM Routine, and
the endgame this plan owns is the state it was all meant to reach:

- **One published surface.** Plan dashboards publish from a single Pages site, with the stack board
  retired in favour of GitHub's native stack map (the one-dashboard decision, 2026-07-31).
- **No scheduled LLM run at all.** A plain scheduled Action takes the deterministic duties -
  fork-main fast-forward, label hygiene, the upstream-link comment, the site build, the happy-path
  cascade - and the judgment residue runs in on-demand sessions surfaced by the dashboard rather
  than by a timer. That finally aligns the machinery with the no-scheduled-checks rule.
- **The superseded branches retired**, once one green cycle has run on the new paths.

What was *not* found in the original review, and is worth keeping: the four-way storage split is
load-bearing rather than accidental. Fork main must mirror upstream, personal data cannot live on a
merged branch, and one repository gets one Pages site.

## Decisions this plan inherits

Numbering is the predecessor's, kept so cross-references in item notes still resolve.

**3. Portability.** No repository names outside configuration defaults and documentation examples.
The site's repository, branch and upstream become repository variables rather than literals.

**4. The hard rules stay inline in the prompt**, because they must bind before the first tool call -
a webhook event can arrive before any file is read. *Partly reversed in practice*: once the doctrine
became a skill the rules no longer bind before the first file is read, and the window is one turn.
Accepted because this plan deletes the scheduled run anyway.

**9. The GitHub steps in this system do not need a session.** The accounting that said otherwise was
wrong: the authenticated login, the label reads and the label creates are all plain API calls. This
is why the deterministic duties can move to an Action at all.

## Standing risks

- **The site lives on a regenerated branch.** The workflow runs from the fork's default branch,
  which is the integration branch, and that branch is rebuilt from scratch - a rebuild that drops
  the tip carrying the workflow takes it off the default branch and manual dispatch stops being
  offered until a later build carries it again.
- **The base-change credential is unverified in the Action.** A session's own git-proxy credential
  refuses a base change while its MCP client performs one; the Action's credential is a third
  identity again. Verify it with a real base change before relying on it.
- **Two operations stay outside the harness.** Tag pushes and branch deletes get a 403 through a
  session's git proxy and no tool substitutes, so `tooling-branch-retirement`'s last two steps are
  the user's to run. A session can do every verification and prepare the exact commands.

## Open

- Whether the Pages workflow eventually lands on `main` or gains a cron. Neither was done: the cron
  was not asked for and the no-scheduled-checks rule makes it the user's call.
- Whether the every-fork-pull-request-belongs-to-a-plan invariant is enforced at site-build time.
  Recorded when the one-dashboard decision was taken, carried by nothing yet.

## The 2026-09-04 review round on #218, and what it found about the other branches

The item read `in_progress` with no blocker while a 26-thread review round sat unanswered on its
own head commit. Nothing about its recorded state said it was stuck, which is why the blocker was
written before the resolution started rather than after it.

Four of the asks are one complaint restated - hard-coded strings where a `StrEnum` member belongs -
and the round is otherwise `payload` as a name, missing per-member docstrings, and a common base for
the error classes. Three are questions, and two of those turn out to be about branches other than
this one:

- **The vocabulary this branch should use already exists on #111.** `RefreshArgument`,
  `RefreshSummaryKey`, `SitePath`, `RepositoryEndpoints`, `PullRequestListFilter` and `IssueField`
  are all in `bastler/build_site.py` and `bastler/pull_request_state.py`, and #111 names a decoded
  response `detail` and a request body `body` - which is the answer to "rename payload". Adopting
  those names here makes the eventual merge an adoption rather than a conflict, so the overlap the
  item's notes already record stays a single-file one.
- **`workflow_document.py` (#211) is a second overlap, and a real one.** Naming the workflow's keys
  for `test_plan_dashboards_workflow.py` builds a small piece of what that 664-line module already
  models. It is on `.claude/stack/` on an unlanded branch, so this branch cannot import it; the
  vocabulary here is deliberately sized to these tests and named after its equivalents, and the
  richer version wins whenever the two meet.
- **Bash to Python is the settled direction, and `publish_site.sh` was the last new bash.**
  `bastler-package` carries a seven-item Bash→Python series; none of its items covers this file,
  because the file does not exist on `main`. Converting it here is the answer to the review's
  question rather than a new claim on that plan's scope.

Left for the user: whether the Artifact publishing path is retired now the dashboards publish to
Pages. That would delete `record_dashboard_url.py`, `_generated/dashboard-urls.yaml` and the
"republish the dashboard" convention every plan skill follows, so it is a plan-level scope change
rather than a review fix.

## The Artifact path is now a tracked retirement, not an open question

`artifact-path-retirement` was added on 2026-09-04, at the user's direction, from a review comment
on #218 asking whether the Artifact tool is still needed now the dashboards publish to Pages.

It belongs to this plan rather than to `plan-dashboards`, whose files it deletes, because it is what
finishes this plan's own first goal: one published surface. It carries the same gate as
`tooling-branch-retirement` - one green cycle on the new path before the old one goes - and the same
shape of question, which is what makes the two siblings rather than one item.

The three things it has to settle are recorded on the item, because each is a way the Artifact still
does something Pages does not: the site is public where an Artifact is private, the workflow reaches
only the pull requests whose base already carries it, and a manifest edit raises no event, so the
republish becomes a dispatch rather than a skill invocation.

## What the round changed, and the two threads it did not close

Pushed as `d61619ac`. The four recurring asks are answered across the branch's own files, and the
answer to the largest of them came from reading #111 rather than from inventing names: every
vocabulary this branch needed - `RefreshArgument`, `RefreshSummaryKey`, `SitePath`,
`RepositoryEndpoints`, `PullRequestListFilter`, `IssueField`, and `detail`/`body` in place of
`payload` - already exists in `bastler/build_site.py` and `bastler/pull_request_state.py`. Taking
those names makes the single-file overlap the item's notes record an adoption rather than a rename.

`publish_site.sh` is now `publish_site.py` on a `GitCommandRunner` that `PersonalNotesBranch` reads
through too. That answers two threads at once, and it is where `bastler-package`'s Bash-to-Python
series was going anyway - none of its seven items covers this file only because the file does not
exist on `main`.

Two asks are answered differently from how they were put, so they stay open for the user rather than
being resolved:

- **The git command runner** is this package's own, not `.claude/stack/maintenance_git_commands.py`'s.
  That module imports `stack`, and reaching it at all depends on another skill directory's conftest
  having inserted its path - which happens to hold under CI's single pytest run and is not a
  dependency worth taking. #111's `bastler/personal_notes.py` runs git through a private method for
  the same reason.
- **The error base** covers the errors this branch introduces. `build_dashboard.py`'s
  `MissingMergeTimestampError`, `MalformedPullRequestDataError` and `PlanValidationError` predate the
  branch and sit outside its diff; retrofitting them widens the pull request rather than answering
  the review.

Of those two, the user closed the error-base thread himself; the git-command-runner one is still
open, and is the only thread on the pull request that is.

## The 2026-09-05 round: one ask, and what making it true exposed

One comment - *always use dataclasses*, on the fake transport in `test_build_site.py` - answered in
`8afbbe30`. It is worth recording because the fix was not the class it pointed at.

That class had a hand-written `__init__` for one reason: to hold a builder function the conftest
handed it. The builder was a closure returning a bare `dict`, and the two fixtures underneath it
were closures over their configuration as well. So the review found one dataclass missing and the
scaffolding behind it turned out to be three classes written as functions:

- the pull request a fake listing serves is now a `PullRequestDetail` dataclass with `to_json()`,
- the scratch repositories are a `ScratchNotesRemote` holding the remote, the seed checkout and the
  clone as named paths, in a `tests/scratch_repositories.py` of their own,
- and `scratch_git` is a `GitCommandRunner` pointed with the `in_directory()` the production class
  already had, rather than a factory that built one.

The move to a named module had a second effect the round did not set out to get. The `plan_files`
fixture existed *only* because `conftest` is not a module name a test can safely import by - four
test directories share one path under CI's single pytest run, and its docstring said so. With the
type in a module with its own name, the fixture is gone and the tests import the class.

## `routine-cutover` resumed 2026-09-06, and what building it turned out to need

Resolved from `in_progress` with no branch: the recorded gate ("stack tooling on
cram2/main and fork main fast-forwards") had cleared unnoticed - `cram2/main` and this
fork's `main` are the identical commit (`f6a53cf9`), both carrying `.claude/stack/`. The
deterministic executor the endgame calls for (`maintenance.py`) was already built and
merged via #139, whose own notes had already answered the base-change-credential
question this item's notes had left open for the Action to verify: label writes,
conflict comments and description writes are all available to the executor's own
token; only a base-branch retarget needs a session, and the executor already reports it
as `reparents` rather than attempting it.

The one gap: nothing called that executor, and nothing notified when it found a
pending reparent - every other kind of residue (a restack conflict) already self-reports
via `conflict_report()`/`needs-resolution`, but `reparents` only ever reached a run
summary. Opened as PR [#280](https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/280),
branch `claude/stack-maintenance-action`:

- `maintenance_reparent_notice.py`: `reparent_notice()`/`notify_reparents()`, mirroring
  `conflict_report()`. Its label write reads the fork's *current* labels
  (`fork.pull_request(number)`), not the stack's own snapshot - promotion and restack
  both run first in `run-report` and can have written a label since the snapshot was
  taken, the same staleness class `promote()` already reads around (and the one the
  executor's own #139 notes recorded fixing twice already).
- `.github/workflows/stack-maintenance.yml`: runs `maintenance.py run-report --json` on
  `pull_request: closed` (the widened, event-triggered re-sweep this item's notes
  already specified), `schedule`, and `workflow_dispatch`. Resolves the upstream remote
  via `stack.py configuration`'s own `upstream_setup_command` rather than hardcoding a
  remote name, and needs no new secret - `GH_TOKEN`/`GITHUB_TOKEN` from
  `secrets.GITHUB_TOKEN` is what the executor already reads.
- Renamed `CONFLICT_COMMENT_PREFIX` to `NEEDS_RESOLUTION_COMMENT_PREFIX` (one rename,
  one new caller) rather than defining a second, identical prefix constant.

**Still gated, per this item's own recorded gate ("one green Action cycle flips this
done") - not done in this PR:** deleting the live Routine
(`trig_01N79jHmLo3bSbg8pLM6MNTB`), and flipping this item to `done`. Both wait for a
verified run of the new Action once it is on the default branch - `workflow_dispatch`
is only offered there, the same constraint `stack-board-single-site`'s notes already
recorded for the Pages site.

**A live coordination point, not a blocker, for whoever next works `stack-maintenance`'s
`promotion-summaries-and-table` (#162):** that item is still adding session-facing
features to the pass an LLM session runs, and `.claude/skills/stacked-pr-maintenance/routine-prompt.md`
(merged 2026-08-13) documents registering exactly the scheduled Routine this item
retires. Its own open question - "an already-registered scheduled run's notification
setting has no field on the update API" - resolves itself once this item deletes that
registration; `routine-prompt.md`'s own guidance becomes dead weight at the same time,
worth a look once this lands.

## `routine-cutover`'s #280 review round, 2026-09-06: the retarget was never actually refused

Two comments on #280, both from the credential-assumption angle. The first asked directly whether
retargeting a base is actually doable from a GitHub Action - it is, for the write itself; what was
never true was the inherited assumption that it wasn't.

**The 403 `stack-maintenance-executor` (#139) recorded was through a Claude session's own proxied
credential, not through a plain GitHub Actions token.** That probe never ran from an Actions runner
at all. `maintenance_github.GitHubRepository` authenticates its own requests directly with
`GH_TOKEN`/`GITHUB_TOKEN`, never through a session's proxy, so there was no basis for assuming it
would hit the same wall - only for testing it, which this round's fix now does.

`resolve_reparents` (renamed from `notify_reparents`) attempts the retarget itself first via a new
`ForkPullRequests.retarget_base` (`PATCH /pulls/{number}` with `{"base": ...}`, the same shape
`set_description` already uses), and only falls back to the label + comment notice on a genuine
refusal - `403` (this credential specifically refused) or `422` (the pull request is a GitHub Stack
member, which has to move through native Stack mechanics instead of a plain base change - a real,
separate restriction traced in an earlier addendum). `MaintenanceReport` gained
`reparents_retargeted` alongside the existing `reparents`, so `run-report --json` says which of the
found reparents this pass resolved itself rather than only that they existed. Reparenting now also
runs before restack in `run-report`, matching the session-driven doctrine's own step ordering - a
restack integrates onto a branch's *current* parent, so a child left on a landed one has to be
retargeted first or it restacks onto a dead end.

The second comment widened the workflow's own triggers: `opened` and `ready_for_review` alongside
`closed`, so a fresh pull request or one leaving draft (the self-review sign-off that makes it
promotable) is picked up the same run rather than waiting up to six hours for the next schedule tick.

Still unverified, and still this item's own recorded gate: whether GitHub actually allows this
credential to retarget a base on this fork, rather than refusing with `403`/`422` for a reason not
yet seen. That answer only comes from a real dispatched run once this is on the default branch.

## `routine-cutover`'s #280 review round, 2026-09-06 (continued): a naming ask and a real coexistence question

Two more comments, one mechanical and one worth the research it took to answer honestly rather
than reassure.

**The two retarget-refusal statuses are now `RetargetRefusal(IntEnum)`** (`CREDENTIAL_REFUSED = 403`,
`STACK_MEMBER = 422`), replacing the bare `frozenset({403, 422})` literal `maintenance_github.py`'s
`retarget_base` checks against - the one magic-number lapse in the previous round's own fix.

**Whether this Action conflicts with the regenerated integration branch pipeline
(`integration-branch`/`integration-branch-ci-verdict`, `stack-maintenance` plan, not yet on `main`)
turned out to have already been answered, by that item's own history.** Its notes record a defect
found during its own development - "the maintenance pass was adopting candidates" - where the
executor's board read treated the pipeline's own judging pull requests as ordinary stack members.
The fix, `BoardExport.is_a_candidate`, was placed deliberately "at the one place both readers derive
their work from" - the shared board-export module both a build and any maintenance pass, this
Action included, read through - and ships in the same pull request that starts opening candidate
pull requests in the first place. So there is no landing-order gap where candidates exist without
the exclusion protecting them: this Action inherits `is_a_candidate` automatically once
`integration-branch` lands, with no change of its own needed. The one thing that still can happen -
both workflows firing on the same `pull_request` event - is a benign race rather than an
interruption, since they write to disjoint refs and a build is regenerated from scratch and
self-limiting by design. Recorded as a comment in `stack-maintenance.yml` itself so a future reader
does not have to re-derive it from `stack-maintenance`'s roadmap.

Both threads replied to and resolved. Pushed as `a1409d71`.

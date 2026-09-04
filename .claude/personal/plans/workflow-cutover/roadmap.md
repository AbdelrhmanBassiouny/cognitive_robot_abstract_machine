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

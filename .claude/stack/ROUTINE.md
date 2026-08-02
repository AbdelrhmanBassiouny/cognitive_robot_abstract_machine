# The stacked-PR Routine (canonical prompt)

**This file is live.** The cloud Routine reads it from git at the start of every run and
executes the fenced text block below, so an edit here changes the running workflow as soon as
it is pushed - there is no separate deploy step and no copy to keep in sync.

What is registered at claude.ai/code/routines is only a short pointer: it resolves this file and
carries the HARD RULES inline, because those must bind before any file is read - a webhook event
can arrive before the first tool call. Everything else lives here. That pointer is kept in
`POINTER.md` beside this file, which is also where the fork and branch it names are recorded, so
nothing here has to be edited to run on another fork.

`README.md` in this directory points here rather than embedding a second copy. A prior duplicate
on `dev/README.md` had already drifted from the live Routine by the time this was written, which
is exactly the failure mode one copy prevents; that copy is no longer read by anything and dies
with `tooling-branch-retirement`.

```text
You maintain a stacked-PR fork-staging workflow. <fork-remote> is my fork (the full stack);
<upstream-remote> is the slow upstream review queue - SETUP step 0 tells you both names, never assume
them. GitHub is the source of truth: a fork PR's BASE branch is its parent, the DRAFT flag is the ready
gate, an `in-review` label means promoted-to-upstream, and a branch that is an ancestor of
<upstream-remote>/main is merged. Do NOT use the Workflow tool. Use plain git + the GitHub MCP. Never
force-push a branch that has an open upstream PR unless it carries the `rebase` label.

YOUR JOB, AND ONLY THIS: close landed fork PRs (Phase 1), restack branches whose parent moved (Phase 2),
promote every approved+unblocked branch (Phase 3), and react to your own restacks' CI. That is the
whole job. It is NOT your job to do code review, or to read/answer/resolve/act on the developer's
review comments, or to make code changes that address review feedback - that is the developer's
interactive session's work. Leave review threads untouched. The only code changes you make are conflict
resolution while restacking and narrow fixes to CI failures your own restack caused.

HARD RULES so you never drift into review work:
- NEVER call `subscribe_pr_activity`, and never stay subscribed - you learn CI by POLLING (Phase 2/SETUP).
- If a review, review-comment, issue-comment, or any `<github-webhook-activity>` event is ever delivered
  to you, your ONLY valid action is to END THE TURN immediately: do not investigate it, do not draft or
  post a plan, do not reply, do not ask the developer to confirm anything. The one exception is a CI/check
  *status* you were polling for your own restack.
- NEVER enter plan mode or post a "here's my plan" comment. You either perform a mechanical step from the
  phases below or you stop; you never open a discussion.
- LABELS ARE REPLACE, NOT ADD: the GitHub label-write call takes the PR's **entire** new label set - it
  does not add to what's already there. "Add `in-review`" or "remove `cram2-link-sent`" NEVER means
  calling it with just that one label. Every single label write, in every phase, is: (1) read the fork
  PR's CURRENT labels, (2) compute the full new set - union with the label you're adding, or the current
  set minus the label you're removing - (3) call the label write with that complete list. Skipping step 1
  silently wipes every other label on the PR (this has happened before and deleted `in-review` off
  already-promoted PRs, making the routine wrongly re-suggest branches that were already under review).

PRE-FLIGHT - before EVERY push, merge, or restack, no exceptions
Never move commits from memory. First WRITE OUT these four lines and verify each with git; only then run
the command:
  - ACTION: push | merge | restack.
  - FROM (source): run `git branch --show-current` and `git rev-parse --short HEAD`. The checked-out
    branch MUST be the one whose content you intend to move. NEVER push while checked out on a different
    branch, and NEVER map a mismatched refspec - use `git push <fork-remote> <branch>` or
    `<branch>:<branch>` with identical names. A `git push <fork-remote> HEAD:<other-branch>`, or a
    `<src>:<dst>` where src≠dst, is FORBIDDEN unless you have written out and verified both sides.
  - INTO (destination): the exact remote + branch (e.g. `<fork-remote>/<branch>`). Confirm the
    remote is <fork-remote>, never <upstream-remote>. If force-pushing, confirm there is no open
    upstream PR (or that it carries `rebase`) and use `--force-with-lease`.
  - WHY: one sentence - what you are integrating and why it belongs on that destination branch.
Then INTENT-CHECK the parentage before pushing: run `git log --oneline -5 <source>` and
`git log --oneline -3 <fork-remote>/<destination>`; the only new commits about to land on the
destination must be the ones you expect. If a CHILD branch's commits would become ancestors of its
PARENT, GitHub will auto-mark the child PR as merged - a false merge. STOP and do not push.

SETUP
0. Get the tooling, then let it tell you the remotes. Do NOT inspect, guess at, or rename remotes
   yourself - names carry no meaning here and a wrong guess points every push at the wrong
   repository.
   a. Every later phase shells out to `.claude/stack/stack.py`, and a Phase 2 failure lands after
      Phase 1 has already mutated pull requests, so do not assume it is present. If
      `ls .claude/stack/stack.py` fails, `git fetch` the ref you resolved this file from and
      `git checkout <ref> -- .claude/stack/` - your pointer prompt is what named that ref. Once
      `.claude/stack/` is on `main` this is a no-op on a fresh clone, and both this fallback and
      the pointer's can be deleted.
   b. Run `python .claude/stack/stack.py configuration`. It prints every resolved setting as one
      `key<TAB>value` line - among them `fork_remote`, `fork_repository`, `upstream_remote` and
      `upstream_repository`, deciding which remote is which by the repository each URL names, not
      by what it is called. Use those values everywhere this document writes <fork-remote>,
      <fork owner>, <upstream-remote> or <upstream-repository>. If an `upstream_setup_command`
      line appears, run exactly that command and re-run `configuration`. If the command exits
      non-zero, STOP and report: it could not tell which remote is the fork, and there is no safe
      guess.
1. UPDATE FORK MAIN FIRST - before anything else. Every `base=main` comparison (both GitHub's PR
   diffs and the board's LOC/conflict chips) is measured against `<fork-remote>/main`, so a stale
   fork main inflates every root branch's diff. Fork main is a pristine mirror of the upstream trunk
   - keep it that way, because root branches base on it and the restack merges it into them, so
   anything you add
   here would flow into every branch and then into the upstream. Fast-forward it:
     `git fetch <upstream-remote> main && git push <fork-remote> <upstream-remote>/main:main`
   This MUST be a fast-forward. If GitHub rejects it as non-fast-forward (fork main has unique
   commits), STOP and report - do NOT force.
2. `git fetch <fork-remote>`.
3. Refresh `.claude/stack/board.json` from the fork's OPEN PRs (number, head, base, isDraft, labels, and
   - for the chips - statusCheckRollup and body) via the GitHub MCP, then run
   `python .claude/stack/stack.py status` to see the derived stack. There is no `--live` flag; state
   comes from board.json + git.
4. CI IS THE VALIDATOR - POLL IT, NEVER SUBSCRIBE. When you need a branch's CI verdict, POLL it with
   the GitHub MCP (`pull_request_read` → `get_check_runs` / `get_status`) and read only the
   success/failure conclusion; never run the ROS (coraplex/SDT) suites here. Do NOT call
   `subscribe_pr_activity` - a subscription delivers human review comments and review threads (not just
   CI) and turns on the built-in per-event handler that makes you investigate, plan, and reply. That is
   how you end up "responding to reviews"; polling avoids it entirely.

THE BOARD PUBLISHES ITSELF
You do not render or redeploy the board. A GitHub Action in the separate `stack-board` repo polls the
fork and republishes the board to its own GitHub Pages site every few minutes. So make your state
changes and move on; the board catches up on its next poll. Never render `board.html` or redeploy an
Artifact here.

PHASE 1 - LANDED PARENTS: REPARENT, LABEL `merged`, THEN CLOSE
The upstream always merges with a merge commit (never squash/rebase), so a landed branch is always an
ancestor
of <upstream-remote>/main. A branch B is MERGED (not merely closed) iff
`git merge-base --is-ancestor <fork-remote>/B <upstream-remote>/main` succeeds - that git-ancestry
test, NOT the PR's open/closed state, is how you know B actually landed in main.

BASE CHANGES GO THROUGH THE GITHUB MCP SERVER. Retarget a base with the MCP `update_pull_request`
tool and nothing else. The same request issued as a raw `PATCH /repos/{owner}/{repo}/pulls/{number}`
with curl and `GH_TOKEN` is refused with `403 - Changing a pull request's base branch is not permitted
for this session type`, however the body is formed - the block is on that credential, not on the
operation, so retrying it or reshaping the request cannot get past it. That 403 is a known, documented
outcome: if you see it, you used the wrong client, so switch rather than report it as a stuck reparent.
The stacks endpoints below are the mirror image - they have no MCP tool, so they do need curl.

REPARENT EVERY ORPHANED CHILD - the ancestry test decides this, never the board. Run the ancestry test
on the BASE branch of every open fork PR whose base is neither `main` nor the head of another open fork
PR: those bases have no board entry of their own, so nothing else in this phase would ever look at them.
Whenever such a base has landed, retarget its child's base to `main` with `update_pull_request`. A
parent whose own PR was CLOSED rather than merged is exactly this case. The reparent is not cosmetic
and is never optional: a child left on a landed base cannot reach `main`, and it is closed outright the
moment that base branch is deleted. The inflated diff such a child shows is a symptom, not the problem.

NATIVE-STACK MEMBERS. Changing the base of a PR that belongs to a GitHub stack fails with
`422 - Cannot change the base branch because the pull request is part of a stack`, so the plain
retarget above cannot move it. This is a different refusal from the 403 above and has a different
cure: the 422 is GitHub protecting the stack's structure, and dissolving the stack clears it. A PR is
a stack member iff its REST JSON carries a non-null `stack` object when fetched with the header
`X-GitHub-Api-Version: 2026-03-10`; the stacks endpoints are not in the GitHub MCP server, so call
them with curl and `GH_TOKEN`, always with that version header. For exactly those children, the
reparent becomes:
1. `GET /repos/{owner}/{repo}/stacks` and record the affected stack's full PR list, bottom to top. Do
   not proceed without the recorded list - dissolving is destructive and there is no undo.
2. `POST /repos/{owner}/{repo}/stacks/{number}/unstack` (no body) to dissolve it. There is no
   selective removal: this drops every open, draft and closed member, leaving merged ones in place.
3. `update_pull_request` each orphaned child's base to `main`, which succeeds once the stack is gone.
   The child keeps its number, its labels and its review thread - never close it and open a
   replacement, which loses all three for a base change that is available to you.
4. Restack normally (Phase 2's local merge/rebase + push).
5. Re-create the stack: `POST /repos/{owner}/{repo}/stacks` with `{"pull_requests": [...]}` - the
   recorded list minus landed and closed members, bottom to top - then `GET` it back and confirm every
   member reports the stack.
Do NOT fast-forward the landed base branch to `main` as a way around this. It moves the merge-base, so
the diff looks right, but the child still targets a branch that is about to disappear - and when that
base is a stack's trunk, moving it desynchronises the stack's recorded `base.sha` from its real head.
If any call in this sequence fails or answers with something not described here, stop work on that
stack, leave the rest untouched, and report it - this is a preview API, so never improvise around it.

For each OPEN fork PR (head branch B) that is merged by the ancestry test:
- REPARENT its children first - for every OTHER open fork PR whose BASE is B, retarget that child's base
  to `main` with `update_pull_request` (B's commits are in main now, so the child stacks on main, not on
  a branch about to disappear). Do this BEFORE closing B so no child is ever orphaned. `.claude/stack/stack.py
  restack-plan` already emits `parent: main` for these children, so Phase 2 rebases them onto main to
  match. (Only when B is merged by the ancestry test - a PR merely CLOSED without merging leaves B's own
  label/close state alone, but NOT its children: they are reparented by the rule above, which keys off
  the branch's ancestry rather than its PR's state.)
- LABEL it `merged` - ALWAYS add the `merged` label to B's fork PR as the durable "this landed"
  indicator, even when you then close it.
- CLOSE it - close B's fork PR with a comment noting it merged into <upstream-remote>/main. If you
  cannot close it, leave it open: the `merged` label already flags it and I will close it myself.
- NEVER label-`merged` or close a fork PR whose work has NOT landed. (The ancestry test is the only
  condition.)

PHASE 2 - RESTACK + VALIDATE (CI is the validator; ROS-free fix-first; work in parallel)
Run `python .claude/stack/stack.py restack-plan` for the bottom-up plan. For each entry whose parent
moved, integrate the parent using its `strategy` (merge = default, no force-push; rebase =
force-push-with-lease) ONLY IF the merge is clean, then push. CI is the validator - never run the
coraplex/SDT (ROS) suites here; poll the PR's checks with the GitHub MCP (do NOT subscribe).

Don't block on CI: after pushing a branch, move on to the next independent branch and keep restacking
/ promoting (Phase 3) in parallel - never sit idle waiting on a ~20-minute run. Poll the checks of the
branches you pushed at the start of each pass (and on your next scheduled run) and react then.

When a branch conflicts or its CI comes back RED, get around ROS as far as you can - never park a
branch on a ROS dependency; resolve it non-blockingly and let CI be the final check:
- If the failure/mechanism lives in the ROS-free layer (`krrood`, which runs here), reproduce it
  locally with a meaningful failing test (mimic the offending pattern in the `krrood` test datasets
  per `AGENTS.md` when it originates in another package), fix it, and validate by running the
  `krrood` suite locally; push and let CI confirm end-to-end.
- A generated `ormatic_interface.py` conflict never blocks - the file is regenerated, not
  hand-authored, so never skip the branch or its descendants over it. Resolve it and depend on CI:
  - Package ORM (`{semantic_digital_twin,coraplex,experiments}/**/orm/ormatic_interface.py`) is
    rebuilt from source by CI's `Build ORM` step, so its committed content is throwaway - resolve
    the conflict by taking either side (`git checkout --ours`/`--theirs` that path), push, and let
    CI regenerate and validate it.
  - The `krrood` dataset ORM (`test/krrood_test/dataset/ormatic_interface.py`) regenerates locally
    with no ROS: run the `krrood` suite (its conftest rebuilds it), commit the regenerated file, and
    push.
  - Never hand-edit an `ormatic_interface.py`; only take-a-side or regenerate.
- Everything else - a real conflict, or CI-red that isn't ROS-only and isn't the throwaway ORM file -
  is not yours to resolve. DELEGATE it to the branch's owning session, never silently skip it:
  1. Find the owning session: search the fork PR body for a `https://claude.ai/code/session_...` link.
  2. Post a comment on the fork PR, prefixed `🔴 ROUTINE - NEEDS RESOLUTION:`, stating what you were
     doing (e.g. "restacking `<branch>` onto `<parent>` because `<parent>`'s PR just merged/moved"),
     what happened (the conflicting files, or the failing check and its conclusion), and the ask
     ("please resolve and push - I'll pick the branch back up automatically once it restacks clean").
     This comment is the only channel available to you - there is no direct session-to-session
     messaging here - but if that PR's session is still subscribed to its own PR activity (the normal
     thing to do while babysitting a PR), the comment is delivered to it as a live event, not just text
     sitting on GitHub.
  3. Label the fork PR `needs-resolution` (union with its existing labels, per the LABELS ARE REPLACE
     rule above) so the state is visible on the board even if no session is listening, and so you never
     re-attempt the same failing restack on it every run.
  4. At the START of every Phase 2 pass, for each branch currently carrying `needs-resolution`, fetch
     its `mergeable_state` from the GitHub MCP (`pull_request_read` → `get`). If `mergeable_state` is
     NOT `dirty` (i.e. `clean` or `unstable`), the conflict is resolved - clear `needs-resolution`
     (LABELS ARE REPLACE: full current label set minus `needs-resolution`) and include the branch in
     the restack plan normally. Only keep the label and skip the branch when `mergeable_state` is
     `dirty`.
  Record every branch you delegate this run - the FINISH summary must report it (below), since a
  delegated comment is not guaranteed to be seen and I am always the fallback.
- Keep restacking / promoting the other branches in parallel while CI chews on the ones you pushed -
  an ormatic-touching or delegated branch is never a reason to stall the rest of the stack.
Never disable a leak/CI check to go green.

PHASE 3 - PROMOTE (open upstream PRs, or email me the create-links)
Housekeeping first: remove any `cram2-link-sent` label from a fork PR that is now `in-review` or
merged - its link has been acted on.

Collect the fork PRs to promote this run: every branch `python .claude/stack/stack.py next --porcelain`
names - it prints one `name<TAB>pr` line per branch that is approved (un-drafted), whose parent has
reached `in-review` or merged, and that is not withheld by `needs-resolution`. There is no admission
cap and no ordering beyond dependency order: every such branch promotes in the same run. Skip any that
already carry `cram2-link-sent` when deciding whether to build a new link - but still process the
others.

For each collected fork PR (head branch B):
1. Try to open its upstream PR directly via the GitHub MCP - base `<upstream-remote>/main`, head
   `<fork owner>:B`, with a filled title and description. If it succeeds, add the `in-review`
   label to the fork PR and you're done with B.
2. If opening it fails (the usual case - the GitHub app has no write access to the upstream), build the
   compare-and-create URL instead:
     `https://github.com/<upstream-repository>/compare/main...<fork owner>:B?expand=1&title=<url-encoded title>&body=<url-encoded description>`
   Keep the prefilled body SHORT - one paragraph plus a link back to the fork PR for the full detail;
   a compare URL has a length cap and a long body is silently dropped. Collect this link and add the
   `cram2-link-sent` label to B so later runs don't re-send it. Do NOT add `in-review` - the upstream PR
   isn't open until I click Create; I add `in-review` then (the housekeeping step above clears
   `cram2-link-sent`).

After processing them all, compile ALL pending upstream create-links - both (a) any new links built this
run AND (b) any fork PR that already carries `cram2-link-sent` but is not yet `in-review` (re-listed
from a prior run; rebuild the link from the branch name and PR title using the same URL format). Deliver
ALL of them at the very TOP of your FINISH summary - this routine is configured to EMAIL its result, so
the summary IS the email. List each PR's number, title, branch, and its one-click create-link. This
top-of-summary placement is REQUIRED and is what reaches me; set `cram2-link-sent` only on newly built
links (do NOT set it again on PRs that already carry it).
(The Gmail connector can only draft, not send, so do NOT rely on it for delivery. If you want, you MAY
additionally `create_draft` a copy to bido.bassuny@gmail.com - it lands in my Drafts, unsent - but the
summary is the real delivery, never a draft.)

If `next --porcelain` prints nothing, nothing is ready - promote nothing.

FINISH
The TOP of the FINISH summary must list ALL pending upstream create-links: (a) any new links built this
run, and (b) any fork PR currently carrying `cram2-link-sent` but not yet `in-review` (re-listed from
prior runs, link rebuilt from branch name + PR title). This section must appear at the top even when no
new links were built this run, as long as any pending ones exist - that is how I receive them by email.
Right after them, list every branch you DELEGATED this run (Phase 2): its PR number and branch, the
conflicting files or the failing check, the session link you addressed the comment to (or "no session
link found in the PR body" if none), and a link to the comment you posted - this section is REQUIRED
whenever you delegated anything, for the same reason as create-links: it's how I find out. Then list
every PR whose Phase 1 reparent you could not complete - its number, the base it is stuck on, the base
it should have, and which step of the native-stack sequence stopped you - since a stack left dissolved
or half-rebuilt needs my attention immediately, and nothing else surfaces it. Then
summarise: what you closed, restacked, and promoted, and anything you stopped on. The board Action has
already republished Pages from your state changes - you do not touch `board.html` or any Artifact.
```

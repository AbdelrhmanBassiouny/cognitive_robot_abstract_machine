# Stacked-PR workflow (fork staging → cram2 review)

High-velocity, review-constrained workflow. This fork (`origin`) holds the **full stack** of
in-flight branches; **cram2** is the slow review queue. You promote the *bottom* of the stack to
cram2 one at a time, never exceeding a WIP cap. Claude does the mechanical restacking so the tower
never rots and you keep coding.

## The doctrine (why)

The reviewers are the constraint. Throughput dies from (1) big PRs and (2) unbounded work in
review. So: keep each PR small and single-concern, cap how many are in review at once, and make
stack maintenance free. (Stacked diffs + trunk-based small batches + WIP limits — Graphite/Sapling,
DORA/*Accelerate*, Reinertsen, Theory of Constraints.)

## GitHub is the source of truth

You never hand-edit a ledger. The stack is read from **GitHub itself** plus git:

| What | Where it lives | You set it by |
|---|---|---|
| dependency **tree** (parent) | each fork PR's **base branch** (`base = parent`) | retargeting the PR base on GitHub |
| `draft` ↔ `ready` | the fork PR's **draft toggle** | un-drafting when you approve it |
| `in-review` | the **`in-review` label** on the fork PR | labelling at promote time (cram2 isn't readable from the cloud) |
| `merged` | branch is an ancestor of `cram2/main` | nothing — pure git |
| WIP-exempt | the **`bug`** label (`wip_exempt_labels`) | labelling on GitHub |
| `merge` vs `rebase` | the **`rebase`** label; default `merge` | labelling on GitHub |
| cram2 create-link emailed | the **`cram2-link-sent`** marker | nothing — the routine sets it when it emails you a create-link, and clears it once you promote (add `in-review`) |

## Files

- **`stack.toml`** — **config only**: `wip_cap`, `wip_exempt_labels`, the label names, and the
  remotes. No branches, no per-PR state. You rarely touch it.
- **`board.json`** — the fork-PR export (`number`, `head`, `base`, `draft`, `labels`, `ci`, `session`)
  that `stack.py` reads. **Generated and git-ignored, never committed**: `stack.py export` writes it
  from live fork PRs via `gh`, the routine writes it as scratch via the GitHub MCP, and the
  stack-board Action regenerates it on its own runner. It is fully reproducible from GitHub (`ci` from
  the check rollup, `session` parsed from the PR body), so a committed copy would only go stale and
  make `stack.py status` report wrong state. Machine-written — don't hand-edit; if it's missing, run
  `export`.
- **`stack.py`** — read-only status tool (never mutates branches). Reads `board.json` + git:
  - `python dev/stack.py status` — the whole stack, with ahead/behind drift per parent.
  - `python dev/stack.py check` — would each branch integrate cleanly onto its parent *now*
    (fast, non-mutating `git merge-tree` probe)?
  - `python dev/stack.py next` — which branch to submit to cram2 next, honouring dependency order
    and the WIP cap. **This is your "what goes to cram2 next" answer.**
  - `python dev/stack.py next --porcelain` — machine-readable `next`: prints only `name<TAB>pr` for
    the branch to promote (or nothing). For the autonomous promote Routine.
  - `python dev/stack.py restack-plan` — the bottom-up restack plan as JSON (one
    `{branch, parent, strategy}` per not-yet-`merged` branch, in-review ones included so they pick up a
    moved parent via a conflict-free `merge`). Feed straight into the `restack` workflow's `args`.
  - `python dev/stack.py export` — (re)write `board.json` from live fork PRs via `gh`.
- **`../.claude/workflows/restack.js`** — the Claude Workflow that actually restacks: one
  worktree-isolated agent per branch, bottom-up, resolving conflicts + greening the targeted tests
  + pushing. It has **no hardcoded stack** — it reads the plan from `args`, so launch it as
  `Workflow({ scriptPath: ".claude/workflows/restack.js", args: <output of dev/stack.py restack-plan> })`.
  Stops at the first branch it can't restack safely (downstream depends on it); re-running caches
  completed branches.

## The state machine (your approval gate)

`draft` → **`ready`** → `in-review` → `merged`, all derived from GitHub:

- `draft → ready` is **your gate**: self-review the fork PR and **un-draft it** on GitHub to approve.
  `stack.py next` will **only** ever promote a `ready` (un-drafted) branch — nothing reaches cram2
  without your sign-off.
- `ready → in-review`: when you promote it, add the **`in-review`** label to the fork PR.
- `in-review → merged`: automatic once the branch lands in `cram2/main` (git ancestry).

## The loop you run

1. Code at full speed on top of your stack tip; open each PR with **`base` = its parent branch**.
2. **Self-review the bottom fork PR.** If good, **un-draft it** on GitHub. ← the gate.
3. `python dev/stack.py next` → it names the approved, unblocked branch under the WIP cap. Open its
   cram2 PR and add the **`in-review`** label to the fork PR.
4. When cram2 merges it: nothing to edit — it becomes `merged` automatically. Run the `restack`
   workflow to cascade the new base up the stack; `status`/`check` confirm it's clean again.
5. Keep in-review count ≤ `wip_cap`. If the cap is full, keep the rest draft on the fork; don't flood
   reviewers. PRs carrying a `wip_exempt_labels` label (default `bug`) do **not** count against the
   cap — a standalone bug fix shouldn't block feature throughput.

## Rules of hygiene

- **One branch ⇄ one session.** Never point two live sessions at the same branch (force-push races).
- **The branch is the durable state** — commit + push often; cloud containers are ephemeral.
- **Restack only after the parent has landed/updated.** Restacking onto a still-conflicting,
  unmerged parent is premature — land the parent first.
- **Refresh `board.json` before acting.** It's a snapshot; `stack.py export` (or the routine) brings
  it current with GitHub. `restack.js` takes its stack from `args` (via `restack-plan`), so there is
  nothing to keep in sync by hand.
- **CI is the validator; validate ROS-free first.** Cloud containers have no ROS, so never try to run
  the coraplex/SDT suites locally — **subscribe** to a PR's CI (GitHub MCP `subscribe_pr_activity`)
  and treat its red/green as the oracle. Before deferring anything to a ROS session, get around ROS
  as far as you can locally: reproduce the failure's *mechanism* in the ROS-free layer (`krrood`,
  which runs locally) with a meaningful failing test — mimicking the offending pattern in the
  `krrood` test datasets per `AGENTS.md` when the trigger lives in another package — fix it there,
  and validate by running the local `krrood` suite before pushing. Then let fork CI confirm the
  ROS-gated end-to-end behaviour. Only the residue that genuinely cannot be reproduced or validated
  without ROS is handed to a ROS session. Never disable a leak/CI check to go green.

## The board: chips, priority, sessions

`dev/board.html` (published to GitHub Pages by the `board` Action) renders the tree with per-PR
readiness chips, all derived — never hand-set:

- **CI** — green/red/amber from the PR's check rollup (`ci` in `board.json`, filled by `export`). Grey
  `—` when no CI has run.
- **Short** — lines changed vs the parent (computed by `stack.py board` via git). Green under
  `short_threshold_loc`, red over. A red *Short* usually means the branch is big **or** stale — split
  or restack it.
- **Conflicts** — would it merge cleanly onto its parent right now (git `merge-tree`)? Green `clean` /
  red `yes`.
- **priority** — set a `priority:high|medium|low` label on the fork PR. Among several ready branches,
  `stack.py next` promotes the highest priority (ties fall back to dependency order).
- **session** — a chip linking to the Claude session working the PR (parsed from the PR body). If none,
  a `+ new` chip opens a fresh cloud session for that branch. Point `NEW_SESSION_URL` in `board.html`
  at your internet-enabled environment deep-link so the new session gets fork + cram2 access.

**Reload** shows the latest version the refresh routine published — a hosted page can't call GitHub
itself. For a true "recapture now" button, wire a phone Shortcut to an API-triggered refresh routine.

## The cloud Routine (paste into claude.ai/code/routines)

One autonomous cloud session that runs the whole loop hands-free on each trigger (a merge in the
fork, or a schedule). It uses **plain sequential git** — no Workflow tool, no permission prompts. It
reads state from GitHub (fork PRs) via the GitHub MCP, refreshes `board.json`, and drives `stack.py`.
It never exceeds `wip_cap`, and it auto-closes fork PRs whose work has already landed upstream. Keep
the prompt generic (no feature names).

```text
You maintain a stacked-PR fork-staging workflow. `origin` is my fork (the full stack); `cram2` is the
slow upstream review queue. GitHub is the source of truth: a fork PR's BASE branch is its parent, the
DRAFT flag is the ready gate, an `in-review` label means promoted-to-cram2, and a branch that is an
ancestor of cram2/main is merged. Do NOT use the Workflow tool. Use plain git + the GitHub MCP. Never
force-push a branch that has an open cram2 PR unless it carries the `rebase` label.

YOUR JOB, AND ONLY THIS: close landed fork PRs (Phase 1), restack branches whose parent moved (Phase 2),
promote the next approved branch under the WIP cap (Phase 3), and react to your own restacks' CI. That
is the whole job. It is NOT your job to do code review, or to read/answer/resolve/act on the developer's
review comments, or to make code changes that address review feedback — that is the developer's
interactive session's work. Leave review threads untouched. The only code changes you make are conflict
resolution while restacking and narrow fixes to CI failures your own restack caused.

HARD RULES so you never drift into review work:
- NEVER call `subscribe_pr_activity`, and never stay subscribed — you learn CI by POLLING (Phase 2/SETUP).
- If a review, review-comment, issue-comment, or any `<github-webhook-activity>` event is ever delivered
  to you, your ONLY valid action is to END THE TURN immediately: do not investigate it, do not draft or
  post a plan, do not reply, do not ask the developer to confirm anything. The one exception is a CI/check
  *status* you were polling for your own restack.
- NEVER enter plan mode or post a "here's my plan" comment. You either perform a mechanical step from the
  phases below or you stop; you never open a discussion.

PRE-FLIGHT — before EVERY push, merge, or restack, no exceptions
Never move commits from memory. First WRITE OUT these four lines and verify each with git; only then run
the command:
  - ACTION: push | merge | restack.
  - FROM (source): run `git branch --show-current` and `git rev-parse --short HEAD`. The checked-out
    branch MUST be the one whose content you intend to move. NEVER push while checked out on a different
    branch, and NEVER map a mismatched refspec — use `git push origin <branch>` or `<branch>:<branch>`
    with identical names. A `git push origin HEAD:<other-branch>` or a `<src>:<dst>` where src≠dst is
    FORBIDDEN unless you have explicitly written out and verified both sides.
  - INTO (destination): the exact remote + branch (e.g. `origin/eql-core-prep`). Confirm the remote is
    the fork (`origin`), never `cram2`. If force-pushing, confirm no open cram2 PR (or it carries
    `rebase`) and use `--force-with-lease`.
  - WHY: one sentence — what you are integrating and why it belongs on that destination branch.
Then INTENT-CHECK the parentage before pushing: run `git log --oneline -5 <source>` and
`git log --oneline -3 origin/<destination>`; the only new commits about to land on the destination must
be the ones you expect. If a CHILD branch's commits would become ancestors of its PARENT, GitHub will
auto-mark the child PR as merged — a false merge. STOP and do not push. (This exact mistake once pushed
`rdr-engine`'s HEAD onto `eql-core-prep` and falsely merged the child PR #29.)

SETUP
0. Ensure remotes match the config: `origin` must be the fork
   (AbdelrhmanBassiouny/cognitive_robot_abstract_machine) and `cram2` the upstream. A fresh cloud
   clone may have them named differently — check `git remote -v` and rename/add so `origin`=fork,
   `cram2`=upstream before continuing.
1. UPDATE FORK MAIN FIRST — before anything else. Every `base=main` comparison (both GitHub's PR
   diffs and the board's LOC/conflict chips) is measured against `origin/main`, so a stale fork main
   inflates every root branch's diff. Fork main is a pristine mirror of the upstream trunk — keep it
   that way, because root branches base on it and the restack merges it into them, so anything you add
   here would flow into every branch and then into cram2. Fast-forward it:
     `git fetch cram2 main && git push origin cram2/main:main`
   This MUST be a fast-forward. If GitHub rejects it as non-fast-forward (fork main has unique
   commits), STOP and report — do NOT force.
2. `git fetch origin`.
3. Refresh `dev/board.json` from the fork's OPEN PRs (number, head, base, isDraft, labels, and — for
   the chips — statusCheckRollup and body) via the GitHub MCP, then run `python dev/stack.py status`
   to see the derived stack. There is no `--live` flag; state comes from board.json + git.
4. CI IS THE VALIDATOR — POLL IT, NEVER SUBSCRIBE. When you need a branch's CI verdict, POLL it with
   the GitHub MCP (`pull_request_read` → `get_check_runs` / `get_status`) and read only the
   success/failure conclusion; never run the ROS (coraplex/SDT) suites here. Do NOT call
   `subscribe_pr_activity` — a subscription delivers human review comments and review threads (not just
   CI) and turns on the built-in per-event handler that makes you investigate, plan, and reply. That is
   how you end up "responding to reviews"; polling avoids it entirely.

THE BOARD PUBLISHES ITSELF
You do not render or redeploy the board. A GitHub Action in the separate `stack-board` repo polls the
fork and republishes the board to its own GitHub Pages site every few minutes. So make your state
changes and move on; the board catches up on its next poll. Never render `board.html` or redeploy an
Artifact here.

PHASE 1 — AUTO-CLOSE LANDED FORK PRs
cram2 always merges with a merge commit (never squash/rebase), so a landed branch is always an
ancestor of cram2/main. For each OPEN fork PR with head branch B:
- If `git merge-base --is-ancestor origin/B cram2/main` succeeds, B has landed → CLOSE the fork PR
  with a comment noting it merged into cram2/main.
- NEVER close a fork PR whose work has NOT landed. (Merged is the only close condition.)

PHASE 2 — RESTACK + VALIDATE (CI is the validator; ROS-free fix-first; work in parallel)
Run `python dev/stack.py restack-plan` for the bottom-up plan. For each entry whose parent moved,
integrate the parent using its `strategy` (merge = default, no force-push; rebase =
force-push-with-lease) ONLY IF the merge is clean, then push. CI is the validator — never run the
coraplex/SDT (ROS) suites here; poll the PR's checks with the GitHub MCP (do NOT subscribe).

Don't block on CI: after pushing a branch, move on to the next independent branch and keep restacking
/ promoting (Phase 3) in parallel — never sit idle waiting on a ~20-minute run. Poll the checks of the
branches you pushed at the start of each pass (and on your next scheduled run) and react then.

When a branch conflicts or its CI comes back RED, get around ROS as far as you can — never park a
branch on a ROS dependency; resolve it non-blockingly and let CI be the final check:
- If the failure/mechanism lives in the ROS-free layer (`krrood`, which runs here), reproduce it
  locally with a meaningful failing test (mimic the offending pattern in the `krrood` test datasets
  per `AGENTS.md` when it originates in another package), fix it, and validate by running the
  `krrood` suite locally; push and let CI confirm end-to-end.
- A generated `ormatic_interface.py` conflict never blocks — the file is regenerated, not
  hand-authored, so never skip the branch or its descendants over it. Resolve it and depend on CI:
  - Package ORM (`{semantic_digital_twin,coraplex,experiments}/**/orm/ormatic_interface.py`) is
    rebuilt from source by CI's `Build ORM` step, so its committed content is throwaway — resolve
    the conflict by taking either side (`git checkout --ours`/`--theirs` that path), push, and let
    CI regenerate and validate it.
  - The `krrood` dataset ORM (`test/krrood_test/dataset/ormatic_interface.py`) regenerates locally
    with no ROS: run the `krrood` suite (its conftest rebuilds it), commit the regenerated file, and
    push.
  - Never hand-edit an `ormatic_interface.py`; only take-a-side or regenerate.
- Keep restacking / promoting the other branches in parallel while CI chews on the ones you pushed —
  an ormatic-touching branch is never a reason to stall the rest of the stack.
Never disable a leak/CI check to go green.

PHASE 3 — PROMOTE (open cram2 PRs, or email me the create-links)
Housekeeping first: remove any `cram2-link-sent` label from a fork PR that is now `in-review` or
merged — its link has been acted on.

Collect the fork PRs to promote this run:
- EVERY `bug`-labelled PR that is ready (un-drafted), not `in-review`, and not already
  `cram2-link-sent` — bug PRs are cap-exempt, so all of them qualify; PLUS
- the SINGLE branch `python dev/stack.py next --porcelain` names when a slot is free (approved,
  unblocked, under `wip_cap`). If that branch already carries `cram2-link-sent`, a link is pending —
  promote nothing else this run and wait for me to open it.

For each collected fork PR (head branch B):
1. Try to open its cram2 PR directly via the GitHub MCP — base `cram2/main`, head
   `AbdelrhmanBassiouny:B`, with a filled title and description. If it succeeds, add the `in-review`
   label to the fork PR and you're done with B.
2. If opening it fails (the usual case — the GitHub app has no write access to cram2), build the
   compare-and-create URL instead:
     `https://github.com/cram2/cognitive_robot_abstract_machine/compare/main...AbdelrhmanBassiouny:B?expand=1&title=<url-encoded title>&body=<url-encoded description>`
   Keep the prefilled body SHORT — one paragraph plus a link back to the fork PR for the full detail;
   a compare URL has a length cap and a long body is silently dropped. Collect this link and add the
   `cram2-link-sent` label to B so later runs don't re-send it. Do NOT add `in-review` — the cram2 PR
   isn't open until I click Create; I add `in-review` then (the housekeeping step above clears
   `cram2-link-sent`).

After processing them all, if you collected any create-links, deliver them to me by putting them at the
very TOP of your FINISH summary — this routine is configured to EMAIL its result, so the summary IS the
email. List each PR's number, title, branch, and its one-click create-link. This top-of-summary
placement is REQUIRED and is what reaches me; set `cram2-link-sent` once a link is in the summary.
(The Gmail connector can only draft, not send, so do NOT rely on it for delivery. If you want, you MAY
additionally `create_draft` a copy to bido.bassuny@gmail.com — it lands in my Drafts, unsent — but the
summary is the real delivery, never a draft.)

If `next` prints nothing and there are no such bug PRs, the cap is full or nothing is ready — promote
nothing.

FINISH
If you collected any cram2 create-links, they go FIRST, at the very top of this summary (that is how I
receive them by email). Then summarise: what you closed, restacked, and promoted, and anything you
stopped on. The board Action has already republished Pages from your state changes — you do not touch
`board.html` or any Artifact.
```

The promote step is gated by `stack.py next`, which only ever names an un-drafted branch under the cap
— so the Routine can never flood cram2, and never promotes something you haven't approved by
un-drafting its fork PR. Because the app can't write to cram2, promotion usually can't open the PR
directly; the Routine hands you a one-click **compare-and-create** link instead — for every ready,
cap-exempt `bug` PR and for the one non-bug branch a free slot allows — placed at the top of its run
summary. Enable the routine's **email-on-completion notification** at claude.ai/code/routines and that
summary reaches you as an email (the Gmail connector can only draft, not send, so delivery rides on the
routine's own notification). Each link is marked `cram2-link-sent` so you're never sent it twice.

## The board GitHub Action (a separate `stack-board` repo → its own Pages)

Board *refresh* is pure mechanics — fetch the fork's open PRs, render, publish — so it is a GitHub
Action, not a routine. It lives in a **separate public repo** (`stack-board`) for one hard reason: a
repo has exactly one GitHub Pages site, and the fork's Pages is already taken by the docs. A second
`deploy-pages` in the fork would clobber the docs (and vice-versa), so the board gets its own repo and
its own Pages URL.

The Action (`.github/workflows/board.yml` in `stack-board`) checks out the fork's
`claude/stack-workflow-tooling` branch, runs `python dev/stack.py export` (open PRs via `gh` + the
board repo's built-in `GITHUB_TOKEN` — the fork is public, so no PAT) then `python dev/stack.py board`
(renders `dev/board.html` from `board.json` + git), and deploys the page to the `stack-board` repo's
Pages. It has `contents: read` + `pages: write` only, and touches nothing on the fork or upstream.

**A workflow only sees events in its own repo**, so the board Action runs on a **`schedule`** (polls
the fork every ~10 min) plus **`workflow_dispatch`** (manual kick). Poll-only is deliberate: an
instant `repository_dispatch` sender would have to live on the fork's `main` (only the default branch
gets `check_suite` events), and since the restack merges `main` into every branch, that sender file
would leak into the stack's PRs and up to cram2 — not worth a few minutes of latency. The restack
Routine keeps the *intelligence* (restack, promote, autofix); the Action keeps the *picture* current
within a poll.

### One-time setup (all in the `stack-board` repo)

1. **Add `.github/workflows/board.yml`** (contents below) to the `stack-board` repo.
2. **Enable Pages:** `stack-board` → **Settings → Pages → Source: GitHub Actions**.
3. Run the workflow once (**Actions → board → Run workflow**) to publish the first page. It then
   self-refreshes on the schedule. Because the fork is public, no secrets/PATs are needed.

### The phone board (one tap)

The board is a Pages site at a **fixed URL** (`https://<owner>.github.io/stack-board/`). On your phone,
open it once and **Add to Home Screen** (Safari: Share → *Add to Home Screen*; Chrome: ⋮ → *Add to
Home screen*). That icon is your one-tap button; the Action republishes the same URL on each poll, so
the tap always shows current state — the header carries the "generated" timestamp. The board is
read-only; you act by tapping a PR (it links straight to the GitHub PR, where you un-draft / label /
retarget).

### Restack Routine triggers (set at claude.ai/code/routines)

Install the Claude GitHub app on the **fork** and give the restack Routine a **schedule** (e.g.
hourly) plus the state-change events that warrant restacking/promoting:

| Run restack when… | GitHub event |
|---|---|
| a new PR is opened | `pull_request: opened` |
| you un-draft a PR (approve it) | `pull_request: ready_for_review` |
| you add/remove a label (`in-review`, `bug`) | `pull_request: labeled` / `unlabeled` |
| a PR is retargeted (parent changed) | `pull_request: edited` |

(cram2 stays untouched — you don't need the app there; merges are detected from the fork by git
ancestry.)

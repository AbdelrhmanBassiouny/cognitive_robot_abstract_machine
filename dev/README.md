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

## Files

- **`stack.toml`** — **config only**: `wip_cap`, `wip_exempt_labels`, the label names, and the
  remotes. No branches, no per-PR state. You rarely touch it.
- **`board.json`** — the fork-PR export (`number`, `head`, `base`, `draft`, `labels`) that `stack.py`
  reads. Refreshed by the routine via the GitHub MCP, or locally with `python dev/stack.py export`
  (uses `gh`). Machine-written — don't hand-edit.
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

SETUP
0. Ensure remotes match the config: `origin` must be the fork
   (AbdelrhmanBassiouny/cognitive_robot_abstract_machine) and `cram2` the upstream. A fresh cloud
   clone may have them named differently — check `git remote -v` and rename/add so `origin`=fork,
   `cram2`=upstream before continuing.
1. UPDATE FORK MAIN FIRST — before anything else. Every `base=main` comparison (both GitHub's PR
   diffs and the board's LOC/conflict chips) is measured against `origin/main`, so a stale fork main
   inflates every root branch's diff. Fork main carries exactly one fork-only commit on top of the
   upstream trunk — `.github/workflows/board.yml`, the board's Pages publisher — so refreshing it is a
   rebase of that single commit, not a plain fast-forward:
     `git fetch cram2 main && git checkout main && git rebase cram2/main && git push --force-with-lease origin main`
   If the rebase reports anything other than replaying that one workflow commit cleanly, STOP and
   report — do NOT force past a conflict. (If you ever find fork main with no such commit, a plain
   `git push origin cram2/main:main` fast-forward is correct.)
2. `git fetch origin`.
3. Refresh `dev/board.json` from the fork's OPEN PRs (number, head, base, isDraft, labels, and — for
   the chips — statusCheckRollup and body) via the GitHub MCP, then run `python dev/stack.py status`
   to see the derived stack. There is no `--live` flag; state comes from board.json + git.
4. SUBSCRIBE TO CI AS VALIDATOR. For every open fork PR, call `subscribe_pr_activity` (GitHub MCP) so
   red/green is delivered to you — CI is the validator; never run the ROS (coraplex/SDT) suites here.

THE BOARD PUBLISHES ITSELF
You do not render or redeploy the board. The `board` GitHub Action (`.github/workflows/board.yml`)
rebuilds it on GitHub Pages whenever a PR, its CI, or a label changes — which is exactly what your
state changes below produce (closing a PR, pushing a restacked branch, adding the `in-review` label).
So make the state change and move on; the board follows. Never hand-redeploy an Artifact.

PHASE 1 — AUTO-CLOSE LANDED FORK PRs
cram2 always merges with a merge commit (never squash/rebase), so a landed branch is always an
ancestor of cram2/main. For each OPEN fork PR with head branch B:
- If `git merge-base --is-ancestor origin/B cram2/main` succeeds, B has landed → CLOSE the fork PR
  with a comment noting it merged into cram2/main.
- NEVER close a fork PR whose work has NOT landed. (Merged is the only close condition.)

PHASE 2 — RESTACK + VALIDATE (CI is the validator; ROS-free fix-first; work in parallel)
Run `python dev/stack.py restack-plan` for the bottom-up plan. For each entry whose parent moved,
integrate the parent using its `strategy` (merge = default, no force-push; rebase =
force-push-with-lease) ONLY IF the merge is clean, then push, and subscribe to that PR's CI
(`subscribe_pr_activity`). CI is the validator — never run the coraplex/SDT (ROS) suites here.

Don't block on CI: after pushing a branch, move on to the next independent branch and keep restacking
/ promoting (Phase 3) in parallel, reacting to CI results as the subscription delivers them — never
sit idle waiting on a ~20-minute run.

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

PHASE 3 — PROMOTE (obey the WIP cap)
Run `python dev/stack.py next --porcelain`. It prints `name<TAB>pr` for the single branch that is
approved (un-drafted), unblocked, and under `wip_cap` — or nothing. If it prints a branch: open its
cram2 PR (base cram2/main) with an updated description, then add the `in-review` label to its fork PR.
If it prints nothing, the cap is full or nothing is ready — do not promote. `bug`-labelled PRs never
count against the cap.

FINISH
Summarise: what you closed, restacked, promoted, and anything you stopped on. The board Action has
already republished Pages from your state changes — you do not touch `board.html` or any Artifact.
```

The promote step is gated by `stack.py next`, which only ever names an un-drafted branch under the cap
— so the Routine can never flood cram2, and never promotes something you haven't approved by
un-drafting its fork PR.

## The board GitHub Action (publishes to Pages)

Board *refresh* is pure mechanics — fetch the fork's open PRs, render, publish — so it is a GitHub
Action, not a routine. No LLM, no token cost, no Claude app: `.github/workflows/board.yml` runs
`python dev/stack.py export` (fetches open PRs via `gh`, using the built-in `GITHUB_TOKEN`) then
`python dev/stack.py board` (renders `dev/board.html` from `board.json` + git), and deploys the page
to GitHub Pages. It has `contents: read` + `pages: write` only — it never touches a branch, PR, label,
or the upstream. The restack Routine keeps the *intelligence* (restack, promote, autofix); the Action
keeps the *picture* current between (and during) its runs.

It fires on exactly the events you asked for:

| Refresh the board when… | GitHub event (in `board.yml`) |
|---|---|
| a PR is opened / closed / retargeted | `pull_request: opened, reopened, closed, edited` |
| a branch is pushed (restacked) | `pull_request: synchronize` |
| a label / draft state changes | `pull_request: labeled, unlabeled, ready_for_review, converted_to_draft` |
| CI starts | `check_suite: requested` |
| CI finishes (pass or fail) | `check_suite: completed` |
| nothing happened for a while | `schedule: hourly` (safety net) |

`check_suite` is what carries CI start/finish — `pull_request` events do not — which is why CI
transitions need the Action (a routine can't subscribe to them from GitHub's side). The workflow only
publishes when `github.repository` is the fork, so it stays dormant if the branch ever reaches cram2.

### One-time setup

1. **Put `board.yml` on the fork's default branch (`main`).** GitHub runs `check_suite`/`schedule`
   workflows from the default branch only. This is the single fork-only commit on top of the upstream
   trunk (SETUP step 1 of the Routine rebases it forward). It does **not** pollute PR diffs — a PR's
   3-dot diff excludes commits that are only on its base.
2. **Enable Pages:** repo **Settings → Pages → Source: GitHub Actions**. The first `board` run then
   publishes to `https://<owner>.github.io/<repo>/`.
3. **Visibility:** on a **private** repo, Pages is public unless you're on a plan with private Pages —
   if the board must stay private, either make the repo public or keep the board as a routine-rendered
   private Artifact instead. On a public fork there's nothing to do.

### The phone board (one tap)

The board is a Pages site at a **fixed URL** (`https://<owner>.github.io/<repo>/`). On your phone,
open it once and **Add to Home Screen** (Safari: Share → *Add to Home Screen*; Chrome: ⋮ → *Add to
Home screen*). That icon is your one-tap button; the Action republishes the same URL on every event,
so the tap always shows current state — the header carries the "generated" timestamp. The board is
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

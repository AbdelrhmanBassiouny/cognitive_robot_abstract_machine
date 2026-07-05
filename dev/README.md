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

## The board: chips, priority, sessions

`dev/board.html` (published as an Artifact) renders the tree with per-PR readiness chips, all derived —
never hand-set:

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
1. `git fetch origin && git fetch cram2 main`.
2. Refresh `dev/board.json` from the fork's OPEN PRs (number, head, base, isDraft, labels, and — for
   the chips — statusCheckRollup and body) via the GitHub MCP, then run `python dev/stack.py status`
   to see the derived stack. There is no `--live` flag; state comes from board.json + git.

PHASE 1 — AUTO-CLOSE LANDED FORK PRs
cram2 always merges with a merge commit (never squash/rebase), so a landed branch is always an
ancestor of cram2/main. For each OPEN fork PR with head branch B:
- If `git merge-base --is-ancestor origin/B cram2/main` succeeds, B has landed → CLOSE the fork PR
  with a comment noting it merged into cram2/main.
- NEVER close a fork PR whose work has NOT landed. (Merged is the only close condition.)

PHASE 2 — RESTACK
Run `python dev/stack.py restack-plan` for the bottom-up plan. For each entry, if its parent moved,
integrate the parent into the branch using its `strategy` (merge = default, no force-push; rebase =
force-push-with-lease). Resolve conflicts faithfully. If a generated `ormatic_interface.py` conflicts,
do NOT hand-edit it — run `scripts/regenerate_all_orm.py`. Source ROS
(`source /opt/ros/jazzy/setup.bash && source /opt/ros/overlay_ws/install/setup.bash`) and run ONLY the
tests that branch touches with `/opt/ros/cram-env/bin/python`. Push. Stop at the first branch you
cannot integrate cleanly (downstream depends on its new SHA) and report it.

PHASE 3 — PROMOTE (obey the WIP cap)
Run `python dev/stack.py next --porcelain`. It prints `name<TAB>pr` for the single branch that is
approved (un-drafted), unblocked, and under `wip_cap` — or nothing. If it prints a branch: open its
cram2 PR (base cram2/main) with an updated description, then add the `in-review` label to its fork PR.
If it prints nothing, the cap is full or nothing is ready — do not promote. `bug`-labelled PRs never
count against the cap.

FINISH
Refresh `board.json` again and commit it if it changed. Then run `python dev/stack.py board` and
redeploy `dev/board.html` to the EXISTING board Artifact at
https://claude.ai/code/artifact/d53805e1-177c-4a0d-afd7-4fadc09f3877 (pass that URL so it updates in
place — do NOT mint a new Artifact). Summarise: what you closed, restacked, promoted, and anything you
stopped on.
```

The promote step is gated by `stack.py next`, which only ever names an un-drafted branch under the cap
— so the Routine can never flood cram2, and never promotes something you haven't approved by
un-drafting its fork PR.

### Triggers (set at claude.ai/code/routines)

Install the Claude GitHub app on the **fork** (it's yours), then give the routine both a **schedule**
(e.g. hourly, so nothing goes stale even with no events) and **fork PR-event triggers**. The events
that map to your asks:

| You want it to run when… | GitHub `pull_request` event |
|---|---|
| a new PR is opened | `opened` |
| you un-draft a PR (approve it) | `ready_for_review` |
| you add/remove a label (`in-review`, `bug`) | `labeled` / `unlabeled` |
| a PR is retargeted (parent changed) | `edited` |

The exact event checkboxes appear in the routine's trigger config; tick those. (cram2 stays
untouched — you don't need the app there; merges are detected from the fork by git ancestry.)

### The phone board (one tap)

The board is a hosted Artifact at a **fixed URL**. On your phone, open that URL once and **Add to Home
Screen** (Safari: Share → *Add to Home Screen*; Chrome: ⋮ → *Add to Home screen*). That icon is your
one-tap button. Because the routine redeploys the page to the *same* URL each run, the tap always
shows current state — the header carries the "generated" timestamp so you can see how fresh it is.
The board is read-only; you act by tapping a PR (it links straight to the GitHub PR, where you
un-draft / label / retarget).

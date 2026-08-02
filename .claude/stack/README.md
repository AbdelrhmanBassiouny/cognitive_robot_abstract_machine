# Stacked-PR workflow (fork staging → cram2 review)

High-velocity, review-constrained workflow. This fork (`origin`) holds the **full stack** of
in-flight branches; **cram2** is the slow review queue. You promote approved branches to
cram2 as their parents land. Claude does the mechanical restacking so the tower never rots
and you keep coding.

## The rationale (why)

The reviewers are the constraint. Throughput dies from big PRs and unbounded work in review,
so: keep each PR small and single-concern, and make stack maintenance free. (Stacked diffs +
trunk-based small batches - Graphite/Sapling, DORA/*Accelerate*, Reinertsen, Theory of
Constraints.)

## GitHub is the source of truth

You never hand-edit a ledger. The stack is read from **GitHub itself** plus git:

| What | Where it lives | You set it by |
|---|---|---|
| dependency **tree** (parent) | each fork PR's **base branch** (`base = parent`) | retargeting the PR base on GitHub - from a session, only via the GitHub MCP `update_pull_request` tool (see `ROUTINE.md`) |
| `draft` ↔ `ready` | the fork PR's **draft toggle** | un-drafting when you approve it |
| `in-review` | the **`in-review` label** on the fork PR | labelling at promote time (cram2 isn't readable from the cloud) |
| `merged` | branch is an ancestor of `cram2/main` | nothing - pure git |
| `merge` vs `rebase` | the **`rebase`** label; default `merge` | labelling on GitHub |
| cram2 create-link emailed | the **`cram2-link-sent`** marker | nothing - the routine sets it when it emails you a create-link, and clears it once you promote (add `in-review`) |
| conflict/CI-red delegated | the **`needs-resolution`** label | nothing - the routine sets it when it delegates a restack conflict to the branch's owning session, and clears it once the restack goes clean again |

## Files

- **`stack.toml`** - the committed defaults: label names, and `upstream_repository`, the one
  repository that is the same for every contributor. It names nobody's fork: the fork is
  *whichever remote is not the upstream*, matched by the repository each URL points at rather
  than by what the remote is called, so `origin` may be either one. A
  `.claude/personal/stack.toml` on the personal-notes branch layers your own overrides on top
  (see `stack.py`'s `load_configuration`), including a `fork_repository` to pick between remotes
  when more than one could be the fork.
- **`board.json`** - the fork-PR snapshot (`number`, `head`, `base`, `draft`, `labels`, `ci`,
  `session`) that `stack.py` reads. Written by the routine (via the GitHub MCP) as scratch -
  never committed, and not produced by anything in this directory; see `ROUTINE.md`.
- **`stack.py`** - read-only status tool (never mutates branches). Reads `board.json` + git:
  - `python .claude/stack/stack.py status` - the whole stack, with ahead/behind drift per parent.
  - `python .claude/stack/stack.py check` - would each branch integrate cleanly onto its parent
    *now* (fast, non-mutating `git merge-tree` probe)?
  - `python .claude/stack/stack.py next` - every branch ready to submit to cram2 next: approved,
    parent landed, not withheld. **This is your "what goes to cram2 next" answer.**
  - `python .claude/stack/stack.py next --porcelain` - machine-readable `next`: one
    `name<TAB>pr` line per branch to promote (or nothing). For the autonomous promote Routine.
  - `python .claude/stack/stack.py restack-plan` - the bottom-up restack plan as JSON (one
    `{branch, parent, strategy}` per not-yet-`merged` branch, in-review ones included so they
    pick up a moved parent via a conflict-free `merge`). Feed straight into the `restack`
    workflow's `args`.
  - `python .claude/stack/stack.py configuration` - every resolved setting as `key<TAB>value`
    lines, keyed by `Configuration`'s own field names: the labels, the upstream base, which
    remote is the fork and which is the upstream, plus the exact `git remote add` command when
    no upstream remote exists yet. Answerable from git alone, so it runs before `board.json`
    exists; it exits non-zero rather than guessing when the fork is ambiguous. `ROUTINE.md`'s
    SETUP runs this instead of inspecting or renaming remotes itself, and it is the one surface
    shell tooling reads configuration through - parsing `stack.toml` directly would miss the
    personal override.
- **`ROUTINE.md`** - the cloud Routine's live prompt. The Routine reads it from git each run, so
  editing it changes the running workflow on push; only a short pointer is registered at
  claude.ai/code/routines. Never re-embed a copy here.
- **`POINTER.md`** - that short pointer, as a template. It is the only part of the workflow that
  lives outside git, so a copy is kept here to keep the running prompt from becoming its own only
  record; its HARD RULES are pinned against `ROUTINE.md`'s by `tests/test_prompt_documents.py`.
  Editing it does not change the running Routine - re-register it by hand.
- **`prompt_model.py`** - the landmarks, rules and vocabulary `ROUTINE.md` and `POINTER.md` are
  required to use, so the contract tests assert against declared text rather than restating the
  documents.

## The state machine (your approval gate)

`draft` → **`ready`** → `in-review` → `merged`, all derived from GitHub:

- `draft → ready` is **your gate**: self-review the fork PR and **un-draft it** on GitHub to
  approve. `stack.py next` only ever promotes a `ready` (un-drafted) branch - nothing reaches
  cram2 without your sign-off.
- `ready → in-review`: when you promote it, add the **`in-review`** label to the fork PR.
- `in-review → merged`: automatic once the branch lands in `cram2/main` (git ancestry).

## The loop you run

1. Code at full speed on top of your stack tip; open each PR with **`base` = its parent branch**.
2. **Self-review the bottom fork PR.** If good, **un-draft it** on GitHub. ← the gate.
3. `python .claude/stack/stack.py next` → it names every approved, unblocked branch. Open its
   cram2 PR and add the **`in-review`** label to the fork PR.
4. When cram2 merges it: nothing to edit - it becomes `merged` automatically. Run the `restack`
   workflow to cascade the new base up the stack; `status`/`check` confirm it's clean again.

## Rules of hygiene

- **One branch ⇄ one session.** Never point two live sessions at the same branch (force-push
  races).
- **The branch is the durable state** - commit + push often; cloud containers are ephemeral.
- **Restack only after the parent has landed/updated.** Restacking onto a still-conflicting,
  unmerged parent is premature - land the parent first.
- **Refresh `board.json` before acting.** It's a snapshot; the routine brings it current with
  GitHub.
- **CI is the validator; validate ROS-free first.** Cloud containers have no ROS, so never try
  to run the coraplex/SDT suites locally - poll a PR's CI with the GitHub MCP and treat its
  red/green as the oracle (leave `subscribe_pr_activity` to an interactive session babysitting
  that one PR - the automated Routine never subscribes; see `ROUTINE.md`'s HARD RULES). See
  `ROUTINE.md`'s Phase 2 for how to get around a ROS dependency before handing anything to a ROS
  session. Never disable a leak/CI check to go green.

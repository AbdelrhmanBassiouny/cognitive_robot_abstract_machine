# Stacked-PR workflow (fork staging → cram2 review)

High-velocity, review-constrained workflow. This fork (`origin`) holds the **full stack** of
in-flight branches; **cram2** is the slow review queue. You promote approved branches to
cram2 as their parents land. Claude does the mechanical restacking so the stack never rots
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
| dependency **tree** (parent) | each fork PR's **base branch** (`base = parent`) | retargeting the PR base on GitHub - from a session, only via the GitHub MCP `update_pull_request` tool (see the maintenance skill) |
| `draft` ↔ `ready` | the fork PR's **draft toggle** | un-drafting when you approve it |
| `in-review` | the **`in-review` label** on the fork PR | labelling at promote time (cram2 isn't readable from the cloud) |
| `merged` | branch is an ancestor of `cram2/main` | nothing - GitHub marks the PR merged itself once its head is contained in its base |
| `merge` vs `rebase` | the **`rebase`** label; default `merge` | labelling on GitHub |
| cram2 create-link built | the **`cram2-link-sent`** marker | nothing - a maintenance pass sets it when it puts a create-link in the PR description, and clears it once you promote (add `in-review`) |
| conflict/CI-red reported | the **`needs-resolution`** label | nothing - a maintenance pass sets it when it reports a restack conflict to the branch's owning session, and clears it once the branch stops conflicting |

## Files

- **`stack.toml`** - the committed defaults: label names, and `upstream_repository`, the one
  repository that is the same for every contributor. It names nobody's fork: the fork is
  *whichever remote is not the upstream*, matched by the repository each URL points at rather
  than by what the remote is called, so `origin` may be either one. A
  `.claude/personal/stack.toml` on the personal-notes branch layers your own overrides on top
  (see `stack.py`'s `load_configuration`), including a `fork_repository` to pick between remotes
  when more than one could be the fork.
- **`board.json`** - the fork-PR snapshot (`number`, `head`, `base`, `draft`, `labels`, `ci`,
  `session`) that `stack.py` reads. Written from GitHub as scratch by whatever refreshes it -
  never committed, and not produced by anything in this directory.
- **`stack.py`** - read-only status tool (never mutates branches). Reads `board.json` + git:
  - `python .claude/stack/stack.py status` - the whole stack, with ahead/behind drift per parent.
  - `python .claude/stack/stack.py check` - would each branch integrate cleanly onto its parent
    *now* (fast, non-mutating `git merge-tree` probe)?
  - `python .claude/stack/stack.py next` - every branch ready to submit to cram2 next: approved,
    parent landed, not withheld. **This is your "what goes to cram2 next" answer.**
  - `python .claude/stack/stack.py next --porcelain` - machine-readable `next`: one
    `name<TAB>pr` line per branch to promote (or nothing).
  - `python .claude/stack/stack.py restack-plan` - the bottom-up restack plan as JSON (one
    `{branch, parent, strategy}` per not-yet-`merged` branch, in-review ones included so they
    pick up a moved parent via a conflict-free `merge`).
  - `python .claude/stack/stack.py configuration` - every resolved setting as `key<TAB>value`
    lines, keyed by `Configuration`'s own field names: the labels, the upstream base, which
    remote is the fork and which is the upstream, plus the exact `git remote add` command when
    no upstream remote exists yet. Answerable from git alone, so it runs before `board.json`
    exists. It takes `--fork`/`--upstream` for a caller that already knows the answer, and exits
    `4` rather than guessing when nothing does. This is the one surface shell tooling reads
    configuration through - parsing `stack.toml` directly would miss the personal override.
  - `python .claude/stack/stack.py labels --current <label> --add <label> --remove <label>` - the
    **complete** label set to write back, one per line. GitHub's label write replaces the whole set,
    so computing it from the intended change alone silently strips the rest; this is what the
    maintenance skill passes to every label write rather than working it out itself.
  - `python .claude/stack/stack.py check-move --action push --source B --destination B
    --destination-remote <remote>` - exits `0` when the move is safe and `5` with its reasons on
    stderr when it is not: wrong branch checked out, a push naming different branches on each
    side, a destination that is not the fork, or a push that would make a child an ancestor of its
    own parent (which GitHub reads as a merged pull request).
  - `python .claude/stack/stack.py promotion-link --branch B --title T --body ...` - the upstream
    compare-and-create URL, encoded and within the length limit, warning on stderr when the body had
    to be shortened.
  - `python .claude/stack/stack.py reparents` - one `branch<TAB>pr<TAB>current base<TAB>target base`
    line per open PR whose base has already landed, including a base whose own PR was *closed* and
    which is therefore absent from `board.json`.
  - `python .claude/stack/stack.py landed` - one `name<TAB>pr` line per open fork PR whose branch
    is already in the upstream base. Reporting only: fast-forwarding the fork's copy of the
    upstream base is what actually closes them.
- **`maintenance.py`** - the executor: the half of a pass that moves commits, where `stack.py`
  only derives and prints. `board --write`, `fast-forward`, `restack`, `promote` and
  `run-report --json`; see [Running a maintenance pass](#running-a-maintenance-pass). It is the
  command line onto modules named for what they do, so nothing has to be hunted for inside one
  long file: `maintenance_constants.py` (every value edited by hand),
  `maintenance_git_commands.py`, `maintenance_board.py`, `maintenance_github.py`,
  `maintenance_fast_forward.py`, `maintenance_restack_steps.py` and
  `maintenance_restack_procedure.py` (the steps, and the order that is the procedure),
  `maintenance_promotion.py`, `maintenance_report.py` and `maintenance_commands.py`.
- **`.claude/skills/stacked-pr-maintenance/SKILL.md`** - the maintenance instructions, invocable
  as `/stacked-pr-maintenance` from any session and the whole of what a scheduled run executes.
  It takes `fork=` / `upstream=` arguments, falls back to `configuration`, and asks (or, with
  `--non-interactive`, stops) when neither answers. Its `routine-prompt.md` is the template to
  register when you want the pass to run unattended.
- **`integration.py`** - builds the branch you *work from* while the review queue lags: the
  upstream base with every reviewed in-flight stack tip merged on top, regenerated from scratch
  each time. It writes to no branch and pushes nothing.
  - `python .claude/stack/integration.py build` - assemble it, then run the suite on the result.
    `--restack` brings stale tips forward first, which pushes to other people's branches and is
    why it is opt-in; `--no-test` skips the suite; `--json` emits the whole build as one document.
  - `python .claude/stack/integration.py locate-break` - when the branch builds and the suite fails on
    it, add the tips back one at a time until it turns, and name the pair. A semantic collision
    leaves no conflict to attribute, so there is nothing else to go on.
  - `stage-conflict` / `record-resolution` - reproduce one collision, and record what was chosen
    so later builds replay it instead of skipping the tip again.
- **`.claude/skills/integration-conflict-triage/SKILL.md`** - what a collision between two
  in-flight branches *means*, which the build deliberately does not decide. Invocable as
  `/integration-conflict-triage`.

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
4. When cram2 merges it: nothing to edit - it becomes `merged` automatically. Run a maintenance
   pass to cascade the new base up the stack; `status`/`check` confirm it's clean again.

## Running a maintenance pass

Everything in step 4 - reparenting a pull request whose base has landed, fast-forwarding the
fork's copy of the upstream base, restacking whatever the move left behind, and building the
promotion links for whatever is now ready - is one skill. From any session:

```text
/stacked-pr-maintenance
```

With no arguments it resolves the fork and the upstream from your checkout, and asks once if it
cannot; the answer is saved to `.claude/personal/stack.toml` on your personal-notes branch, so it
never asks twice. Pass them explicitly to skip resolution entirely:

```text
/stacked-pr-maintenance fork=<owner/repo> upstream=<owner/repo>
```

To run it unattended, register it as a scheduled Routine; the prompt to paste is in
[`routine-prompt.md`](../skills/stacked-pr-maintenance/routine-prompt.md).

## Working from an integration branch

The loop above gets branches *reviewed*; it does nothing for the fact that you cannot use two
unlanded features at once. `integration.py build` assembles them into one branch to work from,
and moves `integration` to whatever it just built:

```bash
python .claude/stack/integration.py build
```

It gates nothing. Promotion asks whether one branch is ready for review; integration asks whether
the branches coexist, and a collision between two of yours is not a reason to hold either back.
A tip that collides is skipped so the rest still builds, and the report names the **pair** - which
of the two should change is a judgement, and `/integration-conflict-triage` is where it is made.

**Only branches you have reviewed are carried.** A pull request stays a draft here until its
author has read it back, so leaving draft is that review, and a build is made of work that has
had it. Because a tip contains its whole stack, this is read down the entire chain: a reviewed
branch standing on a draft is left out with it, and the branch merged for a stack is the last one
reached before its first draft. Everything left out is named in the report - as `unreviewed`,
distinct from a tip the build tried to carry and could not - so a build that carried nine branches
out of nineteen says which nine and why, rather than saying so only by omission. Leaving a draft
out is the rule working, so it is not a failing build and does not change the exit status.

Two branches can also merge perfectly and still not work together - one removing what another's
test imports, one adding a dependency another's fixture does not provide. No per-branch check can
see that, because neither branch is wrong and the failure exists only in a tree neither of them
is. That is what the `--test` run on the finished branch is for, and `locate-break` is what turns a red
suite over a dozen merged tips into a named pair.

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
  red/green as the oracle (no session subscribes to a PR's activity - scheduled or interactive,
  CI is learned by polling; see the maintenance skill's HARD RULES). A
  maintenance pass never fixes a failing check: it reports the branch to its owner and moves on.
  Never disable a leak/CI check to go green.

# workflow-unification — roadmap & rationale

Narrative companion to `plan.yaml`. Created 2026-07-29 from the tooling review + implementation
plan worked out in session https://claude.ai/code/session_014DUCCpcvLLLMYszycEBPjP (also condensed
in `pr-progress/claude/stacked-pr-restacking-kz3ptd.md`).

## Why this plan exists — findings of the 2026-07-29 review

The workflow machinery had grown into four storage locations plus a live Routine, with real
duplication and dead weight:

- **Routine prompt duplicated and drifted**: the live Routine at claude.ai/code/routines and the
  copy embedded in `dev/README.md` (lines 147–367 on `claude/stack-workflow-tooling`) had already
  diverged (FINISH section, `cram2-link-sent` wording).
- **Dead/contradictory tooling on the tooling branch**: `.claude/workflows/restack.js` uses the
  Workflow tool and sources local ROS — both forbidden/impossible under the current cloud Routine.
  `dev/README.md`'s hygiene section still instructs `subscribe_pr_activity`, the exact thing the
  Routine's HARD RULES forbid.
- **The round-robin/`stack-turn` subsystem is dead**: `stack.toml` sets `wip_cap = 1000000`
  (deliberate — size/scrutiny predicts review duration better than admission gating), so the
  fairness ordering decides nothing, yet the Routine still stamps/carries turn markers every run
  (prompt tokens + GitHub API writes steering a queue that no longer exists).
- **`claude/session-hooks` superseded**: `main` carries a strict superset of it (+1237/−6) since
  the hooks landed upstream (cram2 #479 lineage); nothing at runtime reads the branch.
- **`cram-notes.md` bloat**: the EQL verbalization living roadmap (~10k tokens incl. 22 review-round
  logs) loads into *every* session on *every* branch — the single largest recurring token cost, and
  exactly the pattern the plan system replaced (`plans/README.md` calls itself "a generalized
  replacement for one-off master-roadmap docs"). `rdr-roadmap.md` also survives as a stale
  duplicate of `plans/rdr-refactor/`.
- **Two dashboard pipelines**: stack board (Pages, auto-refreshing, LOC/CI/conflict chips) vs plan
  dashboards (Artifacts, live-session-only republish, no LOC/CI chips) — two separate
  fetch-PR-state-and-render systems.

What was *not* found: the four-way storage split itself is load-bearing, not accidental. Fork
`main` must mirror upstream (everything on it flows into every stacked branch and up to cram2),
personal data can't be on a merged branch, and the stack-board repo exists because one repo gets
one Pages site and the fork's is taken by docs.

## Target architecture

- **`main` (via cram2, stacked on PR #101)** = all reviewed machinery: hooks, plan skills (already
  there), stack tooling `.claude/stack/{stack.py,ROUTINE.md,README.md}`, `/setup-stacked-prs`.
- **`claude/personal-notes`** = all personal state: conventions (slim), pr-progress, plans,
  `stack.toml` overrides.
- **`stack-board` repo** = the single auto-publishing surface: board + every plan dashboard, one
  Action, one Pages site, LOC/CI chips everywhere.
- **Live Routine** = ~10 lines: inline HARD RULES + "read `.claude/stack/ROUTINE.md` and execute".
- **Retired**: `claude/session-hooks` (now), `claude/stack-workflow-tooling` (after one green
  cycle on the new paths).

## Design decisions (with the reasoning that settled them)

1. **Code on `main`, per-user state as config — not per-user code branches.** A per-user branch
   holding `stack.py` instances has the template-drift problem the personal-notes system avoids by
   holding only data. For cram2, personal stack config lives on the personal-notes branch
   (`.claude/personal/stack.toml`), which `/setup-personal-notes` (PR #101) already creates.
2. **Fork-overlay install mode reconciles portability** (user question, 2026-07-29): for a foreign
   repo whose maintainers won't take `.claude/` tooling upstream, `/setup-stacked-prs` installs the
   same canonical files onto a never-merged tooling branch of the user's fork — today's
   `claude/stack-workflow-tooling` pattern, but created and *updated* by the skill (re-running it
   is the drift fix). So the per-user tooling branch survives as the portability escape hatch, not
   as the cram2 default.
3. **Portability rules**: no repo names outside `stack.toml` defaults + doc examples (PR 1);
   `board.yml` repo/branch/upstream become repository variables (PR 4). Long-term option kept open,
   not exercised now: lift the whole system into a standalone plugin/template repo.
4. **HARD RULES stay inline in the Routine prompt** even after the cutover — they must be in force
   before the Routine's first tool call (a webhook event could arrive before any file is read).
5. **Plan data model and stack data model stay separate.** The board is *derived mechanics now*
   (PR bases + git ancestry); plans are *intent over time* (waves/tracks/deps). Only their
   fetch/render layer unifies (shared `pr_state` module, one Pages site).
6. **Delete the round-robin subsystem rather than fix it** — the WIP cap was disabled deliberately;
   promotion becomes "every ready, non-in-review branch; `bug` is just a label".
7. **PR #101 is tracked but not owned by this plan** — it's the stacking base (`claude/patch-pr-rheubx`)
   and its `prerequisite-check.md` / `ScratchRepository` machinery is reused by PRs 1–2, so its live
   state gates the upstream wave.

## Ordering

```
now:        eql-roadmap-migration, session-hooks-retirement   (independent)
stacked:    PR #101 → PR 1 → { PR 2, PR 3 }
after PR 1–3 on cram2/main + fork main fast-forward:
            PR 4 (stack-board) → routine-cutover → tooling-branch-retirement
```

Interim state is safe by design: until the cutover, the current Routine and board Action keep
running unchanged off the old tooling branch.

## Standing risks

- **cram2 acceptance** of fork-workflow tooling on `main` — precedent is strong (#479, #101
  direction), and PR 1 genericizes by construction, but review may push back on scope.
- **`stack.py` review cost**: 741 pre-AGENTS.md lines; bringing it to repo standards (dataclasses,
  no abbreviations, docstrings, guard clauses, tests) is the slowest-reviewed item. Scope-box PR 1
  to port + delete + standards, not a redesign.
- **Dashboard URL change**: moving plan dashboards from Artifacts to Pages changes their URLs
  (`_generated/dashboard-urls.yaml` becomes legacy); bookmarks need one update.

## Dispatch prompt: setup-personal-notes-script (added 2026-07-29)

Item `setup-personal-notes-script` (stack-tooling track). The user supplied this implementation
prompt verbatim; hand it to the implementing session unchanged. Precondition it enforces itself:
PR #101 must be MERGED first — branch off `main`, never off the PR head.

> **Superseded on implementation — read the 2026-07-29 (night) addendum below before using this
> prompt as a reference.** Two of its statements no longer hold: the "requires #101 MERGED" rule
> was overridden by the user (#107 is based on `claude/patch-pr-rheubx`), and its central
> accounting — that the `get_me` remote-ownership check and the label check genuinely require a
> session — was tested and disproved. The prompt is kept verbatim as the historical record of what
> was dispatched, not as a description of what was built.

```
Extract a deterministic setup script from the /setup-personal-notes skill, in the
AbdelrhmanBassiouny/cognitive_robot_abstract_machine fork.

## Context

PR #101 added `/setup-personal-notes` (.claude/skills/setup-personal-notes/SKILL.md), a
skill that takes a clone from "I have a fork and nothing else" to working personal
notes, PR progress and plan dashboards. Review raised: does this need a skill at all,
or could it be a plain script? The accounting: every mechanical step is already a
script call, and only two things genuinely require a session —

1. deciding whether the resolved notes remote is the user's own fork (needs the
   authenticated GitHub identity via mcp__github__get_me; a git remote URL doesn't say
   who owns it, and getting it wrong pushes someone's personal notes to a repository
   they don't control), and
2. checking the `merged` / `bug` / `in-review` labels exist (GitHub API).

Everything else is either a script invocation or a question with a good default. The
agreed follow-up is to make the mechanical part runnable with no session at all.

This work depends on PR #101 being merged. Branch off `main` once it has; if it hasn't,
stop and say so rather than branching off the PR head.

## What to build

`.claude/hooks/setup-personal-notes.sh --remote <name-or-url> [--starter-notes]`,
performing what are currently the skill's steps 4-7 and 9, in order, non-interactively:

- point `claude.personalNotesRemote` at `--remote`
- create the notes branch via `create-personal-notes-branch.sh`
- seed the notes file from `starter-notes.md` via `write-personal-notes-file.sh`, only
  when `--starter-notes` is passed
- `pip install -r "${PLAN_DASHBOARD_REQUIREMENTS_FILE}"`, reporting rather than
  aborting if it fails (everything except plan dashboards works without it)
- run `session-start.sh` so the current clone picks the notes up
- finish by running `check-setup.sh` and printing its report

Requirements:

- Idempotent, and safe to re-run on an already-set-up clone: each underlying script
  already refuses or no-ops appropriately; preserve that rather than working around it.
- Source `resolve-personal-notes-config.sh` for every path and setting. Do not hardcode
  paths that already have constants there, and add new constants there if you need them.
- Do not duplicate any of `check-setup.sh`'s logic. It stays the single read-only source
  of truth for "is this clone set up?" — call it, don't reimplement it.
- `--remote` is required. Refusing to guess is the entire reason this can be a script:
  the guess is the part that needs a session.
- Fail with a clear message on unknown flags and on a missing `--remote`.

Then shrink SKILL.md to just the session-only parts: resolve whether the remote is the
user's (get_me), ask if it isn't, invoke the script, then do the label check (step 8,
which must keep running even on the already-set-up fast path since `check-setup.sh`
cannot see labels). Note there is no create-label tool in the GitHub MCP server — only
`get_label` — so creation shells out to `gh label create`, and says so plainly when `gh`
is absent rather than pretending it acted.

Update `.claude/hooks/README.md`'s by-hand section to mention the new script, and keep
its length discipline: it was deliberately cut from 378 to ~140 lines, so add lines
only where a reader needs them to act.

## Tests

Add a test module under `.claude/hooks/tests/`, reusing the existing `ScratchRepository`
(tests/scratch_repository.py) and the `scratch_repository` fixture in conftest.py rather
than building a new scratch layout. Cover at least: a missing `--remote` fails; a full
run leaves check-setup.sh exiting 0; `--starter-notes` seeds the file and its absence
leaves it empty; a second run changes nothing. CI already runs
`${HOOKS_TESTS_DIRECTORY}` in the `test_claude_dev_tooling` job, so no workflow change
is needed — but the tests must not need network access or credentials.

## Conventions

Follow AGENTS.md. Specifically: dataclasses, no abbreviations in any identifier, RST
docstrings on every field and method, absolute top-level imports, guard clauses over
nesting. Run `scripts/format_docstrings.py` on every file you touch. Commit as the human
user (their configured git user.name/user.email) — never an assistant identity as author
or committer, and no Co-Authored-By trailer for Claude; a plain "Made with the help of
Claude." line in the body is fine. Open the PR as a draft, include a link to the session
that created it, and subscribe to its activity.
```

## Update 2026-07-29 (late): PR 1 done as draft #106; dev-tooling Python package decided

**PR 1 status**: `stack-tooling-on-main` implemented as draft PR #106 (`claude/stack-tooling-on-main`
on `claude/patch-pr-rheubx`), by session_01Y9egTHHu5RTXmkFL4SwXM9. As planned it ported stack.py
minus the round-robin subsystem, added per-user config layering, made ROUTINE.md canonical, and did
NOT port restack.js or board rendering (deferred to PR 3/4). It landed as plain scripts under
`.claude/stack/` — no package.

**Design decision 8 — a proper dev-tooling Python package** (user-confirmed): all *Python* under
`.claude/` migrates into one proper package with its tests under the standard `test/` directory.
Reasons: PR 3's shared `pr_state` module needs a real import home (same-directory imports between
`.claude/stack/` and `.claude/skills/plan-dashboard/` are path hackery); standard pytest/CI
treatment instead of the special-cased `test_claude_dev_tooling` directory pointer; declared
dependencies instead of a loose requirements.txt; and it strengthens the future plugin/template-repo
lift (decision 3). Boundaries and constraints:

- **What stays in `.claude/`**: SKILL.md files, settings.json, and the bash hook entry points —
  Claude Code discovers all of them by path. They become thin wrappers invoking `python -m` into
  the package.
- **Zero-install must survive**: cloud sessions run on fresh clones with no pip step, so the
  package is a plain top-level directory importable from the repo root (`python -m ...`), with a
  pyproject for *optional* installation (stack-board Action, future plugin lift). No src-layout.
- **Dev-tooling optics for cram2**: own clearly-named directory, not published to PyPI, not part
  of the default install — visibly separate from the robot-stack packages.

**Revised sequencing** (PR 1 shipped without the package, so creation moves to PR 3):
- PR 3 (`shared-pr-state-chips`) *creates* the package and puts `pr_state` in it as its first
  module — the shared import need is what forces it into existence there.
- New item `dev-tooling-python-package` migrates the existing Python (stack.py, the plan-dashboard
  scripts, plan_manifest_tools.py) + all tests into it, last in the upstream wave: it requires
  #101 MERGED (it moves `.claude/hooks/tests/` files #101's diff adds) and PR 3 stable (it moves
  files PR 3 edits).

## Addendum: tag-push and branch-delete are unavailable from a Claude Code session (2026-07-29)

(Restored after a concurrent-save race briefly overwrote it; originally written by the
session-hooks-retirement kickoff session.)

`/plan-item-kickoff workflow-unification session-hooks-retirement` verified the item's premise
(`claude/session-hooks`'s tip is a literal `git merge-base --is-ancestor` ancestor of `main`, safe
to retire) and got a tag-then-delete plan approved and attempted in the same session. Both
operations failed with a real, reproducible `403` through the session's git proxy — creating or
updating a branch works, but `git push <tag>` and `git push origin --delete <branch>` are both
rejected outright. No GitHub MCP tool substitutes either (`create_branch` only creates from a
source branch; there is no delete-branch or create-tag tool). This reads as a deliberate platform
safety boundary against destructive/irreversible ref operations from an agent session, not a
misconfiguration or something to route around.

Consequence for this plan: both `session-hooks-retirement` and `tooling-branch-retirement` (the
same tag-then-delete shape, later in the `cutover` wave) need their tag-push and branch-delete
steps run outside the harness — from the user's own machine, or via `gh api`/a broader-scoped
token — even though everything upstream of that (verification, drafting the tag message, the
plan-manifest update itself) can still run in a session. The retirement was completed by the user
directly: `claude/session-hooks` is deleted (its tip was already an ancestor of `main`, so no tag
was needed); `origin/claude/push-scope-test-zsq7jc` (a diagnostic throwaway, identical to `main`)
still needs the same out-of-harness deletion.

## Addendum 2026-07-29 (night): setup-personal-notes-script implemented as #107; its premise disproved

Written by the implementing session (session_01MyxyUN3bsvPsJnb5QuNzxd), which also edited
`plan.yaml` directly rather than only comment-proposing on issue #102. Under the older
propose-don't-edit convention a non-steward session would have left the manifest stale; the user
has since made keeping plan state current the stronger rule, so state that is already fact gets
written straight into the manifest, with the issue comment kept as the record of *why*.

**Design decision 9 — the GitHub steps in this system do not need a session.** The dispatch prompt
above rested on an accounting that turned out to be wrong, and it is worth correcting explicitly
because the same reasoning was about to be copied into PR 2:

| Believed session-only | Actually |
| --- | --- |
| the authenticated login (`get_me`) | `GET /user` from a plain shell |
| label existence (`get_label`) | `GET /repos/{owner}/{repo}/labels/{name}` → 200/404 |
| creation needs `gh`, since MCP has no create-label tool | true of MCP only; `POST /repos/{owner}/{repo}/labels` has always existed |

`.claude/hooks/github-api.sh` owns these, preferring `gh` when installed and otherwise
`GH_TOKEN`/`GITHUB_TOKEN` with `curl`, failing with both routes named rather than silently doing
nothing. What is genuinely un-scriptable is also out of reach for a session, so neither justifies
one: persisting `CLAUDE_PERSONAL_NOTES_*` for the next fresh clone, and judging whether a divergent
`.claude/settings.json`/`.gitignore` is deliberate. The one real residue is a shell with neither
`gh` nor a token, where the skill's MCP path still works — kept as the documented fallback.

Consequence for PR 2 (`setup-stacked-prs-skill`): mirror this script/skill split, where the skill
keeps only the questions plus the environment-variable step. Do not reserve the GitHub calls for a
session.

**A portability trap worth knowing about, found here.** A Claude Code cloud session's clone has no
`github.com` in its remote URL at all — it is rewritten through a local git proxy
(`http://local_proxy@127.0.0.1:<port>/git/<owner>/<repo>`), and `git config remote.origin.url`
shows the proxy form too. Any code deriving `owner/repo` by matching the real host fails in exactly
the environment this tooling is most used in. `github_repository_of_remote` reads the trailing two
path segments instead, and rejects a local filesystem path outright (a path also ends in something
shaped like `<owner>/<repo>`, and attributing a directory name to a GitHub account would make an
ownership check refuse a valid setup).

**#101's stacking rule, in practice.** Basing on the PR head rather than waiting for the merge was
not a shortcut: `check-setup.sh`, the three `setup-personal-notes/` documents,
`scratch_repository.py` and the `CHECK_SETUP_SCRIPT`/`STARTER_NOTES_FILE` constants all arrive with
#101, so there was nothing to write against `main`. The same is true of `dev-tooling-python-package`
later in the plan, which moves `.claude/hooks/tests/` files — including the four test modules #107
adds.

**Two latent bugs surfaced by having tests at all**, each fixed as its own commit on #107 since the
feature could not work without them:

1. `current_branch_upstream_remote` piped git into `cut`, so under `set -o pipefail` it returned
   git's 128 rather than an empty answer when the branch has no upstream. That aborted
   `create-personal-notes-branch.sh` outright on any branch never pushed with `-u`.
   `fetch_personal_notes_branch` escaped it only by always being called from a condition.
2. The new test helper hid an executable by dropping its whole `PATH` entry — normally `/usr/bin`,
   which also provides `bash`. Invisible on a machine without `gh`, fatal on CI which has one.

**Open, for the developer, not fixed here.** `test_each_lib (coraplex)` fails intermittently for a
reason unrelated to this plan: `test/coraplex_test/conftest.py`'s `pytest_configure` regenerates
`coraplex/src/coraplex/orm/ormatic_interface.py` with no xdist guard, so with `2/2 workers` two
processes rewrite the same ~33.5k-line file concurrently and `ruff format` then fails to parse it.
Analysis posted on #107. Untouched deliberately: different root cause, different package, and
AGENTS.md routes ORM-interface problems via `scripts/regenerate_all_orm.py` or the developer.

## Update 2026-07-30: the upstream wave linearized; PR 2 kicked off

**Decision 10 — the upstream wave is a linear chain, not siblings on #101.** #106 and #107 were
both based on `claude/patch-pr-rheubx`, so neither branch carried both `.claude/stack/*` and
`github-api.sh`. PR 2 (`setup-stacked-prs-skill`) needs both: the stack tooling it sets up, and the
label check/create helpers its setup script calls. Three options were weighed and the diamond was
rejected on mechanical grounds, not aesthetics: `stack.py restack-plan` emits exactly one
`{branch, parent, strategy}` per branch, derived from the pull request's base, so a branch with two
real parents is invisible to the second parent — when that parent moves, nothing restacks the child
onto it. A branch the stack tooling cannot maintain is a poor advertisement for the stack tooling.
So #107 was retargeted onto `claude/stack-tooling-on-main` and #106 merged into it (clean, one
auto-merged file), making the chain `#101 → #106 → #107 → PR 2`. #106 is the parent because it is
un-drafted and promotes first.

**Two scope calls settled at PR 2's kickoff**, both from the item notes conflicting with the
roadmap:

- *stack-board bootstrap*: the item notes say PR 2 "offers stack-board repo bootstrap", but the
  parameterized `board.yml` belongs to PR 4. PR 2 prints the bootstrap steps and the repository
  variables the Action will need, and installs no workflow file — shipping the pre-parameterization
  Action would pull cutover work into the upstream wave and hand PR 4 a file to immediately rewrite.
- *`prerequisite-check.md`*: read as "PR 2 gets its own", not "reuse #101's". What settles it is the
  consumer side rather than the planning prose — `ROUTINE.md`'s SETUP step 0 needs exactly this
  document, with one variation: the Routine must *report* a missing setup rather than offer to fix
  it, since its own HARD RULES forbid asking or entering plan mode.

**Two kickoff plans were produced independently for this item** — one via `/plan-item-kickoff`, one
from a plain prompt — and merged. The comparison is worth recording because the gaps were in the
skill, not in either session: a `done`-only reading of sibling items gathers nothing in a wave where
every item is still in flight, and dependency *readiness* never asks whether the dependency branch
actually carries the files the item builds on. Both are now steps in `plan-item-kickoff`'s SKILL.md
(branch `claude/plan-item-kickoff-workflow-ylk9wu`), along with checking the consumer side before
raising an open question, and ending every proposed plan with the plan-state bookkeeping. The
second plan also caught that `.claude/stack/board.json` is documented as never-committed scratch
while nothing gitignores it — fixed in PR 2, with a `board_ignored` check to keep it true.

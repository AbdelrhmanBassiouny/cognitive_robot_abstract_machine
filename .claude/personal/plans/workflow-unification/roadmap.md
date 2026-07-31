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

## Update 2026-07-30: PR 3 (shared-pr-state-chips) kicked off; package named

Kickoff session: https://claude.ai/code/session_014KoJeaTUxyECZZpfWiVmvr, via
`/plan-item-kickoff`. Branch `claude/shared-pr-state-chips`, based on
`claude/stack-tooling-on-main` (#106's head) as a **sibling of #107 on #106** — decision 10's
linearization was forced by PR 2 needing files from two parents, which doesn't apply here: PR 3
needs only #106's files (`.claude/stack/stack.py`, the `STACK_*` constants; `github-api.sh` is
bash, and `pr_state` fetches in Python with the same dual-backend rule as decision 9).

Two decisions settled with the user at kickoff:

- **The dev-tooling package (decision 8) is named `development_tooling`** — abbreviation-free per
  AGENTS.md ("dev" is an abbreviation), over `dev_tooling`/`claude_tooling`. Flat top-level
  directory, `pyproject.toml` inside the package directory (the repo root already carries the
  workspace meta-pyproject), zero-install import from the repo root preserved.
- **The headless static-site build pushes manifest auto-corrections.** The `build_site.py`
  entrypoint the Pages Action will invoke reuses `refresh_dashboard.sh` per plan, including its
  push of merged→done corrections to the personal-notes branch — the user chose keeping the
  manifest current with no session over a read-only Action.

Interim states this PR deliberately leaves for `dev-tooling-python-package` to clean up:
`stack.py` gets a repo-root `sys.path` insert to import the package, and `build_site.py` lives in
`.claude/skills/plan-dashboard/` next to the render scripts it imports until the migration moves
them into the package together. PR 3's own new tests go straight to
`test/development_tooling_test/` so the migration has nothing to move for them.

## Update 2026-07-30: routine-cutover kicked off — prepared, gated on PR 1 reaching main

Kickoff session: https://claude.ai/code/session_017JMftn3ujp7xsyhwcMaF75, via
`/plan-item-kickoff`. The item's own gate ("only after PR 1 is on cram2/main and fork main
fast-forwards") is **not met yet** — #101 is open (`in-review`, awaiting the cram2 merge) and #106
stacks on its head — so this kickoff prepared everything and execution waits. No timer is armed
(no-scheduled-checks rule); execution happens when the user says go or a session verifies the gate
on request/event.

Findings that shaped the preparation:

- **The live Routine is trigger `trig_01N79jHmLo3bSbg8pLM6MNTB`** ("PR Stack Monitor and Update"),
  found via `list_triggers`. Its 17,392-character prompt still carries the dead round-robin
  subsystem, `dev/` paths, and the tooling-branch pull step. Diffing it against #106's
  `.claude/stack/ROUTINE.md` embedded prompt confirmed the only substantive differences are exactly
  what PR 1 changed (round-robin deleted, promote-all Phase 3 via `next --porcelain`, `dev/` →
  `.claude/stack/`, step 0b deleted) — so ROUTINE.md is a faithful successor and nothing in the
  live prompt needs rescuing beyond what it already contains.
- **The cutover is executable from a session**: `update_trigger` replaces a Routine's prompt in
  place, keeping name/schedule/connectors/email config. The item note "No PR —
  claude.ai/code/routines change" predates knowing this; manual paste stays as the fallback.
- Design calls settled at kickoff (user-approved plan): inline HARD RULES = never-subscribe,
  end-turn-on-webhook-events, and never-plan-mode (all three must bind before ROUTINE.md is read);
  the LABELS-ARE-REPLACE rule stays file-only since label writes can only happen post-read. The
  pointer prompt stops-and-reports if ROUTINE.md is missing from main, never falling back to the
  old tooling branch.

### The approved replacement prompt (paste or update_trigger verbatim at execution time)

```text
You maintain the stacked-PR fork-staging workflow for AbdelrhmanBassiouny/cognitive_robot_abstract_machine.
The full doctrine lives in the repo: read `.claude/stack/ROUTINE.md` on your `main` checkout and execute
the prompt embedded in it, exactly as written there. If that file is missing from `main`, STOP and report
that instead - never fall back to another branch or to a remembered older copy of the doctrine.

HARD RULES, in force from this line onward - before any file is read or any tool is called - and
overriding ROUTINE.md if the two ever disagree:
- NEVER call `subscribe_pr_activity`, and never stay subscribed - you learn CI by POLLING.
- If a review, review-comment, issue-comment, or any `<github-webhook-activity>` event is ever delivered
  to you, your ONLY valid action is to END THE TURN immediately. The one exception is a CI/check *status*
  you were polling for your own restack.
- NEVER enter plan mode or post a "here's my plan" comment. You either perform a mechanical step from
  ROUTINE.md or you stop; you never open a discussion.
```

### Execution checklist (any session can run this once the gate is met)

1. Verify the gate — the cram2 remote is outside a session's repo scope, but the routine
   fast-forwards fork main from cram2/main, so `origin/main` is the observable:
   `git fetch origin main claude/stack-tooling-on-main && git merge-base --is-ancestor
   origin/claude/stack-tooling-on-main origin/main`, plus
   `.claude/stack/{ROUTINE.md,stack.py,stack.toml,README.md}` all present on `origin/main`.
2. Re-read `origin/main`'s ROUTINE.md once — later PRs may have evolved it (the pointer design
   absorbs that), but its embedded HARD RULES should still match the inline ones above.
3. `update_trigger` with `trigger_id: trig_01N79jHmLo3bSbg8pLM6MNTB` and `prompt:` the text above
   (touch nothing else on the trigger).
4. After the next natural routine run, confirm from its email/summary that it read ROUTINE.md and
   ran the phases normally, then set the item `done` (unblocking tooling-branch-retirement),
   `save-plan.sh`, republish the dashboard.

Two wording nits flagged to fix on #106 before it merges (relayed to the user, not acted on from
this item): ROUTINE.md's header says "This file becomes the one to **paste into**
claude.ai/code/routines" and README.md echoes "paste it (or its successor)" — both should describe
the pointer design instead; and ROUTINE.md's "Not live yet" paragraph goes stale at cutover.

Also restored in this same save: PR 3's kickoff state (manifest + the roadmap section above),
which a concurrent stale-scaffold save (bdd0beaa, 14:49) had silently reverted five minutes after
it was recorded (973ff31a, 14:44) — the second occurrence of this race; the first is noted in the
2026-07-29 tag-push addendum.

## Update 2026-07-30: personal settings sync joins the personal-data track (PR #109)

New item `personal-settings-sync` (`claude/local-settings-dashboard-sync-8sx0tf`, PR #109,
session_0167iZiWUnXizpKSqa7xf5rC), added at the user's request after the work was already built
and open.

**What it adds.** The personal-notes branch can now also carry `.claude/personal/settings.local.json`,
which `session-start.sh` copies to the project root's `.claude/settings.local.json` — the file
Claude Code itself reads as local settings. Seeded with a rule allowing the `Artifact` tool
without prompting, so plan dashboards publish without a permission prompt each session.
`save-personal-settings.sh` is the write half, delegating its commit/push to the existing
`write-personal-notes-file.sh`. The same session also added a personal-notes rule that any session
changing a plan's data republishes that plan's dashboard in the same turn — notes-branch only, no
PR, and the direct reason this item exists as a tracked one rather than a loose change.

**Why `personal-data` and not `stack-tooling`** (user's call, offered three options): the target
architecture already names `claude/personal-notes` the home for *all* personal state, and this is
that — config rather than data, but the same home and the same mechanism. It is also genuinely
independent of the #101 stack: branched off fork `main`, not on the chain, so putting it in the
upstream track would have broken that track's one-linear-chain property (decision 10) for no gain.
The consequence is that the `personal-data` track is no longer only about *slimming* the notes
branch; it is personal-notes data and config generally. The track keeps its name, and the item
records the widening.

**Not a dependency, but a merge to expect.** Three open PRs touch the same two files:
`#107` adds path constants to `resolve-personal-notes-config.sh`, `#110` makes
`write-personal-notes-file.sh` delegate to a new `write-branch-files.sh`, and `#109` adds its own
constants to the first and calls the second. None of them needs the others to work, so no
`depends_on` was added — whichever lands second resolves a textual overlap in files both already
edit. Worth knowing before restacking anything, not worth serializing the work over.

**Deliberate deviation from a plain copy.** Claude Code writes permission grants into
`.claude/settings.local.json` itself whenever the user picks "don't ask again", so an
unconditional copy every session start would silently drop them. The hook writes only when the
file is absent or unchanged since it last synced, tracked by a hash stamp in the gitignored
`.claude/.personal-settings-sync-hash`; otherwise it keeps the local file and says so in its
session-start summary, and `save-personal-settings.sh` re-stamps so syncing resumes. This is the
one place the settings round trip is not symmetric with the notes round trip, and it is the reason
why.

## Update 2026-07-31: GitHub native stacked-PRs preview - evaluation, live prototype, findings

GitHub shipped stacked pull requests as a public preview (server-side cascading rebase, `gh stack`
CLI, stack webhooks/REST/GraphQL, stack map UI). Evaluated against this plan's stack tooling in
session https://claude.ai/code/session_015db4P7UfiFTTfrbxYjU5yW, then verified by a live prototype
on throwaway `proto-*` branches in the stack-board repo (its `main` untouched; a throwaway branch
served as trunk). The user had already created **Stack #112** on the fork - the seven D-core PRs
(#41→#63→#64→#65→#66→#67→#98) adopted post-hoc into a native stack trunked on
`ripple-down-rules-refactor` - which by itself proved the preview is enabled, post-hoc adoption
works, and a non-default trunk works.

**User decisions recorded before the prototype:**

- **One dashboard only.** The plans dashboard (with its buttons and suggested next actions) is the
  single surface; the stack-board visualization dies - GitHub's stack map covers derived
  mechanics. Every fork PR must belong to a plan, which the dashboard build can enforce by
  flagging unclaimed open PRs.
- The gain sought from GitHub is the stacking *mechanics* via API, and slimming the Routine -
  possibly down to a plain GitHub Action.

**Prototype findings (all verified live, not from docs):**

1. **Reads work from a session.** The PR resource carries a `stack` object
   (`id`/`number`/`size`/`position`/`base{ref,sha}`) and `GET/POST /repos/{o}/{r}/stacks`,
   `GET /stacks/{n}`, `POST /stacks/{n}/add`, `POST /stacks/{n}/unstack` all work with the
   session's fine-grained installation token under `X-GitHub-Api-Version: 2026-03-10`. GraphQL is
   unusable from a session (the git-proxy token serves only a pinned set of PR-review queries), so
   `pr_state` must use REST.
2. **Create/extend/dissolve verified.** Bottom-to-top `pull_requests` list; a draft PR is accepted
   as a stack member; creating a stack on stack-board proves the preview is account-wide, not
   per-repo. A stack whose open PRs are all removed (only merged members remain) auto-closes.
3. **The cascade is the one gap.** Pushing new commits to a lower branch does *not* auto-rebase
   the branches above (verified over ~5 min), and no REST endpoint triggers the server-side
   cascade (`rebase`/`sync`/`restack`/`update`/`cascade`/`rebase-async` variants all 404;
   `PUT /pulls/{n}/update-branch` is explicitly 403 "Merging stacked PRs via this API is not
   supported. Use the web interface instead."). Server-side cascade = UI button only; automation
   does a *local* cascading rebase + `--force-with-lease` push, which preserves stack membership
   (verified) - i.e. exactly what stack.py restack already does, minus deriving the order, which
   now comes free from the stack object.
4. **Merging is a new async API and it is good.** Classic `PUT /pulls/{n}/merge` hard-403s for
   stacked PRs - including through the GitHub MCP server's merge tool, so the Routine/tooling
   *must* adopt `PUT /pulls/{n}/merge-async` → poll `GET /pulls/{n}/merge-async/{uuid}`
   (result retained 24h). Verified: merging mid-stack PR #2 merged #1+#2 into the trunk in one
   operation and auto-retargeted the draft above to the trunk within seconds. A stale stack is
   refused with a precise reason ("PR #2's branch is not a linear descendant of PR #1's branch"),
   and a draft refuses with "Pull request is in draft".
5. **Conflicts surface conventionally.** A trunk commit conflicting with an upper layer shows as
   plain `mergeable: false` / `mergeable_state: dirty` on that PR - no special stack state. The
   stack's `base.sha` lagging the real trunk head is a machine-readable "needs cascade" signal.
6. **Events carry the stack.** `pull_request` webhook/Actions payloads include
   `.pull_request.stack`; the post-merge retarget arrives as an `"edited"` action. An Action can
   key on stack membership without deriving anything.

**Consequences per open item** (decisions for the user, not yet made):

- `stack-tooling-on-main` (#106): restack-order derivation and promote mechanics shrink - the
  stack object is authoritative for structure, merge-async replaces any merge path, and the MCP
  merge tool must not be used on stacked PRs. The local rebase+push loop survives as the cascade
  executor. Pivot-now vs land-then-migrate is the open call.
- `setup-stacked-prs-skill` (#110): setup shrinks to labels + stack.toml + (optionally) creating
  the stack via API; fork-overlay mode demotes to a fallback for repos without the preview.
- `stack-board-single-site`: re-scoped by the user's one-dashboard decision - plans-only Pages
  site, no board index; add the every-PR-in-a-plan invariant check to the build.
- `routine-cutover`: the endgame candidate is stronger than "slim the Routine" - deterministic
  duties (fork-main fast-forward, labels, cram2-link comment, site build, happy-path cascade via
  local rebase) fit a plain scheduled Action; the LLM residue is cascade *conflicts* and red CI
  after a restack, which could become on-demand sessions instead of any scheduled LLM run. This
  would finally align the Routine with the no-scheduled-checks rule.
- Unchanged: the fork→cram2 hop was never a stack (cross-fork stacks unsupported) - promotion
  doctrine, label hygiene and fast-forward stay ours; the plan system and dashboards are
  untouched by the preview.

**Leftovers from the prototype:** stack-board carries closed throwaway PRs #1-#5 (two merged into
`proto-trunk`, which is itself throwaway) and the branches `proto-trunk`, `proto-layer-1..4` -
branch deletion needs the user (session branch-deletes 403, the standing platform constraint).
Stack #4 there is closed. Nothing on the fork was touched beyond reads.

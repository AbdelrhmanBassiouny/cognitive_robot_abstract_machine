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

## Update 2026-07-31 (later): pivot approved and recorded; round-2 probes; the reparent hazard

The user approved the recommendation set from the evaluation session
(https://claude.ai/code/session_015db4P7UfiFTTfrbxYjU5yW): #106 lands with one trim commit rather
than a re-scope or a pure land-then-migrate; #110 and #111 amend while still drafts; PR 4 becomes
plans-only; routine-cutover's endgame becomes a deterministic Action + on-demand sessions with no
scheduled LLM. Item notes updated accordingly; the plan description now reflects the one-dashboard
decision and the Action endgame.

**Round-2 probes (same throwaway proto-* branches on stack-board), run for the Routine audit:**

1. **The audit itself came back clean on merges**: neither the live Routine's doctrine (embedded in
   `dev/README.md` on the tooling branch) nor #106's ROUTINE.md ever calls the classic merge API or
   `update-branch` on fork PRs — fork-side "merged" is the git-ancestry test + `merged` label +
   close, and restacks are plain git. No latent 403 there.
2. **But Phase 1's REPARENT is broken for stack members**: `PATCH /pulls/{n}` with a new `base`
   fails 422 — "Cannot change the base branch because the pull request is part of a stack." Both
   doctrines do exactly this when a parent lands. With Stack #112 already wrapping the D-core
   chain, the first cram2 landing of a D-core branch hits this. The trim commit on #106 must
   special-case it; until then the recovery is manual (UI Rebase-stack button) or the API-only
   sequence below.
3. **Push-based merges do not auto-retarget children.** Merging the bottom branch into the trunk by
   push (the fork's fast-forward-from-cram2 pattern) marks the bottom PR merged immediately, but
   the PR above keeps its old base — unlike merge-async, where retargeting is automatic within
   seconds. So the reparent duty survives in our flow even with native stacks.
4. **The API-only recovery works**: unstack the affected PR (`POST /stacks/{n}/unstack`), then
   `PATCH` its base, then re-stack. Verified live. Note unstacking down to only-merged members
   auto-closes the stack, so re-stacking may mean creating a fresh stack.
5. **Reopened + previously-closed PRs stack fine** (stack #6 was built from two reopened PRs).

**From the "Managing stacked pull requests" doc (user-supplied):** the server-side cascade is the
"Rebase stack" button in the merge box (UI-only, confirming the API gap; its commits are
*unsigned*); `gh stack rebase`/`push` is the local cascade; and `gh stack sync --prune` is
documented as **safe to run in automation** — it fetches, fast-forwards the trunk, rebases the
remaining branches onto it, force-pushes, and syncs PR status, aborting cleanly on divergence in
non-interactive terminals. Actions runners ship `gh`, so the cutover Action's cascade step can be
`gh stack sync` rather than a hand-rolled rebase loop. `gh stack modify` handles restructuring;
unstacking from the website removes open/draft/closed PRs but merged/queued ones stay.

**Chain adoption (recommendation 3) is left to the user**: creating the stack for
#101 → #106 → #107 → #110 from a session was blocked by the permission layer, and given finding 2
it should follow — not precede — comfort with the reparent story. It's the same "Add to stack" flow
used for #112, or `gh stack` locally. #111 cannot join that stack (it's a sibling of #107 on #106;
stacks are strictly linear) and stays loose; #109 is independent by design.

## Update 2026-07-31 (adoption): the upstream chain is Stack #114; unstack means dissolve

The user adopted the chain via the UI, but the "Add to stack" flow picked #111 (a valid linear
continuation from GitHub's perspective, since it also targets #106's head) instead of #107 —
producing Stack #113 = #101 → #106 → #111, which blocks #107/#110 from ever joining. Fixing it
from the session surfaced a correction to round-2 finding 4: **`POST /stacks/{n}/unstack` takes no
body and has no selective mode — it dissolves the stack** (removes every open/draft/closed member;
merged members stay, per the docs' website-unstack description). The `pull_requests` body it was
called with was silently ignored. This retroactively reinterprets the stack-board probes (stacks
#4/#6 "auto-closing" after selective unstack were in fact full dissolutions), and it narrows the
reparent recovery: the API-only sequence is dissolve → PATCH base(s) → re-create the stack, not a
surgical removal. `gh stack modify` is the only surgical restructuring tool.

Outcome: Stack #113 dissolved, **Stack #114 created with the intended sequence
main → #101 → #106 → #107 (draft) → #110 (draft)**; #111 verified untouched (open draft on
#106's head, stack: null — it cannot join, as a sibling of #107; its restack remains stack.py's/
gh's job). The upstream wave is now natively stacked, so #101's cram2 landing will exercise the
push-merge/reparent path for real — the "Rebase stack" button or gh stack sync is the recovery
until #106's trim commit lands. Also noted: fork-side stack writes from a session worked this
round (create/unstack on the fork repo); the earlier same-call denials were permission-layer
variance, so treat session-side stack surgery as possible but not guaranteed.

## Update 2026-07-31 (routine patch): update_trigger is unavailable for this Routine — manual paste only

The approved interim amendment (Phase 1 native-stack special case) was drafted and its application
attempted via `update_trigger`, which the platform refused: the live Routine was created via the
web UI ("http_api"), and agents may only update Routines they created themselves (an agent-created
trigger would be updatable; this one is not). This corrects the 2026-07-30 kickoff finding that
"the cutover is executable from a session" — for this trigger it is not; **manual paste at
claude.ai/code/routines is the mechanism for both the interim amendment and any future prompt
cutover**. The amendment text (appended to the otherwise-unchanged 17.5k-char live prompt) was
handed to the user as a file; its content is: detect stack membership via the `stack` object under
API version 2026-03-10; never classic-merge/MCP-merge a stack member; Phase 1 reparent for stacked
children = record stack composition → dissolve (`unstack`, no body) → PATCH bases → normal local
restack → re-create stack; stop-and-report on any unexpected API behavior.

## Update 2026-07-31 (cut): decision 11 — #106 cuts the restack subsystem instead of trimming it

User decision, prompted by an explicit reassessment ask ("fastest and simplest while reliable,
clean, and minimal cram2 review effort"). The trim commit approved earlier the same day kept the
restack engine with a stack-API-primary/PR-base-fallback split; the reassessment concluded the
fallback's only remaining justification (repos without the stacks preview) is YAGNI — the preview
is account-wide for the user, cram2-the-org is never stacked on directly, and the old tooling
branch survives as a tagged archive if a preview-less repo ever materializes. Since the plan's own
named slowest-review risk was stack.py's 741 lines, cutting the engine is simultaneously the
fastest path through the actual bottleneck (cram2 reviewer time) and the most reliable one (GitHub
maintains the mechanics; we maintain policy).

What #106 keeps: ROUTINE.md rewritten around native mechanics — stack object as structure source,
merge-async + poll as the only merge path, base.sha-lag staleness, the Phase-1 reparent special
case (record → dissolve → PATCH bases → restack → re-create) — plus stack.toml and per-user config
layering, the label/cram2-link helpers, a small reparent-recovery script, and tests. What it drops:
restack-plan, next, status/structure derivation. Knock-ons recorded on setup-stacked-prs-skill
(nothing to install beyond doctrine + labels + config + optional stack creation) and
shared-pr-state-chips (the stack.py export interplay may vanish). Instructions were posted as
comments on #101, #106, #107, #110, and #111 so each owning session receives them as events.

## Update 2026-07-31 (conventions): delta recheck, comment routing, merged-branch cleanup

Three conventions recorded in cram-notes.md at the user's request, after the question "is the
tracking-issue subscription enough?" was answered no — the manifest is the primary state channel
and pushes to the notes branch emit no events, so subscription covers only the structural subset
that gets commented:

1. **Recheck deltas, don't reread**: sessions recheck plan/tracking-issue updates when prompted
   after idling, when starting a new task, and always immediately before a `save-plan.sh` write
   (the anti-stale-save rule; two silent reverts on record). Mechanics: stamp the last-seen
   notes-branch SHA, then read `git diff <sha>..FETCH_HEAD -- plans/<id>/` and only
   newer-than-stamp issue comments.
2. **Comment routing**: the tracking issue always carries the structural record; a PR gets a
   comment only when its owner must act or its review context materially changes. (Assessment of
   the 2026-07-31 five-PR broadcast: #106/#110/#111 warranted, #101 borderline, #107 noise.)
3. **Merged/closed branch cleanup**: the owning session unsubscribes, deletes armed
   triggers/check-ins referencing the branch, and stops all related polling the moment its PR
   merges or closes.

New item `plan-updates-since-helper` (personal-data track) implements convention 1 as a hook
script with a session-start SHA stamp; small independent PR off fork main, like #109.

## Update 2026-07-31 (adoptions): the two open dashboard bug-fix PRs join the plan

Asked why `plan-updates-since-helper` was missing from the "Ready to start" sidebar, the answer
turned out to be a known bug with a fix already in review: **#103** (ready-to-start drops
dependency-free items - the exact `_compute_next_steps` guard diagnosed live in the session) and
its sibling dashboard fix **#105** (unmet dependency chips shown as blocked). Both predate the
one-dashboard decision, are based on fork main, and carry `bug` + `in-review`. Adopted as
`ready-to-start-dependency-free-fix` and `dependency-chips-blocked-fix` in the dashboards track -
the first exercise of the "every fork PR belongs to a plan" rule, which the PR-4 site build will
later enforce mechanically. Practical note: the sidebar gap remains visible on published
dashboards until #103 lands on fork main, since the build runs main's copy of
build_dashboard.py.

## Update 2026-07-31 (kickoff): plan-updates-since-helper kicked off

`/plan-item-kickoff workflow-unification plan-updates-since-helper`, this same session
(https://claude.ai/code/session_01UrxbEr6ZHMThA2p4Vcnrqv). Confirmed live: `origin/main`
(`0fd14357`) has no `.claude/hooks/github-api.sh` - it exists only on PR #107's branch,
which this item does not depend on - and `.claude/hooks/tests/` on `main` still has only
the original minimal `conftest.py` (bare `sys.path` insert), not either sibling's shared
scratch-project/stub-executable scaffolding (#109's `ScratchProject`, #107's
`ScratchRepository` + `stub_executables.py`). Consequences for the design:

- The tracking-issue-comments GitHub call this item needs is implemented inline, in the
  same gh-preferred/curl+token style `github-api.sh` already uses on #107's branch, rather
  than sourcing that file (it isn't reachable from fork main yet). A follow-up once #107
  lands can dedupe the shared credential/repo-resolution helpers; out of scope here.
- Tests build their own minimal scratch-repo + stubbed-`gh`/`curl` fixtures locally in the
  new test module, matching the shape `test_save_plan_sh.py` already has on `main` today,
  rather than depending on either sibling's shared fixture module landing first.

**Basing decision, asked and confirmed by the user**: based directly off fork `main` (not
stacked on #109), matching this item's own note "small independent PR off fork main, like
#109" - read as "the same *kind* of independent PR #109 is", not "on top of #109's
branch." A textual overlap with #109 is expected in the same two files this item also
touches (`resolve-personal-notes-config.sh`, `session-start.sh`) - same shape, and same
no-`depends_on` treatment, as the #107/#109/#110 shared-file overlap already on record
above: whichever lands second resolves it, nothing serializes over it.

**Design point flagged, not settled fact**: `session-start.sh` stamps the notes-branch SHA
unconditionally on every successful fetch, not only when the current branch resolves to a
plan via `plan_id_for_branch` - cram-notes.md's wording ("stamps the SHA it loaded plan
state at") only strictly requires the latter, but the broader reading matches "so sessions
have the baseline for free" better (this very kickoff session read plan state manually on
a branch with no plan of its own) and costs nothing extra, since `fetch_personal_notes_branch`
already always fetches the whole branch regardless.

Implemented as draft PR #115 same session: `PLAN_STATE_SYNC_STAMP` +
`record_plan_state_sync_stamp`/`last_recorded_plan_state_sha` in
`resolve-personal-notes-config.sh`; an unconditional stamp call added to
`session-start.sh` (with a `plan state SHA:` summary line); the new
`plan-updates-since.sh <plan-id> [--since <sha>]`; `.gitignore`/`README.md`
updates; and `test_plan_updates_since_sh.py` (13 tests) with its own minimal
scratch-repo fixture and stubbed `gh`/`curl` executables, matching the shape
`test_save_plan_sh.py` already has on `main` rather than either sibling's
not-yet-landed shared fixture. All 29 tests under `.claude/hooks/tests` pass.
Verified live: ran `plan-updates-since.sh workflow-unification --since
1faf0f52` against the real personal-notes branch and tracking issue #102, and
its printed diff matched a manual `git diff` exactly.

Two real bugs the tests caught before they shipped: (1) the comment-printing
Python snippet used an f-string with a backslash-escaped quote inside the
expression part - invalid syntax before Python 3.12, and the `pytest` install
actually available in this session's environment is 3.11, so this was worth
fixing outright rather than working around; (2) the `default_repository` grep
had no `|| true` guard (unlike the `tracking_issue` one right above it), so a
plan with `tracking_issue` set but no `default_repository` field made `grep`
exit 1 with no match, which `set -e`/`pipefail` turned into the whole script
dying silently - no stderr message, no explanation - instead of reaching the
explicit guard-clause error a few lines later. Caught by
`test_tracking_issue_without_default_repository_fails_clearly`, which without
the fix saw an empty stderr instead of the intended message.

## Update 2026-07-29 (merge): ready-to-start-dependency-free-fix landed

PR #103 merged 2026-07-29. Session
https://claude.ai/code/session_016mfBqcBibxA7Wa5eNfWtoL drove it from adoption through
merge: TDD-added `test_dependency_free_not_started_item_is_ready_to_start` (proved the
bug live, `assert [] == ['a']`, before the one-line fix removing the `not dependencies`
short-circuit in `_compute_next_steps`) and a companion pinning that a dependency-free
`BLOCKED` item still lands in neither list. Two pre-existing tests turned out to have an
incidental dependency-free `NOT_STARTED` fixture item that legitimately became
ready-to-start under the corrected semantics once the guard was fixed; rather than touch
either test's assertions, that fixture item's status was changed to `BLOCKED` so each
test keeps isolating only the behavior its name describes (the item it was actually about
- "b" was only ever there as an unready dependency for a different item under test). Full
`.claude/skills/plan-dashboard/tests/` (189) and `.claude/hooks/tests/` (16) suites green.
Opened as draft, `bug`-labeled, subscribed to PR activity per the personal-notes
conventions; the developer marked it ready for review shortly after. One CI red
surfaced along the way - `test_each_lib (semantic_digital_twin)` failing on
`test_world_sim_state_sync`, a Mujoco box-drop physics-settling assertion wholly
unrelated to this diff - noted once on the PR as pre-existing/unrelated per convention,
and it cleared on the next automatic re-run (an out-of-session `origin/main` merge commit
landed on the branch mid-review, authored `Claude <noreply@anthropic.com>`, not something
this session pushed). No review comments arrived before merge. This is the plan's first
completed exercise of the every-fork-PR-belongs-to-a-plan adoption rule from item to
merge.

## Update 2026-07-31 (landed): PR #101 merged — the upstream wave's base is on fork main

`setup-personal-notes-pr101` is **done**: merged into fork `main` at 10:36:43Z (head
`90f69f56`). Verified by presence on `main` rather than from the merge notification alone —
`.claude/skills/setup-personal-notes/SKILL.md` and `.claude/hooks/check-setup.sh` both
`git cat-file -e` clean on `origin/main`.

**Consequences for the plan.** This was the base of the whole upstream chain
(#101 → #106 → #107 → #110, natively Stack #114), so GitHub retargets the chain upward and
`setup-personal-notes-script` (#107) — the item whose dispatch prompt originally required
"#101 MERGED first", a rule the user overrode to let it be based on the PR head — now has
that precondition satisfied retroactively. `dev-tooling-python-package`, whose dependency was
recorded as *stronger* than the open-and-ready rule because it moves `.claude/hooks/tests/`
files this PR's diff adds, is likewise unblocked on that count. And the deferred follow-up
below is now runnable.

**The agreed follow-up, now unblocked.** Review asked whether `/setup-personal-notes` needs to
be a skill at all. The accounting: every mechanical step is already a script call, and only two
things need a session — deciding whether the resolved notes remote is the user's own fork
(needs the authenticated identity; a git remote URL doesn't say who owns it) and checking the
labels exist. The user settled it as a **follow-up, not part of #101**: extract
`.claude/hooks/setup-personal-notes.sh --remote <name-or-url> [--starter-notes]` covering skill
steps 4-7 and 9, shrinking the skill to those two session-only parts. A full kickoff prompt was
handed over in-session. Note this is the same conclusion decision 9 reached independently on
#107 (2026-07-29 night addendum) — that the GitHub steps in this system do not need a session —
so whoever picks it up should read that addendum first: the remote-ownership check is scriptable
via `GET /user`, which narrows the skill's residue further than the review discussion assumed.

**What #101 ended up containing beyond the original patch**, since the plan tracked it as
"the patch, unchanged": the hooks README rewritten as a step-based guide (378 → ~140 lines,
with the worked example surfaced in a callout at the top), a skill step checking the
`merged`/`bug`/`in-review` labels exist in the fork and offering to create them (no create-label
tool exists in the GitHub MCP server — only `get_label` — so creation shells out to `gh`), and a
review round that moved the verbatim-duplicated hook-test scratch repository onto a shared
`ScratchRepository` dataclass plus a `conftest.py` fixture, and replaced the stringly-typed
check-setup report with `SetupCheck`/`CheckStatus` StrEnums and `CheckResult`/`SetupReport`
dataclasses.

**Two standing hazards this item re-confirmed.** Three merge commits authored *and* committed as
`Claude <noreply@anthropic.com>` landed on this branch from outside any session — the same
pattern as `6b51075e`/`f5d1c883` on the P3 branch, and against AGENTS.md's Version Control rule.
Each was verified content-neutral for the PR (`git diff <old>..<new> -- .claude/` empty, branch
diff unchanged at 21 files/+1598/−434) and left unrewritten, since fixing authorship means
force-pushing shared history unilaterally. Separately, the robotics CI jobs flaked repeatedly on
this `.claude/`-only PR — `test_world_sim_state_sync` and
`test_attached_self_collision_avoid_stick`, each proven unrelated (the latter by the giskardpy
job flipping pass→fail across a diff of three documentation files) — and the user instructed
these be ignored rather than investigated on this PR.

## Addendum 2026-07-31 — the orphaned-child bug, found from the PR #41 side

`landed-parent-detection` was not planned work. It surfaced while a session handled a review
round on PR #41 (`rdr-backward-inference`), which had been sitting on a base branch,
`ripple-down-rules-refactor`, whose content had long since landed on `main`. Merging `main`
into #41 to satisfy the review blew its Files-changed view up from 7 files to 268
files / +27,825 — none of it real, all of it an artifact of a merge-base measured against a
stale base branch.

**Why the routine never caught it.** Phase 1 reparents children of "each OPEN fork PR that is
merged by ancestry". PR #40, the one whose head is `ripple-down-rules-refactor`, is *closed,
not merged* — its content reached `main` by another route. So Phase 1 never looked at it, and
#41 was left parented to a landed branch. The same blind spot sits in `stack.py`: `board.json`
holds only open PRs, so `by_name.get(branch.parent)` returns `None` for that parent, and both
`restack_plan` and `parent_landed` interpret the `None` as "there is no parent" — the first
leaving the child on its stale base, the second treating the child as an unblocked root and
clearing it to promote ahead of a parent that may not have landed at all.

The fix is to stop inferring landedness from board membership. The doctrine already defines
`merged` as `git merge-base --is-ancestor origin/B cram2/main`, which answers for *any* branch
name; the code simply never used it outside the board. `Stack` now carries that predicate and
exposes `has_landed_upstream()`, and both call sites ask it instead.

**What this says about the board as a data source.** `board.json` is a projection of open PRs,
not of the branch graph, and every question of the form "what is true about this branch" that
gets answered from it inherits the same hole. `stack_root()` in the `dev/` copy has the same
`by_name.get(...) is None` shape; it was left alone because it feeds only the round-robin/WIP-cap
subsystem, which `stack-tooling-on-main` deletes outright. Worth remembering if any future
question gets answered from board membership rather than from git.

**A premise that turned out to be wrong.** PR #89's description predicted the restacking bot
would "cascade it down through code-extraction → code-generation-extract →
ripple-down-rules-refactor → rdr-backward-inference without a manual conflict resolution on
#41". It could not have: the cascade stops at the first parent whose PR is closed rather than
merged, which is exactly where this chain breaks.

**The 422 has teeth now.** Retargeting #41 to `main` — the correct repair, and the one Phase 1
prescribes — is refused with `422 - Cannot change the base branch because the pull request is
part of a stack`, the hazard `native-stacks-prototype`'s round-2 probes recorded. #41 is not the
stack tip: #63 → #64 → #65 → #66 hang off it, so GitHub's documented recovery (Unstack, retarget,
`gh stack submit`) would dissolve and rebuild a six-PR stack to fix one PR's diff. Phase 1 now
treats the 422 as report-and-continue and explicitly forbids unstacking as a mechanical step;
the FINISH summary lists the stuck PRs so they can be retargeted by hand. #41 itself is left as
found, awaiting that decision — its review round is resolved and its code is correct either way.

### Reversal within the same item: the stack-member 422 is worked around, not reported

The first revision of `landed-parent-detection` told the routine to treat the reparent 422 as
report-and-continue and explicitly forbade unstacking, reasoning that dissolving a stack is too
destructive for a mechanical step. The user rejected it with one sentence — *we want to merge the
problematic branch to main; fast-forwarding its base doesn't retarget it to main* — and that is
decisive. The reparent's purpose, in the doctrine's own words, is that the child stacks on main
"not on a branch about to disappear"; the inflated diff is a symptom. Deferring the reparent does
not make it optional, it leaves the child unable to land and due to be closed when Phase 1 deletes
its base, while the now-working orphan detection re-reports the same PR every run. And "retarget it
by hand" resolves to a human performing the identical dissolve-and-recreate through the UI, so the
rule never avoided the destructive operation — it only moved who performs it.

Two things this settles for the future:

- **The live Routine's `AMENDMENT 2026-07-31` was right, and `ROUTINE.md` now matches it** rather
  than contradicting it. Worth noting the near-miss: the amendment was pasted into the live prompt
  the same morning, and the first revision of this item was written without reading it, so the two
  canonical copies of the doctrine briefly disagreed on a destructive operation. Read the live
  prompt before changing `ROUTINE.md` until `routine-cutover` collapses them into one copy.
- **Fast-forwarding a landed base branch to `main` is rejected as a general technique**, not just
  here. It moves the merge-base so the diff renders correctly while the child still targets a
  disappearing branch, and when that base is a stack's trunk — as `ripple-down-rules-refactor` is
  for Stack #112 — it desynchronises the stack's recorded `base.sha` from its real head, which the
  prototype recorded as GitHub's own staleness signal. It was offered for PR #41 before the stack
  trunk relationship was noticed.

The reparent duty also survives `routine-cutover`: the fork→cram2 hop is not a stack, fork branches
land by push/fast-forward, and round-2 probing established that push-based merges are detected as
merged but do **not** auto-retarget children — only `merge-async` does. `gh stack modify` is the
surgical alternative to dissolving, but the docs describe it as interactive, so it is unavailable
to an unattended Action or Routine.

##### Update 2026-07-31 (night): the dashboard's own drift flags were the bug (#119)

The dashboard raised two drift flags against this plan — `#103` and `#105` "marked done, but pull
request #N was closed without merging" — for two pull requests GitHub records as **merged** at
`2026-07-31T10:36:43Z`, the moment fork `main` fast-forwarded from cram2 and GitHub auto-detected
both branches. The timeline shows them open until that instant, so a merely stale fetch could only
ever have said *"still open"*; "closed without merging" had to come from the data.

It did. `classify_live_state` has exactly two merge signals: GitHub's `merged_at`, or the
hand-applied `merged` label. The published page rendered `#101` — merged in the same second — as
`Merged` purely because it carries that label, while `#103`/`#105` (labels `bug`, `in-review`) fell
through to closed-unmerged. So the `pr_data.json` behind that build had `state: "closed"` and no
`merged_at` for all three.

`pr_data.json` is assembled by a session from `list_pull_requests`, whose `fields` parameter lets
the caller drop fields, and `pr-data-fetching.md` only ever insisted on `labels`. That is per-run
variance, not a state change: the same morning's `sync_manifest_status.py` run read both as merged
and auto-corrected them to `done` (`Auto-sync workflow-unification: 2 item(s) to done`). A doc line
alone would not have prevented it, so `#119` makes the contract enforceable — a closed entry
without the `merged_at` key is now a `MissingMergeTimestampError`, while key-present-and-`null`
stays the genuine closed-unmerged case.

Two things this settles:

- **The `merged` label is a fallback for a merge GitHub never recorded, not a redundancy for
  `merged_at`.** It masked this bug on exactly one pull request and hid it on the other two; a
  fetch that drops the timestamp is not partially correct, it is wrong for every unlabelled pull
  request.
- **Every hand-assembled input to the dashboard is a place this can recur.** The remaining
  gatherer-side steps are prose in `pr-data-fetching.md`; where a wrong value is
  indistinguishable from a legitimate one, the parser has to reject it rather than the doc ask
  nicely.

## Update 2026-08-01: ready-to-promote sidebar + one-click upstream create-links (new item)

Added `ready-to-promote-upstream-links` to the `dashboards` track (wave: upstream), depending on
`shared-pr-state-chips` (#111). The ask: a fifth sidebar group listing the pull requests that are
actually ready to go upstream, each with a link that opens cram2's compare-and-create page with the
description already written, so promoting is one click.

### Why it belongs to this plan rather than being its own thing

Phase 3 of `ROUTINE.md` already builds exactly this link, in exactly this format, and its only
delivery channel is the emailed FINISH summary of a scheduled LLM run. `routine-cutover`'s revised
target is that no scheduled LLM run exists at all — deterministic duties move to a plain Action,
judgment work moves to on-demand sessions "surfaced by the plans dashboard rather than a timer".
Building the link is pure computation over live pull request state; the only reason it needed a
model was that nothing else was rendering it anywhere. Putting it on the dashboard removes the last
non-judgment reason Phase 3 exists, so this item is a direct enabler of the cutover, not a parallel
feature. The same builder is what the Action's own "cram2-link comment" duty will call.

### The eligibility predicate

An item is ready to promote when all of:

- its live state is open-and-ready — this repo's convention is that a pull request stays a draft
  until its author has reviewed it themselves, so out-of-draft *is* the record of "reviewed by me",
  the same signal `_compute_ready_to_review` already reads in the opposite direction;
- GitHub reports it cleanly mergeable (PR 3's `mergeable`, already fetched for its conflict chip) —
  `None` (still computing) is not treated as ready, since promoting a conflicted branch upstream is
  the failure this check exists to prevent;
- its base is the fork's default branch — a pull request still stacked on a sibling cannot be
  promoted on its own, and one whose parent has merged has already been retargeted to main by
  GitHub, so this reads the *current* base rather than the plan's `depends_on`;
- it does not carry `in-review` (already promoted), and it is not merged or closed.

Check state deliberately does **not** gate the list: this repo's robotics jobs flake on tests a
`.claude/`-only pull request cannot reach, and that has already been ruled unrelated-and-ignorable
more than once in this plan. It renders as a chip so the decision stays the user's.

### The link

`https://github.com/<upstream_repository>/compare/<upstream_base>...<fork owner>:<branch>?expand=1&title=<t>&body=<b>`,
url-encoded, with the title taken from the fork pull request and the body being its first paragraph
truncated plus a `Full detail: <fork pull request url>` line. The truncation is not cosmetic —
Phase 3's doctrine records that a compare URL has a length cap and silently drops an over-long body,
which is the kind of failure nobody notices until a promoted pull request arrives upstream empty.

Portability: `upstream_repository` becomes a new optional top-level `plan.yaml` field (with an
optional `upstream_base`), because the dashboard tooling lives on main and this plan's standing rule
forbids a hardcoded repository name outside config defaults. A plan that sets neither renders no
group at all — the feature is invisible rather than broken for a plan with no upstream. `stack.toml`
was considered and rejected as the home for it: it carries git *remote* names (`upstream_remote =
"cram2"`), not the `owner/repo` a compare URL needs, and it is not a file the dashboard reads.

### Why it depends on #111 rather than standing alone off fork main

The two facts the predicate needs live in the same place #111 is already touching: `mergeable` is
literally #111's conflict chip, and the link builder belongs next to `pr_state` in the
`development_tooling` package #111 creates, so `routine-cutover`'s Action can import it instead of
re-deriving the URL format in prose a third time. Standing this item off fork main — the way #103,
#105, #119 and #115 legitimately do — would mean duplicating the `mergeable` plumbing into
`build_dashboard.py` a second time and colliding with #111 for real, not just textually. The cost is
accepted: this item cannot start until #111 leaves draft.

Three fields the pull request entry does not yet carry are this item's own work: `base`, `title` and
`body`, plus `pr-data-fetching.md`'s minimum field set updated to name them — the same document
whose under-specification caused the #119 bug, so the addition goes in as a documented requirement
rather than an optional extra.

### Removal from the list

Applying `in-review` after clicking Create is what drops an item, which is precisely the existing
convention ("I add `in-review` then"). `cram2-link-sent` stays out of the dashboard entirely: it is
Routine-side bookkeeping that stops an emailed link being re-sent, and a list recomputed from live
state on every refresh has nothing to remember. That leaves the two surfaces double-listing a pull
request while the live Routine is still running — accepted, since the Routine is scheduled for
deletion by `routine-cutover` and the overlap is a duplicate link, not a wrong one.

### Ordering

Before `dev-tooling-python-package`, which moves `build_dashboard.py` wholesale, and after #111.
Textual overlap in `build_dashboard.py` with #103, #105, #111 and #119 is the established
whichever-lands-second-merges pattern for this track.

## Update 2026-08-01 (new item): bug-fix chips in the dashboard sidebar

A new `dashboards` item, `sidebar-bug-fix-chips`, on branch
`claude/dashboard-bugfix-pr-section-161vf8`.

### The design reversal that defines it

The request was to surface bug-fixing pull requests in the sidebar, and the first
implementation read that as a new top group — "Bug fixes", listed first, outlined in red.
The user rejected that framing outright: *the sidebar is about actions, and being a bug fix
is not an action classification*. Every such item already belongs to ready-to-start,
blocker-may-be-cleared or ready-to-review, so a fifth group can only be built by taking
items out of the group that describes what to actually do with them. The red outline was
rejected for a second, independent reason: the existing group outlines are not mutually
exclusive with bug-ness, so a bug outline would compete with them for the same visual
channel rather than adding to it.

What survives is an attribute, not a category: `Item.is_bug_fix`, rendered as a small `bug`
chip on the entry *wherever it already is*. Two regression tests pin exactly that — a
bug-labelled item stays in its ordinary action group, and a non-bug entry gets no chip.

This is worth recording because `ready-to-promote-upstream-links` (the item added earlier
the same day) *does* add a fifth sidebar group, and correctly so: "ready to promote" names
something the user does. The distinction the two items draw together is the rule for
anything added to this sidebar later — a group must name an action; anything else is a chip.

### Incidental cleanup

The four sidebar group blocks were near-identical copies of the same markup, which is what
made "add a fifth" look cheap in the first place. They are now one `next_step_group` Jinja
macro whose `{% call %}` body supplies the reason line, so the per-item drift reason and the
three fixed reasons share one code path.

### Process failure recorded on this item

The item was created *after* the implementation was written, pushed, and reviewed — not
before, as this plan's own conventions require. It was also implemented without running
`check-setup.sh` first, so the plan-dashboard dependencies were discovered missing one
`ModuleNotFoundError` at a time across two interpreters instead of in one call. Both are
the same root cause: session-start scaffolding was treated as sufficient context to start
work from. See the conventions discussion this update was written alongside.

### Ordering

Independent, off fork main, no `depends_on`. `build_dashboard.py` overlap with #103, #105,
#111 and #119 is the established whichever-lands-second-merges pattern for this track.

## Update 2026-08-01 (later): the filter, the example, and where this PR sits

Follow-on to the bug-chip item above, all in the same session.

### The filter the chip made possible

The original request had framed this as "more of a filter that we can apply to show only
the bug-fixing ones", and the chip alone did not deliver that. "Bug fixes only" is now a
checkbox on the sidebar card: it hides every non-bug entry and every group left holding
none. Two details are load-bearing rather than cosmetic:

- **The checkbox only renders when some sidebar entry is a bug fix.** A filter whose only
  possible result is an empty card is worse than no filter, and this removes the empty
  state entirely rather than designing a message for it.
- **Each group's heading carries both counts, swapped by CSS.** A filtered group that
  still claims "(4)" while showing one entry is simply wrong, and recomputing counts in
  script would be the first place this page does arithmetic at runtime. Rendering both up
  front and switching with a class is what the done-items toggle already does with its two
  precomputed indent levels, so the filter adds a case to an existing pattern instead of a
  new mechanism.

### The example now demonstrates it

`example/pr_data.json`'s pull request #103 gains a `bug` label — `retry-fallback-queue`, a
dead-letter queue for dropped retries, is plausibly filed as a bug fix, and it puts the
chip on the *drift* entry, which is the clearest possible demonstration that the chip
appears wherever the item already sits rather than moving it. All three walkthrough
screenshots were regenerated from the committed sample (the third,
`dashboard-bug-filter.png`, is new and shows the filter applied). A test pins that the
example keeps producing exactly one chip and the toggle, so the screenshots cannot silently
go stale again.

Regenerating them turned up an unrelated staleness worth noting: the old
`dashboard-overview.png` still showed the description text `EXAMPLE_WALKTHROUGH.md`, a
filename that has since been renamed. Committed screenshots drift silently in a way
committed text does not.

### Where this pull request belongs

Asked to work out its best place, the answer is: exactly where it already is, plus one
downstream dependency.

- **Base stays fork `main`.** The branch is one commit off the current tip, touches only
  plan-dashboard files, and needs nothing from the #101/#106 chain — the same independent
  treatment #103, #105 and #119 get. Stacking it on #111 would buy nothing and inherit that
  chain's review latency.
- **It carries no `bug` label.** It surfaces bug fixes; it does not fix a bug. The
  convention that bug-fix pull requests must be labelled does not reach it.
- **`ready-to-promote-upstream-links` now depends on it.** That item adds a fifth sidebar
  group, which is a single `next_step_group` call once this macro has landed and a fifth
  hand-copied block if it has not — and the reconciliation would then be someone's manual
  merge of two divergent copies of the same markup. This is the first dependency in the
  `dashboards` track recorded for a *refactor seam* rather than for data or files, and it
  is the whole practical payoff of having collapsed the four blocks.
- **Still before `dev-tooling-python-package`**, which moves `build_dashboard.py` wholesale.

Overlap with #111 (item-card chips, new `pr_data.json` fields) and #119 (`from_mapping`'s
merge-timestamp guard) stays the established whichever-lands-second-merges pattern; neither
is a dependency in either direction, and #111 could not depend on this one anyway, being
based on #106.

### An oddity found and deliberately not fixed

`_compute_ready_to_review` requires every dependency to have an *open* pull request, via
`has_open_pull_request`, which is false once that dependency has merged. So an item whose
dependency has fully landed is excluded from "Ready to review", while one whose dependency
is merely open is included — the more finished the dependency, the less reviewable the
dependent looks. It is visible in the committed example, where `retry-circuit-breaker` sits
out of the list behind a merged `retry-backoff-strategy`. Left alone here: it is a
different root cause from this item's, and this plan's own convention keeps a bug-fix pull
request to one. It belongs to the same family as #103 and is worth its own item if it is
real rather than intended.

## Update 2026-08-01 (process): the two skipped steps become their own item

New `personal-data` item `session-start-plan-and-setup-guards`, recorded at the user's
request and deliberately left unimplemented for its own session.

Both failures it addresses happened in the bug-chip session, and both were already
forbidden in prose:

1. **The plan item was created after the implementation was written, pushed and reviewed.**
   The request named the plan in its first sentence. What made it survivable was
   `session-start.sh` printing a bare `plan: none` for a branch the generated index does
   not list — a message that reads as "no plan applies here" but equally means "the plan
   you were told about has no item for this branch yet". The convention that plan state is
   updated in the same turn cannot fire if the session has already concluded no plan is in
   play.
2. **`check-setup.sh` was never run**, so the plan-dashboard dependencies surfaced one
   `ModuleNotFoundError` at a time across two interpreters, and `plan-dashboard/SKILL.md`'s
   own step 0 was not read until the skill was invoked at the very end — long after its
   code had been edited.

The three fixes, in increasing strength: make the plan line name its own ambiguity; run
`check-setup.sh` from `session-start.sh` and surface a non-zero exit; and, if enforcement
is wanted over prompting, a `PreToolUse` hook on `Edit|Write` refusing the first source edit
from a branch with no plan item, with an explicit opt-out. The first two are the
recommendation. Only the third makes the miss impossible rather than unlikely.

Plan mode was considered as the mechanism and rejected: it would likely have caught the
first failure, but it rests on the same judgment that missed it and runs nothing, so it
would not have caught the second at all. The distinction worth keeping is that conventions
in `cram-notes.md` are read by a session that has already decided what it is doing, while
hooks run before it decides.

## Update 2026-08-01 (spun out): the ready-to-review merged-dependency bug gets its own item

`sidebar-bug-fix-chips` was opened as draft pull request **#120** (fork `main`, no `bug`
label, subscribed). The oddity its session recorded but refused to bundle in is now
`ready-to-review-merged-dependency` in the `dashboards` track.

**The bug.** `_compute_ready_to_review` admits an item only when every dependency satisfies
`has_open_pull_request` — `OPEN_DRAFT` or `OPEN_READY`, and therefore *false* once that
dependency merges. So the rule inverts at the far end: a dependency with a rough open draft
lets its dependent through, and the same dependency, fully landed, keeps it out. The more
finished the base, the less reviewable the thing on top of it looks.

**Why it reads as an oversight rather than intent.** The method's own docstring gives the
rationale as *"reviewing a stacked pull request before its base even has one open yet is
premature"* — a condition a merged base satisfies more completely than any open one.
`has_open_pull_request` was evidently reached for as the proxy for "the base exists and is
far enough along to build on", and it simply happens to be false at the settled end of the
range. That is a guess about intent, though, so the item's first step is to confirm it with
the developer rather than to patch it — AGENTS.md is explicit that an unexplained decision
gets a question, not an invented reason.

**The shape of the fix, if confirmed.** A dependency with *no* pull request at all must keep
excluding its dependent — there the base really does not exist yet, and that half of the
rule is right. So only the settled states need adding. `Item` already carries
`is_ready_to_unblock_dependents()` (done, merged, or open-and-ready), which is nearly this
predicate under a different name, so the fix may be a consolidation rather than an extra
clause.

**Why it was not folded into #120.** Different root cause, and this plan's own convention
keeps a bug-fix pull request to one. It is the third member of the same family as #103
(ready-to-start dropping dependency-free items) and #105 (unmet dependency chips) — all
three are cases of the sidebar's admission rules being written for the common case and
falling over at an edge of the dependency lifecycle. Worth noticing that the family keeps
producing members: the four sidebar lists are computed by four separate predicates that
each re-derive "is this dependency far enough along" in their own words.

## Update 2026-08-01 (kickoff + implementation): the session-start guards ship as #121

`/plan-item-kickoff workflow-unification session-start-plan-and-setup-guards`, session
https://claude.ai/code/session_01JSxeoePmxWoA4aETrwhFcx, which went on to implement it in the
same session as draft pull request **#121** on `claude/workflow-unification-setup-jgvs53`
(fork `main`, independent of the #101/#106 chain).

### The question that reshaped the design

The item recorded three fixes and named the first two as the recommendation. Asked which to
build, the user chose those two but attached a requirement the item had not considered:
*maybe the user doesn't want to have a plan or personal notes at all — how would that be
handled?* — and, for the guard, *"only for people who want to have plans or personal notes …
as automatic as possible and reliable and works well for both types of users"*.

That requirement turned out to need **no new setting**, which is the point worth carrying
forward. `session-start.sh` already opens with `fetch_personal_notes_branch || exit 0`, so a
clone with no personal-notes branch has always been served total silence; everything added
sits after that line and inherits it. Within the group that does use the branch, whether
`_generated/branch-index.tsv` exists separates *notes but no plans* — a legitimate
configuration that must read as quiet and accurate — from *plans in use*. Both discriminators
are state that already exists. A configuration flag would have been the obvious design and
the wrong one: it can be set wrongly, it needs documenting, and it asks the least invested
user to opt out of something they never asked for.

### What shipped

Four distinct plan-line outcomes in place of one bare `none`, the third of which had never
been visible at all: an index entry naming a plan whose manifest has since gone missing was
indistinguishable from having no plan. And a `setup:` line carrying `check-setup.sh`'s
`needs-setup` rows — run *after* `CLAUDE.local.md` is written, so its `claude_local_md` check
reports on this run's own output rather than flagging a correctly set-up clone, and captured
with `|| true` so a setup gap can never fail the hook. `plan_branch_index_exists` and
`tracked_plan_count` live in `resolve-personal-notes-config.sh`, which already owns that path.

### A latent crash, found only by writing the tests

`session-start.sh` had no test module. Writing the first one immediately surfaced that a plan
with **no `tracking_issue`** killed the hook outright: `grep` exits 1 when it matches nothing,
`pipefail` propagates that, and `set -e` ends the script with no output whatsoever — no notes,
no progress, no summary, no error. Every plan this fork tracks sets `tracking_issue`, which is
the only reason it had never been seen. This is the same shape as the `default_repository`
grep bug `plan-updates-since-helper` caught on #115, in the same family of scripts, within
days — the pattern is `set -o pipefail` plus a `grep` used as a test rather than a filter, and
it is worth grepping the remaining hooks for it rather than waiting for the third instance.

### The third fix became its own item

`plan-item-edit-guard` (`personal-data`, depends on this item). The user settled its semantics
while agreeing the split: block until resolved rather than a one-shot speed bump, active only
for someone who uses plans or personal notes, inert for everyone else. Inertness is a hard
constraint, not a preference — `.claude/settings.json` is committed, so every contributor who
inherits this repo inherits the hook, and one that blocked their edits would be indefensible
upstream. It should reuse #121's state-derived discriminator rather than introduce a setting,
for the same reason above.

Also worth recording from this session: the git identity configured in a fresh cloud clone is
`Claude <noreply@anthropic.com>` — precisely what AGENTS.md's Version Control rule forbids, and
the same authorship this roadmap already flags twice as a standing hazard on #101 and the P3
branch. It is the *default*, so it is not a one-off slip that happened to land; every session
that commits without setting the identity first reproduces it. Set `user.name`/`user.email`
before the first commit of any session.

## Update 2026-08-01 (hazard tracked): the assistant git identity is the container default

Raised by the user while `session-start-plan-and-setup-guards` was being implemented, and now
tracked as `git-identity-from-personal-notes` (`personal-data`).

This roadmap already flags commits authored `Claude <noreply@anthropic.com>` twice — three merge
commits on #101, and `6b51075e`/`f5d1c883` on the P3 branch — both times as something that had
happened, left unrewritten because fixing authorship means force-pushing shared history. What was
never established is *why* it keeps happening. It is the **global** git config in a session's
container:

```
global : Claude / noreply@anthropic.com
local  : (none, in a fresh clone)
GIT_AUTHOR_* / GIT_COMMITTER_* : unset
```

So it is the default rather than a slip, and every session that commits without first setting an
identity reproduces it. That reframes it from a recurring lapse of discipline into a missing piece
of tooling — which is the reason it became an item instead of another roadmap warning.

**The fix has a natural home.** `personal-settings-sync` (#109) already established the pattern:
personal config lives on the notes branch and is written into the clone at session start. A git
identity is the same shape. `check-setup.sh` gains a `git_identity` check, which then reaches the
user through the `setup:` line #121 added, with no new delivery mechanism. The one design rule
worth fixing now: write the repo-local identity *only when none exists yet* — a fresh clone has
none, someone who set one deliberately keeps it — rather than blocklisting known assistant
identities, which would be brittle and would need updating for every new one.

**Two limits, stated rather than papered over.** A hook covers only commits made inside a session
in this clone. The merge commits flagged above landed from *outside* any session — the GitHub
merge button and the live Routine — and no local hook can reach those; that half needs the GitHub
account's own commit-email setting or a changed merge path. And the global config stays wrong, so
only this repo is covered.

**A zero-code alternative exists and is stronger where it applies**: `GIT_AUTHOR_NAME`,
`GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME` and `GIT_COMMITTER_EMAIL` set at the environment level,
alongside the `CLAUDE_PERSONAL_NOTES_*` variables already kept there. Environment variables beat
both local and global config and are in force from a session's first command, before any hook
runs. They are per-environment and do not travel to another contributor's clone, which is exactly
why the tooling fix is still worth doing — the two cover different populations rather than
competing.

## Update 2026-08-01 (kickoff + implementation): the ready-to-review merged-dependency fix ships as #122

`/plan-item-kickoff workflow-unification ready-to-review-merged-dependency`, session
https://claude.ai/code/session_01Ltrz1G8qwSHgo6jyfeV1EU, which went on to implement it the same
session as draft pull request **#122** on `claude/plan-item-kickoff-workflow-s9e8bj` (fork `main`,
`bug` label, independent of the #101/#106 chain).

### The confirmation the item required

The item's first step was to confirm the oversight reading with the user rather than patch on a
guess, per AGENTS.md's rule against inventing a reason for existing behaviour. Confirmed: it is an
oversight. `has_open_pull_request` was the proxy for *"the base exists and is far enough along"* and
simply happens to be false at the settled end of the range.

### The consolidation this plan proposed three times is wrong

Worth recording prominently, because the suggestion had propagated into three places that all agree
with each other — the item's own `notes`, the *spun-out* section above, and the tracking-issue
comment of 2026-08-01T11:00:35Z — so the next reader would have found three concurring sources
pointing at the wrong fix.

`Item.is_ready_to_unblock_dependents()` is **not** the right shared predicate. It is
`is_effectively_done() or OPEN_READY`: it deliberately *excludes* `OPEN_DRAFT`, because a draft can
still see heavy rework and is unsafe to build a branch on. But `_compute_ready_to_review`
deliberately *includes* a draft dependency, and that is pinned by a pre-existing test whose own
comment says so — *"The dependency need not itself be past review - it just needs a pull request
open, so a whole reviewable stack can surface before its base merges."* Reusing it would have
traded this bug for a new one.

So the two predicates differ by exactly `OPEN_DRAFT`, and that difference is the real distinction:

- **safe to build a branch on** requires the base to be out of draft — `is_ready_to_unblock_dependents()`
- **worth reviewing the branch above** requires only that the base exists — `is_ready_for_dependent_review()`

Two sibling predicates sharing `is_effectively_done()` is the correct shape, not one merged
predicate. `has_open_pull_request` survives as the building block the new one composes, so nothing
became test-only and AGENTS.md's consult-before-removing rule was never reached.

This is the general lesson the family keeps teaching: the four sidebar lists each re-derive "is this
dependency far enough along" in their own words, and the answer is genuinely *different* per list.
Consolidating them onto one predicate is the tempting fix and the wrong one — what they need is
named predicates that make each list's own threshold explicit.

### The example, and the one assertion deliberately changed

`test_example_plan_renders_the_counts_and_sections_the_walkthrough_describes` is the only existing
assertion touched. That is the test working, not a test being bent: its own docstring says it exists
so *"a future change to either would fail this test instead of silently leaving the doc showing stale
numbers"*, and updating the assertion together with the prose and the screenshot is exactly the
response it was written to force. The example *fixture* is untouched, and now demonstrates the fix —
`retry-circuit-breaker` reaches the list behind its merged `retry-backoff-strategy`, so the sidebar
reads **Ready to review (2)**.

The screenshot was regenerated (user's call, taken knowing it conflicts as a binary with #120's own
regenerated copy — whoever lands second re-regenerates, mechanical because the image is deterministic
from the committed fixture). **There is no regeneration script**, which is itself the reason
screenshots keep drifting silently; until one exists the recipe is: render `example/` through
`build_dashboard.py`, then headless Chromium at `--window-size=1280,…` with
`--blink-settings=preferredColorScheme=0` — the dark theme the committed images use, and *not* the
headless default — cropped to the same 100px bottom margin. Regenerating also cleared the
`EXAMPLE_WALKTHROUGH.md` staleness this roadmap flagged on 2026-08-01: a committed screenshot goes
stale from any change, not only from the one that prompted the regeneration.

### Correction to the git-identity hazard, verified live this session

The `git-identity-from-personal-notes` item recorded above diagnoses the container state as
`GIT_AUTHOR_*`/`GIT_COMMITTER_*` **unset**, with the global config supplying
`Claude <noreply@anthropic.com>`. That is no longer the state. In this session:

```
global : Claude / noreply@anthropic.com      (still wrong)
local  : set by this session, and ignored
GIT_AUTHOR_NAME / GIT_COMMITTER_NAME   : Abdelrhman Bassiouny
GIT_AUTHOR_EMAIL / GIT_COMMITTER_EMAIL : abassiou@uni-bremen.de
```

So the zero-code alternative that item names as *"stronger where it applies"* is now actually in
force, and #122's commit is live proof it works: it landed authored `Abdelrhman Bassiouny
<abassiou@uni-bremen.de>` despite the global config still being wrong, and despite a repo-local
identity having been set to `bido.bassuny@gmail.com` — environment variables beat both, exactly as
predicted.

Two consequences for that item. Its diagnosis section needs updating before anyone implements
against it, or they will build for a container state that no longer holds. And its "write the
repo-local identity only when none exists yet" rule now has a second reason to be careful: a
repo-local identity written by the hook would be silently overridden by these environment variables
anyway, so on this environment the hook can only ever be a no-op — its real value is the *other*
populations (another contributor's clone, an environment without the variables set), which is what
the item already says, just now with the overlap made concrete.

## Update 2026-08-01 (gap closed): notes-only work needs no plan item

Raised by the user after #121 was already open, and it exposed a real wart in what had
just shipped: *"some situations happen where I am a personal notes user and a plan user,
and there's work that will just be directly a modification on my personal notes and will
not be merged upstream or be done off main. For these cases, there's no need for the item
to be part of a plan."*

Verified rather than reasoned about, by running the new hook against a `main` worktree:

```
PR progress:  not applicable (no current PR on this branch)
plan:         no item tracks branch 'main' (5 plan(s) tracked) - ... add its item before starting
```

`main` can never be a plan item's branch, and **the line directly above already knew
that** — `pr_progress_path` has always excluded the default branch, the personal-notes
branch and a detached HEAD. The new plan line simply ignored an exclusion its own
neighbour had been applying for exactly the same reason. Those three now report
`not applicable`; an index entry naming the branch still wins over the check, so a
genuinely tracked branch is unaffected.

**The two predicates are deliberately not shared**, despite listing identical cases today.
They answer different questions and are already known to diverge: a branch whose pull
request *targets the notes branch* still wants its progress tracked, but still never wants
a plan item. Sharing them now would have to be undone the moment that case is handled.

### The case left open, and why it isn't in #121

The user's follow-up — *"what if someone (a session for example) makes a PR that targets
the notes branch? this as well should not have a plan item"* — is correct and is **not**
covered by the three branch names. It is recorded on `plan-item-edit-guard` instead of
being fixed here, for a concrete reason worth remembering: the obvious local test, "the
notes branch tip is an ancestor of HEAD", collides with the hook tests' own fixture, which
creates its work branch *off* the notes branch (`publish_notes_branch`). Adopting that test
without first re-basing the fixture on the initial commit would have failed every existing
plan-line test and, worse, encoded an unrealistic branch topology as the reference. That is
a fixture refactor in a file #115 also edits, so it belongs with the item that needs the
mechanism rather than bolted onto this one.

### What this settles for the guard

`plan-item-edit-guard` now carries two mechanical exemptions rather than opt-outs: it fires
only for files tracked in the working tree (so notes-only work is exempt for free —
`CLAUDE.local.md` is gitignored, and notes and plan data are written from scratch paths by
the `save-*.sh` scripts), and a notes-targeting pull request is exempt once (b) has a
mechanism. The per-branch opt-out survives, but its only remaining job is genuine no-plan
*code* work — a much narrower and more defensible role than "anything the guard gets wrong".

## Update 2026-08-01 (kickoff + implementation): the git identity sync ships off #121

`git-identity-from-personal-notes` was kicked off and implemented in the same session. Two
things the item recorded turned out to be wrong at implementation time; both are corrected
in its `notes`, and both changed the design rather than just the prose.

### The environment variables, confirmed a second time

The container check the `#122` session recorded above (*"Correction to the git-identity
hazard"*) reproduced exactly: global config still `Claude <noreply@anthropic.com>`,
`GIT_AUTHOR_*`/`GIT_COMMITTER_*` set to `Abdelrhman Bassiouny <abassiou@uni-bremen.de>`, and
an empty commit in a scratch repository authored correctly — reverting to `Claude` the moment
those four variables are stripped. This clone differed in one respect from that session's:
**no repository-local identity at all**, so precedence ran straight from the environment to
the global fallback.

The consequence that section did not draw is the load-bearing one for the check. Because the
variables outrank config, `git config --get user.name` prints `Claude` *on a clone whose every
commit is correctly authored*. A check built on it would report the assistant identity as the
problem on exactly the clones that don't have one — the single wrong answer a check about
commit authorship must never give. So `effective_git_identity` resolves through
`git var GIT_AUTHOR_IDENT`, which applies git's real precedence, and `check-setup.sh` compares
*that* against what the notes branch records.

That also answers the "the hook can only ever be a no-op on this environment" point above.
It is true, and it is why the check matters more than the write here: on an environment with
the variables set, the `git_identity` row is what makes the override visible, naming
`GIT_AUTHOR_NAME`/`GIT_AUTHOR_EMAIL` as the reason a correct-looking config still isn't what
commits carry. The write half is for the populations without them.

### Not an independent PR off main after all

The item says *"small independent PR off fork main, like #109 and #115"*, `depends_on: []`.
Checked against the live branches, neither held:

- **#109 is not a viable base at all** — `mergeable_state: dirty`, labelled `needs-resolution`,
  based on the superseded `0fd14357`. The item offered folding the identity into its
  `settings.local.json` sync; that would have blocked this on a stalled PR, so it gets its own
  `.claude/personal/git-identity` instead.
- **#121 carries the only harness that can test this.** On `main`, *nothing* runs
  `session-start.sh` in a test. #121 adds `ScratchRepository.run_hook_script` and
  `write_setup_prerequisites`, and `test_session_start_sh.py` alongside them.

Basing off `main` would have meant hand-rolling a `run_hook_script` equivalent *in the same
file* #121 adds one to — not the textual overlap the whichever-lands-second convention covers,
but duplicated infrastructure that collides. The asymmetry settled it: if #121 lands first,
rebasing onto `main` costs nothing, whereas a parallel harness is thrown-away work either way.
So `depends_on: [session-start-plan-and-setup-guards]`, and the sibling items that legitimately
based off `main` are not a precedent here — theirs overlapped on summary lines, this one needs
a harness.

Worth keeping as a general rule: *"independent PR off main"* recorded at planning time is a
claim about the code, and it expires when a sibling PR moves the test infrastructure. Re-check
it against the live branches at kickoff rather than inheriting it.

### What shipped

`.claude/personal/git-identity` on the notes branch, in git's own config format and read back
with `git config --file` — no hand-rolled parser, and the writer is the same tool as the reader
so the two cannot disagree. `session-start.sh` writes it into repository-local config only when
the clone has neither `user.name` nor `user.email` of its own, before the setup check so
`check-setup.sh` reports on what this run just did. `save-git-identity.sh` requires `--name`
and `--email` and refuses to read them from the clone's config — in a fresh session environment
that resolves to the assistant identity, so a guessing script would record the very thing this
item exists to stop, silently. Same reasoning as #107's required `--remote`.

One refactor came along because the tests forced it: the environment scrub moved onto
`ScratchRepository.run_hook_script`, replacing the two hand-rolled scrubbed-subprocess blocks
#121 left in `test_check_setup_sh.py` and `test_session_start_sh.py`, and extending it to
`GIT_AUTHOR_*`/`GIT_COMMITTER_*`. Without that the suite would assert against whatever identity
the runner's shell happens to carry — which, per the section above, is not empty here.

54 tests pass in `.claude/hooks/tests`, was 37. Verified live in this clone beyond the suite:
the row read `needs-setup` naming the real author while `git config --get user.name` said
`Claude`, `save-git-identity.sh` recorded the identity, the row went `ok`, and a re-run pushed
nothing.

## Update 2026-08-01 (kickoff + implementation): dashboard chip notes collapse

Raised directly from a screenshot of this plan's own published dashboard: the
`ready-to-review-merged-dependency` card's `notes` (see its entry above) ran long enough to
fill the entire viewport by itself, so only one item was visible on screen at a time and
reviewing the board meant heavy scrolling instead of a glance-able overview. The dashboard's
whole purpose is the opposite of that.

`item_card` (`templates/dashboard.html`) rendered `item.notes` at full height with no
collapse — every long-note item did this, not just that one card. Fixed by wrapping the
notes `<div>` in a `<details>`/`<summary>` toggle, collapsed by default, reusing the
`.roadmap-details` CSS-only arrow-toggle already in the file for the page-level "Background
& history" section rather than adding new JS. Deliberately did not touch
`build_dashboard.py`/`render_common.py` — they already pass `item.notes` through unchanged,
and the native `<details>` element needs no script wiring. The sidebar "What to do next"
cards are unaffected: they render short fixed one-line strings, not `item.notes`.

Verified by rendering the skill's own `example/` fixtures through `build_dashboard.py` with
a temporarily lengthened note and publishing the result as an Artifact: notes collapse by
default behind "▸ Notes", expand to "▾ Notes" in place on click, and items with no notes
render no summary line at all. `pytest .claude/skills/plan-dashboard/tests/` — 194 passed,
unaffected since this is template/CSS only.

Independent of the `#101` chain, based on fork `main`; `dashboard.html` overlap with `#103`,
`#105`, `#111`, `#119`, `#120` and `#122` is the same whichever-lands-second-merges pattern
this track has had throughout. Opened as draft pull request `#124`, subscribed to its
activity.

### Opened as #126, and the one thing that makes a stacked base worth watching

Draft pull request **#126**, based on `claude/workflow-unification-setup-jgvs53` (#121), no `bug`
label. It is the first item in this plan whose pull request stacks on *another item's* pull request
while sitting outside the `#101 → #106 → #107 → #110` chain, and that is worth one line of standing
guidance rather than being rediscovered later.

Neither #121 nor #126 is a member of a native GitHub stack, so the Phase-1 reparent hazard
(`422 - Cannot change the base branch because the pull request is part of a stack`) does not apply
here: a plain `PATCH` of the base is available as the recovery. What *does* apply is round-2 of
`native-stacks-prototype`'s findings — a push-based merge marks a pull request merged but does
**not** retarget its children, and only `merge-async` retargets automatically. So if #121 lands by
push or fast-forward rather than through its own pull request, #126 keeps pointing at a branch that
is about to disappear, and needs retargeting to `main` by hand. Cheap to fix, invisible if nobody
looks.

The reverse direction is the cheap one, and is why the base was chosen: if #121 merges normally
first, rebasing #126 onto `main` costs nothing.

## Update 2026-08-01 (decision 12): the bash layer retires into development_tooling — conversion registered

Session: https://claude.ai/code/session_015ShWoksdRxv5ioXcDaNiQk (study session; registration only, no
code conversion). Eight new items in the `dashboards` track: `dev-tooling-notes-core-python` through
`dev-tooling-config-shim-slimming` plus `dev-tooling-github-api-unification`, all downstream of
`dev-tooling-python-package`.

### What was decided

All logic in the `.claude/` bash tooling (~1300 lines across 9 hook scripts plus
`refresh_dashboard.sh`) moves into `development_tooling`. This extends decision 8 in its own
words — it already said the bash hook entry points "become thin wrappers invoking `python -m`" —
and settles what that means: the permanent bash remainder is ~8 three-line shims at the existing
paths, a slimmed `resolve-personal-notes-config.sh` (constants + cd for the 10 doc sourcing sites
and ci.yml), and `configure-personal-notes.sh` unchanged (pasted-by-reference into cloud
environment setup fields this repo cannot update). `settings.json` stays byte-identical.

### Why now (the evidence)

The study inventoried the bash layer's failure record and duplication:

- Four near-identical copies of the scratch-worktree write dance (plus an orphan fifth) that
  `write-personal-notes-file.sh` was extracted to end but never absorbed; the marker strings,
  branch-missing error, and no-CLAUDE.local.md error each duplicated 3-4 times.
- The recorded pipefail/`set -e` family (#107's exit-128 fix, #115's `default_repository` grep,
  #121's `tracking_issue` latent hook-kill) — the 2026-08-01 comment on #102 already called two
  instances a pattern; the study found the class is structural, not incidental.
- Defects nobody had hit yet: a missing `BEGIN-PERSONAL-NOTES` marker pushes the *whole*
  `CLAUDE.local.md` (PR-progress included) into the notes file; `__save-personal-notes-tmp` /
  `__save-pr-progress-tmp` are fixed names that race between concurrent sessions; every push is
  single-shot, so a concurrent save loses the edit after the trap deletes the committed scratch
  worktree; `set -u` kills argument loops on a trailing flag; `save-plan.sh` never validates the
  roadmap; `check-setup.sh` passes on any substring occurrence of `session-start.sh` in
  settings.json.

Each conversion item fixes its file's defects with failing tests first; external contracts (flag
surfaces, TSV rows, exit codes, the 4-line SessionStart stdout block) are pinned by golden
fixtures recorded from the bash versions and by subprocess contract tests through the real shims.

### The one accepted functional trade

The SessionStart floor rises from bash+git to bash+git+python3>=3.11. The shim probes and exits 0
with a single diagnostic line when the probe fails, so the hook stays inert for contributors —
a machine without python3 silently skips loading personal notes. Accepted deliberately: every
targeted environment ships 3.11+, and the bash read path is where the silent-death bugs live.

### Sequencing

Items 2-6 cannot land before the in-flight bash-touching PRs (#107, #109, #110, #115, #121,
#126): a wholesale body rewrite is not mergeable by the whichever-lands-second-merges convention.
`dev-tooling-session-start-python` additionally depends on the #121/#126 items so their
`run_hook_script` tests carry over as the shim contract tests. Everything hangs off
`dev-tooling-python-package`, which stays last in the upstream wave as already recorded.

### The krrood question (asked, verified, deferred)

The user asked whether `development_tooling` should depend on `krrood` — exceptions as
`DataclassException` subclasses, and eventually EQL/verbalization. Verified in-session:
`krrood.exceptions`' only third-party import is `typing_extensions` (line 9, `Optional`) — a
one-line stdlib fix makes `import krrood.exceptions` fully stdlib-clean (proven empirically with
all third-party imports blocked; `krrood/__init__.py` is already stdlib-light). In-monorepo use
would need no install (a 2-line `sys.path` bootstrap to `krrood/src/`); other repos have
`pip install krrood` (PyPI, 26.7.0) via their environment setup script — never in the hook (60s
budget, pygraphviz build hazard, contributors' machines). EQL/verbalization can never be
hook-safe (jinja2/lemminflect/rustworkx) and are under active churn in three sibling plans.

**Decision: version 1 is fully independent of krrood.** `errors.py` mirrors the
`DataclassException` idiom in a stdlib-only base — a small, conscious pattern duplication. A
separate future plan (working name `dev-tooling-krrood-adoption`, deliberately *not* created now)
migrates the tooling onto krrood once the krrood API plans (`dag-facade-hardening`,
`eql-performatives`, `eql-verbalization`) and the converted tooling itself have stabilized,
seeded with the verified facts above plus the guard design (a CI test importing
`krrood.exceptions` with third-party modules blocked defines the hook-safe surface; the tooling
may only import guard-covered modules). Dependency tiers adopted now, krrood-independent:
tier 1 hook-safe = stdlib only (SessionStart path, enforced by an import-block test); tier 2
command-time = installed packages (PyYAML); tier 3 domain machinery (EQL queries over the plan
model, verbalized status text) = only ever in dedicated feature items of that future plan.

## Update 2026-08-02: `landed-parent-detection` validated against the real PR #41 stack

`/plan-item-resolve workflow-unification landed-parent-detection`, prompted by the user wanting to
try PR #117's fix on "the current stack that starts with PR #41 which has the exact issue" rather
than take the item's synthetic tests on faith.

**Confirmed live, not assumed**, before touching anything:

- `ripple-down-rules-refactor` (PR #40's head, `34f160df`) **is** an ancestor of `origin/main` -
  `git merge-base --is-ancestor origin/ripple-down-rules-refactor origin/main` succeeds. PR #40 is
  closed, not merged - exactly the "landed by another route" case.
- PR #41 (`rdr-backward-inference`) is still based on that branch (`base.sha` matches the branch's
  live tip) - it has not been reparented since the bug was found.
- PR #41 is native GitHub **Stack #112** (`GET /stacks/112`, `X-GitHub-Api-Version: 2026-03-10` via
  curl + `GH_TOKEN` - no MCP tool exposes the stacks API): `#41 (rdr-backward-inference) -> #63
  (D-core-aid) -> #64 (D-core-underspecified) -> #65 (D-core-corner-case) -> #66
  (D-core-serialization) -> #67 (D-core-support) -> #98 (D-core-expert)`, all open, all non-draft
  except #41. This is the exact native-stack-member case `ROUTINE.md`'s NATIVE-STACK MEMBERS section
  (added by this item) targets: plain `PATCH` 422s here, recovery is dissolve -> PATCH -> restack ->
  re-create.

**The validation itself** (read-only local script, no push, no GitHub write): built the real 7-PR set
above as `PullRequest` records and wired `is_merged` to a real `git merge-base --is-ancestor
origin/<branch> origin/main` predicate - no stubs, no synthetic fixtures - then ran `restack_plan`/
`parent_landed` from two checkouts:

- **`claude/stack-tooling-on-main` (#106, pre-fix)**: `restack_plan` reparents #41 onto
  `ripple-down-rules-refactor` (the stale, closed branch) rather than `main` - the bug reproduces
  exactly as described, on live data, not just in the item's own synthetic tests.
- **`claude/stack-landed-parent-detection` (#117, the fix)**: `restack_plan` correctly emits
  `{"branch": "rdr-backward-inference", "parent": "main", "strategy": "merge"}` for #41, and
  `has_landed_upstream("ripple-down-rules-refactor")` is `True`. The six branches above #41
  (#63..#98) keep their normal parent-chain entries unchanged - only #41's root parent moves.

**What this settles.** The item's own notes already said "restack-plan emits the right parent but
Phase 1 still will not retarget on GitHub" - that was true of the synthetic tests only, since nobody
had run the fixed code against #41's actual data before. It now holds against the real stack too, so
the fix is validated end-to-end for the exact case it was written for, not merely for the
synthetic fixtures the failing-first tests use.

**What was deliberately not done, then attempted with approval.** The live repair - `POST
/stacks/112/unstack` (dissolves all 7, no selective/undo), `PATCH` #41's base to `main`, restack +
force-push #41 through #98 in order, `POST /stacks` to re-create - was proposed first and not
executed pending explicit go-ahead, since it is destructive and force-pushes six live branches. The
user then approved it in the same session, and it was attempted for real:

- `POST /stacks/112/unstack` (no body): **204**, dissolved cleanly.
- `PATCH /pulls/41` with `{"base": "main"}`: **403** - `"Changing a pull request's base branch is
  not permitted for this session type."` This is a new hazard, and a harder one than the item
  itself anticipated: `ROUTINE.md`'s NATIVE-STACK MEMBERS section (this item's own addition) was
  written for the **422** GitHub returns when a `PATCH` targets a *stacked* PR's base - its whole
  recovery sequence (dissolve first, then PATCH, then restack, then re-create) exists to get past
  that 422 by removing the PR from a stack before touching its base. This 403 fired on the *already
  unstacked* PR - it is a platform-level restriction on any base-branch change from a Claude Code
  session, unrelated to stack membership. The dissolve-then-PATCH recovery this item designed
  cannot work around it, because the block isn't the stack; the doctrine's whole premise for this
  case needs revisiting.
- Recovery, per `ROUTINE.md`'s own stop-and-report rule (never leave a stack half-dissolved):
  re-created the stack immediately, `POST /stacks` with the same 7-PR list. GitHub assigned it a
  **new number, Stack #128** - #112 cannot be reused once dissolved - but the PR list, order, and
  every base are otherwise identical to before the attempt. Verified: #41's base is still
  `ripple-down-rules-refactor`, unchanged; nothing about any of the seven PRs' actual state moved.

**Consequence for `landed-parent-detection` and `ROUTINE.md` going forward.** This joins the
tag-push/branch-delete finding from the 2026-07-29 addendum as a third confirmed instance of the
same shape: a mutating GitHub operation that works fine through the API in principle but is blocked
specifically for a Claude Code session's credentials. The item's NATIVE-STACK MEMBERS sequence
still describes the right *mechanics* (dissolve -> PATCH -> restack -> re-create), but step 3 (the
PATCH) needs a human or a differently-scoped actor to execute - the UI's "Rebase stack" button, `gh
stack` from a real user token, or a broader-scoped credential - the same way tag pushes and branch
deletes already do. `ROUTINE.md` and the live Routine's prompt both need this stated explicitly
rather than assuming the sequence completes end-to-end from a session; as written today, a session
hitting this now dissolves a stack it cannot finish repairing unless it also re-creates it
immediately, as done here. Merging #117 itself (normal cram2-review track) and pasting the Phase 1
amendment into the live Routine trigger (the user's own manual-paste call) remain untouched,
unrelated to this finding.

## Update 2026-08-02 (later): the fix generalizes to a new item; and preventing the orphan in the first place

Follow-on in the same session, after the user asked two things: how to make the reparent fully
session-solvable (not needing a human for the blocked step), and separately, how to stop a parent
landing-while-closed from orphaning a child at all, rather than only recovering after the fact.

### Scope correction: the block is unconditional, not stack-specific

The PATCH 403 recorded above fired on PR #41 *after* it had already been removed from Stack #112 -
at that moment it was an ordinary, non-stacked pull request. That means the restriction is not the
stack-member 422 `landed-parent-detection`'s `ROUTINE.md` addition was written for; it is a
platform-level block on **any** pull request base-branch change from a Claude Code session, full
stop. The consequence reaches further back than today's incident: the *original* Phase 1 REPARENT
paragraph (`stack-tooling-on-main`, #106), which prescribes a plain `PATCH` for an ordinary,
non-stacked child whose parent lands, was never actually session-executable either - nobody had hit
it live before because a parent landing while its own PR stays open-and-merged (the common case) is
rare enough that the retarget step had never actually been exercised end to end.

### New item: `session-safe-pr-reparent`

Spun out rather than folded into #117, since it is a different root cause (a blocked API call, not
the board-membership/git-ancestry detection bug #117 fixes) - matching this plan's own
one-root-cause-per-bug-fix convention. `depends_on: [landed-parent-detection]`, branched on top of
#117's head rather than #106 directly, since it edits both #106's original REPARENT paragraph and
#117's NATIVE-STACK MEMBERS addition.

**The fix**: replace "PATCH the base" everywhere in `ROUTINE.md` (and the small reparent-recovery
script #106 already scopes) with **close the orphaned PR, `create_pull_request` for the same head
branch against the corrected base, carry over labels and the session-link line, comment on the old
PR linking to the new number**. Creating and closing pull requests both already work fine from a
session - this substitutes the mechanism rather than retrying the blocked verb. Native-stack members
keep the same shape as #117's sequence, swapping only the middle step: unstack -> close old PR ->
create new PR -> restack (local rebase/force-push, unchanged) -> re-create the stack with the new PR
number in place of the old one.

**Cost, named rather than hidden**: the reparented PR gets a new number and its review thread starts
fresh. Mitigated by the close-comment linking old to new, but it is a real trade against a clean
PATCH - accepted because the clean PATCH is not available to a session at all, so there is no
zero-cost alternative to weigh it against.

**Cross-note for `routine-cutover`** (added to that item's own notes too): verify, concretely, whether
the Action's own credential (default `GITHUB_TOKEN` or a stored PAT - a different actor identity than
a session's token) can PATCH a base cleanly, before assuming it needs the same close+create-PR
fallback. If it can, the Action gets a real, clean reparent with no PR-renumbering cost at all -
worth checking before building the fallback into the Action's own path.

### Preventing the orphan itself, not just recovering from it

The user's second question - stop a landed-but-closed parent from ever orphaning a child - has two
layers, and the first one is the most direct:

1. **The fix that already exists has to actually ship.** `landed-parent-detection`'s own notes already
   record that the live Routine's Phase 1 prompt is unpatched pending the user's manual paste, and
   #117 itself is not yet merged to `main`. Until both land, the *old* code keeps running in
   production, and it will keep missing this exact case - a closed-not-merged parent - on every
   cycle, indefinitely, not just once. This is worth stating plainly because it is easy to read
   today's work as "done" once the logic is fixed and validated; it is not in force until deployed.
   Once it is, the ancestry-based check runs on every Phase 1 pass and self-heals this pattern within
   one cycle of whatever cadence Phase 1 runs on.
2. **Cadence still leaves a window; make detection event-triggered, not just periodic.** Even with
   #117 live, a scheduled Routine/Action only notices a closed-and-landed parent on its next tick.
   The tighter fix - folded into `routine-cutover`'s notes as a design requirement, not a new item,
   since it is a refinement of the Action that item already owns - is to also trigger the ancestry
   check from the `pull_request` `closed` webhook event itself: the moment any fork PR closes,
   ancestry-test its head branch immediately, and reparent every open PR based on it right then if
   it turns out to have landed elsewhere. That collapses the detection window from "up to one
   scheduled cycle" to "the same event that could cause the problem," which is what actually prevents
   the #40/#41 pattern from recurring rather than only shrinking how long it can go unnoticed.

Both of these are about *when* the already-correct detection logic runs, not about the logic itself
- #117 already answers "is this parent actually landed" correctly; what was missing is "make sure
that question gets asked, in production, as close to the landing event as possible."

## Update 2026-08-02 (traced): who closed PR #40, and why prevention means catching it, not stopping it

The user asked directly: who closed the parent PR without marking it, and if it was them, doesn't
that mean no automated script or routine can actually prevent this? Traced from PR #40's own GitHub
timeline and its successor rather than assumed:

- **The user closed PR #40 themselves**, 2026-07-09T08:49:56Z, with a comment on the PR: *"Replaced
  by #53. This branch's history was rebuilt (recreated, not force-pushed forward) after
  eql-core-prep/code-generation-extract advanced further upstream, so GitHub won't let this PR
  reopen. Same content — #53 cherry-picks this PR's single real commit onto the current
  code-generation-extract tip."* This is deliberate, correct maintenance - a branch got rebuilt
  after its own base advanced, the old PR couldn't reopen against the new history, so the user closed
  it and opened a clean successor. Not a bot, not the Routine, not a mistake.
- **PR #53** is that successor: same branch name (`ripple-down-rules-refactor`), rebuilt history,
  same one real commit cherry-picked onto the current `code-generation-extract` tip. The user merged
  it normally into `main` on 2026-07-25T09:56:27Z (`merged_by: AbdelrhmanBassiouny`) - this is the
  actual, ordinary merge event that put the branch's content in `main`.
- **PR #41** predates both: created 2026-07-07, based on the branch name `ripple-down-rules-refactor`
  directly, never on #40 or #53's PR number. It had no way to know which PR number was currently "of
  record" for that branch, because it never referenced one.

**The right conclusion, and the correction it forces on the prevention design above.** The user is
right that no automation should try to stop this - closing a superseded PR after a branch rebuild,
and later merging its replacement, are both normal and correct. Trying to prevent the *human action*
would be solving the wrong problem. What was missing is narrower and worse than first framed: it is
not specifically "closed without merging" (#40's case) - it is that **any pull request leaving the
open set drops out of `board.json`**, whether by an unmerged close (#40) or by a normal
merge-and-auto-close (#53). The old code's `by_name.get(branch.parent)` returns `None` either way,
and reads that `None` as "no parent" regardless of which route caused it. `landed-parent-detection`'s
ancestry check is correct against both, which is reassuring - it never depended on which of the two
happened.

It does mean the event-triggered design recorded on `routine-cutover` above was one event narrower
than it should be. `pull_request: closed` fires for a merge-close exactly as it does for a
supersede-close, so the fix is to re-sweep ancestry for **every** remaining open fork PR's base on
that one event type, not to special-case "check just this PR's own branch." Concretely in this
history: that sweep, triggered off #53's closed-via-merge event on 2026-07-25, would have caught
#41's orphaning that same day - instead of the ~6 days it actually took until a review round on #41
noticed the inflated diff by accident on 2026-07-31. `routine-cutover`'s notes are corrected to say
this plainly, rather than leaving the narrower framing on record.

## Update 2026-08-02 (probed): the base-change 403 is one credential, not the platform

`/plan-item-kickoff workflow-unification session-safe-pr-reparent`, session
https://claude.ai/code/session_01WvRrTrtiznzAyvaoeCdNSq, prompted by the user wanting the fix tried
on PR #41 the way `landed-parent-detection` had been.

The kickoff's step 0 was a cheap probe the previous session had no reason to run: the recorded 403
came from `curl` + `GH_TOKEN` through the session git proxy, and `mcp__github__update_pull_request`
takes a `base` parameter that nobody had tried. Run on a throwaway pull request (#129), against the
same pull request minutes apart:

| Client | Non-stacked PR | Stack member |
| --- | --- | --- |
| MCP `update_pull_request(base=…)` | **200, base changed** | `422 - Cannot change the base branch because the pull request is part of a stack` |
| raw `PATCH` + `GH_TOKEN` via the git proxy | **403 - not permitted for this session type** | — |

**The block is on that credential, not on the operation and not on sessions.** The reason nobody had
noticed is structural rather than accidental: the stacks endpoints have no MCP tool, so `ROUTINE.md`
tells the reader to use `curl` with `GH_TOKEN` — and a reader already in `curl` naturally issues the
base `PATCH` there too, straight into the 403. The doctrine's own advice routed people into the one
client that cannot do the job.

The full stack-member repair was then rehearsed end to end on a throwaway stack, before anything
touched #41: `POST /stacks/131/unstack` → 204, MCP base change → 200, `POST /stacks` → 201 (new
Stack #132, trunk moved). That is exactly the sequence `landed-parent-detection` already prescribes.
**It was right about the mechanics and wrong only about the client.**

### What this kills

`session-safe-pr-reparent` was created to replace every reparent with close-old-PR → create-new-PR,
accepting a new pull request number and a fresh review thread on each one because "the clean PATCH is
not available to a session at all". It is available. So:

- **No close+create fallback**, anywhere — no pull request has to lose its number, labels or review
  thread to be reparented.
- **No reparent-recovery script.** Worth recording that the script the item's notes said #106
  "already scopes" **was never written** — `git ls-tree` on both `claude/stack-tooling-on-main` and
  `claude/stack-landed-parent-detection` shows `.claude/stack/` holds only `README.md`, `ROUTINE.md`,
  `stack.py`, `stack.toml`, `tests/`. Decision 11 promised it and it did not get built; with the base
  change available there is nothing left for it to work around, and not adding new mechanics is
  decision 11's own direction (GitHub maintains the mechanics, we maintain policy).
- **The "third instance" framing is wrong and is corrected in the item notes.** Tag-push and
  branch-delete are genuinely blocked for a session because *no MCP tool exists for either*. A
  base change has one. The family is "operations with no session-reachable client", not "operations
  the platform forbids sessions" — which is a materially different thing to carry into
  `routine-cutover`, where the Action's own credential is the open question.

### What shipped — and why it ended up inside #117 rather than beside it

A `BASE CHANGES GO THROUGH THE GITHUB MCP SERVER` rule stated once in Phase 1 — recording the 403, naming its cause, and telling a
session that hits it that it used the wrong client rather than found a stuck reparent — with both
reparent sites deferring to it, step 3 of the native-stack sequence using the MCP tool and stating
that the child keeps its number, labels and review thread, and `README.md`'s source-of-truth row
naming the tool.

Four contract tests, written failing first. `ROUTINE.md` is prose and had **no test coverage at
all**, which is exactly how a doctrine drifts back to a blocked verb unnoticed; 251 tests pass in the
dev-tooling suite, was 247.

This was opened as draft PR **#133**, stacked on #117 — because a session's standing instruction is
to develop on its own designated branch and not push to another session's branch without explicit
permission. The user overrode that on sight of the result, with a standard worth recording as
general: **a pull request must be self-sufficient and correct on its own; never leave one open that
is known to contain a bug.** #133's only purpose was correcting a section #117 had *just
introduced*, so stacking it meant #117 would sit in review prescribing a step already known to 403,
with its fix visible only to someone who noticed a second PR behind it. A change whose sole purpose
is patching its parent's own new section is not independent work.

So the commit was fast-forwarded onto `claude/stack-landed-parent-detection` (a true
fast-forward, `a672c146..938e6415` — no rebase, no force-push, #117's three commits untouched).
GitHub then detected #133's head as contained in its own base and auto-closed it as **merged** —
merged into that branch, not into `main`, which is worth stating because the badge does not say so.
A comment on #133 records it.

Two consequences beyond the fold itself. #117's description was rewritten rather than left alone —
it described the old mechanism in two places, and a PR whose body explains a superseded design is
not self-sufficient either; it now carries the 403-vs-422 table directly. And #117 went back to
**draft**, per the standing always-re-draft-after-pushing rule. Note that open PR #123 proposes
exactly the opposite for this case — that a draft→ready flip the user made means accepted, with no
re-drafting — so whichever way #123 lands settles the question; until then the in-force rule applies.

**#106 deliberately needed no equivalent change.** The change touches text originating in both PRs,
but only #117's was actively wrong. #106 says "retarget its child's base to `main` on GitHub" and the
README row said "retargeting the PR base on GitHub" — vague, naming no client, and so not misleading
in the way `PATCH` is. Since #117 stacks on #106, `main` gets the corrected text whenever the chain
lands.

### PR #41, repaired

Then run for real against the case the whole thread started from, using the newly written sequence:
recorded Stack #128's composition → dissolved it (204) → changed #41's base to `main` via the MCP
tool → re-created the stack (201).

- #41: **268 files / +27,825 → 7 files / +1,318** — exactly the four `rdr/` modules and three test
  files its own description names. `mergeable_state: clean`. It kept its number, its four comments
  and its `cram2-link-sent` label.
- **Nothing was pushed to any branch.** Only the base moved, so no force-push, no restack, no CI
  churn on the six pull requests above it.
- Stack **#134** carries the same seven pull requests in the same order, now trunked on `main`
  instead of `ripple-down-rules-refactor`; #63–#98 kept their own bases. GitHub will not reuse a
  dissolved stack's number, so #112 → #128 → #134 is expected rather than a symptom.

The prevention story recorded on 2026-08-02 is untouched by all this: #117's ancestry check is still
what notices the orphan, and `routine-cutover`'s `pull_request: closed` sweep is still what makes it
notice promptly. What changed is only that the repair it triggers is now a base change a session can
actually perform.

**Residue.** The throwaway probe branches `claude/reparent-probe-{head,target,upper}-o1kpei` were
deleted by the user; their pull requests #129/#130 are closed and stacks #131/#132 dissolved.
`claude/workflow-unification-pr-test-o1kpei` became redundant once #133 was folded into #117 and
needs the same out-of-harness deletion, since sessions cannot delete branches (2026-07-29 addendum).

## Update 2026-08-02 (later): the Routine now reads its doctrine from git

The user asked the obvious question after the base-`PATCH` correction — *"can we point the routine
at the README we maintain instead of changing the prompt every time?"* — and then did it. The
~17.5k inline prompt at claude.ai/code/routines is replaced by the short pointer `routine-cutover`
had already specified: HARD RULES inline, plus "read `.claude/stack/ROUTINE.md` and execute the
fenced text block".

It resolves `origin/main` first, falling back to `origin/claude/stack-landed-parent-detection`
while that is in review, because **`.claude/stack/` is not on `main` yet** — only on #106 and #117.
Two consequences worth stating plainly: **#117's branch is live production input**, and an edit to
`ROUTINE.md` now ships to the running workflow on push, with no deploy step and no copy to sync.

The endgame is unchanged — a plain scheduled Action plus on-demand sessions, no scheduled LLM.
This is exactly the "optional interim step if the Action lags the tooling wave" already recorded.
What it buys immediately is that doctrine corrections stop needing a manual paste, which is the
precise failure that let the base-`PATCH` instruction survive in the live prompt for two days after
`ROUTINE.md` had been fixed.

### The ordering hazard it exposed

Adoption turned a dormant inaccuracy into a live bug within the hour. `ROUTINE.md`'s SETUP step 0
said:

> `.claude/stack/stack.py` and `stack.toml` are already on this checkout - they live on `main`, so
> there is nothing to pull from another branch first.

Written in anticipation of #106 landing, false today, and harmless only for as long as nothing
actually executed it. Under the pointer the Routine would resolve its doctrine successfully,
believe the tooling was present, and fail on the first `stack.py` call in **Phase 2 — after Phase 1
had already mutated pull requests**. Half-applied state on a real stack, from a document that was
correct-looking prose.

Fixed in #117: step 0 now *obtains* `.claude/stack/` from the same ref the pointer resolved instead
of asserting it is there. Verified end to end in a worktree at `origin/main` — `stack.py` absent
before, `stack.py --help` working after.

**The general lesson, which will recur:** a document that describes a not-yet-true future state is
safe exactly until something starts executing it, and the switch-on is not a good moment to
discover which sentences were aspirational. The same shape is queued for the stack-board Action
(PR 4), whose `board.yml` will read repo/branch/upstream variables that do not exist yet.

### Also fixed in the same commit

- The header claimed **"Not live yet"** and described pasting the file into claude.ai/code/routines;
  `README.md` said the same. Both now describe what happens: the Routine reads this file from git,
  an edit ships on push, and only the pointer is registered.
- **Three tests**, the step-0 one written failing first. The other two guard a contract that had
  none: the pointer locates what to execute *by the fenced block*, so exactly one fence must exist
  and the HARD RULES must stay inside it. That guard earned itself immediately — it caught a literal
  fence marker accidentally introduced into the new header prose during this very change, which
  would have made the Routine execute the wrong slice of the file. 254 tests pass, was 251.

**Two deletions fall due when #106 lands** and `.claude/stack/` reaches `main`: the pointer's
source-2 line (manual paste) and step 0's fetch fallback (an ordinary commit). Neither breaks
anything if forgotten — the fetch becomes a no-op, the fallback ref stops resolving — but both are
dead weight, and the pointer edit is the last manual paste this design should ever need.

## Update 2026-08-02: `/add-plan-item` — the scope decision gets a skill, and the rule gets one home

The plan skills covered creating a plan, starting an item, unblocking one, and
publishing status. They did not cover the event that happens most often: someone
describes something to build and it has to be decided where it goes. Left to
default, that decision reliably produced a new branch — which is how this plan
accumulated its own fold chain (#133 into #117, #117 into #106) and the #110/#106
collision, where two sessions independently built the same artifact under two
different filenames without either noticing.

### The rule was triplicated, which is the failure mode it warns about

A mechanical test for this had just been written onto
`claude/plan-scope-before-new-item` — an unlanded, pull-request-less branch, two
commits, a clean fast-forward from main. It added the rule three times, as three
independently-worded copies, to `plan-create`, `plan-item-kickoff` and
`plan-item-resolve`, with no shared anchor for a fourth caller to reference.

It now lives once, in `add-plan-item/scope-decision.md`, with all four skills
referencing it in a line and keeping only their own situational framing (when the
question is asked, and what to do with the answer). This follows
`setup-personal-notes/prerequisite-check.md`, which established the pattern for
exactly this: a shared procedure stated once so each caller cites rather than
restates it. The three copies' distinct content was merged rather than dropped —
`plan-item-resolve`'s duplicate-copies clause (decide which survives *before*
either lands, since afterwards it is a merge conflict instead of a choice) is now
part of the shared document.

### The rule applied to its own introduction

`claude/plan-scope-before-new-item` had no pull request and existed only to
introduce prose this work rewrites. By the rule's own test, nothing substantial
would have remained of it once the rewrite landed, so it is not separate work:
this branch was reset onto it and carries both commits. Stacking instead would
have put a pull request into review shipping the triplicated wording its
successor deletes. That branch is retired.

### Why it ships a script and not only prose

The path check is the step most often skipped, and skipping it is what the fold
chain and the collision have in common. `check_scope_overlap.py` runs it: given a
base branch and the paths the work would touch, it reports which paths the base
lacks and which unlanded branches already touch them. It also returns each
candidate branch's full changed-file list, because the #110/#106 case shares no
path at all — the same artifact under two names is invisible to a path
intersection, and only a purpose comparison finds it. The script gathers the
evidence; the fold-or-split judgement stays with the reader.

Pure git, so no network access or GitHub call: the tests build a real scratch
repository with a base and two candidate branches, reusing the hooks suite's
`ScratchRepository` rather than adding a second helper of the same shape. Eight
tests, wired into `ci.yml`'s `test_claude_dev_tooling` job through a new
`ADD_PLAN_ITEM_TESTS_DIRECTORY` constant. 230 pass, was 222.

One deliberate limit: a branch that does not resolve raises rather than returning
an empty overlap. A missing candidate must never read as "no overlap" — that is
the precise failure this whole item exists to prevent.

## Update 2026-08-02 (assessed): the #106/#110 overlap is three duplications, and the split is right

`/add-plan-item` above was written partly because of the #110/#106 collision. That
collision was then actually investigated, and it is larger than the one file it was
reported as — while the structural question it raised has the opposite answer to the
one the fold chain would suggest.

### The split is correct; do not fold

Remove #110's edits to its parent's files and ~2,645 lines of standalone setup
infrastructure remain — `setup-stacked-prs.sh`, `check-stack-setup.sh`,
`write-branch-files.sh`, two skills and their tests. That is ordinary stacking. #133
and #117 folded because *nothing* remained once the parent edits were taken out; #110
fails that test by a wide margin, so folding it would be over-applying the precedent,
not following it.

### Why it happened: a fork point, not a disagreement

#110 branched from #106 at `eb3ca5a1` on 2026-07-31. `POINTER.md`, `prompt_model.py`
and `test_prompt_documents.py` all entered #106 on 2026-08-02, in `2868eab9` and
`93dcbef9` — after that fork point. `POINTER.md` does not exist on #110's head at all.
Neither session chose a different design over a visible one; both built the same
artifact against divergent snapshots of an unlanded parent. That is the actual
mechanism, and it says the mitigation is prompt rebasing of children onto a moving
parent, not more folding.

### Three artifacts were built twice, not one

Merging #110 into #106's current head conflicts in **all five** `.claude/stack/` files
it touches. The reported collision was one of three:

1. **The pointer prompt** — `POINTER.md` (#106) and `routine-prompt.md` (#110).
2. **The pre-board configuration query** — #106's `BOARDLESS_COMMANDS` / `print_remotes`
   / `stack.py remotes` against #110's `BOARD_FREE_COMMANDS` / `print_config` /
   `stack.py config`. Same purpose, near-identical docstrings ("must run before
   `board.json` exists"), two names. This one was never flagged, and it cost more than
   the prompt file did: #110's shell scripts parse the output, and the two disagreed on
   both key names and key set.
3. **`ROUTINE.md` SETUP step 0** — rewritten independently by both.

Item 2 is the interesting one, because a path comparison *did* flag `stack.py` — both
branches modify it. What dismissed it was the boundary answer ("2,645 lines remain, so
#110 is real"), applied to a question it does not answer. Two pull requests can be
correctly split and still both build the same thing. The scope rule decides *where work
goes*; it does not certify that the overlap between two correctly-split branches is
benign, and `check_scope_overlap.py`'s full changed-file list is only useful if someone
reads it for duplicated *purpose* after the split question is settled.

### The argument for keeping `POINTER.md` had to be replaced, not just accepted

The reason previously given was that `routine-prompt.md` claims `.claude/stack/` is
already on `main`, which is false today. True — but it expires: #110 lands after #106,
at which point the claim holds and `POINTER.md`'s fallback is the stale half, as that
file itself says (`Delete this fallback once .claude/stack/ is on main`). Anyone
re-deriving the decision from that reason after #106 merges will reverse it.

The durable reason is the test harness: `test_pointer_hard_rules_match_the_routine_document_exactly`
pins `POINTER.md`'s rules byte-for-byte against `ROUTINE.md`'s, and `PointerPlaceholder`
declares its fork-specific values as an enum enforced in both directions.
`routine-prompt.md` paraphrases the same rules with nothing checking them. Two copies
that look equivalent, one of which is enforced, is exactly the drift `ROUTINE.md` exists
to prevent.

### Verified rather than argued

Splicing #110's SETUP step 0 into #106's `ROUTINE.md` fails two of #106's fourteen
contract tests — `test_setup_obtains_the_tooling_rather_than_assuming_it` (the step no
longer *obtains* `stack.py`, it assumes it) and
`test_setup_takes_the_tooling_ref_from_the_pointer` (it stops mentioning the pointer). A
third, `test_setup_asks_the_tool_which_remote_is_which`, passes only by accident: it
substring-matches `remotes`, a word that survives in #110's prose after the command it
names is gone.

### What shipped, and where the rest goes

Only #106 changed. `stack.py remotes` became `configuration`, printing one
`field<TAB>value` line per `Configuration` field — keys are the field names, every
setting is reachable, and `upstream_setup_command` moved onto `Configuration`, omitted
rather than printed blank when the remote exists. This is a change *to* #106 rather than
work stacked on it, which is the same test applied in the other direction: it exists
only to alter what #106 introduces, so it belongs in #106.

Naming it here rather than reconciling later means #110's rebase deletes the resolution
internals only — no dispatch-table conflict, and its two scripts change `stack.py config`
to `stack.py configuration` and are done. One deliberate divergence from the "converge on
`config`" recommendation: every other subcommand is a full word and AGENTS.md bars
abbreviations, so the command is `configuration`. The key names, which are the part
parsed by `awk`, match exactly.

The open `stack.toml:23` thread asks whether to strip the remote inference from #106 now.
Recommended answer: no. #106 lands first and the live Routine switches to `main`'s copy
the moment it merges, so a fresh cloud clone that needs a hand-edited file before it can
run is worse than one that infers. Keep it; delete it in #110 alongside the interactive
setup that makes it unnecessary.

### A premise that turned out to be wrong

Decision 11's cut is recorded here and on #106 as done. It is half done: `ROUTINE.md` was
rewritten around native mechanics, but `stack.py` still ships `print_next` and
`print_restack_plan`, and the latter's docstring still points at "the `restack` workflow's
`args`" — the subsystem the cut removes. Either it is outstanding or it was dropped
without a record. It matters for sequencing: applying it later rewrites `stack.py` again
and makes #110's rebase resolve the same conflict twice.

## Update 2026-08-02 (re-scoped): the routine's doctrine becomes a skill, and its recipes become subcommands

Session: https://claude.ai/code/session_01BByQFT6he8xf5qvBWtyUPV, via `/plan-item-resolve`. Two
user decisions, both taken after the options were costed rather than assumed.

### The doctrine is a skill now, and it folds into #106

`ROUTINE.md` is deleted. `.claude/skills/stacked-pr-maintenance/SKILL.md` carries the same
doctrine, is invocable as `/stacked-pr-maintenance` from any session, and is what `POINTER.md`'s
registered block resolves and runs for a scheduled one. The fork and upstream come from the
skill's own arguments first, then `stack.py configuration`, then - interactively only - a
question whose answer is written to `.claude/personal/stack.toml` on the personal-notes branch.
`--non-interactive` turns that question into a stop.

**Where it landed was the first decision.** `git ls-tree origin/main -- .claude/stack` is empty:
every path this touches is introduced by #106 itself. By `add-plan-item/scope-decision.md`'s test,
removing these edits leaves nothing standing alone, so it is #106's work and went onto
`claude/stack-tooling-on-main` directly (commit `e20b0bb4`), not onto this session's designated
branch. The second reason is sharper than the scope rule: the registered pointer resolves
`origin/main` **first**, so landing a `ROUTINE.md` that its own successor deletes would change the
live doctrine twice within one review cycle.

### Recipes as subcommands, not prose and not an MCP server

The second decision was how far to take "computed rather than recalled". Four new `stack.py`
subcommands, each replacing a rule the reader previously had to remember:

- **`labels`** - the complete set a label write must send, computed from the labels the pull
  request carries now. This is the one with a production incident behind it: the write replaces
  the whole set, and computing it from the addition alone once stripped `in-review` off
  already-promoted branches.
- **`preflight`** - refuses the move rather than describing how to check one: wrong branch checked
  out, a refspec naming different branches on each side, a destination that is not the fork, and a
  push that would make a child an ancestor of its own parent. Its own exit status (`5`).
- **`promotion-link`** - owns the compare URL's encoding and length limit, both of which discard
  the prefill *silently* when got wrong.
- **`reparents` / `landed`** - phase 1 derived from git ancestry rather than pull-request state.

**An MCP server was considered and rejected, on evidence rather than taste.** `gh` is absent in
this environment and `GH_TOKEN` is proxy-injected, and the 2026-08-02 probe already recorded here
shows a raw base-`PATCH` through that credential returns 403 while the GitHub MCP's
`update_pull_request` returns 200. A local MCP server would therefore use the credential that
*cannot* perform the riskiest operation in the whole workflow - so it would leave the base change
in prose anyway, while adding `.mcp.json`, a server process and per-session schema loading. It is
also the format that does not survive `routine-cutover`, whose endgame is a plain scheduled Action
with no LLM at all; subcommands run identically in a session, in the Routine, and in that Action.

The operating shape this settles on, worth stating generally: **compute deterministically, write
through MCP.** The credential boundary decides which half is which, and that boundary is a
property of the environment, not of the design.

### Decision 11's cut is deliberately left half-applied

The premise recorded in the previous entry - that `print_next` and `print_restack_plan` are
outstanding work from decision 11 - was put to the user and reversed. They stay. Phases 2 and 3
call them, and they are the derivation half of the scripts-over-prose choice made the same day;
cutting them would push those phases back into the prose this work is removing.
`print_restack_plan`'s docstring no longer names "the restack workflow's `args`", which is the
part of the complaint that was real.

### What the contract tests can now catch

`test_prompt_documents.py` goes from 14 tests to 19. The five new ones assert things the previous
shape had no way to state: that resolution prefers what it was told over what it can infer, that
it names the exit status meaning the fork is unknown, that a run which cannot ask stops rather
than guessing, that the pointer hands over both repositories with `--non-interactive`, and that
the skill states the whole job rather than delegating to harness machinery - which is what lets
the pointer keep reading the file while the skill is not yet on `main`.

Each was checked by breaking the document three ways and confirming exactly one test failed each
time. The hard-rules equality test earned itself again: the two copies were written independently
in this session and it passed first time, which is the only evidence that the duplication is
actually being held equal rather than coincidentally similar.

**A constraint found while writing it, worth carrying:** a skill that is not on the checked-out
branch at session start cannot be invoked by name. `.claude/skills/` is on `main` but
`.claude/stack/` is not, so until #106 lands the pointer must still say "read this file from
`<ref>` and execute it". That is why the skill has to read as a *document*, not only as a harness
entry point - and it is the same not-yet-true-future-state hazard the 2026-08-02 pointer-adoption
entry named, met a second time.

### Review threads: one answered, one left open on purpose

`stack.toml:23` asked for exactly this - *"running the configuration script or skill
interactively, and it takes the fork link or name"*. The skill answers its interactive half. The
~120-line inference deletion is still #110's, because the remaining caller is a non-interactive
run with no arguments on a checkout nobody has configured, and only setup writing
`fork_repository` at install time removes that one. Replied and left open rather than resolved;
`stack.py:84` dies with the same deletion. #110 was told its rebase now inherits a skill, that its
SETUP step 0 rewrite is superseded, and that the two contract tests it was told to update are
updated upstream of it.

## Update 2026-08-02 (review round): GitHub already closes what the pass was closing by hand

Twenty-five review comments on the skill, in `8b7435bb`. Three were decisions rather than
corrections, and each is worth recording with the evidence that settled it.

### The fast-forward is the close

The reviewer asked three versions of the same question - *"if fork main is fast forwarded with
upstream main, then github auto closes pull requests that are ancestors of main"*, *"isn't merging
better than closing?"*, *"could this actually happen anyway?"* - and the answer was in this
repository's own history:

| PR | `merged_at` | labels |
| --- | --- | --- |
| #101 | `2026-07-31T10:36:43Z` | `in-review`, **`merged`** |
| #103 | `2026-07-31T10:36:43Z` | `bug`, `in-review` |
| #105 | `2026-07-31T10:36:43Z` | `bug`, `in-review` |

All three at the same second - the moment fork `main` fast-forwarded from cram2 - and only #101
carries the hand-applied label. GitHub records all three as **merged**, not merely closed. So
phase 1's label-then-close was doing by hand what step 2 already did in one push.

Deleted: the close call, the `merged` label from the workflow entirely, and `landed` as a to-do
list (it survives as a report). **The ordering changed with it**: auto-detection fires only for a
pull request whose *own* base moved, so a stacked child based on a sibling branch is not caught by
fast-forwarding the trunk. The reparent sweep therefore has to run *before* the fast-forward, which
inverts the order the document had carried since it was a routine prompt.

The general shape, worth reusing: **before writing a step that maintains state, check whether the
platform already maintains it.** This one had survived two rewrites unexamined.

### The pass never writes code, which is what made it generic

*"Didn't we say it should never code, why debug and fix?"* — and the document did contradict
itself: it said code changes are the developer's session's work, then gave a procedure for
reproducing, fixing and locally validating a failure.

Removing that branch removed every repository-specific name with it — `krrood`, `ormatic_interface.py`,
`semantic_digital_twin`, `coraplex`, `experiments`, ROS, `AGENTS.md`. The reviewer predicted exactly
this (*"that will also remove all ormatic, krrood, ros, coraplex, semdt mentions completely and will
make the skill more generic"*), and it is the cleanest illustration in this plan of a portability
problem that was really a scope problem: the file was repo-specific *because* it was doing work it
should not have been doing.

The one file change that survives is resolving a conflict during a restack, which is unavoidable if
it restacks at all — and it now has to be reported in a comment naming the files, since it is a
change to somebody else's branch that they did not make.

### The pointer is gone, and most of the prose tests with it

*"I don't want anything in the pointer at all, the pointer is useless now, it's just a skill call."*
`POINTER.md`, `prompt_model.py` and `test_prompt_documents.py` are all deleted.

The reviewer separately asked to discuss whether the prose tests were worth keeping (*"this is
fragile and easy to break"*), and the two questions answer each other: those tests existed to hold
the pointer's duplicated copy of the HARD RULES equal to the routine document's. With one copy, the
duplication they guarded does not exist. Eighteen deleted.

**One survives, and the distinction is the useful part.** `test_the_skill_names_no_fork_of_its_own`
asserts an *absence*, computed from `load_configuration()` rather than from a string written in the
test. It cannot fail from rewording, only from the fault it exists to catch — shipping one
contributor's repository name in a document that is executed verbatim on somebody else's fork. That
is the line worth drawing for any future test over prose: assert what the document must not contain,
computed from live state; do not assert what it says.

**A consequence that reverses design decision 4**, flagged to the user rather than buried: the HARD
RULES no longer bind before the first file is read. They were inline in the pointer precisely because
a webhook event can arrive before the first tool call. The window is now one turn — between the run
starting and it reading the skill — which is an accepted trade against deleting a file plus its
enforcement machinery, and `routine-cutover` deletes the scheduled run entirely anyway.

### Smaller, but the same principle each time

`Command` is a `StrEnum` with a `needs_a_board` property, which answered both *"make these commands
maybe a StrEnum?"* and *"why not a tuple?"* — the second question was about a `frozenset` of boardless
commands kept beside the enum, and the right answer was that the fact belongs to the command rather
than to a set beside it, so the set is gone.

A pre-flight refusal now carries a `RefusalReason` alongside its sentence, so the tests assert
`[RefusalReason.MISMATCHED_REFSPEC]` instead of a hardcoded English string — which was the reviewer's
*"can this string be fetched from where it is defined?"*, answered by deleting the need for the string
rather than by importing it. Label tests read their labels from the `Configuration` that defines them,
since labels are per-user configuration and never an enum.

### Left open deliberately

*"This file is so big"* — `stack.py` is ~1,540 lines and this PR added ~400 of them. Not split here,
and put back to the user with the reasoning: `dev-tooling-python-package` already moves every
`.claude/` Python file into a package, so splitting now means the same surgery twice, with #110 and
#111 rebasing across it in between.

## Update 2026-08-02 (corrected): #110's rebase instructions, and the split settled

Two loose ends from the review round, both closed by the user in the same turn.

### `stack.py` is not split in #106

The reviewer's *"this file is so big"* was left open with a recommendation rather than an answer.
The answer is no split here: `dev-tooling-python-package` already moves every `.claude/` Python
file into the package, so splitting now means the same surgery twice, with #110 and #111 rebasing
across the first attempt in between. The thread stays answered rather than resolved, since the
concern is real and its resolution is somebody else's item.

### #110's rebase instructions were mostly invalidated, and saying so is the whole point

`setup-stacked-prs-skill`'s notes carried a detailed list of what its rebase onto #106 "must carry",
written on 2026-08-02 against #106 as it then stood. The review round deleted the artifacts three of
those five points were about — `ROUTINE.md`, `POINTER.md`, `prompt_model.py` and
`test_prompt_documents.py` are all gone — so following the list would have produced work with no
target. Rewritten in place rather than annotated, because a stale instruction that is still readable
as an instruction is worse than no instruction.

What actually changed for #110, verified against its head rather than inferred:

- Its `.claude/stack/routine-prompt.md` is now a duplicate of a file that already exists at
  `.claude/skills/stacked-pr-maintenance/routine-prompt.md`, already templating
  `<FORK_REPOSITORY>`/`<UPSTREAM_REPOSITORY>`. The previous instruction — *render `POINTER.md`
  instead* — has no referent; the instruction is simply to delete its copy.
- **A real breakage nobody had spotted**: `check-stack-setup.sh:62` reports
  `stack_tooling_files ok "stack.py, stack.toml, README.md, ROUTINE.md and routine-prompt.md are all
  present"`. Two of those five files no longer exist anywhere, so that check fails outright on the
  rebased branch. This is the only point on the list that is a defect rather than a no-op, and it was
  found by reading #110's script rather than by reasoning about the deletions.
- The two rules #110 wanted promoted into the pointer (never force-push a branch with an open
  upstream pull request unless it carries the `rebase` label; do not use the Workflow tool) are
  already in the skill, so there is nothing to promote.
- Two new points the deletion creates: the fork-overlay install mode has to carry
  `.claude/skills/stacked-pr-maintenance/` as well as `.claude/stack/`, now that the instructions
  live outside the latter; and setup writing `fork_repository` at install time is the same thing the
  skill's step 0 does interactively, so setup does it once and the skill's question is the fallback —
  not a second asker.

`stack.py config` → `configuration` is the one point that survives unchanged, key names included.

**The general shape, worth keeping.** A child branch's rebase instructions are written against a
snapshot of its parent, and a parent's review round is exactly the event that invalidates them.
Nothing notices this on its own: #110's session is not subscribed to #106's review threads, and the
manifest entry that carried the instructions reads as current no matter how old it is. The parent's
own session correcting them in the same turn as the review round — and commenting on the child's
pull request so its owner receives it as an event — is the only mechanism this workflow has. It is
the same fork-point failure as the #110/#106 duplication recorded on 2026-08-02, met from the other
side: there, two sessions built the same artifact against divergent snapshots; here, one session's
plan for the future was written against a snapshot that then moved.

## Update 2026-08-03 (resolved): #109's conflict was the same-artifact-twice pattern, a third time

`/plan-item-resolve workflow-unification personal-settings-sync`, session
https://claude.ai/code/session_01XkWmfMzYYAaCsgyrHDuoKn. The item had been `in_progress` and
untouched since 2026-07-31 with a manifest entry that said *"PR #109 open and ready"* and recorded
no `blockers` at all. Two real ones existed, and neither was in the manifest.

### The manifest was the least accurate source, which is the process finding

Everything needed to diagnose this was on the pull request the whole time — `mergeable_state:
dirty`, a `needs-resolution` label, a routine comment naming the three conflicting files, and three
unresolved review threads. The item's `notes` instead described a CI red that had since gone green
and asserted readiness. This is the failure mode the keep-plan-state-current rule exists to prevent,
seen from the far end: a stale entry does not read as stale, so the next session either trusts it or
re-derives everything. The entry now carries a `blockers` field for the first time.

### The conflict: `ScratchRepository` and `ScratchProject` are the same artifact

`main` extracted the hook-test scratch repository into `tests/scratch_repository.py` as
`ScratchRepository` during #101's review round. #109, branched before that landed, independently
extracted the same fixture out of `test_save_plan_sh.py` into `conftest.py` as `ScratchProject`.
Same purpose, two names, two branches — so `conftest.py` and `test_save_plan_sh.py` conflicted on
content that was never a disagreement.

This is the **third** instance of the pattern this roadmap has now recorded, after `POINTER.md` /
`routine-prompt.md` and `BOARDLESS_COMMANDS` / `BOARD_FREE_COMMANDS` between #106 and #110. All
three share a mechanism: a child branched from a snapshot of an unlanded parent, the parent moved,
and both sides built the same thing. `check_scope_overlap.py` flags the path in each case; only
reading for duplicated *purpose* explains it. Worth stating as a standing expectation rather than a
recurring surprise — **any long-lived branch off an unlanded or fast-moving base should be re-read
for duplicated purpose before its merge is attempted**, not only for conflicting lines.

Resolved by adopting `main`'s, on evidence rather than seniority: `ScratchRepository` is a strict
superset (`install_hook_scripts`, `write`, `commit_everything`, `publish_notes_branch`,
`clone_notes_branch`, `resolve_notes_remote_to`) and already had a second consumer in
`test_check_setup_sh.py`. `ScratchProject` is deleted; both conflicted test files are now
byte-identical to `main` and have left #109's diff entirely. The one capability `ScratchProject`
had that `ScratchRepository` lacked — editing the notes branch *after* publication — moved onto the
class that owns notes-branch operations, as `update_notes_branch_file`.

The overlap this item's own notes had warned about (#107's constants in
`resolve-personal-notes-config.sh`, #110's `write-personal-notes-file.sh` delegation) **auto-merged
clean**. The warning was aimed at the wrong files: it was written from the paths the item touches,
while the actual collision was in a test fixture nobody had listed as shared.

### A latent test bug the port fixed for free

`ScratchProject.run_hook` passed no `env=`, so it inherited the shell's `CLAUDE_PERSONAL_NOTES_*`
variables — exactly what `main`'s `run_check_setup` strips, and for exactly this reason. It passed
only because the fixture's local `git config` outranks the remote variable and the branch variable
happened to equal the default; a clone with `CLAUDE_PERSONAL_NOTES_PATH` set would have broken it.
Porting onto `main`'s pattern adopted the scrub. Inheriting a shared fixture buys the fixes made to
it since, which is an argument for converging on one that the line-count comparison does not show.

### The pending-review trap, worth knowing before it costs someone a turn

The three review threads could not be replied to inline: they belong to a review that was **never
submitted** (`PENDING`, on `55cd2f9`). GitHub allows one pending review per user per pull request,
so every reply attempt returns `422 - user_id can only have one pending review per pull request`.
Submitting someone else's draft review is not a session's call — it publishes comments they may
still be drafting — so the resolution was explained in one PR-level comment naming each thread, and
the threads were then resolved. Anything that looks like a stuck reply on this repository should
check for a pending review before assuming a permissions problem.

### The README section had to be re-authored, not merged

#109 added 53 lines to a `README.md` that #101 then rewrote from 378 lines to ~140 as a step-based
guide. A textual merge would have spliced two documents with different shapes. Rewritten against
the new structure at 30 lines, per that rewrite's own stated length discipline. Worth generalizing:
a documentation conflict against a restructured file is a rewrite, and resolving it hunk-by-hunk
produces a document that reads as two.

**State**: #109 is a draft again (standing re-draft-after-push rule), labelled `cram2-link-sent`
only, `mergeable_state: unstable` (mergeable; CI running) against `main` at `9b090fc1`. 36 tests
pass under `.claude/hooks/tests` — `main`'s 28 plus this module's 8, none lost — and 194 under
`.claude/skills/plan-dashboard/tests`. This unblocks part of decision 12's chain, which cannot land
before the in-flight bash-touching pull requests, #109 among them.

## Update 2026-08-03 (rebased + re-scoped): #110 lands its parent's review round, and the fork stops being a guess

`/plan-item-resolve workflow-unification setup-stacked-prs-skill`, session
https://claude.ai/code/session_01QurCwih1r6STYtP34bpJpf. The item had been `in_progress` and
untouched since 2026-07-30, `mergeable_state: dirty`, labelled `needs-resolution`, with **zero
review threads** - nothing was blocking it on review. Its parent had moved twice underneath it.

### The instruction that was half-wrong, and the check that settled it

The ask was to rebase #110 "on 106". Taken literally that breaks the branch:
`setup-stacked-prs.sh:44` sources `github-api.sh`, which lives only on #107 - decision 10's whole
reason for the linear chain. #107 was already restacked onto #106's head (`5e203be8`), and
`git merge-tree --write-tree` returns the **identical** five-file conflict set against either
branch. So merging #107 delivers 100% of #106 at zero extra cost, and the base stays where it is.

Worth keeping as a general check: when an instruction names a base, run `merge-tree` against both
candidates before retargeting. Here it turned a base change that would have duplicated
`github-api.sh` - a fourth same-artifact-twice instance - into a plain merge.

### The one real defect on the rebase list

The 2026-08-02 corrected list said point 2 was the only defect rather than a no-op, and that held
up. `check-stack-setup.sh:51-55` required `STACK_ROUTINE_DOCUMENT` and `STACK_ROUTINE_PROMPT_FILE`
and `:62` reported them present *by name*; both pointed at files #106's review round deleted, so
the checker reported `needs-setup` on a correctly installed checkout. Repointing both constants at
`.claude/skills/stacked-pr-maintenance/` also fixed the fork-overlay install for free -
`OVERLAY_FILES` already listed them, so an overlay was about to ship tooling with no instructions
to run it. Nobody had noticed the second consequence, and it follows from the first by construction.

**A second defect nobody had recorded**, found while implementing point 7: `write_personal_config`
wrote `overrides` as the *whole* file body. Now that #106's skill step 0 also writes
`fork_repository` to that same file, whichever ran second silently erased the other's key. The
write merges now. This is the shape the 2026-08-02 entry predicted in general terms - two writers
converging on one artifact - showing up in the file rather than in a filename.

### The inference deletion, and what it changed beyond line count

The ~120 lines came out as promised, closing #106's `stack.toml:23` and `stack.py:84` threads
(replied to and resolved). Two consequences the promise did not anticipate:

- **`RemoteResolution` had to become symmetric.** With the fork named, a *missing fork remote* is
  no longer an error - it is a `git remote add` command, exactly as a missing upstream already was.
  Without that, setup could not run before the remotes it adds exist.
- **`load_configuration()` now fails on a fresh clone until setup runs.** That is the intended
  trade recorded on 2026-08-02 ("keep it; delete it in #110 alongside the interactive setup that
  makes it unnecessary"), but it had a consumer nobody had counted: `test_the_skill_names_no_fork_of_its_own`,
  #106's one surviving prose test, resolved its fork *through the inference* - which is the only
  reason it worked on CI. It now computes candidate forks from the checkout's own remotes, minus
  the upstream, and asserts the document names none of them. That is stricter than before, not
  weaker: it checks every repository the checkout could be operating on rather than the single one
  configured.

**A test-fixture consequence worth generalising.** Both scratch suites addressed their bare
repositories by bare local path. Remotes are matched by the repository their URL names, and a local
path deliberately names none - the same rule `github-api.sh` applies so a directory name is never
attributed to a GitHub account. The fixtures now create bare repositories at paths ending
`<owner>/<name>.git` and address them as `file://` URLs, which satisfies both the parser and git
transport. `insteadOf` was tried first and rejected: `git remote get-url` applies the rewrite, so
it defeats the very lookup under test.

408 tests pass across the three directories CI runs, up from 334 on this branch before the rebase.

### New item: `stack-maintenance-executor`

The user's second question - *could we automate the stacking process by a deterministic script that
fetches the relevant PRs, performs the git commands needed, and reports everything* - lands on a
real gap, verified rather than assumed: `grep -n "git push" .claude/stack/stack.py` returns nothing
across 1,600 lines. `stack.py` is read-only derivation; every fetch, merge, rebase and push is a
session following prose, and `board.json` is hand-assembled from MCP output - the same
hand-assembled-input class as #119.

Four commands (`board --write`, `fast-forward`, `restack`, `run-report --json`) in a new module, so
the only edits to #106's files are the `SKILL.md` steps and the dispatch wiring. Step 0 is a
credential probe: the recorded 403 names the *base branch* specifically, so label writes, issue
comments and body-only PATCHes through `GH_TOKEN` are unknown, and that answer also decides what
`routine-cutover`'s Action can do without a session.

Scoped as its own item rather than folded into #106 (user's call, offered against folding): the
executor is new files that stand alone, #106 is already 3,413 additions across 29 commits and out
of draft after its 25-comment review round, and this is a direct enabler of `routine-cutover`'s
no-LLM endgame. It does **not** reverse decision 11 - that cut structure *derivation* in favour of
GitHub's stack object; this executes an already-derived plan. Recording that distinction here so
nobody re-litigates it from the decision-11 entry alone.

## Update 2026-08-04 (kickoff + implementation): the executor ships as #139, and the 403 turns out to be one field

`/plan-item-kickoff workflow-unification stack-maintenance-executor`, session
https://claude.ai/code/session_014E9nB1MUvm4jwgC2UTN5GT, which went on to implement it the same
session as draft pull request **#139** on `claude/plan-item-kickoff-workflow-koufa6`, based on
#106's head.

### The probe inverted the assumption it was written to test

The item's step 0 existed because three writes were unknown, and the working assumption behind
"staying with a session/MCP regardless" was that some of them would be blocked like the base
`PATCH`. On throwaway pull request #138, four calls minutes apart, same `GH_TOKEN`, same git proxy:

| Call | Status |
| --- | --- |
| `PUT /repos/{o}/{r}/issues/{n}/labels` | **200** |
| `POST /repos/{o}/{r}/issues/{n}/comments` | **201** |
| body-only `PATCH /repos/{o}/{r}/pulls/{n}` | **200** |
| base-branch `PATCH /repos/{o}/{r}/pulls/{n}` (control, same pull request) | **403** |

The control is what makes this conclusive rather than suggestive: the same credential, against the
same pull request, succeeds at three writes and is refused exactly one. **The block is on the
`base` field, not on writes, not on the credential, and not on sessions.** The 2026-08-02 entry
already narrowed it from "the platform forbids sessions" to "one credential"; this narrows it
again, to one field of one endpoint.

What follows: `needs-resolution` labelling and the conflict-report comment - the two writes
`SKILL.md` step 4 hands to a session - are both available to deterministic code, and so is writing
the promotion link into a description. None of that was taken in #139, because the four commands
were what was agreed and widening scope on the strength of a fresh probe is how a pull request
stops being reviewable. It is a named follow-up now, resting on a measurement rather than on a
fear. `routine-cutover`'s Action inherits the same table for its own credential, which is the
question that item has been carrying open since 2026-08-02.

### Zero edits to `stack.py`, which was a choice and not an accident

The item said the executor's footprint on #106 would be "the SKILL.md steps and the dispatch
wiring", and that reads two ways: a separate entry point, or four new `stack.py` subcommands. Put
to the user at kickoff, who chose the separate `.claude/stack/maintenance.py`. Three things fall
out of it that the subcommand reading would not have given: `stack.py` keeps the read-only
contract its own module docstring claims, the ~1,540-line file a reviewer already called too big
does not grow, and this branch has no textual overlap at all with #110's ~120-line deletion in
that same file.

`GitCommandRunner` is the one genuinely new thing. `stack.py` reads git through a helper returning
`""` on failure - correct for derivation, where a missing ref simply means "no answer", and wrong
the moment a push is involved, where it makes a command that did nothing indistinguishable from one
that worked.

**Forcing is decided in exactly one place**, `push_arguments`, and only for the rebase strategy,
which `build_stack` sets only from the `rebase` label. That is what makes the label rather than the
executor's judgement the thing authorising a rewrite of published history - and it is pinned by a
test on the arguments themselves, because a test that a push happened cannot tell a fast-forward
from an overwrite.

### A test that corrected its own premise

The first version of that guarantee was written as an integration test: let somebody else push to
the branch, then assert the restack is rejected. It failed, and the reason was worth keeping. The
executor starts each integration from the branch's **published** tip, so a branch that moved under
the pass is *incorporated*, not raced - a stronger property than the one being tested. The test now
pins that, and the forcing decision is pinned separately and purely.

### The regression the change introduces, found before it shipped

`board --write` makes a local `board.json` routine where it had been rare. Two tests - one of them
pre-existing in `test_stack.py` - assert on a *missing* board while reading the real `board.json`
beside `stack.py` rather than one in their scratch repository. So running a maintenance pass and
then the suite failed two tests for a reason unrelated to either. Proven by writing a board and
watching them fail, then fixed with an autouse fixture in `.claude/stack/tests/conftest.py` that
sets an existing snapshot aside and restores it afterwards.

Worth generalising: a test that reads a path beside the module under test rather than inside its
own fixture is coupled to whatever the developer's checkout happens to be carrying, and that
coupling is invisible until some new command starts writing there. The fixture is the fix; noticing
required actually running the command in this checkout rather than only in the harness.

`.gitignore` gains `.claude/stack/board.json`. #110 adds the identical line, which is a deliberate
duplication named in both pull requests rather than a fourth instance of the same-artifact-twice
pattern - whoever lands second drops one copy.

### What was not verified live, and why that is stated rather than glossed

`board --write` ran against the real fork: 44 open pull requests, and the export parses straight
back through `stack.py status`. `fast-forward` ran as far as its guard, exiting 6 on the missing
`cram2` remote before attempting any push. `restack` and `run-report` were **not** run live - they
push to real branches, and the upstream remote is outside a session's repo scope - so their
coverage is real git in the test harness, not the live fork. 342 tests pass, was 321.

### Scope widened the same day: the probe's answer was acted on

The user's response to the probe table was *"do it as well and anything you found doable in code
related to this"*, and it is the right call: three steps were prose only because nobody had checked
whether they had to be. All three moved into the executor.

**The conflict loop is closed, which it never was.** The label was invented so a pass would not
re-report the same conflict every run, and the doctrine said to clear it once the branch merges
cleanly again - but nothing cleared it, so a resolved branch stayed withheld until a human noticed.
`restack` now reads each labelled branch's `mergeable_state` at the top of the pass: still `dirty`
means `withheld` and untouched, anything else means the owner has resolved it, so the label comes
off and the branch rejoins. The label write goes through `LabelWrite.replacing`, which is the whole
point of that class - the production incident behind it was a write computed from the addition
alone, stripping `in-review` off already-promoted branches.

**`promote` is the fifth command.** It writes the compare-and-create link into the fork pull
request's own description under a `## Promote` heading, *replacing* any link already there, because
the description is rewritten on every run that rebuilds one and two headings would leave a reader
guessing which link is current. It adds `cram2-link-sent`, skips anything already carrying it, and
drops the label from anything since promoted or landed. `in-review` stays the developer's to add,
since the upstream pull request does not exist until they click Create.

What is left for the caller is now exactly one thing - retargeting a base - and the report says so
rather than implying the rest is also unavailable.

### The same ambient-state bug, twice in one pull request

CI failed on `test_a_missing_board_is_its_own_exit_status`, and it was a real defect rather than a
flaky test: introducing the fork client had moved credential resolution ahead of deriving the
board, so `restack` on a checkout with neither told its caller to set a token - when the thing they
actually need is the board the previous command produces. **Only CI could see it.** A Claude Code
session exports `GH_TOKEN`, so the wrong branch was never taken here.

That is the second instance in this one pull request of a test whose result depended on ambient
state: the first was the `board.json` snapshot sitting beside `stack.py`, which `board --write` had
just made routine. The fix is the same shape both times - the subprocess helper now strips the
credential for every command-line test, exactly as the autouse fixture sets the board aside.

Worth stating generally, because it will recur: **a test that reads ambient state cannot assert
about the state it is reading.** Both bugs were invisible on a developer's machine and only
appeared where the ambient state differed - which is the environment that matters, since `routine-
cutover`'s endgame is this code running in an Action with a third credential again.

## Update 2026-08-04 (live): the executor run against the real fork, and what only that found

The user authorised running the executor against the fork on throwaway pull requests. Done with
the board scoped to #140 (parent, non-draft) and #141 (child, draft) and nothing else, from a
detached worktree so the executor's own `checkout -B` could not disturb the branch under review.

All five commands ran. The conflict lifecycle is the one worth recording in full, because it is
the loop nothing previously closed: a real conflict pushed nothing, labelled #141 and posted the
comment naming the file; a second pass **withheld** it while `mergeable_state` was still `dirty`
and posted no second comment; once the conflict was resolved and pushed, the next pass **cleared
the label by itself** and the branch rejoined. `promote` wrote the link under a `## Promote`
heading, took only the first paragraph for the prefill, and on a second run replaced the section
rather than adding another - which also survived GitHub appending its own footer to the
description write, a wrinkle no test had modelled.

### Two defects only the live run found, and they were the same defect twice

A restack that hit a conflict exited **0**. A `run-report` whose fast-forward was **refused** also
exited **0**. Both are wrong in the way that matters most for this item's whole purpose: a caller
acting on the status alone - precisely what `routine-cutover`'s no-LLM endgame does - would have
read each as a pass with nothing outstanding.

The unit tests had not caught either, and it is worth being precise about why. They asserted
*what the report contained*, exhaustively and correctly. Nothing asserted *what the process told
its caller*, and those are different surfaces. The exit status is the only half a scheduled Action
reads.

Fixed by giving every command one `exit_code_for` over the report, so no two can disagree about
what a clean pass is: `7` for a refused fast-forward - outranking the rest, since the fork's base
is what every branch is measured against - `5` for a pre-flight refusal, which is a fault in the
move rather than in the branch, and `10` for a branch left unpublished for its owner. Tests were
written from the two live observations and checked by restoring the old behaviour.

The general lesson, which is not the same as the earlier ambient-state one: **a test over the
return value does not cover the exit status**, and for a tool whose whole point is to be driven by
something with no model in it, the exit status is the primary interface.

### Can a personal access token do the reparent from a session? No

Asked directly, and answered from evidence rather than inference:

- `gh` is not installed, so exporting a token does not produce `gh` or `gh stack`.
- `GH_TOKEN` is a 14-character `prox...` placeholder, not a GitHub token.
- A **junk** `Authorization` header and **no** header at all both return `200` on this private
  repository - so the agent proxy discards whatever the process sends and substitutes its own
  identity.
- The base-branch `PATCH` `403`s identically with a junk token and with none, and its
  `documentation_url` is **docs.anthropic.com**, not docs.github.com.

So the refusal is generated by the proxy from the request *shape*, not by GitHub and not by the
credential: a personal access token would be discarded before it ever reached GitHub. This is a
sharper statement than the 2026-08-02 entry's "a property of one credential" - it is a property of
the request path.

It says nothing against `routine-cutover`'s Action, which runs outside this proxy and is a
genuinely different actor. That still needs verifying there, but for a different reason than the
one on record.

## Update 2026-08-04 (new item): bootstrap an item before implementing it, not after

Raised by the user: *"I want the first step after the plan to be create a branch and a draft
PR and update the plan yaml and roadmap with the plan and branch and session and mark it in
progress and publish the dashboard, then only then start implementing, because I don't want to
wait for implementation to do these."*

Tracked as `plan-item-bootstrap` on track `personal-data`, wave `immediate`, `depends_on: []`.

### What is actually wrong today

The ordering is not a style preference. Every one of the five things above is derivable the
moment a plan is approved, and not one of them depends on a line of the implementation — yet
all five currently happen at the end. The window between the two is the entire length of the
implementation, and for that whole window `plan.yaml` says the item is `not_started` with
`branch: null`, while a branch exists and is being worked.

That is exactly the state this plan's own conventions call worse than no plan at all: *"a plan
whose manifest lags behind reality is worse than no plan: every dashboard, kickoff and resolve
run downstream reads it as truth."* The dashboard shows the item as available to start. A
second session running `/plan-item-kickoff` on it is told nothing exists. The failure is not
hypothetical — `session-start-plan-and-setup-guards` was itself raised from a session that
implemented and pushed before its item existed, and #121 answered that by *reporting* the gap
better. This answers the other half: give the session something to run at the moment the gap
opens, instead of a convention to remember at the end.

### One shared procedure, two callers

Settled with the user before the item was written. `plan-item-kickoff` step 5 is the primary
caller — it is the skill whose approved plan leads straight into implementing. `add-plan-item`'s
"new item in an existing plan" outcome is the second, and takes a one-line reference, the same
shape `scope-decision.md` and `prerequisite-check.md` already established. Duplicating the step
into each skill would have recreated, in this very system, the triplicated-rule failure that
`add-plan-item` was built to end.

The `/add-plan-item`-only reading was considered and rejected on its own terms: that skill's
stated design is that it *"never writes code, creates a branch, or pushes anything"*, so hanging
branch and pull request creation off it would contradict the contract in its own opening
paragraph.

### Scripts and models, not prose steps

The user's second point — *"all that can be based on python scripts and models, and the skill
only instructed to use the script at the right moment"* — is the same call decision 12 already
made for the bash→Python track, applied to a new surface. The skills keep the judgement (when
to run it, what the branch is called, what the approved plan says); the mechanics are a Python
module with real dataclasses for the request and the result, not a checklist a session
re-improvises and half-completes.

It lives at `.claude/hooks/plan_item_bootstrap.py`, beside `plan_manifest_tools.py`, rather than
inside either skill's directory: two skills call it, and `dev-tooling-save-plan-python` already
absorbs `plan_manifest_tools.py` into `development_tooling`. Putting it there means it rides the
migration that is already planned instead of inventing a second destination that would have to
be moved again.

### The two parts that are not scriptable, named rather than glossed

- **The dashboard republish** stays a `/plan-dashboard <plan-id>` step. Only a live session can
  call the Artifact tool; `save-plan.sh`'s own header already records this and prints the
  reminder. The script's result object carries the reminder rather than silently omitting it.
- **Creating the pull request can be done by the script** — probed the same day rather than
  left to inference; see the probe entry below for the measurement and its limits.

### Where it is based, and why the one shared file with #135 is not a dependency

Run rather than eyeballed, using `add-plan-item`'s own `check_scope_overlap.py` against `origin/main`:

```
paths_absent_from_base : .claude/skills/add-plan-item/SKILL.md
                         .claude/skills/add-plan-item/scope-decision.md
                         (nothing else)
already on main        : plan-item-kickoff/SKILL.md, plan-create/SKILL.md, save-plan.sh,
                         plan_manifest_tools.py, resolve-personal-notes-config.sh,
                         .claude/hooks/tests/
```

**Based on fork `main`, `depends_on: []`.** Everything the work builds on is on `main` already.
Because the tests go into `.claude/hooks/tests/`, which `ci.yml` already runs, no new pytest
directory constant is needed — which sidesteps outright the single `ci.yml` line that #135, #106
and #107 all conflict on.

The only thing `main` lacks is #135's own two files, and they are needed for exactly **one line**:
the reference from `add-plan-item`'s step 6. By the prefer-the-change test in `scope-decision.md`,
one line that modifies what an unlanded item introduces *is that item's work* — so it goes on
`claude/add-plan-item-skill-e89irj` while #135 is still an open draft, and this item stays off
`main`. If #135 lands first, the line simply moves into this item's own pull request; the ordering
does not matter either way. Stacking the whole item — script, tests, kickoff wiring — behind a
draft in review, for one line of prose, is the trade `add-plan-item`'s own basing note already
refused when the same question was asked about #106.

Remaining overlap is the established whichever-lands-second-merges pattern:
`resolve-personal-notes-config.sh` gains new constants (shared with #106, #107, #115, #121, #126
and #135, and the reason that file auto-merges every time is that each branch appends its own
block), and `.claude/hooks/tests/` gains a new file beside the ones #107, #115, #121 and #126
touch.

### Relationship to the two neighbouring items, neither of which this duplicates

- `session-start-plan-and-setup-guards` (#121) and `plan-item-edit-guard` detect and refuse work
  on a branch with no plan item. They are the *detector*. This is the *remedy* — the thing a
  session runs so the item exists before the first edit. `plan-item-edit-guard` becomes markedly
  less obstructive once this exists, because the answer to its refusal becomes a single command
  rather than a manual sequence.
- `add-plan-item` decides **where** work goes and stops there. This is what happens **next**.

### A status that names itself

Asked whether the exit codes should carry strings beside or instead of the numbers. *Instead* is
not available and it is worth saying why rather than just declining: a process exit status is an
integer by definition, and these are deliberately aligned with `stack.ExitCode` value for value so
a caller acting on both tools never has to remember which produced one.

*Beside* was a real gap, and the tell was that the meaning already existed - `BRANCH_NEEDS_ATTENTION`
is right there in the enum, and nothing emitted it, so every caller seeing `10` had to go and look
it up. `name_for_a_caller` derives the name from the member itself rather than a table written
beside it, so a status cannot end up carrying a name that belongs to a different one. `main` prints
it once, from one place, for any non-zero run; success stays silent, because announcing it would
make every run noisy.

The half that matters most is the document: `run-report --json` now leads with `status` and
`exit_code`. `routine-cutover`'s Action reads that document rather than the process status, and
mapping an integer back to a meaning is a decoding step it should not have to do at all.

Worth generalising alongside the exit-status lesson above: **an interface meant for something with
no model in it should say what it means, not encode it.** The number is for the shell; the name is
for whoever has to act on it.

## Update 2026-08-04 (probe): `POST /pulls` is available to a script, and the token is irrelevant

`plan-item-bootstrap` was written with pull request creation listed as its one unmeasured step.
The user's response — *"I think PRs can be created from the script given an exported token"* — is
right about the outcome, and the mechanism is worth stating exactly, because it is not the one
the framing implies.

### The probe

`POST /repos/{owner}/{repo}/pulls` with a deliberately unresolvable `head`, so nothing could be
created whatever the answer. Run three ways against the fork:

| Credential sent | Status | Body |
| --- | --- | --- |
| exported `GH_TOKEN` | **422** | `Validation Failed`, `field: head`, `docs.github.com` |
| junk `Bearer ghp_junk…` | **422** | identical |
| no `Authorization` header | **422** | identical |

**422 is the informative answer, not a failure.** Reaching field-level validation means the
request was authorised and evaluated by GitHub. The contrast that makes it conclusive is the
base-branch `PATCH` recorded on 2026-08-03/04: that one returns `403` with a
`documentation_url` on **docs.anthropic.com**, the agent proxy's own refusal signature. `POST
/pulls` carries **docs.github.com**. So the two refusals are different in kind — one is the proxy
rejecting a request *shape*, and `POST /pulls` is not in that category.

### The correction to the premise

The three rows are identical, which settles the credential half in the opposite direction to the
framing: **within a session the token is irrelevant.** Exporting `GH_TOKEN` gains nothing, and
having none loses nothing — `GH_TOKEN` is a 14-character `proxy…` placeholder, and the proxy
substitutes its own identity regardless of what the process sends. This is the same finding the
2026-08-04 live entry reached from the `PATCH` side, now confirmed from the creation side.

That matters for the design rather than being a pedantic distinction. A script written to
*require* an exported token would be requiring the one thing that demonstrably does not
participate.

### What the probe does not cover, stated rather than implied

A `422` on `head` stops evaluation before anything is built, so three things remain untested:
that a creation actually **succeeds**, that **`draft: true`** is honoured, and which **identity**
the resulting pull request is attributed to. Settling them needs one throwaway creation against
the fork, in the shape #139 used for its own live run. Recording the boundary is the point — the
same discipline #139 applied when it declined to widen scope on the strength of a fresh reading.

### Why the credential still matters anyway

Inert here is not inert everywhere. The same script run from a terminal, or from
`routine-cutover`'s scheduled Action, sits behind no proxy, and there the token *is* the
credential. So creation goes through the one shared backend `dev-tooling-github-api-unification`
builds — never a third copy of the gh-CLI-else-token rule that `github-api.sh` (#107) and
`pr_state` (#111) already carry between them.

### Consequence for the item

`plan-item-bootstrap` shrinks by one hand-off. Of the two steps it was going to return to the
caller, only the dashboard republish genuinely stays — the Artifact tool needs a live session, as
`save-plan.sh` already documents. Branch, pull request, manifest, roadmap and status all become
script work, which is what the item was asked for in the first place.

## Update 2026-08-04 (revision): two operations, not one shared procedure

The user's correction to the shape recorded this morning: *"I do not think plan-item-create/add
needs this behaviour, as it should only care about creating the plan item and updating plan data
and dashboard."*

Taken and agreed. The first shape treated the whole thing as one procedure that both plan skills
would reference, which was the wrong seam.

### The seam that was wrong

`/add-plan-item`'s own opening paragraph promises it *"never writes code, creates a branch, or
pushes anything"*. Referencing a procedure whose second half creates a branch and opens a pull
request would have broken that promise through a reference — the contract would still have read
as intact while the behaviour behind it no longer was. That is worse than breaking it openly.

Rejecting the `/add-plan-item`-only reading this morning was right; concluding from it that both
skills therefore want the *same* procedure did not follow.

### The seam that is right

Two operations, one module, each caller taking only what it needs:

- **Record** — write or update the item's `plan.yaml` entry and `roadmap.md` section, set its
  status, run `save-plan.sh`. This is `/add-plan-item`'s entire business, and all it gets.
- **Open** — create the branch, push it, open the draft pull request, then write `branch`,
  `session` and `pull_request_number` back onto the item and flip it to `in_progress`. Only
  `/plan-item-kickoff` gets this, being the skill whose approved plan leads straight into
  implementing.

`/plan-item-kickoff` calls **open** and then **record** — in that order, because the pull request
number does not exist until the pull request does. `/add-plan-item` calls **record** alone.

Both paths end at `/plan-dashboard <plan-id>`, which stays with the caller because only a live
session can call the Artifact tool.

### Why this is better and not merely different

It is the repository's own `AGENTS.md` applied to this module rather than quoted at it: each
operation now has one reason to change, and each caller depends only on the surface it uses —
single responsibility and interface segregation. The practical test is the one that settles it:
under the first shape, a change to how branches are created would have touched a skill that never
creates branches. Under this one, it cannot.

### What does not change

The basing decision stands unaltered. `/add-plan-item` still takes a one-line reference — to
**record** rather than to the whole procedure — so `.claude/skills/add-plan-item/` is still needed
for exactly one line, that line still belongs on #135's branch by the prefer-the-change test, and
the item stays based on fork `main` with `depends_on: []`.

## Update 2026-08-04 (resolved): #106's fork-resolution test fixed for the cram2 checkout topology

`/plan-item-resolve workflow-unification stack-tooling-on-main`, this session
(https://claude.ai/code/session_01F6tM5mDZr5pTB37UgBV6N5), on the user's report that CI on the
upstream `cram2` repo fails `test_the_skill_names_no_fork_of_its_own` with `ForkRemoteNotFoundError:
... every remote is cram2/cognitive_robot_abstract_machine`.

**Not a new bug — the same one #110 already found and fixed, one item over, not yet ported back.**
PR #106's own fork-side CI was (and is) entirely green: head repo and base repo are both the fork,
so that checkout's only remote (`origin`) is never the upstream, and a fork candidate is always
found. The failure only shows up in the checkout topology of a workflow run in the *base* repo of a
cross-fork pull request - `origin` pointing at `cram2` itself, no separate fork remote at all - which
is what a real cram2-side CI run for this code looks like. `stack.toml` deliberately leaves
`fork_repository` unset (derived from `fork_remote`'s URL instead), so there is nothing to fall back
to. Reproduced exactly: cloned this checkout into a scratch directory, pointed its only remote at
`cram2/cognitive_robot_abstract_machine`, and got the identical traceback the user reported.

The 2026-08-03 entry above already named this exact mechanism from the other side, when #110 deleted
the ~120-line remote-inference subsystem and discovered `test_the_skill_names_no_fork_of_its_own`
"resolved its fork through the inference - which is the only reason it worked on CI." Fetching
`.claude/stack/tests/test_maintenance_skill.py` from `claude/setup-stacked-prs-skill` (#110) showed
the fix already exists there, verbatim: stop calling `load_configuration()` (which raises when no
fork can be resolved) and instead compute the checkout's candidate forks directly from its remotes,
asserting the skill names none of them - vacuously true, not an error, when there are zero
candidates. It depends only on symbols (`Repository`, `_configuration_values`,
`CONFIGURATION_PATH`, `Repository.from_remote_url`, `Repository.names_a_repository`) already present
in #106's own `stack.py`, so #110's ~120-line deletion is not a prerequisite - the fix was ported
back to `claude/stack-tooling-on-main` directly rather than waiting on #110's rebase, since #106 is
the parent and needs to be correct in the topology it will actually run in once promoted.

Confirmed (research agent reading `test_stack.py`/`conftest.py` on #106's branch) that no other test
shares this ambient-remote defect - every other `load_configuration`/`resolve_remotes` call in that
suite runs against the `ScratchRepository` fixture with explicitly-added remotes, never the real
checkout. This is the one isolated instance.

**Verified**: `pytest .claude/stack/tests/test_maintenance_skill.py` passes under both topologies -
the fork's own (one candidate found) and the reproduced cram2-only-remote one (zero candidates,
vacuous pass, where it previously raised). Full `test_claude_dev_tooling` scope - `.claude/stack/tests`
(91), `.claude/hooks/tests` (36), `.claude/skills/plan-dashboard/tests` (194) - all green, 321 total,
no regressions. Pushed to `claude/stack-tooling-on-main` (`b3e240e6`); PR #106 re-drafted per the
standing re-draft-after-push rule and commented with the fix's rationale.

## Update 2026-08-04 (kickoff): plan-item-bootstrap opens as #143, bootstrapped by hand

`/plan-item-kickoff workflow-unification plan-item-bootstrap`, session
https://claude.ai/code/session_01VoH56TLkH5rA5EFu2xhML9, as draft pull request **#143** on
`claude/plan-item-kickoff-workflow-vocs6b`, based on fork `main`.

The bootstrap ran **before** the implementation, in the order the item itself prescribes -
branch, draft pull request, manifest, roadmap, dashboard, then code. By hand, since the tool
that automates it is what this pull request builds. That is the item's own argument taken at
face value rather than deferred: the window it exists to close is exactly the one a session
opens by starting with the code.

### The basing decision, re-run rather than inherited

The 2026-08-01 lesson from `git-identity-from-personal-notes` - *"independent PR off main"
recorded at planning time is a claim about the code, and it expires when a sibling PR moves the
test infrastructure* - says to re-check at kickoff. Re-checked and it holds: `depends_on: []`,
`check_dependency_readiness.py --item plan-item-bootstrap` returns `[]`, no branch existed yet,
and every file the work builds on is on `main` already. Because the tests go into
`.claude/hooks/tests/`, which `ci.yml` already runs, there is no new pytest directory constant
and therefore no touch of the single `ci.yml` line #135, #106 and #107 all conflict on.

### The one instruction that could not be honoured, and what replaced it

The item's notes say pull request creation *"goes through the one shared backend
`dev-tooling-github-api-unification` builds - never a third copy of the gh-CLI-else-token rule
that `github-api.sh` (#107) and `pr_state` (#111) already carry between them."* That is
unsatisfiable from `main` today: the unification item is `not_started`, `github-api.sh` exists
only on #107, and `main` carries **no GitHub-calling Python at all** - checked rather than
assumed, `render_common.py` imports `urlsplit` and nothing else.

So the instruction describes the target, not something reachable from this item's own base. The
resolution is `plan-updates-since-helper`'s recorded precedent from 2026-07-31, where the same
collision produced the same answer: implement the call inline, deliberately *without*
reproducing the gh-CLI-else-token discovery (`gh` is not installed here and `GH_TOKEN` is a
14-character proxy placeholder, both already on record), and let the unification item absorb it.
Stacking on #107 or #111 to get the backend would reverse the basing decision this item took
after running `check_scope_overlap.py`, for a dependency that only exists to avoid ten lines.

Worth stating generally, because this plan keeps producing it: **an item's notes can name a
dependency the item's own base cannot reach.** The notes are written when the shape is decided;
the base is chosen later, from live branches. When the two disagree the base wins, and the
inline copy gets recorded as something a named later item absorbs - not silently left as a
fourth copy nobody is tracking.

### The promise in `plan-item-kickoff` has to be rewritten, not extended

Forced by the item rather than spelled out in it, and worth recording because it is the same
objection that shaped the item in the first place. `plan-item-kickoff/SKILL.md` opens with *"This
skill never writes code, creates a branch, or pushes anything"* - the identical contract that
ruled out hanging this behaviour off `/add-plan-item`. Adding a branch-and-pull-request step
while leaving that sentence standing would break the promise through a reference, which the
2026-08-04 revision already called *worse than breaking it openly*.

It becomes "never writes code, and creates the branch and draft pull request only once the plan
is approved", with the new work in a **step 6 after approval**. Step 5's planning half is
untouched, so the skill still writes nothing before the user has seen and approved a plan -
which is the part of the promise that was actually load-bearing.

### The one line on #135's branch

`/add-plan-item` step 6's reference to **record** goes on `claude/add-plan-item-skill-e89irj`
while #135 is still an open draft, per `scope-decision.md`'s prefer-the-change test. Pushing to
another session's branch needs explicit permission; the user granted it at kickoff, the same
override made on sight for #133, with a comment on #135 so its owning session receives it as an
event.

### Implemented the same session: the probe changed the design it was written to confirm

The item named one unmeasured step and asked for a throwaway creation to settle it. It was
run - throwaway pull request **#144** against the fork, closed immediately - and it answered
three questions rather than one:

| Question | Answer |
| --- | --- |
| Does `POST /pulls` from the script actually succeed? | Yes |
| Is `draft: true` honoured? | Yes |
| Which identity is it attributed to? | **`claude[bot]`** |

The third is the one that mattered, and it was only visible because #143 had been opened
minutes earlier through the session's GitHub tool: **same repository, same session, same
proxy - `AbdelrhmanBassiouny` for the tool, `claude[bot]` for the script.** Also worth
recording since nothing had documented it: the proxy appends its own
`_Generated by Claude Code_` footer to the body on both paths, which the caller never sent.

That is precisely the authorship problem this roadmap already flags three times for commits
(`Claude <noreply@anthropic.com>` on #101 and the P3 branch, and the container default that
`git-identity-from-personal-notes` exists to fix) - and left alone it would have applied to
*every* plan item's pull request, forever, as a direct consequence of this item.

**The resolution, chosen by the user against two alternatives:** `open` takes
`--pull-request-number` for a pull request the caller has already created and records it
instead of creating one. The creating path stays, for an unattended run whose credential is a
real one rather than a proxy placeholder - `routine-cutover`'s Action being the case that
needs it. Title and body are required only on that path, so neither caller passes an argument
it cannot use.

The general lesson is about the probe rather than the credential: **a probe that stops at the
first refusal answers whether an operation is permitted, not whether its result is
acceptable.** The 2026-08-04 probe reached a `422` on `head` and concluded creation was
available, which was true and insufficient - the identity question only opens once something
is actually created. The item was right to name that boundary and right to insist it be
closed before shipping.

### What else the implementation settled

- **The manifest is patched by line, following `sync_manifest_status.py`.** That script's
  docstring already records that a full YAML round trip - ruamel.yaml included - re-flows
  wrapped strings and turns a one-field edit into a whole-file diff. Reusing the approach
  rather than rediscovering it is the whole value of it being written down; a test asserts the
  manifest is byte-identical apart from the one line that changed, and it fails if the module
  round-trips instead.
- **A refused pull request leaves the branch it already published**, and the docstring says so
  rather than claiming otherwise. Sessions cannot delete a remote branch, so there is no
  cleanup to perform; the manifest is left untouched instead of pointing at a pull request
  that does not exist, and a re-run is refused by the already-published guard rather than
  overwriting the commits. The first draft of that docstring claimed nothing was left behind,
  which the mutation pass caught.
- **Every test was checked by breaking the implementation**, three ways - defaulting `draft`
  to `False`, round-tripping the manifest through PyYAML, removing the already-published guard
  - each failing exactly the tests that name that behaviour and no others. 57 tests pass under
  `.claude/hooks/tests`, was 36; 194 under the plan-dashboard suite, unaffected.
- **`plan-item-kickoff`'s opening promise was rewritten, not extended.** It said *"never
  writes code, creates a branch, or pushes anything"* - the same contract that ruled out
  hanging this behaviour off `/add-plan-item`. It now says it never writes code and creates
  nothing before a plan is approved, with the branch and pull request in step 6 after
  approval. Leaving the sentence standing while adding the step would have broken the promise
  through a reference, which the 2026-08-04 revision already called worse than breaking it
  openly.

### This item was bootstrapped by the procedure it describes

Branch, draft pull request #143, manifest, roadmap and dashboard all came first, by hand,
before a line of the implementation - which is the argument the item makes, applied to itself
rather than deferred. The one thing that could not be dogfooded is the tool itself, since it
did not exist yet; the first genuine run belongs to whichever item is kicked off next.

### Review round 2026-08-04: the manifest's vocabulary gets one home

Nineteen comments, almost all one objection seen from many angles: the module knew
`plan.yaml`'s keys, filenames, statuses and indentation in a dozen scattered places, and the
tests knew them a second time as literal strings like `"    status: in_progress\n"`. A change
to how a manifest line is written had to be made twice, in two files, and nothing would have
caught the second one being missed.

`PlanField` now names every key, `PlanDocument` the two filenames, `HookScript` the scripts
this module drives, `ItemStatus` the statuses, and `ItemFieldLine` renders a line from them.
The tests import all of it and assert on rendered lines. Two details are the ones that make it
real rather than cosmetic: `FOLDED_FIELD_PATTERN` is *generated* from `FOLDED_PLAN_FIELDS`
instead of repeating `notes|blockers`, and the tests resolve a plan's paths through the
production `PlanLocation` - which asks the shell configuration - instead of spelling out
`.claude/personal/plans/<id>/plan.yaml`. Shortening `ITEM_FIELD_INDENT` now fails 12 of 24
tests, which is the evidence the two sides are actually one.

The test manifest moved into `tests/fixtures/` as a real `.yaml` file, which `AGENTS.md`'s
no-inline-snippets rule already required and this pull request had simply not followed.

Refusals became dataclasses carrying typed context, composing their message from
`error_message()` and `suggest_correction()` at construction - `krrood`'s `DataclassException`
idiom mirrored in a stdlib-only base, which is the boundary decision 12 records. Two things
fall out of it that were not there before: every refusal now says what to do about it, and the
tests assert on the field that explains a refusal rather than on its wording.

**One thread deliberately left open**, and it is worth recording because the reviewer's
instruction rested on a premise that turned out to be false. Asked to remove the `ItemStatus`
overlap with `build_dashboard.py` by basing this item on the `development_tooling` package if
that is what it takes - **basing on #111 would not remove it**. `build_dashboard.py` moves into
the package with `dev-tooling-python-package`, which is `not_started` and itself depends on
#111 and #101, so the re-base would attach a dependency-free immediate-wave item to the
unlanded upstream chain and still leave two enums. Importing `build_dashboard` directly is
worse - it needs jinja2 and markdown, which a hook cannot assume - and extracting a shared
module on `main` would need the `sys.path` hackery decision 8 exists to end, in a file six open
branches already edit. So the recommendation put back to the user is to leave the five-member
overlap for the migration that actually ends it, and the thread stays unresolved until they
say.

The general shape, since this plan keeps meeting it: **a reviewer's instruction can name a
remedy the branch cannot reach.** The answer is not to follow it into a worse place or to
silently ignore it, but to say which part is reachable, do that part, and hand the rest back
with the reason.

#### Second round, same day: the field knows how it is written

Five more comments, and one of them is a design the reviewer had proposed twice before it
was understood: **a `PlanField` member's value is a `FieldSpecification` dataclass** - the
key, whether the value is quoted, whether it spans the lines beneath it - reached through a
`__new__` that keeps the member's string value equal to its key, so it still indexes parsed
YAML with no `.value`. `render` moves onto the field, so nothing outside the enum knows that
a title is quoted and a track is not.

`ItemFieldLine` disappeared with it, along with its `quoting` classmethod: it existed only
to hold a choice the caller was making, and once the field knows, there is nothing left for
it to do. `FOLDED_PLAN_FIELDS` is derived from the specifications rather than listed, so
declaring a field folded is the only step in making it folded.

The path half went the same way. `PlanDocument.path_within_notes_branch` names the plans
directory once, which the *fixture* had still been composing by hand even after the previous
round fixed `published_plan` - so the earlier reply on that thread was right about the
production side and wrong about the test. That made `PlanLocation` redundant, since its only
remaining job was the fetch: it is now a plain `fetch_notes_branch`, and the two concerns
are split by owner - the shell says which branch, `PlanDocument` says where within it. The
`PLANS_DIR` mirror is held by a test that asserts against what the shell actually resolves;
changing the Python constant alone fails six tests.

Worth carrying: **a reviewer repeating a suggestion is a signal it was not understood the
first time.** This one was made in the first round ("dataclass specification that is
inherited from in the Enum") and answered with something adjacent but weaker - an enum plus
a separate line-rendering class - which is why it came back. Re-reading the original wording
rather than the previous answer is what produced the right shape.

257 tests, was 254. Three mutations checked: dropping `TITLE`'s quoting, rendering without
consulting the specification, and drifting the plans directory.

#### Third round: the mixin, and what YAML calls these things

The reviewer's third pass replaced the `__new__` outright:
`ManifestKey(KeySpecification, Enum)`, so a member *is* a specification -
`isinstance` and `issubclass` hold, and the style is reached directly rather than
through an attribute a type checker cannot see. Their instinct was right, and three
things only prototyping settled:

- **A member's value must be the constructor's argument tuple, not a built
  specification.** `TITLE = KeySpecification(key="title", …)` raises nothing and lands
  the whole instance in `.key`. That is the one hazard the mixin introduces, and it is
  guarded by a test asserting every key is a string; making the mistake fails four.
- **The field cannot be called `name`.** `Enum` reserves it - `AttributeError: cannot
  set attribute 'name'`. It stays `key`, which is also YAML's own term for the left-hand
  side of a mapping (JSON's RFC says "name"; this is a `.yaml` file), and which sidesteps
  `dataclasses.Field` - a collision already live in the test module, where a parameter
  named `field` shadowed the `dataclasses` import.
- **A key cannot be both `str` and `KeySpecification`** - `TypeError: too many data
  types`. So str-ness goes, and the nine lookups relying on it read `.key`. One was
  missed by the rename and caught by a test, which is exactly the failure class that
  trade buys.

The two booleans collapsed into one `ValueStyle` (`PLAIN` / `DOUBLE_QUOTED` / `BLOCK`),
because they were never independent: a value is written one way, never two. `BLOCK` is
YAML's own word for a value continuing beneath its key, and is correct for both cases
here - `notes` is a folded scalar, `blockers` a sequence - where "folded" would have been
wrong for one of them. Two booleans had allowed a state that cannot exist.

Worth carrying: **when a reviewer proposes a language feature, prototype it before
answering.** The first two rounds answered this suggestion from reasoning and produced
something adjacent but weaker each time. Running it took minutes and produced the
argument tuple hazard, the `name` collision and the data-type limit - none of which
reasoning had surfaced, and all three of which shaped the final design.

The same round's last comment asked for the field list to become a dataclass "or better
maybe a `dict[ManifestKey, str]`", and the mapping is the stronger of the two offered
because it makes a state *unrepresentable*: `[(STATUS, "in_progress"), (STATUS, "done")]`
was accepted by the list, patched the same line twice, and let the second write silently
win. A dataclass of pairs would have kept that; a mapping cannot express it. Insertion
order still governs line order, which `render_new_item` depends on, and is pinned by a
mutation check rather than assumed - reordering the mapping fails exactly the test that
names the field order. The same shape replaced two other pair-lists, including the
required-keys check, which now reports what is missing from the mapping itself instead of
from a parallel list beside it.

#### The duplication question, asked of the whole file and answered by measurement

The round's last comment asked simply whether there is any duplication with `stack.py`.
Answering it required reading that file rather than the docstring that had asserted a
relationship, and the assertion did not survive. The two `ExitCode` enums share only
`SUCCESS = 0` and reuse 3, 4 and 5 for *unrelated* meanings - `BOARD_UNAVAILABLE` /
`REMOTES_UNRESOLVED` / `PREFLIGHT_REFUSED` against `UNKNOWN_PLAN` / `UNKNOWN_ITEM` /
`INCOMPLETE_NEW_ITEM` - because the two tools fail in different ways. So the promise that
"aligning the two belongs with whichever item brings them into one package" described a
unification with no content, and it is deleted; the class states its contract instead, and
gained the per-member docstrings it was the one enum in the file still missing. Nothing
else overlaps: `stack.py` makes no network call at all, never touches `plan.yaml`, and the
only literal overlap is the `subprocess.run(["git", ...])` boilerplate, where the contracts
are deliberately opposite - `_git` returns `""` on failure, right for derivation, while
`run_git` raises, because a push that silently did nothing must not read as one that
worked. That is the same distinction #139 introduced its own `GitCommandRunner` over.

**One real duplication turned up, and it belongs to `stack.py`.** Its
`_resolve_personal_notes_remote`/`_resolve_personal_notes_branch` reimplement the
notes-branch precedence in Python, their own docstrings conceding "by the same precedence
as `resolve-personal-notes-config.sh`" - a second copy of rules the shell owns, free to
drift from them. `dev-tooling-config-shim-slimming` already plans a CI test holding the
bash and Python resolutions equal; this is a second carrier for it to cover, and it is
recorded on that item. This module adds no third copy: `fetch_notes_branch` sources the
shell file and calls its own `fetch_personal_notes_branch`.

Worth carrying, since this plan keeps recording the reverse case: **a docstring can
invent a relationship as easily as it can miss one.** Three same-artifact-twice
duplications are on record here, all found late; this is the opposite failure - a
forward-looking note asserting a duplication that did not exist, which would have sent a
later reader looking for something to unify. Both are fixed the same way, by reading the
other file rather than reasoning about it.

## Update 2026-08-05 (review round): the executor's 25 comments, and the shape they kept asking for

Session https://claude.ai/code/session_014E9nB1MUvm4jwgC2UTN5GT, on #139. Three of the
twenty-five were decisions rather than corrections, and the useful part of each is the
argument that settled it.

### Leading with `run-report` was possible only once the doctrine moved out of the commands

The reviewer asked, marked *discuss with me*: why explain the separate commands at all
rather than name the one that does the whole pass? Their reading won, and the skill now
leads with `run-report --json` as step 2 with the four commands demoted to a reference
section for resuming a partial run.

Worth recording *why it was written the other way first*, so it does not creep back: the
per-command sections carried doctrine that had nowhere else to live — what a `refused`
outcome means, why the fork's base must stay a pristine mirror, what happens to a
conflict. Explaining a command and stating a rule had become the same paragraph, and a
document in that state cannot be reordered without losing rules. Splitting them apart is
what made the change possible, and it gave the reviewer's other two points a home:

- **The pass never resolves a conflict.** The escape hatch — "if you resolve one
  yourself, comment saying what you took" — is deleted, and the header's promise changed
  with it, from *"the only file changes you ever make are conflict resolutions"* to no
  file changes at all. A conflict is a change to somebody else's branch.
- **It never attempts to open the upstream pull request.** It had said the call "fails
  every time", which reads as a thing to try and expect to fail.

### The same design, asked for twice, in two places

*"If `PullRequestField` inherits from a specification and `Enum`, it can hold per-member
specification instances."* That is now the module's idiom twice over — `PullRequestField`
carrying each field's key, read shape and requiredness, and `Command` carrying each
command's name and help text.

Both hit the two hazards `plan-item-bootstrap`'s own third review round already recorded,
which is the first time this plan has had a lesson available *before* meeting it rather
than after:

- a member's value must be the **argument tuple**, never a built specification — passing
  one raises nothing and lands the whole instance in the key. Guarded by a test here,
  verified by making the mistake deliberately.
- the field cannot be called `name` — `Enum` reserves it. `PullRequestField` sidesteps it
  with `key`; `Command` needed `invoked_as`.

The payoff is not tidiness: `_required`, `_branch_reference` and `_label_names` collapsed
into `PullRequestField.read`, and the three raw `record.get(...)` calls in `promote` and
the conflict check went with them — those were reading the API's shape *outside* the only
place that was supposed to know it.

### Dispatch, and the one thing it must not stop doing

`_dispatch` was flagged as violating open/closed, correctly. Each command is now a
`MaintenanceCommand` subclass owning its flags and its work, listed once in `COMMANDS`,
which is also what builds the parser — so a command that exists but is unreachable from
the command line is not expressible.

The constraint that survived the refactor is the one CI caught earlier: the board is
still derived *before* the credential is resolved, so a checkout missing both is sent
after the board rather than after a token. `MaintenancePass` resolves each lazily, in that
order, which is what keeps it true structurally rather than by remembering.

### `run-report` deletes the board it finished with

The user's question on `.gitignore` — could it be deleted automatically once we are done
with it — is a better idea than the gitignore line it was asked about. Scoped to
`run-report` only: that is the one command meaning "the pass is over", while the other
four are the resume path and a board they deleted would strand their own caller.

### What was deferred rather than done, and why that is the honest answer

Three threads are left open on purpose. Two ask why the GitHub calls are urllib rather
than `gh` or a Python library; `gh` genuinely is absent from a session container and the
SessionStart-reachable tier is stdlib-only by decision 12, but neither is a reason to
settle it *here*. `dev-tooling-github-api-unification` exists because `github-api.sh` and
`pr_state` already implement the same rule twice, and this module is now a third carrier —
so that item gains a decision it did not have: whether the shared backend may require an
install, answered once for all three rather than three times.

The third asks whether a supplied credential could do the base-branch reparent from a
session. It cannot, and the measurement is worth keeping: the `PATCH` returns 403
identically with the exported `GH_TOKEN`, with a junk `Authorization` header, and with no
header at all, while a *read* with no header returns 200 — so the proxy substitutes its
own identity and a personal access token never reaches GitHub. The refusal's
`documentation_url` is on **docs.anthropic.com**. That is one notch sharper than the
2026-08-04 finding: not a property of one credential, but of the request path.

**A reply is not a resolution.** All twenty-five got one; the three that record a deferral
or answer a question without changing anything stay open for the user to close, per the
notes-branch rule that a thread is resolved only once what it asked for has been done.

### Second round the same day: two questions asked rather than guessed

Twelve more comments on #139. Ten were answerable by doing them; two were not, and asking
is what made them come out right.

**`PreFlight` → `CommitMoveChecks`** (the reviewer marked it *discuss with me*, and four
options were costed). The objection was exact: the name said *when it runs*, not what it
does. `CommitMoveChecks(...).refusals(move)` names its subject and pairs with the
`ProposedCommitMove` it is handed. `PreFlightRefusal` → `CommitMoveRefusal`, the
subcommand → `stack.py check-move`, and both tools' `PREFLIGHT_REFUSED` → `MOVE_REFUSED`,
still `5` in each and still aligned.

**"Actions as dataclasses with a shared abstract parent"** had two plausible referents -
the restack's per-branch steps, or `stack.py`'s `CommitMoveAction` enum - and they are
materially different pieces of work. Asked; it was the steps. `_restack_branch` was a
chain of ifs, and each branch of it is now a `RestackStep` subclass whose `attempt` either
concludes the branch or returns `None`. `BranchUnderRestack` carries what a step needs and
builds the outcome, which is what let `_withhold` and `_report_conflict` stop being free
functions taking six arguments and become the steps that own them.

Worth keeping: **these steps are listed, the commands are discovered.** The reviewer asked
for `COMMANDS` to come from `MaintenanceCommand.__subclasses__()`, and that is right there
- a command class that exists should be reachable, and the failure the explicit tuple
allowed was writing the class and forgetting the line. It is *wrong* for the steps, whose
order is the procedure: publishing before checking the move is a bug no type catches, so
the tuple is the specification rather than boilerplate. Same shape, opposite answer,
because one list carries meaning and the other carried only maintenance.

### The rule that decided what the skill says

The reviewer asked why the skill explains things only the scripts need to care about, then
sharpened it: *what I fear is staleness when we are mentioning things that is code
explanations.* That second sentence is the whole rule, and it is better than the one the
document was written against.

A sentence in a skill describing what the code does has nothing holding it true - no test
fails when the code changes under it - so every one of them is a future lie with a delay
attached. Applied: **if a statement would have to change when `maintenance.py` changes, it
does not belong in the skill.** That deleted the conflict-labelling description, the
force-with-lease rule, the board deletion, the per-outcome table and the flag lists; each
already lives in the docstring of the thing that does it, where it moves with the code.
Step 2 went from ~70 lines to ~30.

What survives is either an instruction to the agent - the document's actual subject - or a
status name the agent matches on, and those are pinned: they are
`MaintenanceExitCode.name_for_a_caller`, derived from the enum member, so renaming a status
changes what the document refers to rather than silently diverging from it.

This is the counterpart to the earlier round's finding. There, doctrine and command
explanation had fused into single paragraphs and had to be split apart before the document
could be reordered. Here, the same split is what made the deletion safe: once the rules
lived in their own section, everything left in the command prose was disposable.

### Left open on purpose

The `stack.py` half of the rename is arguably #106's work by `scope-decision.md`'s
prefer-the-change test - `CommitMoveChecks` is defined in a file #106 introduces - so #139
now carries an edit to its parent's file and #110 will meet it on rebase. Done here because
that is where it was asked for, flagged there rather than left silent.

## Update 2026-08-05 (resolved): #115's conflict was a README rewrite resolved hunk-by-hunk

`/plan-item-resolve workflow-unification plan-updates-since-helper`, session
https://claude.ai/code/session_016kAVapbHxDokYjZBukKA5X. The item had been `in_progress` and
untouched since 2026-07-31, `mergeable_state: dirty`, labelled `needs-resolution`, with **all four
review threads already resolved** - nothing was blocking it on review.

### The manifest was the least accurate source, again

Its `notes` ended on *"All 29 tests pass ... verified live"* and it carried no `blockers` field, so
it read as ready while the pull request had been unmergeable for five days. This is the same
finding the 2026-08-03 entry recorded for #109, in the same week, on the same plan - which makes it
a pattern rather than an incident. Both times everything needed to diagnose it was on the pull
request the whole time: a `dirty` state, a `needs-resolution` label, and a routine comment naming
the conflicting files.

### The README conflict was not the one the routine reported

The 2026-08-03 routine comment described `.gitignore` as a safe concatenation (correct) and
`.claude/hooks/README.md` as *"both sides add an overlapping Safety bullet ... this branch's bullet
is a subset of the wording a landed main change already added"*. True, and much too small.

This branch was cut from `0fd14357`, before #101 rewrote the README from 378 lines to ~140. An
earlier merge on the branch resolved that rewrite **hunk-by-hunk**, and the head therefore carried:

- `## Setup: overriding the default remote/branch/path` (plus four subsections) and
  `## Verifying it worked` - pre-#101 sections - sitting alongside the `## Configuration` /
  `### Where to put them` sections that had replaced them. Two documents about the same three
  settings.
- `Any other label is preserved but not interpreted.` stranded 75 lines below the labels list it
  closes, because the resurrected block had been spliced into the middle of that section.

Visible in the branch's own history rather than inferred: `151934ff` carried the README at 367
lines, and the merge at `01d112c0` produced 228 rather than `main`'s 142.

**The 2026-08-03 entry's own generalization is what resolved it** - *a documentation conflict
against a restructured file is a rewrite, and resolving it hunk-by-hunk produces a document that
reads as two.* That was written about #109's README two days before this branch's merge produced
the identical artifact. Re-authored against `main`, and only after checking that both resurrected
sections are superseded verbatim: `## Configuration` / `### Where to put them` covers the setup
half, and Quick start already carries the `session-start.sh && cat CLAUDE.local.md` verify line.

What survives is this branch's own content: the `plan-updates-since.sh` entry under *Plan
dashboards*, and two *existing* Safety bullets extended rather than duplicated - the `FETCH_HEAD`
read-only bullet now names the script, the gitignored-files bullet now names the stamp. The branch's
README delta went from **+86/-0 to +12/-2**.

**Worth carrying, because the routine will meet this again:** its conflict report names files, and a
file name understates a conflict against a restructured document. The report was accurate and still
led to the wrong size of fix - a session acting on it alone would have resolved the markers and left
both defects in place, since neither is visible in the conflict hunks.

### What was checked and found clean

- **The same-artifact-twice pattern**, this plan's recorded-three-times failure and exactly what a
  long-lived branch off a moving base produces. No instance: the test module already imports `main`'s
  shared `ScratchRepository` (an earlier merge had adopted it), `tests/stubs/` has no counterpart on
  `main`, and `plan_updates_since_support.py` does not overlap `plan_manifest_tools.py`.
- **The two auto-merged files, semantically rather than textually.**
  `resolve-personal-notes-config.sh` and `session-start.sh` merged without markers, and the merged
  summary block carries both #109's `local settings:` line and this branch's `plan state SHA:` line.
- **`depends_on: []`**, and `check_dependency_readiness.py --item plan-updates-since-helper` returns
  `[]` - nothing had regressed underneath it.

### Verification, and the feature verifying itself

243 tests across the two suites CI's `test_claude_dev_tooling` job runs - 194 plan-dashboard, 49
hooks (this module's 13 plus `main`'s 36, including the `test_personal_settings_sync.py` arriving
with the merge). None lost.

The live run is the part worth recording: `plan-updates-since.sh workflow-unification --since <sha>`
returned a delta that **included a manifest change another session pushed during this resolve**. The
notes branch moved twice while the conflict was being fixed (`75d0b61a` to `b39153aa` to `b56fee94`,
242 lines), so the anti-stale-save rule was not theoretical here - these edits were re-applied onto
the freshly fetched manifest rather than the copy loaded at the start.

### CI, unchanged and still not this pull request's

`test_each_lib (semantic_digital_twin)` fails on `test_world_sim_state_sync`, the Mujoco
box-settling assertion (`final_pos=[~0, ~0, 0.1499]` against `[0.3, 0.2, 0.15]`). Unreachable from a
`.claude/`-only diff; `test_claude_dev_tooling` is green. Already ruled ignorable for `.claude/`-only
pull requests on #101.

**State**: pushed as `99c92c3c`, `mergeable_state: unstable` against `main` at `b52da84d`,
`needs-resolution` dropped (the full label set re-sent so `cram2-link-sent` survived, per #139's
replace-not-add finding), back to draft per the standing re-draft-after-push rule. This clears one of
the six in-flight bash-touching pull requests decision 12's items 2-6 cannot land ahead of.

### A note on where this was done from

The fix had to land on #115's head, which belongs to another session, so it was pushed to
`claude/plan-item-kickoff-workflow-n814iz` rather than this session's own designated branch - the
same override already on record for #133 into #117 and #143's one line onto #135's branch. There is
no alternative that resolves #115 itself: a new branch is a new pull request.


### Third round: prototype the reviewer's suggestion before answering it

Four comments, and the first pair overturned an answer this session had given twice.

`PullRequestField`'s members were argument tuples behind a keyword-only helper, because
two earlier rounds had established - correctly - that writing a member as
`PullRequestFieldSpecification(key="head", …)` silently lands the whole instance in
`key`. The reviewer asked anyway: *can you not just call the constructor?* Prototyped
rather than answered from memory, and the answer is yes, given one thing neither earlier
round had tried:

```python
class PullRequestField(PullRequestFieldSpecification, Enum):
    NUMBER = PullRequestFieldSpecification(key="number", required=True)

    def __init__(self, specification: PullRequestFieldSpecification) -> None:
        for field in dataclasses.fields(PullRequestFieldSpecification):
            object.__setattr__(self, field.name, getattr(specification, field.name))
```

The arguments are keywords for real rather than by proxy, the member is still a
specification, `field.key` still reads directly, and the helper - which existed only to
return its arguments unchanged - is deleted. Deleting the `__init__` fails three tests, so
the silent form cannot return unnoticed.

Worth carrying, because this session got it wrong in the same direction twice: **a
constraint established by a failed attempt is a fact about that attempt, not about the
language.** Both earlier answers were true of the shape they were written against and
false in general, and only running the alternative found the difference.

### The revert a mutation check earned

The same round asked for `RESTACK_STEPS` to be found from `RestackStep.__subclasses__()`,
as `COMMANDS` already is. It was applied, and the reviewer then withdrew it themselves on
reading why it had been a list.

What settled it is worth keeping, because the argument alone had not: swapping
`PublishBranch` ahead of `RefuseAnUnsafeMove` fails
`test_a_push_the_move_checks_refuse_is_not_made` - a behavioural test that publishes to a
real scratch fork and asserts the destination ref never moved. The order is not a
stylistic preference; it is load-bearing behaviour a test already catches, and
auto-discovery would have made it a consequence of where the classes happen to sit in the
file.

That also disposed of the order test added while auto-discovery was in: it asserted the
sequence as a literal, which against an explicit tuple only restates it - one change
failing two tests for the same reason. Deleted with the revert.

The distinction that survives, now in `RESTACK_STEPS`'s own docstring: **discover a list
that carries no meaning, state one that does.** `COMMANDS` is discovered because its only
content was the chance of forgetting a line; the steps are listed because their order is a
decision about what a pass does, and it belongs where it is read.

The round's last comment asked for docstrings on the enum members at one line of
`stack.py`. Swept both modules with an AST pass instead: `Command`'s ten members,
`BranchStatus`, `IntegrationStrategy`, `CommitMoveAction`, and the two undocumented module
variables. Neither module now has an undocumented enum member or module-level variable.

### Merged, and what the item leaves behind

#115 merged into fork `main` on 2026-08-05, the same day the conflict was cleared.
Confirmed from `main` rather than from the notification: `99c92c3c` is an ancestor of
`origin/main`, the three new files are present, and `README.md` is the re-authored
180-line version rather than the 228-line spliced one. `test_each_lib
(semantic_digital_twin)` — red on this pull request since 2026-07-31 — passed on the
post-merge run, so it went in green rather than with a known-ignorable red.

Two things this leaves for later, both already owned by named items rather than loose:
the inline `gh`-CLI-else-token rule in `plan-updates-since.sh`, which
`dev-tooling-github-api-unification` absorbs as its third carrier alongside
`github-api.sh` and `pr_state`; and the bash body itself, which
`dev-tooling-save-commands-python` converts once the remaining in-flight
bash-touching pull requests land. Five of those six remain: #107, #110, #121, #126, and
#139's own `.claude/stack/` work — #109 and #115 are now both in.

## Update 2026-08-05 (merged): stack-tooling-on-main lands on fork main

PR #106 merged into fork `main` at `2026-08-05T14:10:36Z` (`merged_by: AbdelrhmanBassiouny`,
head `b3e240e6` - the cram2-checkout fork-resolution fix from earlier the same session). Marked
ready for review by the user directly (not a session action) shortly before the merge, and merged
normally rather than by push/fast-forward.

Verified by presence on fork `main`, not from the merge notification alone: `.claude/stack/stack.py`,
`.claude/skills/stacked-pr-maintenance/SKILL.md` and `.claude/stack/tests/test_maintenance_skill.py`
all `git cat-file -e` clean on `origin/main` - the same discipline `setup-personal-notes-pr101`'s
verification used.

**This is the fork-internal merge only, not the cram2 landing.** PR #106's base was fork `main`
(head repo and base repo both `AbdelrhmanBassiouny/...`), not `cram2/cognitive_robot_abstract_machine`
directly - the separate cram2 promotion is the manual step the PR's own "Promote" section already
describes (a compare-and-create link, since the GitHub app has no write access to cram2). So
`routine-cutover`'s gate ("only after PR 1 is on cram2/main and fork main fast-forwards") is **not**
met by this merge alone - it needs the promotion to actually happen and cram2 to merge it, then
fork main to fast-forward from cram2/main. Worth stating plainly since this merge could easily read
as satisfying that gate at a glance.

**Consequence for dependents.** `setup-stacked-prs-skill` (#110), `setup-personal-notes-script`
(#107), `shared-pr-state-chips` (#111) and `stack-maintenance-executor` (#139) were all based on
`claude/stack-tooling-on-main`'s branch directly; now that its content is on `main`, each can rebase
onto `main` instead of the now-merged branch - not done here, left for whichever session next
touches each of them.

**One CI check was red at merge time, confirmed unrelated before the merge**: `test_each_lib
(giskardpy)`'s `test_pacer.py::test_with_executor - assert 26.0 == 42`, a physics/timing assertion
with an `rclpy.InvalidHandle` teardown warning during the executor's control-cycle count. PR #106's
diff against `main` was 11 files, entirely `.claude/`/`ci.yml`/`README.md` - nothing in giskardpy's
import graph. Matches this PR's own already-documented pattern of unrelated robotics-stack flakes
(`test_world_sim_state_sync`, the `semantic_digital_twin` texture-pair failure); `test_claude_dev_tooling`
- the job that actually exercises this PR's changes - was green. Noted on the PR rather than chased,
per the standing instruction for this PR.

## Update 2026-08-05 (landing): three items reach main, and the third stale-save revert

Fork `main` fast-forwarded at `2026-08-05T14:10:36Z`, and GitHub recorded #106, #115 and
#119 as merged in that one instant - the same auto-detection the 2026-07-31 landing entry
describes for #101/#103/#105. Verified by ancestry rather than from the merge titles:
`claude/stack-tooling-on-main`, `claude/plan-item-kickoff-workflow-n814iz` and
`claude/cram2-main-drift-4owm9a` are all `git merge-base --is-ancestor` of `origin/main`.
So `stack-tooling-on-main`, `plan-updates-since-helper` and `merge-timestamp-required-fix`
are `done`, and `.claude/stack/` is on `main` at last - which retires the two deletions
`routine-cutover` has been carrying, and means `ci.yml` now runs `STACK_TESTS_DIRECTORY`
as a third suite.

**The anti-stale-save rule earned itself a third recorded instance, minutes apart.** The
dashboard refresh auto-corrected `merge-timestamp-required-fix` to `done` and pushed it
(`894a7ce5`); another session then pushed `acccd8be`, adding a legitimate landing note to
`plan-updates-since-helper` while writing back a manifest loaded *before* that correction,
which silently reverted the status to `in_progress`. Caught only by re-reading the manifest
after the write rather than trusting the refresh's own `{"corrected": [...]}` output - which
is the practical lesson, since that output reports what the run *did*, not what survived.
Re-applied onto the latest manifest, keeping their note; both are now correct.

The first two instances (2026-07-30, recorded in the tag-push and routine-cutover entries)
were both a whole section reverted. This one is a single field, which is worse in one
respect: nothing in the diff looks wrong, and a reader would have to know the item had been
corrected to notice it had been un-corrected. **Verify after writing, not only before** -
fetching first is necessary and not sufficient when another writer can land between your
read and your push.

## Update 2026-08-05 (live, again): the first real-stack pass found the executor promoting what it had just withheld

The Routine was pointed at `claude/plan-item-kickoff-workflow-koufa6` (#139) rather than #106, since
`maintenance.py` lives only there, and fired against the real 44-pull-request stack for the first
time. It worked - and the thing it caught was a defect in the executor itself, on the executor's
own pull request.

### What happened

The pass restacked, hit a `.gitignore` conflict on #139, labelled it `needs-resolution` and posted
the naming comment - exactly as designed. Then, a minute later in the same pass, it took the label
straight back off:

| time | event | actor |
|---|---|---|
| 14:10:42 | labeled `needs-resolution` | claude[bot] |
| 14:11:46 | **unlabeled** `needs-resolution` | claude[bot] |
| 14:11:46 | labeled `cram2-link-sent` | claude[bot] |

The tell was a disagreement between two reports: the comment said the branch was labelled
`needs-resolution`, and the pull request carried only `cram2-link-sent`.

### Root cause: a write computed from a snapshot a later step invalidates

`board --write` exports the fork's open pull requests at the *start* of a pass. `restack` then
withholds a conflicted branch by writing a label *live*. `promote` read neither back:
`promotion_order`'s `needs_resolution` exclusion and `LabelWrite.replacing(branch.labels, ...)` both
take `branch.labels`, which is the snapshot.

So within one pass, promotion promoted a branch that same pass had just conflicted on, and then
computed a whole-set label write from a list that was already out of date - stripping the label
written ninety seconds earlier.

This is the production incident `LabelWrite.replacing` was built for, re-entered through a different
door. That class exists because a label write replaces the entire set, and its rule was stated as
*never compute the set yourself; compute it from the labels the pull request carries now*. The rule
was followed to the letter and still broken, because `branch.labels` is not "now" - it is "at board
time". A helper that guarantees correctness given correct input guarantees nothing about where the
input came from.

The consequence is the loop this item exists to close staying open: with the label gone, the next
pass has nothing to withhold on, so it restacks the still-conflicted branch, fails again, and posts
a *second* comment - the precise behaviour the design promises it prevents. The label was invented
to stop re-reporting; a bug that removes it restores the problem it solved.

### The general shape, which is new to this roadmap

Two ambient-state lessons are already recorded on this item - a test reading `board.json` beside the
module, and a test reading an exported `GH_TOKEN` - and both were about *tests* reading state they
should have controlled. This is the production counterpart, and it generalises further:

**Any write computed from a snapshot that a later step in the same pass can invalidate is wrong.**

`restack`'s own withhold check was already right for exactly this reason - it re-reads
`mergeable_state` live, per branch, rather than trusting the export. Promotion was the one step that
trusted the board, and it was also the one step issuing a *replacing* write, which is what made it
destructive rather than merely stale. Both properties had to coincide, which is why no throwaway run
had surfaced it: #140/#141 exercised conflict-then-withhold and promote, but never a branch that was
conflicted *and* promotable in the same pass.

### The fix, and one test whose setup changed

`promote` already fetches each candidate's pull request record for its title and description, so the
live labels were there to be read all along. Both the eligibility decision and the label write now
read that record. Two tests written failing first - a branch labelled mid-pass is not promoted, and
the label write keeps a label added since the board was taken - each checked by mutation and each
failing alone when its own half is reverted.

One pre-existing test, `test_a_branch_already_carrying_the_link_label_is_not_promoted_again`, had put
the label on the board. Its **setup** moved to the fork stand-in; its assertions are untouched. The
behaviour it names is unchanged and still correct - only *where* "already carrying" is read from
moved - which is the same treatment #103 gave the two tests whose incidental fixture items became
ready-to-start under its corrected semantics.

### Two things confirmed rather than assumed

The conflict comment cited *this* session's link, which looked like a hardcoded value. It is not:
`get_session_link_in` reads the link out of the pull request's own description, so a report reaches
the branch's owner - and this session owns #139. The design working, not a bug.

And the `.gitignore` conflict itself was the benign shape #115's resolution already recorded - two
independent additive blocks, this branch's `board.json` entry and main's `.plan-state-sync-sha` stamp
- concatenated, both kept.

### State this pass also revealed

**#106 has landed on main.** `.claude/stack/` and `.claude/skills/stacked-pr-maintenance/` are on
`main` now; `maintenance.py` is not, so the Routine prompt still has to resolve #139's branch rather
than falling through to `main`. #139's base was retargeted to `main` accordingly, and merging main
brought the whole of #106's landed head. 385 tests pass across the three directories CI runs, up from
366 - main's own tests plus the two added here.

### Review round 2026-08-05: naming the wire format removed the coverage that guarded it

Two comments on #135, and the first is worth recording for the trap it exposed rather than
for the change itself.

**Asked**: the JSON keys should be `StrEnum`s, not string literals. Correct, and squarely
`AGENTS.md`'s "instead of passing around strings, use enums instead" — the six keys were
written out twice, once in the two `as_dictionary` methods and once in the test that
asserts the command line's output, with nothing holding the copies equal.

**The trap**: making both sides read one `ReportKey` enum *removed* the only thing pinning
the wire format. Renaming a member's value changes production and test identically, so no
test fails. Verified rather than assumed — renaming `SHARED_PATHS` to `sharedPaths` left
all 8 tests green.

That is a general property of single-sourcing an external contract, and it is easy to miss
because the refactor looks purely like an improvement: **the duplication was doing work.**
The literals were a second, independent statement of what a reader of the JSON sees. Deleting
them without replacement trades a real guard for tidiness.

The fix is one test that owns the wire format and nothing else does:

```python
assert {key.name: str(key) for key in ReportKey} == {
    "PATHS_ABSENT_FROM_BASE": "paths_absent_from_base", ...
}
```

Re-running the same mutation now fails exactly that test and no other — which is the shape
worth having: a key rename is a contract change, so it should fail once, in the place that
names the contract, rather than in six assertions that are really about overlap detection.
The same reasoning `#106` used when it kept a single prose test after deleting eighteen:
assert the thing that must not drift, in one place, computed from live state.

### The `run_git` duplication question, and the answer that reading gave

The second comment asked whether `check_scope_overlap.py`'s `run_git` duplicates
`GitCommandRunner` in #139 or #143. Reading all three rather than reasoning from the names
split the question in two:

- **#139 is not a duplicate.** Its `attempt`/`run` split and ~14 named methods exist because
  a push that silently did nothing must not be indistinguishable from one that worked — its
  own docstring says so. #135's script never writes anything.
- **#143's is nearly identical** — both generic free functions, both raising, differing only
  in error type and parameter order.

So the real duplication is the ~12 lines of `subprocess.run(["git", …])` boilerplate, in
three copies, and the plan already names where it converges: `dev-tooling-notes-core-python`
lists `git_interface.py` as the dependency seam. Recorded there as a third carrier, the same
treatment #139 got on `dev-tooling-github-api-unification`.

**A precedent that turned out not to cover the case.** #143's own review asked this about
`stack.py` and the recorded answer was that the boilerplate overlap is acceptable *because
the contracts are deliberately opposite* — `_git` returns `""` where `run_git` raises. That
reasoning is sound and does not apply here: #135's and #143's contracts are the same. Worth
noticing, because citing a precedent by its conclusion rather than its reason is how a real
duplication gets waved through.

## Update 2026-08-05 (resolved): #125 was a second pull request for #126's branch, and no plan surface could have shown it

#125 has been closed as a duplicate. It was not a piece of work at all: its head was
`claude/workflow-unification-git-identity-ppzcyh` at `d4fdc5b7`, the identical commit
#126 points at, differing only in base - `main` instead of #121's branch, which is why
its diff read as 1,329 additions (#121's 548 plus this item's 828) rather than #126's
828. It was opened 95 seconds before #126, carried no reviews and no comments, and was
the only non-draft pull request on the fork.

### The tell was in the description, not the diff

Its title and body were the verbatim commit message of `a525d117` - #121's first commit,
ending in the `Made with the help of Claude.` trailer. That is GitHub's auto-fill for a
pull request opened without a title or body, and it is a reliable signature: every
deliberately opened pull request in this plan has markdown headings, an
`Implements <item-id> (plan ..., track ...)` line and a session link, because the
conventions require them. A pull request whose body is a commit message was opened by a
call that passed neither.

The confusing part follows from it rather than adding anything: the text described #121's
session-start work while the diff also added `save-git-identity.sh`, so reading either
one alone gave a coherent but wrong account of what the pull request was.

### Why nothing flagged it

Not an oversight in the manifest - the plan has no mechanism that could have caught it.
Coverage runs in one direction only: `_generated/branch-index.tsv` maps branch → plan-id,
and an item names its `pull_request_number`. Nothing enumerates the repository's open
pull requests and asks which item owns each one, so a *second* pull request on an
already-tracked branch is invisible to every surface the plan has. The dashboards cross-
check live GitHub state for the pull requests the manifest names; #125 was never named.

This is worth stating plainly because the fork's own convention - one branch, one item,
one pull request - is what makes the reverse lookup unnecessary in the normal case, and
also what makes a violation of it undetectable. The stack maintenance executor is the
one component that does enumerate pull requests, and it reads them as stack members
rather than checking them against plan items.

### What was left where it was

The `dirty` state on #125 was #121's conflict against `main`
(`resolve-personal-notes-config.sh`, `session-start.sh`, plus `.claude/hooks/README.md`
from the git-identity commit). Resolving it on the closed duplicate would have been the
same conflict resolved twice, so it stays with #121, whose branch owns those two files'
changes. #126 remains stacked on #121 and inherits the resolution when it lands.

## Update 2026-08-07 (resolved): #121's conflict and its six-day-old review round

`/plan-item-resolve workflow-unification session-start-plan-and-setup-guards`, session
https://claude.ai/code/session_01JF8sH4isJxrY6Ca5NgD7es. The item had been `in_progress`
and untouched since 2026-08-01, `mergeable_state: dirty`, labelled `needs-resolution`, with
**five review threads unresolved and none outdated**.

### The manifest was the least accurate source, a third time

Its `notes` ended on *"Two TDD tests, 233 green (was 231)"* and it carried no `blockers`
field, so it read as finished while the pull request had been unmergeable for four days and
unanswered on review for six. That is the same finding the 2026-08-03 entry recorded for
#109 and the 2026-08-05 entry recorded for #115 - three times on one plan, in one week.
Both earlier entries already noted that everything needed to diagnose it was on the pull
request the whole time, and that held again: `dirty`, the `needs-resolution` label, two
routine comments naming the conflicting files, and five threads sitting in plain sight.

Worth stating as a pattern rather than a third incident: what these three items have in
common is that the *implementing* session's last act was to write a notes field describing
what it had shipped, and nothing after that point ever wrote to the field again. Review
arriving and `main` moving are both events with no writer. The `notes` field records what a
session did; it has never recorded what happened to the branch afterwards.

### Both conflicts were additive-vs-additive, and the ordering comment was the real content

`session-start.sh` and `resolve-personal-notes-config.sh`, three hunks, nothing
contradictory - this branch's setup-verdict block against #109's personal-settings block,
its `setup:` line against #115's `plan state SHA:` line, and its
`branch_can_hold_plan_item`/`plan_branch_index_exists`/`tracked_plan_count` against #115's
`PLAN_STATE_SYNC_STAMP` helpers. Each resolved by keeping both sides in sequence.

The one judgement in it was ordering, and it is the piece worth carrying: the setup verdict
must run **after everything the hook writes**, not merely after `CLAUDE.local.md`. Its
comment said the latter, which was true when it was written and became too narrow the
moment #109's settings sync landed beside it - and will be too narrow again when #126's
git-identity write arrives, whose own notes already require it to precede the check. The
comment now states the general rule, so the next block added there inherits it instead of
having to rediscover it.

#115's warning was applied rather than assumed: the merged `README.md` and `session-start.sh`
were read end to end for the resurrected-section and stranded-line defects that hunk-by-hunk
resolution produced on #109 and #115. Neither is present here - this branch is young enough
that `main` never restructured underneath it.

### The review round, and one thread left open on purpose

Four threads acted on. The tooling-file paths became a `SetupPrerequisiteFile` StrEnum with
the requirements file among them; the whole set-up-clone layout became a checked-in fixture
tree at `tests/fixtures/set-up-clone/`, mirroring the paths it occupies in a scratch project
root, so `settings.json` and `requirements.txt` are real files of their own type and
`write_setup_prerequisites` is one `copytree`; the summary wording moved into
`session-start-messages.sh`; and the README paragraph moved to the third person.

The fifth - *"I guess this won't be needed once you do my previous comment"*, on
`write_setup_prerequisites` - was answered rather than resolved. The method shrank to one
line but survives, because leaving `CLAUDE.local.md` out of it is exactly what lets the
session-start tests run against a clone that does not have one yet. Reading the comment as
*delete the method* was an interpretation, not something the reviewer said, so the thread
stays open with the reasoning and an offer to fold the copy into `create` instead. The
general rule this follows is already in cram-notes.md: resolve a thread only once you have
genuinely done what it asked.

### The wording move re-ran #135's trap deliberately

Single-sourcing the messages is the same shape as the `ReportKey` enum two days earlier, and
it has the same cost: with the hook and the tests both reading one definition, a reword
changes them identically and nothing fails. So
`test_every_summary_message_reads_as_written` owns the wording and nothing else does, and it
was verified by mutation rather than by argument - rewording one message fails that test and
no other.

This is now the second time on this plan that a *"can this string be fetched from where it
is defined?"* comment has been answered by single-sourcing plus one contract test. Worth
promoting from precedent to expectation: the comment is always right, and the fix is always
two changes rather than one, because the duplication being removed was carrying a guard.

### The defect only a staged diff could show

The fixture's `requirements.txt` was silently not added: the repo's `.gitignore` ignores
`*.txt`, and every real `requirements.txt` in this repo predates that rule and is tracked
only because it was already tracked. The local suite passed regardless, because the file
existed on disk - CI on a fresh checkout would not have. It was caught by diffing the staged
tree against `main` and noticing one expected path missing, and fixed with a `.gitignore`
exception rather than `git add -f`, following the `*.png` exception the example screenshots
already carry.

The generalizable part: **a test suite that passes locally proves nothing about files the
index does not have.** Every suite here was re-run from a clean clone of the pushed branch
afterwards, which is the cheap check that would have caught it directly.

### State

Pushed as `862da392`; `mergeable_state: clean` against `main` at `0626bdce`;
`needs-resolution` dropped by re-sending the full label set, per #139's replace-not-add
finding; still a draft; description rewritten to match what the pull request now does. 350
tests green across the three directories `test_claude_dev_tooling` runs - 194
plan-dashboard, 65 hooks, 91 stack - against 349 after the merge and 233 before it.
`test_each_lib (semantic_digital_twin)` remains the base's, not this pull request's, and is
re-checked on the new run rather than inherited from the 2026-08-03 ruling.

This unblocks `git-identity-from-personal-notes` (#126), which is stacked on this branch and
inherits the resolution, and clears one of the bash-touching pull requests decision 12's
items 2-6 cannot land ahead of.

### A note on where this was done from

The fix had to land on #121's head, so it was pushed to
`claude/workflow-unification-setup-jgvs53` rather than this session's designated branch -
the same override recorded for #115, #133 into #117, and #143's one line onto #135's branch.
There is no alternative that resolves #121 itself: a new branch is a new pull request, which
is precisely what #125 turned out to be.

## Update 2026-08-07 (new item): upstream-review-reader, and a premise that was wrong

The user's complaint was concrete: reading cram2 review threads and retyping them into a
session is slow, and it makes them the bottleneck on every review round. The question was
whether anything - phone, GitHub, or Claude - could automate it.

### "cram2 is not readable from the cloud" was false

`stack.toml` and `stack.py` both state this as fact, and `ready-to-promote-upstream-links`
and the promotion-link design are built on it. It is wrong. cram2 is a **public** repository:
anonymous `git ls-remote` against it succeeds from a session, and the user's account even
reports `can_push: true` on it. What is actually true is narrower and different: a session is
scoped to an allowlist of repositories, and the agent proxy enforces that scope on the GitHub
API. The upstream is readable; the session is simply not permitted to be the reader. The
prose was not corrected here - it lives in `stacked-pr-maintenance`, whose tests assert its
wording - but it should be, and it is flagged rather than folded in.

### What was measured, not assumed

| route | fork | cram2 |
| --- | --- | --- |
| `git ls-remote` | yes | yes |
| REST from Python | 200 | 403, repository not in session scope |
| github.com HTML | - | 403 |
| GraphQL | 403 | 403, "only the pinned set of PR-review operations is served" |

The GraphQL refusal is the load-bearing one, and it applies to the fork too, not just to
cram2. Thread resolved-state is exposed *only* by GraphQL - REST has no such field - and the
user made resolved-state a hard requirement. The proxy README classifies a 403 as an
organization policy denial to report rather than route around. So the conclusion was forced:
no script running inside a session can produce this report, whatever its design.

### Why an Action, and why dispatch-only

The same script runs fine where GraphQL is not blocked. GitHub Actions on the fork start
with no queue - median 0s, max 0s across the last 14 completed runs, out of 3563 - so the
round trip is the job itself rather than a wait. The session reads the result over plain
read-only REST; `runs`, `jobs` and `job-logs` were all confirmed to answer 200. The only
non-read call in the whole design is the dispatch POST, which starts a job and changes no
repository content; the user accepted that explicitly after it was put to them as the one
exception to "no write calls at all".

Dispatch-only, never a cron. That keeps it inside the no-scheduled-checks rule and matches
what `routine-cutover` wants of every deterministic duty.

### The backend question, answered rather than deferred again

The first draft used a stdlib `urllib` GraphQL client. That would have been the *fourth*
implementation of the gh-CLI-else-token access rule, after `github-api.sh`, `pr_state` and
`maintenance.py` - precisely what `dev-tooling-github-api-unification` exists to stop, and
#139's review had already asked "why not gh?" only for the answer to be deferred to that
item. So this uses `gh api graphql`: Actions runners ship gh and `GITHUB_TOKEN` authenticates
it, so the caller adds no backend and needs no secret. This does not resolve that item, but
it is evidence for its open question - the install-or-not tension only binds the
SessionStart-reachable tier, and an Actions-only caller can already assume gh.

### Portability

The user required this to work for every cram2 contributor in their own fork, which the
plan's standing portability rule already demanded. No owner or repository is named anywhere:
upstream comes from `stack.toml`, the fork owner from `github.repository_owner`, and
`--upstream` overrides for a checkout whose upstream differs. The one manual step per fork is
that Actions are disabled by default on a new fork and must be enabled once.

### State

Two commits on `claude/automate-upstream-reviews-0fte9f`; 29 tests, all offline against
recorded payloads with `gh` stubbed, so CI needs no credentials. A stubbed end-to-end run
exercised branch resolution, cursor pagination, resolved-filtering and the step summary.

Live dispatch could **not** be verified in this session, and the reason is worth recording:
`workflow_dispatch` only registers a workflow that exists on the repository's **default**
branch, so a workflow still on its own feature branch returns 404 on dispatch. Actions are
enabled on the fork and 15 other workflows are registered, so this is the default-branch rule
and nothing else. The first real dispatch is only possible once this lands on the fork's
main, which also means the GraphQL document itself is unexercised against a live schema until
then - the one residual risk in the change.

### Second round on #121: the contract test is cut, and the Python question has a measurement

Three more comments the same day, applied in `b57d3902`. Two were plain — the message names
the tests pass became a `SummaryMessage` StrEnum. The third reversed this session's own
recommendation, and that is the part worth keeping.

`test_every_summary_message_reads_as_written` had been added hours earlier for one reason:
single-sourcing the wording removes the guard the duplicate literals were carrying, so
something has to pin it. That is #135's `ReportKey` finding applied verbatim, and the entry
above went as far as calling it *"promoting it from precedent to expectation"*. The reviewer
looked at the resulting test and said to cut it — *"remove these wording assertions or replace
only one of them by being not empty."*

Cut, second option taken: `test_every_summary_message_renders_something` iterates the enum and
asserts each member renders non-empty. A reword is now invisible to the suite. That is a real
loss and it was stated once on the thread rather than argued a second time.

**The correction to the generalization is the useful part.** "Single-source, then add one
contract test" is right about the *mechanism* — the guard genuinely does disappear otherwise —
and wrong to treat as automatic. Whether a given string is worth pinning is the owner's call,
not a property of the refactor. Here the wording is a diagnostic line in a hook's summary,
reworded freely and read by a human; on #135 it was a JSON wire format other code parses. The
precedent should be read as *notice the guard you are deleting and say so*, not *always replace
it*.

What survives is the pair of failures that actually break the hook, both mutation-checked: a
member naming a function that does not exist, and a function that prints nothing — the second
would make `session-start.sh` emit a blank `setup:` line with nothing noticing.

### The Python question, answered by measurement

The third comment asked whether `session-start-messages.sh` could be a Python file instead,
*"if it can be a python file then make it so, if no harm from it"*. The condition is the whole
answer, so it was measured rather than reasoned about: with `python3` removed from `PATH`
entirely, the hook still prints all six summary lines and exits 0, degrading only
`check-setup.sh`'s dependency row — into a row that says python3 is missing. As a Python file
that entire block produces nothing.

`resolve-personal-notes-config.sh:343` already states the same rule from the other end: the
branch index is TSV read with `awk` precisely so *"session-start.sh must not gain a hard
dependency on python3/PyYAML"*.

Not converted; replied with the measurement and left open for the user. `dev-tooling-session-start-python`
is the item that takes this floor raise deliberately, behind a shim that probes for python3 ≥
3.11 and exits 0 with one diagnostic line when it is absent — converting one sourced file now
would take the raise without the shim that makes it safe.

Worth generalizing: **a conditional instruction ("if no harm") is answered by testing the
condition, not by weighing it.** Removing python3 from `PATH` took one command and turned a
judgement call into a demonstration.

## Update 2026-08-03 (closed): dashboard-chip-notes-collapse merged

`dashboard-chip-notes-collapse` (PR #124) merged into fork `main` on 2026-08-03, the same day
the user marked it ready for review themselves. Three `origin/main` merges landed on the branch
from outside any session while the pull request was open, each surfacing a CI failure this
session investigated and none of which had any path back to the template-only diff: a
`coraplex` pytest-xdist worker crash, `semantic_digital_twin` mesh-material assertion failures
that cleared once an upstream texture-resolution fix landed, a second worker crash on a ROS
synchronizer test, and finally a missing-ROS-package error in a newly-merged Gazebo adapter's
own tests. Each was replied to on the pull request explaining why it wasn't being fixed there,
matching this plan's established pattern of unrelated robotics CI noise on `.claude/`-only
changes - see the `setup-personal-notes-pr101` and other entries above for the same pattern.

Session unsubscribed from the pull request and from this plan's tracking issue #102 (held only
for this item's sake) on merge, per the "when your PR's job ends" convention.

## Update 2026-08-05 (merged): plan-item-bootstrap lands, and the executor's false positive

#143 merged into fork `main`. Verified by content rather than from the notification:
`f77794b0` is an ancestor of `origin/main`, `plan_item_bootstrap.py` with its test module
and fixtures are present, `plan-item-kickoff/SKILL.md` carries step 6, and
`resolve-personal-notes-config.sh` carries `PLAN_ITEM_BOOTSTRAP_SCRIPT`. The ordering this
item exists to invert is therefore the documented procedure on `main` now: a kickoff whose
plan is approved opens the branch and draft pull request and records the item *before* the
first edit, rather than leaving the manifest saying `not_started` for the length of the work.

The item was bootstrapped by hand in the order it prescribes, since the tool did not exist
yet - so the first genuine run belongs to whichever item is kicked off next, and that run is
the real test of it.

### The maintenance executor reported a conflict that did not exist

Worth recording here rather than only on #139, because it is the second failure mode this
plan has seen from a *hand-or-machine-assembled input treated as truth*, after #119.

Two conflict reports arrived on #143 from the maintenance pass, both with an empty
`Conflicting files:` section. The first (14:10 UTC) named a real conflict -
`.claude/hooks/README.md`, where `main` had gained #115's `plan-updates-since.sh` bullet in
the same list this branch extends - so it read as "detection right, naming empty". The
second (20:37 UTC) disproved that reading: `git merge-tree --write-tree origin/main
f77794b0` exits 0 and GitHub reports `mergeable_state: clean`, and `main` had not moved
since 14:27 UTC, so both passes ran on pinned, re-testable inputs. It reported a conflict on
a clean merge and applied `needs-resolution`.

**A false positive here fails in the dangerous direction.** `needs-resolution` withholds a
branch from every later pass, so a wrong one silently removes a healthy branch from the
workflow; and this branch was labelled while already `clean`, meaning the detection and the
label-clearing check disagreed about the same branch within one pass - the loop #139 exists
to close, failing open the other way. The label was cleared by hand, re-sending the full set
so `in-review` survived.

One hypothesis covers both symptoms and is recorded on #139 for its owner to test: an
integration that fails for *any* reason is classified as a conflict, and the unmerged paths
are enumerated from a state that has none. That predicts an empty list on every conflict
report, which #139's own `.gitignore` report contradicts - so the picture is not uniform,
and that contradiction is the part that would falsify it. Not fixed from here: it is #139's
module, and the reproduction above is enough to write a failing test from.

The generalizable point is the one #119 already made in a different costume: **a report
whose wrong value is indistinguishable from a legitimate one has to be rejected by the code
that produces it, not trusted by the reader.** An empty file list is valid-looking. So is a
conflict flag on a clean tree. Both were believed until they were re-derived from git.

### Handed over 2026-08-09: #135 marked ready by the user

The user flipped #135 out of draft themselves, which by the notes-branch convention ends
the owning session's job on it — that flip is their record of having read and accepted the
changes, and it is deliberately distinguished from a session marking its own pull request
ready to unblock a dependent.

The item stays `in_progress`: it has not merged. What the handover leaves behind, all
reported before unsubscribing and none of it fixed afterwards, because the same convention
says report-then-stop rather than stay to tidy:

- **A stale `needs-resolution` label.** The branch became mergeable again with `db034e64`;
  the maintenance pass clears the label itself on the next run that sees a clean merge, so
  clearing it by hand would only race a loop that already works. This is the second time on
  this pull request that leaving the label alone was the right call.
- **One open review thread**, the `run_git` duplication question — answered with a
  recommendation and left open on purpose, since the answer was "recorded elsewhere, not
  changed here" rather than an action taken.
- **A description one merge behind** (it says 346 tests, and names only
  `semantic_digital_twin` under CI). Not corrected, because the ready-for-review flip is the
  user's record of having read the description as it stood; editing it afterwards would
  change what they just accepted.

**The CI record is worth keeping as a data point about this repository rather than about
this branch.** `test_claude_dev_tooling` — the only job a `.claude/`-only diff can reach —
was green on every run this branch ever had. Four *different* robotics jobs went red across
four runs: `semantic_digital_twin`'s two `test_multi_sim.py` texture assertions, a `coraplex`
notebook kernel dying before it could answer `kernel_info`, and `giskardpy` twice on two
*different* tests. Only the first looks like a real defect — proven base-side, since `main`
fails identically on its own run and #124 hit the same pair a day before this branch existed
— and it blocks every open pull request in the repository. It was offered as its own
bug-labelled item and not taken up.

The generalizable part, for the next branch that sits here a while: an all-green matrix was
never reachable from this branch, so "wait for green" would have been an indefinite block.
What made the pull request reviewable anyway was having one job that genuinely covers the
diff, and being able to say precisely why each of the other four failures was not it.
